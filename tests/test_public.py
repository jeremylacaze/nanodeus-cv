"""Site public : routes FR/EN, en-têtes de sécurité, aucune fuite, aucun cookie."""
import re

import pytest

from cv.amorcage import amorcer
from cv.app import create_app
from cv.config import Config
from cv.db import Base
from cv.models import Profil, Version

URLS = ["/", "/devops", "/lead-tech", "/en/", "/en/devops", "/en/lead-tech",
        "/inconnue", "/en/inconnue"]
TELEPHONE, EMAIL = "+33 6 99 88 77 66", "fuite@test.invalid"


def _app(tmp_path, monkeypatch, role="public"):
    monkeypatch.setenv("CV_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CV_ROLE", role)
    app = create_app(Config())
    Base.metadata.create_all(app.extensions["cv_moteur"])
    with app.extensions["cv_sessions"]() as s:
        amorcer(s)
        profil = s.get(Profil, 1)
        profil.telephone, profil.email = TELEPHONE, EMAIL
        s.add(Version(slug="brouillon", statut="brouillon", titre_fr="Brouillon"))
        s.commit()
    return app


@pytest.fixture
def app(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app.testing = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def client_qui_plante(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)

    def plante():
        raise RuntimeError(f"secret {EMAIL}")

    app.add_url_rule("/plante", "plante", plante)
    return app.test_client()


def test_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/devops").status_code == 200
    assert client.get("/en/").status_code == 200
    assert client.get("/inconnue").status_code == 404
    assert client.get("/en/inconnue").status_code == 404


def test_slug_invalide_404(client):
    assert client.get("/Devops").status_code == 404
    assert client.get("/" + "a" * 41).status_code == 404


def test_brouillon_404(client):
    assert client.get("/brouillon").status_code == 404
    assert client.get("/en/brouillon").status_code == 404


def test_en_sans_barre_redirige(client):
    r = client.get("/en")
    assert r.status_code in (301, 308) and r.headers["Location"].endswith("/en/")


def test_non_listee_noindex(client):
    r = client.get("/lead-tech")
    assert r.headers["X-Robots-Tag"] == "noindex" and b'name="robots"' in r.data
    r = client.get("/devops")
    assert "X-Robots-Tag" not in r.headers and b'name="robots"' not in r.data


@pytest.mark.parametrize("url", URLS)
def test_aucune_fuite_ni_cookie(client, url):
    r = client.get(url)
    corps = r.get_data(as_text=True) + str(r.headers)
    assert EMAIL not in corps and "99 88 77 66" not in corps
    assert "Set-Cookie" not in r.headers


def test_cookie_pose_par_erreur_retire(app):
    @app.get("/avec-cookie")
    def avec_cookie():
        from flask import make_response
        r = make_response("x")
        r.set_cookie("a", "1")
        r.set_cookie("b", "2")
        return r

    assert "Set-Cookie" not in app.test_client().get("/avec-cookie").headers


def test_erreur_500_sans_fuite(client_qui_plante):
    r = client_qui_plante.get("/plante")
    corps = r.get_data(as_text=True)
    assert r.status_code == 500
    assert EMAIL not in corps and "Traceback" not in corps and "RuntimeError" not in corps
    assert "Content-Security-Policy" in r.headers


@pytest.mark.parametrize("url", ["/", "/inconnue"])
def test_entetes_de_securite(client, url):
    h = client.get(url).headers
    csp = h["Content-Security-Policy"]
    assert re.fullmatch(
        r"default-src 'self'; script-src 'self' 'nonce-[\w-]+'; style-src 'self'; "
        r"img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        r"frame-ancestors 'none'; form-action 'self'", csp)
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_csp_nonce(client):
    r = client.get("/")
    nonce = re.search(r"'nonce-([^']+)'", r.headers["Content-Security-Policy"]).group(1)
    balises = re.findall(r"<script[^>]*>", r.get_data(as_text=True))
    assert all(f'nonce="{nonce}"' in tag for tag in balises)
    assert nonce != re.search(r"'nonce-([^']+)'",
                              client.get("/").headers["Content-Security-Policy"]).group(1)


def test_anglais(client):
    assert 'lang="en"' in client.get("/en/devops").get_data(as_text=True)
    assert 'lang="en"' in client.get("/en/inconnue").get_data(as_text=True)
    assert 'lang="fr"' in client.get("/devops").get_data(as_text=True)


def test_page_anglaise_traduite(client):
    corps = client.get("/en/devops").get_data(as_text=True)
    assert "Application administrator / DevOps" in corps


def test_lien_autre_langue(client):
    assert 'href="/en/devops"' in client.get("/devops").get_data(as_text=True)
    assert 'href="/devops"' in client.get("/en/devops").get_data(as_text=True)
    assert 'href="/en/"' in client.get("/").get_data(as_text=True)


def test_suggestion_anglais(client):
    r = client.get("/devops", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert "suggestion-langue" in r.get_data(as_text=True)
    r = client.get("/devops", headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    assert "suggestion-langue" not in r.get_data(as_text=True)
    r = client.get("/en/devops", headers={"Accept-Language": "en-US"})
    assert "suggestion-langue" not in r.get_data(as_text=True)


def test_pas_de_route_admin(client, app):
    assert client.get("/admin").status_code == 404
    assert not [r.rule for r in app.url_map.iter_rules() if "admin" in r.rule]


def test_role_admin_sans_blueprint_public(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, role="admin")
    assert "public" not in app.blueprints
