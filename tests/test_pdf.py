"""PDF du CV : public (sans coordonnées, en cache) et complet (admin, jamais sur disque)."""
import re
import socket
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from cv import medias, pdf
from cv.models import Version, Visite
from tests.conftest import EMAIL
from tests.test_medias import _image

NAVIGATEUR = {"User-Agent": "Mozilla/5.0 (X11; Linux)"}
ORIGINE = {"Origin": "http://localhost"}


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


def _legende_qr(texte: str) -> str:
    """La légende du QR code passe à la ligne là où la police le décide ; pypdf colle
    alors les deux mots de part et d'autre de la coupure. On la compare sans espaces."""
    return texte.replace(" ", "")


def _cache(app):
    dossier = app.config["CV"].DOSSIER_CACHE_PDF
    return sorted(dossier.iterdir()) if dossier.exists() else []


def _id(app, slug):
    with app.extensions["cv_sessions"]() as s:
        return s.scalar(select(Version.id).where(Version.slug == slug))


def test_pdf_public(client):
    r = client.get("/devops.pdf")
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.headers["Content-Disposition"] == 'inline; filename="cv-jeremy-lacaze-rusques-devops-fr.pdf"'
    assert r.headers["ETag"] and "no-cache" in r.headers["Cache-Control"]
    assert "Set-Cookie" not in r.headers and "X-Robots-Tag" not in r.headers
    texte = _texte(r.data)
    # Les titres de section sont en petites capitales, comme sur la page web.
    for attendu in ("LACAZE-RUSQUES", "Administrateur applicatif / DevOps", "EXPÉRIENCES",
                    "FORMATIONS", "cv.nanodeus.com/devops", "B / A2", "PARCOURS",
                    "PHONE *** · EMAIL ***"):
        assert attendu in texte
    assert "Scannezpourlaversionenligne" in _legende_qr(texte)
    # En France, un CV tient sur une page : le contenu d'amorçage doit y tenir.
    assert "https://" not in texte and _pages(r.data) == 1


def test_pdf_anglais(client):
    r = client.get("/en/devops.pdf")
    assert r.headers["Content-Disposition"] == 'inline; filename="cv-jeremy-lacaze-rusques-devops-en.pdf"'
    texte = _texte(r.data)
    assert "EXPERIENCE" in texte and "EDUCATION" in texte and "EXPÉRIENCES" not in texte
    assert "Scanfortheonlineversion" in _legende_qr(texte) and "Scannez" not in texte
    assert "cv.nanodeus.com/en/devops" in texte and _pages(r.data) == 1


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
    assert r.headers["Content-Disposition"] == 'attachment; filename="cv-jeremy-lacaze-rusques-devops-fr-complet.pdf"'
    # Témoin : l'extraction voit bien les coordonnées quand elles sont imprimées.
    texte = _texte(r.data)
    assert EMAIL in texte and "99 88 77 66" in texte and "***" not in texte
    assert _cache(app) == []


def test_pdf_complet_anglais(admin):
    app = admin.application
    r = admin.get(f"/admin/versions/{_id(app, 'devops')}/cv.pdf?complet=1&lang=en")
    assert r.headers["Content-Disposition"] == 'attachment; filename="cv-jeremy-lacaze-rusques-devops-en-complet.pdf"'
    assert "EXPERIENCE" in _texte(r.data)


def test_pdf_public_depuis_admin_brouillon(admin):
    app = admin.application
    r = admin.get(f"/admin/versions/{_id(app, 'brouillon')}/cv.pdf")
    assert r.status_code == 200
    assert r.headers["Content-Disposition"] == 'attachment; filename="cv-jeremy-lacaze-rusques-brouillon-fr.pdf"'
    texte = _texte(r.data)
    assert EMAIL not in texte and "99 88 77 66" not in texte


def test_pdf_admin_version_inconnue(admin):
    assert admin.get("/admin/versions/99999/cv.pdf").status_code == 404


def test_page_version_liens_pdf(admin):
    id_ = _id(admin.application, "devops")
    corps = admin.get(f"/admin/versions/{id_}").get_data(as_text=True)
    for lien in ("cv.pdf", "cv.pdf?lang=en", "cv.pdf?complet=1", "cv.pdf?lang=en&amp;complet=1"):
        assert f'href="/admin/versions/{id_}/{lien}"' in corps


def test_page_version_sans_avertissement(admin):
    corps = admin.get(f"/admin/versions/{_id(admin.application, 'devops')}").get_data(as_text=True)
    assert "pages : en France" not in corps


def test_page_version_avertit_si_plus_d_une_page(fabrique_app):
    def allonger(s):
        s.scalar(select(Version).where(Version.slug == "devops")).accroche_en = "Long. " * 1500
    admin = fabrique_app(role="admin", modifier=allonger).test_client()
    corps = admin.get(f"/admin/versions/{_id(admin.application, 'devops')}").get_data(as_text=True)
    assert "Le PDF EN fait" in corps and "Le PDF FR fait" not in corps


