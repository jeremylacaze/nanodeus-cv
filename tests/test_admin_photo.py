"""Photo du profil : envoi depuis l'admin, service public et aperçu."""
from io import BytesIO

import pytest

from cv.app import create_app
from cv.config import Config
from cv.medias import enregistrer_photo, traiter_photo
from cv.models import Profil, Version
from tests.test_medias import _bombe, _image, _tronque

ORIGINE = {"Origin": "http://localhost"}


def _profil(app):
    with app.extensions["cv_sessions"]() as s:
        return s.get(Profil, 1)


def _photos(app):
    dossier = app.config["CV"].DOSSIER_PHOTOS
    return sorted(f.name for f in dossier.iterdir()) if dossier.exists() else []


def _envoyer(admin, donnees=None, nom="photo.jpg"):
    donnees = _image() if donnees is None else donnees
    return admin.post("/admin/profil/photo", headers=ORIGINE,
                      data={"photo": (BytesIO(donnees), nom)},
                      content_type="multipart/form-data")


def test_envoi_photo(admin):
    r = _envoyer(admin)
    assert r.status_code == 303
    assert r.headers["Location"] == "/admin/profil?ok=photo-enregistree"
    nom = _profil(admin.application).photo_fichier
    assert _photos(admin.application) == [nom]
    r = admin.get(f"/admin/photo/{nom}")
    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    corps = admin.get("/admin/profil?ok=photo-enregistree").get_data(as_text=True)
    assert "Photo enregistrée." in corps and f'src="/admin/photo/{nom}"' in corps


def test_remplacement_supprime_l_ancienne(admin):
    _envoyer(admin)
    ancienne = _profil(admin.application).photo_fichier
    _envoyer(admin, _image(taille=(300, 300)))
    nouvelle = _profil(admin.application).photo_fichier
    assert nouvelle != ancienne and _photos(admin.application) == [nouvelle]
    assert admin.get(f"/admin/photo/{ancienne}").status_code == 404


def test_suppression_photo(admin):
    _envoyer(admin)
    r = admin.post("/admin/profil/photo/supprimer", headers=ORIGINE)
    assert r.status_code == 303
    assert r.headers["Location"] == "/admin/profil?ok=photo-supprimee"
    assert _profil(admin.application).photo_fichier is None
    assert _photos(admin.application) == []


@pytest.mark.parametrize("donnees", [None, b"pas une image", _bombe(), _image("GIF"), _tronque()],
                         ids=["sans-fichier", "texte", "bombe", "gif", "tronque"])
def test_envoi_refuse_400(admin, donnees):
    _envoyer(admin)
    actuelle = _profil(admin.application).photo_fichier
    if donnees is None:
        r = admin.post("/admin/profil/photo", headers=ORIGINE, data={},
                       content_type="multipart/form-data")
    else:
        r = _envoyer(admin, donnees)
    assert r.status_code == 400
    assert "pas une photo lisible (JPEG, PNG ou WEBP" in r.get_data(as_text=True)
    assert _profil(admin.application).photo_fichier == actuelle
    assert _photos(admin.application) == [actuelle]


def test_photo_de_8_mio_acceptee(admin):
    # Une photo de téléphone dépasse largement le Mio des autres formulaires.
    lourde = _image("PNG", (2000, 2000)) + b"\x00" * (8 * 1024 * 1024)
    assert _envoyer(admin, lourde, "photo.png").status_code == 303


def test_envoi_sans_origine_refuse(admin):
    r = admin.post("/admin/profil/photo", data={"photo": (BytesIO(_image()), "p.jpg")},
                   content_type="multipart/form-data")
    assert r.status_code == 403 and _photos(admin.application) == []


@pytest.fixture
def public_avec_photo(fabrique_app):
    app = fabrique_app()
    nom = enregistrer_photo(app.config["CV"].DOSSIER_PHOTOS, traiter_photo(_image()))
    with app.extensions["cv_sessions"]() as s:
        s.get(Profil, 1).photo_fichier = nom
        s.commit()
    return app.test_client(), nom


def test_photo_publique(public_avec_photo):
    client, nom = public_avec_photo
    r = client.get(f"/photo/{nom}")
    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    assert "immutable" in r.headers["Cache-Control"]
    assert "max-age=31536000" in r.headers["Cache-Control"]
    assert "Set-Cookie" not in r.headers
    corps = client.get("/devops").get_data(as_text=True)
    assert f'<img class="photo" src="/photo/{nom}"' in corps
    assert f'<meta property="og:image" content="http://localhost/photo/{nom}">' in corps


def test_sans_photo_ni_og_image(fabrique_app):
    corps = fabrique_app().test_client().get("/devops").get_data(as_text=True)
    assert "og:image" not in corps and 'class="photo" aria-hidden="true"' in corps


@pytest.mark.parametrize("nom", ["abc.jpg", "..%2Fcv.sqlite3", "0123456789abcdef.png",
                                 "0123456789abcdef.jpg"])
def test_photo_inconnue_404(public_avec_photo, nom):
    client, _ = public_avec_photo
    assert client.get(f"/photo/{nom}").status_code == 404


def test_apercu_admin_photo(admin):
    _envoyer(admin)
    nom = _profil(admin.application).photo_fichier
    with admin.application.extensions["cv_sessions"]() as s:
        id_ = s.query(Version.id).filter_by(slug="devops").scalar()
    corps = admin.get(f"/admin/versions/{id_}/apercu").get_data(as_text=True)
    assert f'src="/admin/photo/{nom}"' in corps and "og:image" not in corps


def test_fichier_orphelin_404(public_avec_photo):
    # Présent sur disque, bien nommé, mais ce n'est pas la photo du profil.
    client, _ = public_avec_photo
    orphelin = enregistrer_photo(client.application.config["CV"].DOSSIER_PHOTOS, b"autre")
    assert client.get(f"/photo/{orphelin}").status_code == 404


def test_ancienne_url_publique_404_apres_remplacement(admin, monkeypatch):
    _envoyer(admin)
    ancienne = _profil(admin.application).photo_fichier
    _envoyer(admin, _image(taille=(300, 300)))
    nouvelle = _profil(admin.application).photo_fichier
    monkeypatch.setenv("CV_ROLE", "public")  # même dossier de données que l'admin
    public = create_app(Config()).test_client()
    assert public.get(f"/photo/{ancienne}").status_code == 404
    assert public.get(f"/photo/{nouvelle}").status_code == 200


def test_photo_absente_du_disque_initiales(public_avec_photo):
    # Base restaurée sans le dossier photos/ : pas d'image cassée ni d'og:image en 404.
    client, nom = public_avec_photo
    (client.application.config["CV"].DOSSIER_PHOTOS / nom).unlink()
    corps = client.get("/devops").get_data(as_text=True)
    assert "og:image" not in corps and 'class="photo" aria-hidden="true"' in corps


def test_profil_absent_message_dedie(fabrique_app):
    def sans_profil(s):
        s.delete(s.get(Profil, 1))
    admin = fabrique_app(role="admin", modifier=sans_profil).test_client()
    r = _envoyer(admin)
    corps = r.get_data(as_text=True)
    assert r.status_code == 400 and "Enregistrez d" in corps and "pas une photo lisible" not in corps


def test_photo_trop_lourde_reste_sur_le_profil(admin):
    lourde = b"\xff\xd8" + b"\x00" * (17 * 1024 * 1024)
    r = _envoyer(admin, lourde)
    corps = r.get_data(as_text=True)
    assert r.status_code == 413 and "16 Mio" in corps and 'id="photo-fichier"' in corps
