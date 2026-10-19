"""Stock de contenu : les quatre types d'éléments que les versions cochent.

Chaque type est décrit une fois (champs, libellé, tri) ; les routes et les
templates de l'admin sont communs aux quatre.
"""
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import delete

from cv.admin.formulaires import MAX_TEXTE, Champ
from cv.admin.libelles import libelle
from cv.models import (TYPES_ENTREE, VOIES, Chiffre, Competence, Entree, SoftSkill,
                       VersionElement)


@dataclass(frozen=True)
class TypeStock:
    cle: str
    titre: str
    modele: type
    type_element: str
    champs: tuple[Champ, ...]
    libelle: Callable[[object], str]
    tri: tuple
    verifier: Callable[[dict], dict[str, str]] | None = None
    detail: Callable[[object], str] | None = None  # sous-titre dans la liste


def _dates_dans_l_ordre(valeurs: dict) -> dict[str, str]:
    debut, fin = valeurs.get("debut"), valeurs.get("fin")
    if debut and fin and fin < debut:
        return {"fin": "La fin précède le début."}
    return {}


def _libelle_entree(e: Entree) -> str:
    return " · ".join(filter(None, (e.intitule_fr, e.organisation)))


def _detail_entree(e: Entree) -> str:
    fin = e.fin.strftime("%m/%Y") if e.fin else "en cours"
    return f"{libelle(e.type)} · {e.debut:%m/%Y} – {fin}"


def _libelle_soft_skill(s: SoftSkill) -> str:
    # Sans preuve, la soft skill est masquée sur le site public.
    return s.nom_fr if (s.preuve_fr or "").strip() else f"{s.nom_fr} — à compléter"


def _libelle_competence(c: Competence) -> str:
    return f"{c.nom_fr} ({c.categorie_fr})" if c.categorie_fr else c.nom_fr


UNE_PAR_LIGNE = "Une mission par ligne."

TYPES = {t.cle: t for t in (
    TypeStock(
        "parcours", "Parcours", Entree, "entree",
        (Champ("type", "Type", type="choix", choix=TYPES_ENTREE, requis=True),
         Champ("voie", "Voie", type="choix", choix=VOIES, requis=True,
               aide="Principale : le parcours ; parallèle : les projets à côté."),
         Champ("intitule_fr", "Intitulé (FR)", requis=True),
         Champ("intitule_en", "Intitulé (EN)"),
         Champ("organisation", "Organisation"),
         Champ("via", "Via", aide="Ex. l'ESN par laquelle passait la mission."),
         Champ("debut", "Début", type="date", requis=True),
         Champ("fin", "Fin", type="date", aide="Vide = en cours."),
         Champ("lieu", "Lieu", max=120),
         Champ("technos", "Technos", max=400),
         Champ("missions_fr", "Missions (FR)", type="texte", max=MAX_TEXTE, aide=UNE_PAR_LIGNE),
         Champ("missions_en", "Missions (EN)", type="texte", max=MAX_TEXTE, aide=UNE_PAR_LIGNE)),
        _libelle_entree, (Entree.debut.desc(), Entree.id.desc()), _dates_dans_l_ordre,
        _detail_entree),
    TypeStock(
        "soft-skills", "Soft skills", SoftSkill, "soft_skill",
        (Champ("nom_fr", "Nom (FR)", max=120, requis=True),
         Champ("nom_en", "Nom (EN)", max=120),
         Champ("preuve_fr", "Preuve (FR)", type="texte", max=1000,
               aide="Sans preuve, la soft skill n'apparaît pas sur le site."),
         Champ("preuve_en", "Preuve (EN)", type="texte", max=1000)),
        _libelle_soft_skill, (SoftSkill.id,)),
    TypeStock(
        "competences", "Compétences", Competence, "competence",
        (Champ("nom_fr", "Nom (FR)", max=120, requis=True),
         Champ("nom_en", "Nom (EN)", max=120),
         Champ("categorie_fr", "Catégorie (FR)", max=120),
         Champ("categorie_en", "Catégorie (EN)", max=120)),
        _libelle_competence, (Competence.categorie_fr, Competence.nom_fr)),
    TypeStock(
        "chiffres", "Chiffres", Chiffre, "chiffre",
        (Champ("valeur_fr", "Valeur (FR)", max=40, requis=True),
         Champ("valeur_en", "Valeur (EN)", max=40),
         Champ("libelle_fr", "Libellé (FR)", max=120, requis=True),
         Champ("libelle_en", "Libellé (EN)", max=120)),
        lambda c: f"{c.valeur_fr} {c.libelle_fr}", (Chiffre.id,)),
)}

PAR_ELEMENT = {t.type_element: t for t in TYPES.values()}


def supprimer_element(session, type_stock: TypeStock, obj) -> None:
    """Supprime l'élément et ses coches dans toutes les versions, d'un seul commit.
    `element_id` n'a pas de clé étrangère (stock polymorphe) : le type compte."""
    session.execute(delete(VersionElement).where(
        VersionElement.type_element == type_stock.type_element,
        VersionElement.element_id == obj.id))
    session.delete(obj)
    session.commit()
