"""Formulaires de l'admin, décrits une fois : lecture, validation et rendu.

`lire` rend les valeurs prêtes à poser sur l'objet, ou les erreurs par champ ;
la macro `champs` de templates/admin/_champs.html affiche la même liste.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from cv.contact import CONTROLE

TYPES = ("ligne", "texte", "date", "case", "url", "choix")
MAX_TEXTE = 4000


@dataclass(frozen=True)
class Champ:
    nom: str
    libelle: str
    type: str = "ligne"
    max: int = 200
    requis: bool = False
    choix: tuple[str, ...] = ()
    aide: str = ""


def _lire_un(champ: Champ, brut: str) -> tuple[object, str | None]:
    """(valeur, erreur) d'un champ non vide."""
    if champ.type == "texte":
        brut = brut.replace("\r\n", "\n").replace("\r", "\n")
        if len(brut) > champ.max:
            return brut, f"{champ.max} caractères au plus."
        return brut, None
    if champ.type == "date":
        try:
            return date.fromisoformat(brut), None
        except ValueError:
            return None, "Date attendue au format AAAA-MM-JJ."
    if champ.type == "choix":
        return brut, None if brut in champ.choix else "Valeur inconnue."
    if len(brut) > champ.max:
        return brut, f"{champ.max} caractères au plus."
    if CONTROLE.search(brut):
        return brut, "Une seule ligne, sans caractère de contrôle."
    if champ.type == "url" and (not brut.startswith("https://") or any(c.isspace() for c in brut)):
        return brut, "Adresse https:// attendue, sans espace."
    return brut, None


def lire(donnees: Mapping[str, str], champs: Sequence[Champ]
         ) -> tuple[dict[str, object], dict[str, str]]:
    valeurs, erreurs = {}, {}
    for champ in champs:
        if champ.type == "case":
            valeurs[champ.nom] = champ.nom in donnees
            continue
        brut = (donnees.get(champ.nom) or "").strip()
        if not brut:
            if champ.requis:
                erreurs[champ.nom] = "Champ obligatoire."
            valeurs[champ.nom] = None if champ.type == "date" else ""
            continue
        # date.fromisoformat accepte aussi 20240301 : seul AAAA-MM-JJ passe.
        if champ.type == "date" and len(brut) != 10:
            erreurs[champ.nom] = "Date attendue au format AAAA-MM-JJ."
            continue
        valeur, erreur = _lire_un(champ, brut)
        if erreur:
            erreurs[champ.nom] = erreur
        else:
            valeurs[champ.nom] = valeur
    return valeurs, erreurs


def appliquer(obj, valeurs: dict[str, object]) -> None:
    for nom, valeur in valeurs.items():
        setattr(obj, nom, valeur)


def valeurs_de(obj, champs: Sequence[Champ]) -> dict[str, object]:
    """Valeurs actuelles d'un objet, pour pré-remplir le formulaire."""
    return {c.nom: getattr(obj, c.nom, None) for c in champs}
