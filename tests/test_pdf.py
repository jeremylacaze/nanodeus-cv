"""PDF du CV : public (sans coordonnées, en cache) et complet (admin, jamais sur disque)."""
import re
import socket
from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from cv import pdf
from cv.models import Version, Visite
from tests.conftest import EMAIL

NAVIGATEUR = {"User-Agent": "Mozilla/5.0 (X11; Linux)"}


@pytest.fixture(autouse=True)
def _sans_url_publique(monkeypatch):
    monkeypatch.delenv("CV_URL_PUBLIQUE", raising=False)


@pytest.fixture
def client(fabrique_app):
    return fabrique_app().test_client()


def _texte(contenu: bytes) -> str:
    lecteur = PdfReader(BytesIO(contenu))
    return re.sub(r"\s+", " ", " ".join(p.extract_text() for p in lecteur.pages))


def _pages(contenu: bytes) -> int:
    return len(PdfReader(BytesIO(contenu)).pages)


def _cache(app):
    dossier = app.config["CV"].DOSSIER_CACHE_PDF
    return sorted(dossier.iterdir()) if dossier.exists() else []


def _id(app, slug):
    with app.extensions["cv_sessions"]() as s:
        return s.scalar(select(Version.id).where(Version.slug == slug))


def test_pdf_public(client):
    r = client.get("/devops.pdf")
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.headers["Content-Disposition"] == 'inline; filename="cv-devops-fr.pdf"'
    assert r.headers["ETag"] and "no-cache" in r.headers["Cache-Control"]
    assert "Set-Cookie" not in r.headers and "X-Robots-Tag" not in r.headers
    texte = _texte(r.data)
    for attendu in ("LACAZE-RUSQUES", "Administrateur applicatif / DevOps", "Expériences",
                    "Formations", "cv.nanodeus.com/devops", "B / A2"):
        assert attendu in texte
    assert "https://" not in texte and _pages(r.data) <= 2


def test_pdf_anglais(client):
    r = client.get("/en/devops.pdf")
    assert r.headers["Content-Disposition"] == 'inline; filename="cv-devops-en.pdf"'
    texte = _texte(r.data)
    assert "Experience" in texte and "Education" in texte and "Expériences" not in texte
    assert "cv.nanodeus.com/en/devops" in texte and _pages(r.data) <= 2


@pytest.mark.parametrize("url", ["/devops.pdf", "/en/devops.pdf", "/lead-tech.pdf",
                                 "/en/lead-tech.pdf"])
def test_pdf_public_sans_coordonnees(client, url):
    r = client.get(url)
    texte = _texte(r.data)
    assert EMAIL not in texte and "99 88 77 66" not in texte
    assert EMAIL.encode() not in r.data


def test_metadonnees_sans_coordonnees(client):
    lecteur = PdfReader(BytesIO(client.get("/devops.pdf").data))
    meta = lecteur.metadata
    assert meta.title == "Jeremy LACAZE-RUSQUES · Administrateur applicatif / DevOps"
    assert EMAIL not in str(dict(meta)) and "99 88 77 66" not in str(dict(meta))


def test_pdf_complet_admin(admin):
    app = admin.application
    r = admin.get(f"/admin/versions/{_id(app, 'devops')}/cv.pdf?complet=1")
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.headers["Content-Disposition"] == 'attachment; filename="cv-devops-fr-complet.pdf"'
    # Témoin : l'extraction voit bien les coordonnées quand elles sont imprimées.
    texte = _texte(r.data)
    assert EMAIL in texte and "99 88 77 66" in texte
    assert _cache(app) == []


def test_pdf_complet_anglais(admin):
    app = admin.application
    r = admin.get(f"/admin/versions/{_id(app, 'devops')}/cv.pdf?complet=1&lang=en")
    assert r.headers["Content-Disposition"] == 'attachment; filename="cv-devops-en-complet.pdf"'
    assert "Experience" in _texte(r.data)


