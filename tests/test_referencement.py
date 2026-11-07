"""Référencement : robots.txt, sitemap.xml, en-tête des pages et security.txt."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

import pytest

from tests.conftest import EMAIL, TELEPHONE

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


# --- En-tête des pages : canonique, langues, données structurées, icône ---------

class _Tete(HTMLParser):
    """Liens <link>, balises <meta> et blocs JSON-LD d'une page."""

    def __init__(self):
        super().__init__()
        self.liens, self.metas, self.jsonld, self._dans_jsonld = [], {}, [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link":
            self.liens.append(a)
        elif tag == "meta":
            self.metas[a.get("property") or a.get("name")] = a.get("content")
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._dans_jsonld = True

    def handle_endtag(self, tag):
        self._dans_jsonld = False if tag == "script" else self._dans_jsonld

    def handle_data(self, data):
        if self._dans_jsonld:
            self.jsonld.append(json.loads(data))


def _tete(client, chemin):
    r = client.get(chemin)
    assert r.status_code == 200
    tete = _Tete()
    tete.feed(r.get_data(as_text=True))
    return tete


def _alternates(tete):
    return {lien["hreflang"]: lien["href"] for lien in tete.liens
            if lien.get("rel") == "alternate" and lien.get("hreflang")}


def _canonique(tete):
    return [lien["href"] for lien in tete.liens if lien.get("rel") == "canonical"]


@pytest.mark.parametrize("chemin, attendu", [
    ("/", "http://localhost/"), ("/devops", "http://localhost/"),
    ("/en/", "http://localhost/en/"), ("/en/devops", "http://localhost/en/"),
    ("/sre", "http://localhost/sre"), ("/en/sre", "http://localhost/en/sre"),
])
def test_url_canonique(client, chemin, attendu):
    # La version par défaut a deux adresses (/ et /devops) : une seule fait foi.
    tete = _tete(client, chemin)
    assert _canonique(tete) == [attendu]
    assert tete.metas["og:url"] == attendu


def test_canonique_ignore_la_query_string(client):
    assert _canonique(_tete(client, "/sre?src=qr")) == ["http://localhost/sre"]


@pytest.mark.parametrize("chemin", ["/sre", "/en/sre"])
def test_alternates_relient_les_deux_langues(client, chemin):
    assert _alternates(_tete(client, chemin)) == {
        "fr": "http://localhost/sre", "en": "http://localhost/en/sre",
        "x-default": "http://localhost/sre"}


def test_alternates_de_la_version_par_defaut(client):
    assert _alternates(_tete(client, "/devops")) == {
        "fr": "http://localhost/", "en": "http://localhost/en/",
        "x-default": "http://localhost/"}


def test_icone_annoncee_et_servie(client):
    tete = _tete(client, "/")
    icones = {lien["href"] for lien in tete.liens if lien.get("rel") == "icon"}
    assert any(href.endswith(".svg") for href in icones)
    for href in (*icones, *(lien["href"] for lien in tete.liens
                            if lien.get("rel") == "apple-touch-icon")):
        assert client.get(href).status_code == 200
    r = client.get("/favicon.ico")
    assert r.status_code == 200 and r.mimetype in ("image/x-icon", "image/vnd.microsoft.icon")


def test_jsonld_decrit_la_personne(client):
    blocs = _tete(client, "/sre").jsonld
    assert len(blocs) == 1
    page = blocs[0]
    assert page["@context"] == "https://schema.org" and page["@type"] == "ProfilePage"
    personne = page["mainEntity"]
    assert personne["@type"] == "Person"
    assert personne["name"] == "Jeremy LACAZE-RUSQUES"
    assert personne["jobTitle"] == "SRE"
    assert personne["address"]["addressLocality"] == "Toulouse, France"
    assert page["url"] == "http://localhost/sre" and page["inLanguage"] == "fr"


def test_jsonld_sans_coordonnees(client):
    for chemin in ("/", "/en/", "/sre"):
        texte = json.dumps(_tete(client, chemin).jsonld)
        assert EMAIL not in texte and TELEPHONE not in texte
        assert "email" not in texte and "telephone" not in texte


def test_jsonld_echappe_le_html(fabrique_app):
    from cv.models import Version

    def piege(s):
        v = s.query(Version).filter_by(slug="devops").one()
        v.accroche_fr = "</script><script>alert(1)</script>"
    corps = fabrique_app(modifier=piege).test_client().get("/").get_data(as_text=True)
    assert "</script><script>alert(1)" not in corps


# --- security.txt (RFC 9116) ---------------------------------------------------

def _champs_security(client):
    r = client.get("/.well-known/security.txt")
    assert r.status_code == 200 and r.mimetype == "text/plain"
    champs = {}
    for ligne in r.get_data(as_text=True).splitlines():
        if ligne and not ligne.startswith("#"):
            nom, valeur = ligne.split(": ", 1)
            champs.setdefault(nom, []).append(valeur)
    return champs


def test_security_txt(client):
    champs = _champs_security(client)
    # Le formulaire de la version par défaut : aucune coordonnée personnelle.
    assert champs["Contact"] == ["http://localhost/devops/contact"]
    assert champs["Canonical"] == ["http://localhost/.well-known/security.txt"]
    assert champs["Preferred-Languages"] == ["fr, en"]
    expire = datetime.fromisoformat(champs["Expires"][0].replace("Z", "+00:00"))
    maintenant = datetime.now(UTC)
    assert maintenant < expire <= maintenant + timedelta(days=366)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", champs["Expires"][0])


def test_security_txt_absent_de_l_admin(admin):
    assert admin.get("/.well-known/security.txt").status_code == 404
