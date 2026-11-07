"""Carte d'aperçu og:image : 1200×630, par version et par langue, en cache."""
import re
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from cv.carte_og import contenu_carte, dessiner_carte
from cv.models import Version
from tests.conftest import EMAIL, TELEPHONE


@pytest.fixture
def client(fabrique_app):
    return fabrique_app().test_client()


def _image(contenu: bytes) -> Image.Image:
    return Image.open(BytesIO(contenu))


@pytest.mark.parametrize("url", ["/devops/carte.png", "/en/devops/carte.png",
                                 "/lead-tech/carte.png"])
def test_carte_servie(client, url):
    r = client.get(url)
    assert r.status_code == 200 and r.mimetype == "image/png"
    image = _image(r.data)
    assert image.format == "PNG" and image.size == (1200, 630)
    assert r.headers["ETag"] and "Set-Cookie" not in r.headers
    assert "max-age=" in r.headers["Cache-Control"]


def test_revalidation(client):
    etag = client.get("/devops/carte.png").headers["ETag"]
    assert client.get("/devops/carte.png", headers={"If-None-Match": etag}).status_code == 304


def test_une_carte_par_langue_et_par_version(client):
    etags = {client.get(u).headers["ETag"] for u in
             ("/devops/carte.png", "/en/devops/carte.png", "/lead-tech/carte.png")}
    assert len(etags) == 3


@pytest.mark.parametrize("url", ["/brouillon/carte.png", "/inconnue/carte.png",
                                 "/a..b/carte.png"])
def test_brouillon_ou_inconnue_404(client, url):
    assert client.get(url).status_code == 404


def test_mise_en_cache_sur_disque(fabrique_app):
    app = fabrique_app()
    client = app.test_client()
    premiere = client.get("/devops/carte.png").data
    dossier = app.config["CV"].DOSSIER_CACHE_CARTES
    fichiers = list(dossier.glob("*.png"))
    assert len(fichiers) == 1 and fichiers[0].read_bytes() == premiere
    assert client.get("/devops/carte.png").data == premiere
    assert len(list(dossier.glob("*.png"))) == 1


def test_contenu_change_la_carte(fabrique_app):
    app = fabrique_app()
    client = app.test_client()
    avant = client.get("/devops/carte.png").headers["ETag"]
    with app.extensions["cv_sessions"]() as s:
        s.scalars(select(Version).where(Version.slug == "devops")).one().titre_fr = "Autre titre"
        s.commit()
    assert client.get("/devops/carte.png").headers["ETag"] != avant


def test_contenu_de_la_carte_sans_coordonnees(fabrique_app):
    from cv.vue import assembler_vue
    app = fabrique_app()
    with app.extensions["cv_sessions"]() as s:
        vue = assembler_vue(s, "devops", "fr")
    contenu = contenu_carte(vue, "cv.nanodeus.com")
    assert contenu["nom"] == vue.nom and contenu["titre"] == vue.titre
    assert contenu["etapes"] and len(contenu["etapes"]) <= 4
    assert contenu["prochaine"] == vue.prochaine_mission
    texte = repr(contenu)
    assert EMAIL not in texte and TELEPHONE not in texte


def test_textes_longs_sans_erreur():
    contenu = {"dessin": "1", "nom": "Prénom " * 30, "titre": "Titre " * 40,
               "accroche": "mot " * 200, "etapes": ["Organisation très longue " * 5] * 4,
               "prochaine": "Prochaine " * 10, "adresse": "cv.nanodeus.com/" + "x" * 80,
               "initiales": "PN"}
    assert _image(dessiner_carte(contenu, None)).size == (1200, 630)
    vide = {**contenu, "titre": "", "accroche": "", "etapes": [], "prochaine": ""}
    assert _image(dessiner_carte(vide, b"pas une image")).size == (1200, 630)


def test_photo_dans_la_carte():
    contenu = {"dessin": "1", "nom": "A B", "titre": "", "accroche": "", "etapes": [],
               "prochaine": "", "adresse": "x", "initiales": "AB"}
    tampon = BytesIO()
    Image.new("RGB", (300, 300), (255, 0, 0)).save(tampon, "JPEG")
    image = _image(dessiner_carte(contenu, tampon.getvalue())).convert("RGB")
    # Centre du portrait (en haut à droite) : le rouge de la photo.
    r, v, b = image.getpixel((1200 - 72 - 86, 72 + 8 + 86))
    assert r > 200 and v < 60 and b < 60


def test_meta_open_graph_et_twitter(client):
    html = client.get("/devops").get_data(as_text=True)
    assert '<meta property="og:image" content="http://localhost/devops/carte.png">' in html
    assert '<meta property="og:image:width" content="1200">' in html
    assert '<meta property="og:image:height" content="630">' in html
    assert '<meta property="og:image:type" content="image/png">' in html
    assert re.search(r'<meta property="og:image:alt" content="[^"]+">', html)
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    en = client.get("/en/devops").get_data(as_text=True)
    assert '<meta property="og:image" content="http://localhost/en/devops/carte.png">' in en


def test_page_par_defaut_pointe_sa_carte(client):
    assert 'content="http://localhost/devops/carte.png"' in client.get("/").get_data(as_text=True)


def test_carte_non_journalisee(fabrique_app):
    from cv.models import Visite
    app = fabrique_app()
    app.test_client().get("/devops/carte.png", headers={"User-Agent": "Mozilla/5.0"})
    with app.extensions["cv_sessions"]() as s:
        assert s.scalars(select(Visite)).first() is None


def test_admin_n_a_pas_de_carte(admin):
    assert admin.get("/devops/carte.png").status_code == 404



