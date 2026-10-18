"""Routes du contact : avec et sans JavaScript, Origin, limites, aucune fuite."""
import pytest
from sqlalchemy import select

from cv.models import DemandeContact, Visite
from tests.conftest import EMAIL
from tests.fabriques import FauxEnvoi

ORIGINE = {"Origin": "http://localhost"}
JSON = {**ORIGINE, "Accept": "application/json"}
OK = {"email": "r@ex.fr", "message": "Bonjour", "nom": "Alice", "entreprise": "ACME"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux)"}
DESTINATAIRE = "dest@test.invalid"


@pytest.fixture
def client_et_envoi(fabrique_app, monkeypatch):
    monkeypatch.setenv("CV_EMAIL_DESTINATAIRE", DESTINATAIRE)
    app = fabrique_app()
    envoi = FauxEnvoi()
    app.extensions["cv_envoi"] = envoi
    return app.test_client(), envoi


def _demandes(client):
    with client.application.extensions["cv_sessions"]() as s:
        return s.scalars(select(DemandeContact)).all()


def _visites(client):
    with client.application.extensions["cv_sessions"]() as s:
        return s.scalars(select(Visite)).all()


def test_demande_envoyee_reply_to(client_et_envoi):
    c, envoi = client_et_envoi
    r = c.post("/lead-tech/contact", data=OK, headers=JSON)
    assert r.status_code == 200 and r.json["ok"] is True
    assert envoi.messages[0]["Reply-To"] == "r@ex.fr"
    assert "[CV · lead-tech]" in envoi.messages[0]["Subject"]
    (d,) = _demandes(c)
    assert (d.version_slug, d.langue, d.statut) == ("lead-tech", "fr", "envoyee")


def test_langue_anglaise_enregistree(client_et_envoi):
    c, _ = client_et_envoi
    r = c.post("/en/devops/contact", data=OK, headers=JSON)
    assert r.status_code == 200 and "Jeremy will reply" in r.json["message"]
    assert _demandes(c)[0].langue == "en"


def test_echec_envoi_202_demande_gardee(client_et_envoi):
    c, envoi = client_et_envoi
    envoi.erreur = TimeoutError("smtp.interne:587 trop lent")
    r = c.post("/devops/contact", data=OK, headers=JSON)
    assert r.status_code == 202 and r.json["ok"] is False
    assert "bien enregistrée" in r.json["message"]
    assert "TimeoutError" not in r.get_data(as_text=True)
    assert "smtp.interne" not in r.get_data(as_text=True)
    (d,) = _demandes(c)
    assert d.statut == "echec" and d.erreur.startswith("TimeoutError")


def test_champ_piege(client_et_envoi):
    c, envoi = client_et_envoi
    r = c.post("/devops/contact", data={**OK, "site_web": "http://spam.example"}, headers=JSON)
    assert r.status_code == 200 and r.json["ok"] is True
    assert _demandes(c) == [] and envoi.messages == []


def test_erreurs_de_validation_400(client_et_envoi):
    c, envoi = client_et_envoi
    r = c.post("/devops/contact", data={**OK, "email": "pas-un-email"}, headers=JSON)
    assert r.status_code == 400 and r.json["ok"] is False and "email" in r.json["erreurs"]
    assert _demandes(c) == [] and envoi.messages == []


def test_limite_429(client_et_envoi):
    c, _ = client_et_envoi
    ip = {"REMOTE_ADDR": "203.0.113.5"}
    for _ in range(3):
        assert c.post("/devops/contact", data=OK, headers=JSON, environ_base=ip).status_code == 200
    r = c.post("/devops/contact", data=OK, headers=JSON, environ_base=ip)
    assert r.status_code == 429 and r.json["ok"] is False
    autre = {"REMOTE_ADDR": "198.51.100.9"}
    assert c.post("/devops/contact", data=OK, headers=JSON, environ_base=autre).status_code == 200
    assert len(_demandes(c)) == 4


