"""Versions du CV : métadonnées, version par défaut et suppression."""
import re

from sqlalchemy import select, update

from cv.admin.formulaires import Champ
from cv.models import SLUG, STATUTS, Version

# Chemins du site public qu'un slug masquerait.
SLUGS_RESERVES = frozenset({"en", "contact", "static", "admin"})
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