def test_page_version_rend_chaque_langue_dans_sa_langue(admin):
    # Le PDF anglais compté par la page d'admin est bien celui servi en anglais :
    # le télécharger ensuite le trouve en cache, sans nouveau rendu.
    app = admin.application
    id_ = _id(app, "devops")
    admin.get(f"/admin/versions/{id_}")
    assert len(_cache(app)) == 2
    texte = _texte(admin.get(f"/admin/versions/{id_}/cv.pdf?lang=en").data)
    assert "EXPERIENCE" in texte and len(_cache(app)) == 2
    # La page d'admin elle-même reste en français.
    assert "Consulter" in admin.get(f"/admin/versions/{id_}").get_data(as_text=True)


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


def _rendu_factice(html):
    return html.encode(), 1


def test_cache_garde_le_nombre_de_pages(tmp_path, monkeypatch):
    rendus = []

    def rendu(html):
        rendus.append(html)
        return html.encode(), 3
    monkeypatch.setattr(pdf, "rendu_pdf", rendu)
    contenu, etag, pages = pdf.pdf_en_cache(tmp_path, "<p>x</p>")
    assert (contenu, pages) == (b"<p>x</p>", 3) and (tmp_path / f"{etag}-3.pdf").exists()
    assert pdf.pdf_en_cache(tmp_path, "<p>x</p>") == (contenu, etag, 3) and len(rendus) == 1


def test_rendu_compte_les_pages():
    html = '<p style="break-after: page">1</p><p>2</p>'
    contenu, pages = pdf.rendu_pdf(html)
    assert pages == 2 == _pages(contenu)


def test_cache_borne(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf, "rendu_pdf", _rendu_factice)
    for i in range(pdf.CACHE_MAX + 5):
        contenu, etag, _ = pdf.pdf_en_cache(tmp_path, f"<p>{i}</p>")
        assert contenu == f"<p>{i}</p>".encode() and (tmp_path / f"{etag}-1.pdf").exists()
    assert len(list(tmp_path.iterdir())) == pdf.CACHE_MAX
    # Le plus récent reste, le plus ancien est parti.
    assert pdf.pdf_en_cache(tmp_path, f"<p>{pdf.CACHE_MAX + 4}</p>")[0]
    assert len(list(tmp_path.iterdir())) == pdf.CACHE_MAX


def test_cache_elague_par_un_autre_processus(tmp_path, monkeypatch):
    # Lu, puis élagué par l'autre conteneur avant le rafraîchissement de sa date :
    # le contenu est déjà en mémoire, la réponse ne doit pas échouer.
    monkeypatch.setattr(pdf, "rendu_pdf", _rendu_factice)
    pdf.pdf_en_cache(tmp_path, "<p>x</p>")

    def disparu(chemin, *args):
        raise FileNotFoundError(chemin)
    monkeypatch.setattr(pdf.os, "utime", disparu)
    assert pdf.pdf_en_cache(tmp_path, "<p>x</p>")[0] == b"<p>x</p>"


def test_cache_ecriture_interrompue_sans_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf, "rendu_pdf", _rendu_factice)

    def echec(*args):
        raise OSError("disque plein")
    monkeypatch.setattr(medias.os, "replace", echec)
    with pytest.raises(OSError):
        pdf.pdf_en_cache(tmp_path, "<p>x</p>")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("action", ["envoi", "suppression"])
def test_changer_la_photo_vide_le_cache(fabrique_app, action):
    # Les PDF en cache portent la photo incorporée : une photo retirée ne doit pas
    # survivre sur disque jusqu'à l'élagage.
    admin = fabrique_app(role="admin").test_client()
    id_ = _id(admin.application, "devops")
    envoyer = {"photo": (BytesIO(_image()), "p.jpg")}
    admin.post("/admin/profil/photo", headers=ORIGINE, data=envoyer,
               content_type="multipart/form-data")
    assert admin.get(f"/admin/versions/{id_}/cv.pdf").status_code == 200
    assert _cache(admin.application)
    if action == "envoi":
        admin.post("/admin/profil/photo", headers=ORIGINE,
                   data={"photo": (BytesIO(_image(taille=(300, 300))), "p.jpg")},
                   content_type="multipart/form-data")
    else:
        admin.post("/admin/profil/photo/supprimer", headers=ORIGINE)
    assert _cache(admin.application) == []


def test_aucune_ressource_externe(monkeypatch):
    def interdit(*args, **kwargs):
        raise AssertionError("connexion réseau ouverte")

    monkeypatch.setattr(socket, "socket", interdit)
    monkeypatch.setattr(socket, "create_connection", interdit)
    html = ('<html><head><style>@import url("http://127.0.0.1:9/a.css");</style></head>'
            '<body><img src="http://127.0.0.1:9/x.png"><p>Bonjour</p></body></html>')
    assert "Bonjour" in _texte(pdf.rendre_pdf(html))


@pytest.mark.parametrize(("nom", "complet", "attendu"), [
    ("Jérémy Lacaze-Rusques", False, "cv-jeremy-lacaze-rusques-devops-fr.pdf"),
    ("  Zoë  O'Brien ", True, "cv-zoe-o-brien-devops-fr-complet.pdf"),
    ("", False, "cv-devops-fr.pdf"),
])
def test_nom_fichier(nom, complet, attendu):
    vue = SimpleNamespace(nom=nom, slug="devops", lang="fr")
    assert pdf.nom_fichier(vue, complet) == attendu