@pytest.mark.parametrize("entetes", [{}, {"Origin": "null"}, {"Origin": "https://evil.example"},
                                     {"Origin": "http://localhost.evil.example"}])
def test_origin_refuse(client_et_envoi, entetes):
    c, envoi = client_et_envoi
    r = c.post("/devops/contact", data=OK, headers=entetes)
    assert r.status_code == 403 and b'name="robots"' in r.data
    assert _demandes(c) == [] and envoi.messages == []


def test_corps_trop_gros_413(client_et_envoi):
    c, _ = client_et_envoi
    r = c.post("/devops/contact", data={**OK, "message": "x" * 70_000}, headers=ORIGINE)
    assert r.status_code == 413 and _demandes(c) == []


@pytest.mark.parametrize("url", ["/brouillon/contact", "/inconnue/contact", "/Devops/contact",
                                 "/en/brouillon/contact"])
def test_version_non_publique_404(client_et_envoi, url):
    c, _ = client_et_envoi
    assert c.get(url).status_code == 404
    assert c.post(url, data=OK, headers=JSON).status_code == 404
    assert c.post(url + "/ouverture", headers=ORIGINE).status_code == 404
    assert _demandes(c) == []


def test_sans_js_page_de_confirmation(client_et_envoi):
    c, _ = client_et_envoi
    r = c.post("/devops/contact", data=OK, headers=ORIGINE)
    corps = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == "text/html"
    assert "Jeremy vous répondra" in corps and 'name="email"' not in corps


def test_sans_js_erreurs_et_valeurs_conservees(client_et_envoi):
    c, _ = client_et_envoi
    r = c.post("/devops/contact", headers=ORIGINE,
               data={**OK, "email": "faux", "nom": '<b>"Alice"</b>'})
    corps = r.get_data(as_text=True)
    assert r.status_code == 400
    assert "Indiquez une adresse email valide." in corps
    assert "&lt;b&gt;&#34;Alice&#34;&lt;/b&gt;" in corps and "<b>" not in corps
    assert 'value="faux"' in corps


def test_page_contact_journalise_et_noindex(client_et_envoi):
    c, _ = client_et_envoi
    r = c.get("/en/lead-tech/contact", headers=UA)
    corps = r.get_data(as_text=True)
    assert r.status_code == 200 and r.headers["X-Robots-Tag"] == "noindex"
    assert 'name="robots"' in corps and 'action="/en/lead-tech/contact"' in corps
    assert 'name="site_web"' in corps and 'href="/lead-tech/contact"' in corps
    (v,) = _visites(c)
    assert (v.type, v.version_slug, v.langue) == ("contact", "lead-tech", "en")


def test_balise_ouverture_204(client_et_envoi):
    c, _ = client_et_envoi
    r = c.post("/devops/contact/ouverture", headers={**ORIGINE, **UA})
    assert r.status_code == 204 and r.data == b""
    assert [v.type for v in _visites(c)] == ["contact"]
    assert c.post("/devops/contact/ouverture", headers=UA).status_code == 403


@pytest.mark.parametrize("appel", [
    ("get", "/devops/contact", {}, {}),
    ("post", "/devops/contact", OK, JSON),
    ("post", "/devops/contact", OK, ORIGINE),
    ("post", "/devops/contact", {**OK, "email": "x"}, ORIGINE),
    ("post", "/devops/contact", OK, {}),
    ("post", "/devops/contact/ouverture", {}, ORIGINE),
])
@pytest.mark.parametrize("echec", [False, True])
def test_reponses_sans_fuite_ni_cookie(client_et_envoi, appel, echec):
    c, envoi = client_et_envoi
    if echec:
        envoi.erreur = OSError(f"refus pour {DESTINATAIRE}")
    methode, url, donnees, entetes = appel
    r = getattr(c, methode)(url, data=donnees, headers=entetes)
    corps = r.get_data(as_text=True) + str(r.headers)
    assert EMAIL not in corps and "99 88 77 66" not in corps and DESTINATAIRE not in corps
    assert "Set-Cookie" not in r.headers