def test_pdf_public_depuis_admin_brouillon(admin):
    app = admin.application
    r = admin.get(f"/admin/versions/{_id(app, 'brouillon')}/cv.pdf")
    assert r.status_code == 200
    assert r.headers["Content-Disposition"] == 'attachment; filename="cv-brouillon-fr.pdf"'
    texte = _texte(r.data)
    assert EMAIL not in texte and "99 88 77 66" not in texte


def test_pdf_admin_version_inconnue(admin):
    assert admin.get("/admin/versions/99999/cv.pdf").status_code == 404


def test_page_version_liens_pdf(admin):
    id_ = _id(admin.application, "devops")
    corps = admin.get(f"/admin/versions/{id_}").get_data(as_text=True)
    for lien in ("cv.pdf", "cv.pdf?lang=en", "cv.pdf?complet=1", "cv.pdf?lang=en&amp;complet=1"):
        assert f'href="/admin/versions/{id_}/{lien}"' in corps


@pytest.mark.parametrize("url", ["/brouillon.pdf", "/inconnue.pdf", "/Devops.pdf",
                                 "/devops.PDF", "/devops.pdf/x", "/en/brouillon.pdf",
                                 "/en/inconnue.pdf"])
def test_pdf_404(client, url):
    assert client.get(url).status_code == 404


def test_page_reste_la_page(client):
    r = client.get("/devops")
    assert r.status_code == 200 and r.mimetype == "text/html"


def test_pdf_non_liste_noindex(client):
    assert client.get("/lead-tech.pdf").headers["X-Robots-Tag"] == "noindex"


def test_pdf_journalise(client):
    client.get("/en/lead-tech.pdf", headers=NAVIGATEUR)
    with client.application.extensions["cv_sessions"]() as s:
        (v,) = s.scalars(select(Visite)).all()
    assert (v.type, v.version_slug, v.langue) == ("pdf", "lead-tech", "en")


def test_cache_reutilise_puis_invalide(client):
    app = client.application
    r1, r2 = client.get("/devops.pdf"), client.get("/devops.pdf")
    assert r1.headers["ETag"] == r2.headers["ETag"] and len(_cache(app)) == 1
    r = client.get("/devops.pdf", headers={"If-None-Match": r1.headers["ETag"]})
    assert r.status_code == 304
    with app.extensions["cv_sessions"]() as s:
        s.scalar(select(Version).where(Version.slug == "devops")).accroche_fr = "Accroche neuve"
        s.commit()
    r3 = client.get("/devops.pdf")
    assert r3.headers["ETag"] != r1.headers["ETag"] and "Accroche neuve" in _texte(r3.data)


def test_cache_borne(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf, "rendre_pdf", lambda html: html.encode())
    for i in range(pdf.CACHE_MAX + 5):
        contenu, etag = pdf.pdf_en_cache(tmp_path, f"<p>{i}</p>")
        assert contenu == f"<p>{i}</p>".encode() and (tmp_path / f"{etag}.pdf").exists()
    assert len(list(tmp_path.iterdir())) == pdf.CACHE_MAX
    # Le plus récent reste, le plus ancien est parti.
    assert pdf.pdf_en_cache(tmp_path, f"<p>{pdf.CACHE_MAX + 4}</p>")[0]
    assert len(list(tmp_path.iterdir())) == pdf.CACHE_MAX


def test_aucune_ressource_externe(monkeypatch):
    def interdit(*args, **kwargs):
        raise AssertionError("connexion réseau ouverte")

    monkeypatch.setattr(socket, "socket", interdit)
    monkeypatch.setattr(socket, "create_connection", interdit)
    html = ('<html><head><style>@import url("http://127.0.0.1:9/a.css");</style></head>'
            '<body><img src="http://127.0.0.1:9/x.png"><p>Bonjour</p></body></html>')
    assert "Bonjour" in _texte(pdf.rendre_pdf(html))
