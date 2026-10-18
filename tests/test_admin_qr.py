"""QR code des versions : servi par l'admin, vers l'adresse publique avec ?src=qr."""
import pytest

from cv.medias import qr
from cv.models import Version

SITE = "https://cv.nanodeus.com"


@pytest.fixture(autouse=True)
def _sans_url_publique(monkeypatch):
    monkeypatch.delenv("CV_URL_PUBLIQUE", raising=False)


def _id(admin, slug):
    with admin.application.extensions["cv_sessions"]() as s:
        return s.query(Version.id).filter_by(slug=slug).scalar()


def test_qr_svg_affichable(admin):
    r = admin.get(f"/admin/versions/{_id(admin, 'devops')}/qr.svg")
    assert r.status_code == 200 and r.mimetype == "image/svg+xml"
    assert "Content-Disposition" not in r.headers
    # L'adresse encodée est vérifiée par segno lui-même : même URL, même symbole.
    assert r.data == qr(f"{SITE}/devops?src=qr", "svg")


def test_qr_png_telecharge_en_anglais(admin):
    r = admin.get(f"/admin/versions/{_id(admin, 'lead-tech')}/qr.png?telecharger=1&lang=en")
    assert r.status_code == 200 and r.mimetype == "image/png"
    assert r.headers["Content-Disposition"] == 'attachment; filename="qr-lead-tech-en.png"'
    assert r.data == qr(f"{SITE}/en/lead-tech?src=qr", "png")


def test_qr_svg_telecharge_en_francais(admin):
    r = admin.get(f"/admin/versions/{_id(admin, 'devops')}/qr.svg?telecharger=1")
    assert r.headers["Content-Disposition"] == 'attachment; filename="qr-devops.svg"'


@pytest.mark.parametrize("chemin", ["{id}/qr.gif", "{id}/qr.SVG", "99999/qr.svg", "{id}/qr"])
def test_qr_404(admin, chemin):
    url = "/admin/versions/" + chemin.format(id=_id(admin, "devops"))
    assert admin.get(url).status_code == 404


def test_brouillon_a_son_qr(admin):
    r = admin.get(f"/admin/versions/{_id(admin, 'brouillon')}/qr.svg")
    assert r.status_code == 200 and r.data == qr(f"{SITE}/brouillon?src=qr", "svg")


def test_url_publique_respectee(admin):
    app = admin.application
    app.config["CV"].URL_PUBLIQUE = "https://exemple.test"
    r = app.test_client().get(f"/admin/versions/{_id(admin, 'devops')}/qr.svg")
    assert r.data == qr("https://exemple.test/devops?src=qr", "svg")


def test_page_version_montre_le_qr(admin):
    id_ = _id(admin, "devops")
    corps = admin.get(f"/admin/versions/{id_}").get_data(as_text=True)
    assert f"{SITE}/devops?src=qr" in corps and f"{SITE}/en/devops?src=qr" in corps
    assert f'<img src="/admin/versions/{id_}/qr.svg"' in corps
    for lien in ("qr.svg?telecharger=1", "qr.png?telecharger=1",
                 "qr.svg?lang=en&amp;telecharger=1", "qr.png?lang=en&amp;telecharger=1"):
        assert f'href="/admin/versions/{id_}/{lien}"' in corps
