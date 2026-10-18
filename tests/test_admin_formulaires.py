"""Formulaires de l'admin : lecture et validation déclaratives."""
from datetime import date

import pytest

from cv.admin.formulaires import Champ, appliquer, lire


def test_ligne_nettoyee_et_bornee():
    c = [Champ("nom", "Nom", max=5)]
    assert lire({"nom": "  abc "}, c) == ({"nom": "abc"}, {})
    for valeur in ("abcdef", "a\nb", "a b", "a\x00b"):
        assert "nom" in lire({"nom": valeur}, c)[1]


def test_requis():
    assert lire({}, [Champ("nom", "Nom", requis=True)])[1] == {"nom": "Champ obligatoire."}
    assert lire({"nom": "   "}, [Champ("nom", "Nom", requis=True)])[1] == {
        "nom": "Champ obligatoire."}


def test_texte_normalise_avant_la_borne():
    c = [Champ("m", "M", type="texte", max=3)]
    assert lire({"m": "a\r\nb"}, c) == ({"m": "a\nb"}, {})
    assert "m" in lire({"m": "a\r\nbcd"}, c)[1]


def test_date():
    c = [Champ("d", "D", type="date")]
    assert lire({"d": "2024-03-01"}, c)[0]["d"] == date(2024, 3, 1)
    assert lire({"d": ""}, c)[0]["d"] is None
    for valeur in ("01/03/2024", "2024-02-30", "20240301"):
        assert "d" in lire({"d": valeur}, c)[1]


def test_case():
    c = [Champ("ok", "OK", type="case")]
    assert lire({"ok": "1"}, c)[0]["ok"] is True and lire({}, c)[0]["ok"] is False


@pytest.mark.parametrize("url, valide", [("https://x.fr/a", True), ("", True),
    ("http://x.fr", False), ("javascript:alert(1)", False), ("https://a b.fr", False),
    ("https://" + "x" * 300, False)])
def test_url(url, valide):
    assert ("u" not in lire({"u": url}, [Champ("u", "U", type="url", max=300)])[1]) is valide


def test_choix():
    c = [Champ("t", "T", type="choix", choix=("poste", "formation"))]
    assert lire({"t": "poste"}, c)[1] == {} and "t" in lire({"t": "autre"}, c)[1]


def test_appliquer():
    class Objet:
        pass
    obj = Objet()
    appliquer(obj, {"a": 1, "b": "x"})
    assert (obj.a, obj.b) == (1, "x")
