"""Versions du CV : métadonnées, composition, version par défaut et suppression."""
import re
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select, update

from cv.admin.formulaires import MAX_TEXTE, Champ
from cv.admin.stock import PAR_ELEMENT
from cv.models import SLUG, STATUTS, TYPES_ELEMENT, Version, VersionElement

# Chemins du site public qu'un slug masquerait.
SLUGS_RESERVES = frozenset({"en", "contact", "static", "admin", "photo"})
_SLUG = re.compile(SLUG)

CHAMPS_VERSION = (
    Champ("slug", "Slug", max=40, requis=True,
          aide="Changer le slug casse les liens et QR codes déjà partagés."),
    Champ("statut", "Statut", type="choix", choix=STATUTS, requis=True,
          aide="Brouillon : invisible ; non listée : servie mais non indexée."),
    Champ("titre_fr", "Titre (FR)", requis=True),
    Champ("titre_en", "Titre (EN)"),
    Champ("accroche_fr", "Accroche (FR)", type="texte", max=500),
    Champ("accroche_en", "Accroche (EN)", type="texte", max=500),
    Champ("prochaine_mission_fr", "Prochaine mission (FR)"),
    Champ("prochaine_mission_en", "Prochaine mission (EN)"),
)


def verifier_version(session, valeurs: dict, version: Version | None) -> dict[str, str]:
    """Contrôles que les champs seuls ne voient pas (format, réservation, unicité)."""
    erreurs = {}
    slug = valeurs.get("slug") or ""
    if not _SLUG.fullmatch(slug):
        erreurs["slug"] = "Minuscules, chiffres et tirets, 40 caractères au plus."
    elif slug in SLUGS_RESERVES:
        erreurs["slug"] = "Ce slug est réservé."
    else:
        autre = session.scalar(select(Version.id).where(Version.slug == slug))
        if autre is not None and (version is None or autre != version.id):
            erreurs["slug"] = "Ce slug est déjà utilisé."
    if version is not None and version.par_defaut and valeurs.get("statut") == "brouillon":
        erreurs["statut"] = "La version par défaut ne peut pas être un brouillon."
    return erreurs


def definir_par_defaut(session, version: Version) -> bool:
    """Fait de `version` celle servie sur /. Un brouillon est refusé (rien ne change)."""
    if version.statut == "brouillon":
        return False
    # L'index unique partiel refuserait deux lignes à 1 pendant le flush : on éteint
    # d'abord toutes les autres.
    session.execute(update(Version).values(par_defaut=False))
    session.flush()
    version.par_defaut = True
    session.commit()
    return True


def supprimer_version(session, version: Version) -> bool:
    """Supprime la version et ses coches (cascade). La version par défaut est protégée."""
    if version.par_defaut:
        return False
    session.delete(version)
    session.commit()
    return True


ORDRE_MAX = 999
_ENTIER = re.compile(r"[0-9]{1,3}")


@dataclass
class LigneComposition:
    type_element: str
    element_id: int
    libelle: str
    coche: bool
    ordre: int
    missions_fr: str
    missions_en: str


def _coches(session, version: Version) -> dict[tuple[str, int], VersionElement]:
    return {(c.type_element, c.element_id): c for c in session.scalars(
        select(VersionElement).where(VersionElement.version_id == version.id))}


def elements_du_stock(session, version: Version) -> dict[str, list[LigneComposition]]:
    """Tout le stock, type par type : les éléments cochés d'abord, dans l'ordre de la
    version, puis les autres dans l'ordre du stock."""
    coches = _coches(session, version)
    resultat = {}
    for type_element in TYPES_ELEMENT:
        t = PAR_ELEMENT[type_element]
        lignes = []
        for obj in session.scalars(select(t.modele).order_by(*t.tri)):
            c = coches.get((type_element, obj.id))
            lignes.append(LigneComposition(
                type_element, obj.id, t.libelle(obj), c is not None,
                c.ordre if c else 0, (c.missions_fr or "") if c else "",
                (c.missions_en or "") if c else ""))
        # Tri stable : l'ordre du stock départage les non cochés et les égalités.
        lignes.sort(key=lambda ligne: (not ligne.coche, ligne.ordre if ligne.coche else 0))
        resultat[type_element] = lignes
    return resultat


def _surcharge(texte: str | None) -> str | None:
    texte = (texte or "").replace("\r\n", "\n").replace("\r", "\n")
    return texte if texte.strip() else None


def composer(session, version: Version, donnees: Mapping[str, str]) -> dict[str, str]:
    """Applique le formulaire de composition. Seuls les éléments existants du stock sont
    lus : un id inconnu est ignoré. En cas d'erreur, rien n'est écrit."""
    voulues, erreurs = {}, {}
    for type_element in TYPES_ELEMENT:
        modele = PAR_ELEMENT[type_element].modele
        for id_ in session.scalars(select(modele.id)):
            cle = f"{type_element}-{id_}"
            if f"coche-{cle}" not in donnees:
                continue
            brut = (donnees.get(f"ordre-{cle}") or "").strip() or "0"
            if not _ENTIER.fullmatch(brut):
                erreurs[f"ordre-{cle}"] = f"Un entier de 0 à {ORDRE_MAX}."
                continue
            missions = {}
            if type_element == "entree":
                for langue in ("fr", "en"):
                    nom = f"missions_{langue}-{id_}"
                    missions[f"missions_{langue}"] = _surcharge(donnees.get(nom))
                    if len(missions[f"missions_{langue}"] or "") > MAX_TEXTE:
                        erreurs[nom] = f"{MAX_TEXTE} caractères au plus."
            voulues[(type_element, id_)] = {"ordre": int(brut), **missions}
    if erreurs:
        return erreurs
    existantes = _coches(session, version)
    for cle, coche in existantes.items():
        if cle not in voulues:
            session.delete(coche)
    for (type_element, id_), champs in voulues.items():
        coche = existantes.get((type_element, id_))
        if coche is None:
            coche = VersionElement(version_id=version.id, type_element=type_element,
                                   element_id=id_)
            session.add(coche)
        for nom, valeur in champs.items():
            setattr(coche, nom, valeur)
    session.commit()
    return {}
