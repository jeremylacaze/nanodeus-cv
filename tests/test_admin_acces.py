"""Admin : réservé au tailnet, aucun cookie, jamais en cache."""
import pytest

from cv.admin.acces import RESEAUX_PAR_DEFAUT, adresse_autorisee, lire_reseaux
from cv.config import Config
from tests.conftest import EMAIL

DEHORS = {"REMOTE_ADDR": "203.0.113.5"}


@pytest.mark.parametrize("adresse, attendu", [
    ("100.64.0.7", True), ("100.127.255.254", True), ("127.0.0.1", True), ("::1", True),
    ("fd7a:115c:a1e0::1", True), ("::ffff:100.64.0.7", True),
    ("100.128.0.1", False), ("203.0.113.5", False), ("172.17.0.1", False),
    ("::ffff:203.0.113.5", False), ("", False), (None, False), ("pas-une-ip", False)])
def test_adresse_autorisee(adresse, attendu):
    assert adresse_autorisee(adresse, lire_reseaux(RESEAUX_PAR_DEFAUT)) is attendu


@pytest.mark.parametrize("url", ["/", "/admin/", "/admin/static/admin.css", "/static/cv.css",
                                 "/admin/inconnue"])
def test_hors_tailnet_403_partout(admin, url):
    r = admin.get(url, environ_base=DEHORS)
    assert r.status_code == 403 and EMAIL.encode() not in r.data


def test_x_forwarded_for_ignore(admin):
    r = admin.get("/admin/", environ_base=DEHORS, headers={"X-Forwarded-For": "100.64.0.7"})
    assert r.status_code == 403


def test_reseaux_vides_desactivent_le_controle(fabrique_app, monkeypatch):
    monkeypatch.setenv("CV_ADMIN_RESEAUX", "")
    assert fabrique_app(role="admin").test_client().get(
        "/admin/", environ_base=DEHORS).status_code == 200


@pytest.mark.parametrize("valeur", ["pas-un-reseau", "100.64.0.0/33", "100.64.0.7/10"])
def test_reseau_invalide_refuse(monkeypatch, valeur):
    monkeypatch.setenv("CV_ROLE", "admin")
    monkeypatch.setenv("CV_ADMIN_RESEAUX", valeur)
    with pytest.raises(ValueError):
        Config()


def test_trust_proxy_interdit_en_admin(monkeypatch):
    monkeypatch.setenv("CV_ROLE", "admin")
    monkeypatch.setenv("TRUST_PROXY", "1")
    with pytest.raises(ValueError):
        Config()


def test_accueil(admin):
    r = admin.get("/admin/")
    corps = r.get_data(as_text=True)
    assert r.status_code == 200 and "Set-Cookie" not in r.headers
    assert r.headers["Cache-Control"] == "no-store" and r.headers["X-Robots-Tag"] == "noindex"
    for lien in ("/admin/profil", "/admin/stock/parcours", "/admin/versions",
                 "/admin/demandes", "/admin/visites"):
        assert f'href="{lien}"' in corps
    assert 'src="/admin/static/admin.js"' in corps and "nonce=" in corps


def test_racine_redirige(admin):
    r = admin.get("/")
    assert r.status_code == 302 and r.headers["Location"] == "/admin/"


def test_message_ok_connu_seulement(admin):
    assert "Modifications enregistrées." in admin.get("/admin/?ok=enregistre").get_data(as_text=True)
    assert "<b>x</b>" not in admin.get("/admin/?ok=<b>x</b>").get_data(as_text=True)


def test_corps_jusqu_a_un_mio(admin):
    assert admin.application.config["MAX_CONTENT_LENGTH"] == 1024 * 1024


@pytest.mark.parametrize("hote, attendu", [
    ("localhost", 200), ("localhost:5011", 200), ("127.0.0.1:5011", 200), ("[::1]:5011", 200),
    ("LOCALHOST", 200), ("evil.example", 403), ("evil.example:5011", 403),
    ("localhost.evil.example", 403)])
def test_hote_controle_contre_le_dns_rebinding(admin, hote, attendu):
    # Une page tierce dont le domaine pointe vers l'IP de l'admin enverrait son propre
    # Host (et un Origin assorti) : seul un Host attendu ouvre l'admin.
    r = admin.get("/admin/", headers={"Host": hote})
    assert r.status_code == attendu and EMAIL.encode() not in r.data
    origine = {"Host": hote, "Origin": f"http://{hote}"}
    assert admin.post("/admin/profil", headers=origine, data={}).status_code in (
        (400,) if attendu == 200 else (403,))


def test_hotes_configures(fabrique_app, monkeypatch):
    monkeypatch.setenv("CV_ADMIN_HOTES", "100.64.0.5, Admin.Exemple.ts.net")
    client = fabrique_app(role="admin").test_client()
    assert client.get("/admin/", headers={"Host": "admin.exemple.ts.net:5011"}).status_code == 200
    assert client.get("/admin/", headers={"Host": "localhost"}).status_code == 403


def test_hotes_vides_refuses(monkeypatch):
    monkeypatch.setenv("CV_ROLE", "admin")
    monkeypatch.setenv("CV_ADMIN_HOTES", " , ")
    with pytest.raises(ValueError):
        Config()
