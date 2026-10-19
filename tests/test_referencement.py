"""robots.txt et sitemap.xml : seules les versions publiées et listées y figurent."""
import xml.etree.ElementTree as ET

import pytest

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "x": "http://www.w3.org/1999/xhtml"}


@pytest.fixture
def client(fabrique_app):
    from cv.models import Version

    def versions(s):
        s.add(Version(slug="sre", statut="publiee", titre_fr="SRE"))
    return fabrique_app(modifier=versions).test_client()


def _urls(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and r.mimetype == "application/xml"
    return ET.fromstring(r.data).findall("s:url", NS)


def test_robots_autorise_tout_et_annonce_le_sitemap(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.mimetype == "text/plain"
    lignes = r.get_data(as_text=True).splitlines()
    assert "User-agent: *" in lignes
    assert "Disallow: /" not in lignes
    assert "Sitemap: http://localhost/sitemap.xml" in lignes


def test_sitemap_liste_les_versions_publiees(client):
    # devops est la version par défaut (servie sur /), lead-tech est non listée,
    # brouillon n'est pas publiée : ni l'une ni l'autre n'a sa propre entrée.
    locs = {u.findtext("s:loc", namespaces=NS) for u in _urls(client)}
    assert locs == {"http://localhost/", "http://localhost/en/",
                    "http://localhost/sre", "http://localhost/en/sre"}


def test_sitemap_relie_les_deux_langues(client):
    for url in _urls(client):
        liens = {lien.get("hreflang"): lien.get("href")
                 for lien in url.findall("x:link", NS)}
        assert set(liens) == {"fr", "en"}
        assert url.findtext("s:loc", namespaces=NS) in liens.values()


def test_sitemap_suit_l_url_publique(fabrique_app, monkeypatch):
    monkeypatch.setenv("CV_URL_PUBLIQUE", "https://cv.exemple.test")
    locs = {u.findtext("s:loc", namespaces=NS) for u in _urls(fabrique_app().test_client())}
    assert locs == {"https://cv.exemple.test/", "https://cv.exemple.test/en/"}


def test_pas_de_robots_sur_l_admin(admin):
    assert admin.get("/robots.txt").status_code == 404
    assert admin.get("/sitemap.xml").status_code == 404
