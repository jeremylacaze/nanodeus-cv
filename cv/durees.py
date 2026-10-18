"""Durées et périodes du parcours, dans la langue de la page.

Ce sont des données du CV, pas des textes d'interface : les unités sont donc
tenues ici plutôt que dans le catalogue Babel.
"""
from datetime import date

from babel.dates import format_date

_UNITES = {
    "fr": {"mois": "m", "an": "an", "ans": "ans", "present": "aujourd'hui"},
    "en": {"mois": "mo", "an": "yr", "ans": "yrs", "present": "present"},
}


def _mois_ecoules(debut: date, fin: date) -> int:
    # Au moins un mois : une date incohérente ne doit jamais donner « 0 » ou moins.
    return max(1, (fin.year - debut.year) * 12 + (fin.month - debut.month))


def duree(debut: date, fin: date | None, lang: str, aujourd_hui: date | None = None) -> str:
    u = _UNITES[lang]
    total = _mois_ecoules(debut, fin or aujourd_hui or date.today())
    ans, mois = divmod(total, 12)
    morceaux = []
    if ans:
        morceaux.append(f"{ans} {u['an'] if ans == 1 else u['ans']}")
    if mois:
        morceaux.append(f"{mois} {u['mois']}")
    return " ".join(morceaux)


def periode(debut: date, fin: date | None, lang: str) -> str:
    fin_texte = format_date(fin, "MMM y", locale=lang) if fin else _UNITES[lang]["present"]
    return f"{format_date(debut, 'MMM y', locale=lang)} → {fin_texte}"
