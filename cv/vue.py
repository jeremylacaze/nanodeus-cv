"""Assemblage de la vue publique d'une version du CV.

La vue ne contient que ce qui peut être montré : aucun téléphone, aucun email.
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from cv.durees import duree, periode
from cv.models import (Chiffre, Competence, Entree, Profil, SoftSkill, Version,
                       VersionElement)


def champ(obj, nom: str, lang: str) -> str:
    """Valeur traduite d'un champ, repli sur le français, jamais « None »."""
    for suffixe in (lang, "fr"):
        valeur = (getattr(obj, f"{nom}_{suffixe}", None) or "").strip()
        if valeur:
            return valeur
    return ""


def _url_sure(url: str | None) -> str:
    """Un lien du profil finit dans un href : https uniquement (pas de javascript:)."""
    url = (url or "").strip()
    return url if url.lower().startswith("https://") else ""


def _lignes(texte: str) -> list[str]:
    return [ligne.strip() for ligne in (texte or "").splitlines() if ligne.strip()]


@dataclass(frozen=True)
class Job:
    cle: str
    type: str
    voie: str
    intitule: str
    organisation: str
    via: str
    periode: str
    duree: str
    missions: list[str]
    technos: str
    en_cours: bool
    annee: str  # année de fin (ou de début) : ce qu'affiche une formation


@dataclass(frozen=True)
class VueCV:
    slug: str
    lang: str
    noindex: bool
    nom: str
    titre: str
    accroche: str
    localisation: str
    age: int | None
    ouvert: bool
    photo_url: str | None
    chiffres: list[tuple[str, str]]
    formations: list[Job]
    postes: list[Job]
    projets: list[Job]
    prochaine_mission: str
    soft_skills: list[tuple[str, str]]
    competences: dict[str, list[str]]
    interets: list[str]
    linkedin_url: str
    github_url: str


def version_publique(session, slug: str | None, apercu: bool = False) -> Version | None:
    """Version servie sur /<slug> (ou / si None). Un brouillon n'est rendu qu'en aperçu,
    depuis l'admin."""
    requete = select(Version)
    requete = (requete.where(Version.par_defaut.is_(True)) if slug is None
               else requete.where(Version.slug == slug))
    version = session.scalars(requete).first()
    if version is None or (version.statut == "brouillon" and not apercu):
        return None
    return version


def _age(naissance: date, aujourd_hui: date) -> int:
    anniversaire_passe = (aujourd_hui.month, aujourd_hui.day) >= (naissance.month, naissance.day)
    return aujourd_hui.year - naissance.year - (0 if anniversaire_passe else 1)


def _missions(entree: Entree, coche: VersionElement, lang: str) -> list[str]:
    """Surcharge puis stock dans la langue demandée, et seulement ensuite en français :
    une surcharge écrite en français ne masque pas l'anglais du stock."""
    for langue in dict.fromkeys((lang, "fr")):
        for source in (coche, entree):
            lignes = _lignes(getattr(source, f"missions_{langue}") or "")
            if lignes:
                return lignes
    return []


def _job(entree: Entree, coche: VersionElement, lang: str, aujourd_hui: date) -> Job:
    missions = _missions(entree, coche, lang)
    return Job(
        cle=f"e{entree.id}", type=entree.type, voie=entree.voie,
        intitule=champ(entree, "intitule", lang),
        organisation=entree.organisation or "", via=entree.via or "",
        periode=periode(entree.debut, entree.fin, lang),
        duree=duree(entree.debut, entree.fin, lang, aujourd_hui),
        missions=missions, technos=entree.technos or "", en_cours=entree.fin is None,
        annee=str((entree.fin or entree.debut).year),
    )


def assembler_vue(session, slug: str | None, lang: str, aujourd_hui: date | None = None,
                  apercu: bool = False, prefixe_medias: str = "") -> VueCV | None:
    """`prefixe_medias` : "/admin" pour l'aperçu, qui sert la photo depuis l'admin."""
    version = version_publique(session, slug, apercu)
    if version is None:
        return None
    aujourd_hui = aujourd_hui or date.today()
    profil = session.get(Profil, 1) or Profil()

    coches = session.scalars(
        select(VersionElement).where(VersionElement.version_id == version.id)
        .order_by(VersionElement.ordre, VersionElement.id)).all()

    def charger(modele, type_element):
        """Éléments cochés d'un type, dans l'ordre de la version, avec leur coche."""
        lignes = [c for c in coches if c.type_element == type_element]
        objets = {o.id: o for o in session.scalars(
            select(modele).where(modele.id.in_([c.element_id for c in lignes])))}
        return [(objets[c.element_id], c) for c in lignes if c.element_id in objets]

    entrees = sorted(charger(Entree, "entree"), key=lambda paire: (paire[0].debut, paire[0].id))
    jobs = [_job(e, c, lang, aujourd_hui) for e, c in entrees]

    soft_skills = []
    for skill, _ in charger(SoftSkill, "soft_skill"):
        preuve = champ(skill, "preuve", lang)
        if preuve:
            soft_skills.append((champ(skill, "nom", lang), preuve))

    competences: dict[str, list[str]] = {}
    for comp, _ in charger(Competence, "competence"):
        competences.setdefault(champ(comp, "categorie", lang), []).append(champ(comp, "nom", lang))

    age = None
    if profil.afficher_age and profil.date_naissance:
        age = _age(profil.date_naissance, aujourd_hui)

    return VueCV(
        slug=version.slug, lang=lang, noindex=version.statut == "non_listee",
        nom=profil.nom_complet or "", titre=champ(version, "titre", lang),
        accroche=champ(version, "accroche", lang), localisation=profil.localisation or "",
        age=age, ouvert=bool(profil.ouvert_opportunites), photo_url=(f"{prefixe_medias}/photo/{profil.photo_fichier}"
                                                  if profil.photo_fichier else None),
        chiffres=[(champ(c, "valeur", lang), champ(c, "libelle", lang))
                  for c, _ in charger(Chiffre, "chiffre")],
        formations=[j for j in jobs if j.type == "formation"],
        postes=[j for j in jobs if j.type != "formation" and j.voie == "principale"],
        projets=[j for j in jobs if j.type != "formation" and j.voie == "parallele"],
        prochaine_mission=champ(version, "prochaine_mission", lang),
        soft_skills=soft_skills, competences=competences,
        interets=_lignes(champ(profil, "interets", lang)),
        linkedin_url=_url_sure(profil.linkedin_url), github_url=_url_sure(profil.github_url),
    )
