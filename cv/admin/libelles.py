"""Valeurs stockées en base (cv/models.py) telles qu'on les lit à l'écran."""

LIBELLES = {
    "brouillon": "Brouillon", "publiee": "Publiée", "non_listee": "Non listée",
    "en_attente": "En attente", "envoyee": "Envoyée", "echec": "Échec",
    "poste": "Poste", "formation": "Formation", "projet": "Projet",
    "principale": "Principale", "parallele": "Parallèle",
    "page": "Page", "contact": "Contact", "pdf": "PDF", "apercu_linkedin": "Aperçu LinkedIn",
}


def libelle(valeur: str) -> str:
    """Libellé d'une valeur connue ; une valeur inconnue reste telle quelle."""
    return LIBELLES.get(valeur, valeur)
