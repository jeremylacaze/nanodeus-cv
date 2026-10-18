"""Durée d'un poste (« 1 an 3 m ») et période affichée (« févr. 2024 → mai 2025 »)."""
from datetime import date

import pytest

from cv.durees import duree, periode


@pytest.mark.parametrize("debut,fin,fr,en", [
    (date(2023, 10, 1), date(2024, 2, 1), "4 m", "4 mo"),
    (date(2024, 2, 1), date(2025, 5, 1), "1 an 3 m", "1 yr 3 mo"),
    (date(2024, 1, 1), date(2025, 1, 1), "1 an", "1 yr"),
    (date(2023, 1, 1), date(2025, 1, 1), "2 ans", "2 yrs"),
    (date(2022, 1, 1), date(2024, 4, 1), "2 ans 3 m", "2 yrs 3 mo"),
    (date(2025, 5, 1), date(2025, 5, 1), "1 m", "1 mo"),   # même mois
    (date(2025, 5, 1), date(2024, 1, 1), "1 m", "1 mo"),   # fin avant début
])
def test_duree(debut, fin, fr, en):
    assert duree(debut, fin, "fr") == fr
    assert duree(debut, fin, "en") == en


def test_duree_en_cours_utilise_aujourdhui():
    assert duree(date(2025, 5, 1), None, "fr", aujourd_hui=date(2026, 10, 18)) == "1 an 5 m"


def test_periode():
    assert periode(date(2024, 2, 1), date(2025, 5, 1), "fr") == "févr. 2024 → mai 2025"
    assert periode(date(2024, 2, 1), date(2025, 5, 1), "en") == "Feb 2024 → May 2025"
    assert periode(date(2025, 5, 1), None, "fr") == "mai 2025 → aujourd'hui"
    assert periode(date(2025, 5, 1), None, "en") == "May 2025 → present"
