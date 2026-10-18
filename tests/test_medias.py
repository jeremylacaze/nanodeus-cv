"""Photo du profil (redimensionnée, sans métadonnées) et QR codes."""
import random
import struct
import zlib
from io import BytesIO

import pytest
from PIL import Image, ImageCms

from cv import medias
from cv.config import Config
from cv.medias import (NOM_PHOTO, PhotoInvalide, enregistrer_photo, qr, traiter_photo,
                       url_version)


def _image(format="JPEG", taille=(400, 200), **options) -> bytes:
    """Moitié gauche rouge, moitié droite bleue."""
    img = Image.new("RGB", taille, (255, 0, 0))
    img.paste((0, 0, 255), (taille[0] // 2, 0, taille[0], taille[1]))
    tampon = BytesIO()
    img.save(tampon, format, **options)
    return tampon.getvalue()


def _rouge(pixel) -> bool:
    return pixel[0] > 200 and pixel[2] < 60


def _bleu(pixel) -> bool:
    return pixel[2] > 200 and pixel[0] < 60


def _bombe() -> bytes:
    """PNG minuscule dont l'en-tête annonce 20 000 × 20 000 pixels."""
    png = bytearray(_image("PNG", (8, 8)))
    debut = 8 + 8  # signature, puis longueur et type du bloc IHDR
    png[debut:debut + 8] = struct.pack(">II", 20_000, 20_000)
    crc = zlib.crc32(bytes(png[12:debut + 13]))
    png[debut + 13:debut + 17] = struct.pack(">I", crc)
    return bytes(png)


def _tronque() -> bytes:
    """JPEG coupé en plein flux d'image : l'en-tête se lit, le décodage échoue."""
    bruit = random.Random(0).randbytes(600 * 600 * 3)
    tampon = BytesIO()
    Image.frombytes("RGB", (600, 600), bruit).save(tampon, "JPEG", quality=90)
    return tampon.getvalue()[: len(tampon.getvalue()) * 6 // 10]


def _profil_icc_permute() -> bytes:
    """Profil ICC v2 minimal (matrice + courbes identité) dont les primaires rouge et
    verte sont échangées : un pixel (255, 0, 0) y désigne du vert."""
    def s15(x):
        return struct.pack(">i", round(x * 65536))

    def xyz(x, y, z):
        return b"XYZ " + b"\0" * 4 + s15(x) + s15(y) + s15(z)

    courbe = b"curv" + b"\0" * 4 + struct.pack(">I", 0)  # identité
    vert, rouge, bleu = (0.3851, 0.7169, 0.0971), (0.4361, 0.2225, 0.0139), (0.1431, 0.0606, 0.7141)
    tags = [(b"wtpt", xyz(0.9642, 1.0, 0.8249)), (b"rXYZ", xyz(*vert)), (b"gXYZ", xyz(*rouge)),
            (b"bXYZ", xyz(*bleu)), (b"rTRC", courbe), (b"gTRC", courbe), (b"bTRC", courbe)]
    decalage = 128 + 4 + 12 * len(tags)
    table, donnees = b"", b""
    for sig, contenu in tags:
        contenu += b"\0" * (-len(contenu) % 4)
        table += sig + struct.pack(">II", decalage + len(donnees), len(contenu))
        donnees += contenu
    corps = struct.pack(">I", len(tags)) + table + donnees
    entete = (struct.pack(">I", 128 + len(corps)) + b"\0" * 4 + bytes([2, 0x10, 0, 0])
              + b"mntrRGB XYZ " + b"\0" * 12 + b"acsp" + b"\0" * 28
              + s15(0.9642) + s15(1.0) + s15(0.8249) + b"\0" * 48)
    assert len(entete) == 128
    return entete + corps


def test_photo_carree_jpeg_sans_metadonnees():
    exif = Image.Exif()
    exif[0x0110] = "Appareil"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (43.0, 36.0, 0.0)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = _image(exif=exif.tobytes(), icc_profile=icc)
    assert b"Appareil" in source and "icc_profile" in Image.open(BytesIO(source)).info
    sortie = traiter_photo(source)
    img = Image.open(BytesIO(sortie))
    assert img.format == "JPEG" and img.size == (512, 512)
    assert len(img.getexif()) == 0 and "icc_profile" not in img.info
    assert b"Exif" not in sortie and b"Appareil" not in sortie


def test_jpeg_mpo_de_telephone_accepte():
    # Les JPEG HDR des téléphones récents portent une seconde image (MPF) : Pillow les
    # ouvre en « MPO ». Seule la première image est gardée.
    principale = Image.open(BytesIO(_image()))
    tampon = BytesIO()
    principale.save(tampon, "MPO", save_all=True, append_images=[Image.new("RGB", (40, 20))])
    assert Image.open(BytesIO(tampon.getvalue())).format == "MPO"
    img = Image.open(BytesIO(traiter_photo(tampon.getvalue())))
    assert img.format == "JPEG" and img.size == (512, 512) and not getattr(img, "is_animated", False)
    assert _rouge(img.getpixel((40, 256))) and _bleu(img.getpixel((470, 256)))


def test_orientation_appliquee():
    exif = Image.Exif()
    exif[0x0112] = 6  # à tourner de 90° dans le sens horaire pour l'afficher
    img = Image.open(BytesIO(traiter_photo(_image(exif=exif.tobytes()))))
    assert _rouge(img.getpixel((256, 40))) and _bleu(img.getpixel((256, 470)))


def test_png_transparent_sur_fond_blanc():
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    tampon = BytesIO()
    img.save(tampon, "PNG")
    pixel = Image.open(BytesIO(traiter_photo(tampon.getvalue()))).getpixel((10, 10))
    assert min(pixel) >= 250


@pytest.mark.parametrize("donnees", [b"pas une image", _image()[:200], _tronque(), _image("GIF")],
                         ids=["texte", "en-tete-coupe", "flux-coupe", "gif"])
def test_photo_invalide(donnees):
    with pytest.raises(PhotoInvalide):
        traiter_photo(donnees)


def test_bombe_de_decompression():
    with pytest.raises(PhotoInvalide):
        traiter_photo(_bombe())


def test_nom_derive_du_contenu(tmp_path):
    nom = enregistrer_photo(tmp_path / "photos", b"x")
    assert NOM_PHOTO.fullmatch(nom) and (tmp_path / "photos" / nom).read_bytes() == b"x"
    assert enregistrer_photo(tmp_path / "photos", b"x") == nom
    assert [f.name for f in (tmp_path / "photos").iterdir()] == [nom]


def test_url_version(monkeypatch):
    monkeypatch.delenv("CV_URL_PUBLIQUE", raising=False)
    assert url_version(Config(), "devops", "fr", "qr") == "https://cv.nanodeus.com/devops?src=qr"
    monkeypatch.setenv("CV_URL_PUBLIQUE", "https://exemple.test")
    assert url_version(Config(), "lead-tech", "en") == "https://exemple.test/en/lead-tech"


def test_qr_svg_et_png():
    svg = qr("https://cv.nanodeus.com/devops?src=qr", "svg")
    assert svg.lstrip().startswith(b"<?xml") and b"<svg" in svg and b"<script" not in svg
    # Fond blanc dans le fichier : transparent, il disparaîtrait sur un fond sombre.
    assert b'fill="#fff"' in svg
    assert qr("https://cv.nanodeus.com/devops?src=qr", "png").startswith(b"\x89PNG")


def test_profil_icc_converti_en_srgb():
    # Une photo en Display P3 réinterprétée en sRGB sortirait terne : les couleurs sont
    # converties, puis le profil disparaît avec les autres métadonnées.
    source = _image(quality=95, icc_profile=_profil_icc_permute())
    sortie = traiter_photo(source)
    img = Image.open(BytesIO(sortie))
    gauche = img.getpixel((40, 256))   # rouge dans le fichier, vert une fois interprété
    assert gauche[1] > 150 and gauche[0] < 100, gauche
    assert "icc_profile" not in img.info


def test_ecriture_interrompue_sans_fichier_temporaire(tmp_path, monkeypatch):
    def echec(*args):
        raise OSError("disque plein")
    monkeypatch.setattr(medias.os, "replace", echec)
    with pytest.raises(OSError):
        enregistrer_photo(tmp_path, b"x")
    assert list(tmp_path.iterdir()) == []
