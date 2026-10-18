"""Photo du profil (redimensionnée, sans métadonnées) et QR codes."""
import struct
import zlib
from io import BytesIO

import pytest
from PIL import Image, ImageCms

from cv.medias import NOM_PHOTO, PhotoInvalide, enregistrer_photo, traiter_photo


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


@pytest.mark.parametrize("donnees", [b"pas une image", _image()[:200], _image("GIF")],
                         ids=["texte", "tronque", "gif"])
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
