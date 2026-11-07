"""Pied de page « ✓ déployé il y a … · sha » : le commit réellement en ligne,
injecté au build de l'image (Dockerfile, release.yml)."""
import re
from datetime import UTC, datetime, timedelta

import pytest

from cv.config import Config
from cv.deploiement import deploiement

SHA = "51c3f85d0e1a2b3c4d5e6f708192a3b4c5d6e7f8"


def _config(monkeypatch, **env):
    for cle in ("CV_COMMIT", "CV_CONSTRUIT_LE", "CV_URL_DEPOT"):
        monkeypatch.delenv(cle, raising=False)
    for cle, valeur in env.items():
        monkeypatch.setenv(cle, valeur)
    return Config()


def test_lu_dans_l_environnement(monkeypatch):
    c = _config(monkeypatch, CV_COMMIT=SHA, CV_CONSTRUIT_LE="2026-11-04T09:30:00Z")
    assert c.COMMIT == SHA
    assert c.CONSTRUIT_LE == datetime(2026, 11, 4, 9, 30, tzinfo=UTC)
    assert c.URL_DEPOT == "https://github.com/jeremylacaze/nanodeus-cv"


@pytest.mark.parametrize("commit", ["", "main", "51c3f8", "z" * 40, SHA + "0", "abc'; rm"])
def test_commit_invalide_ignore(monkeypatch, commit):
    # Une valeur de build douteuse ne doit jamais empêcher le site de démarrer.
    assert _config(monkeypatch, CV_COMMIT=commit).COMMIT == ""


@pytest.mark.parametrize("date", ["", "hier", "2026-13-01T00:00:00Z"])
def test_date_invalide_ignoree(monkeypatch, date):
    assert _config(monkeypatch, CV_CONSTRUIT_LE=date).CONSTRUIT_LE is None


def test_depot_en_https_seulement(monkeypatch):
    with pytest.raises(ValueError):
        _config(monkeypatch, CV_URL_DEPOT="javascript:alert(1)")
    assert _config(monkeypatch, CV_URL_DEPOT="https://git.test/x/").URL_DEPOT == "https://git.test/x"


def test_resume_du_deploiement(monkeypatch):
    c = _config(monkeypatch, CV_COMMIT=SHA, CV_CONSTRUIT_LE="2026-11-04T09:30:00Z")
    maintenant = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    d = deploiement(c, "fr", maintenant)
    assert d == {"court": "51c3f85", "url": f"https://github.com/jeremylacaze/nanodeus-cv/commit/{SHA}",
                 "quand": "il y a 3 jours", "date": "2026-11-04T09:30:00Z"}
    assert deploiement(c, "en", maintenant)["quand"] == "3 days ago"


def test_sans_date_le_commit_suffit(monkeypatch):
    d = deploiement(_config(monkeypatch, CV_COMMIT=SHA), "fr")
    assert d["court"] == "51c3f85" and d["quand"] == "" and d["date"] == ""


def test_date_future_lue_comme_maintenant(monkeypatch):
    # Horloges décalées entre la CI et le serveur : jamais « dans 2 minutes ».
    c = _config(monkeypatch, CV_COMMIT=SHA, CV_CONSTRUIT_LE="2026-11-07T10:02:00Z")
    assert deploiement(c, "fr", datetime(2026, 11, 7, 10, 0, tzinfo=UTC))["quand"] == "il y a 1 seconde"


def test_rien_en_developpement(monkeypatch):
    assert deploiement(_config(monkeypatch), "fr") is None


def _pied(fabrique_app, monkeypatch, url="/devops", **env):
    for cle, valeur in env.items():
        monkeypatch.setenv(cle, valeur)
    return fabrique_app().test_client().get(url).get_data(as_text=True)


def test_pied_de_page(fabrique_app, monkeypatch):
    hier = (datetime.now(UTC) - timedelta(days=1, hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    html = _pied(fabrique_app, monkeypatch, CV_COMMIT=SHA, CV_CONSTRUIT_LE=hier)
    bloc = re.search(r'<p class="deploiement[^"]*">.*?</p>', html, re.S).group(0)
    assert "déployé" in bloc and f'<time datetime="{hier}">il y a 1 jour</time>' in bloc
    assert (f'<a href="https://github.com/jeremylacaze/nanodeus-cv/commit/{SHA}" '
            'rel="noopener" target="_blank">51c3f85</a>') in bloc


def test_pied_de_page_en_anglais(fabrique_app, monkeypatch):
    html = _pied(fabrique_app, monkeypatch, "/en/devops", CV_COMMIT=SHA)
    assert re.search(r'<p class="deploiement[^"]*">.*deployed.*51c3f85</a>', html, re.S)


def test_pied_de_page_absent_sans_commit(fabrique_app, monkeypatch):
    monkeypatch.delenv("CV_COMMIT", raising=False)
    assert 'class="deploiement' not in _pied(fabrique_app, monkeypatch)
