"""Médias du CV : photo du profil et QR codes des versions.

La photo envoyée depuis l'admin est réencodée : seuls ses pixels survivent. Une photo
de téléphone porte souvent la position GPS du lieu de la prise de vue.
"""
import hashlib
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path

from flask import abort, send_file
import segno
from PIL import Image, ImageOps

from cv.models import Profil

TAILLE_PHOTO = 512
PIXELS_MAX = 40_000_000
FORMATS_PHOTO = ("JPEG", "PNG", "WEBP")
# Nom tiré du contenu : une nouvelle photo change d'URL, le cache peut être éternel.
NOM_PHOTO = re.compile(r"[0-9a-f]{16}\.jpg")

FORMATS_QR = {"svg": "image/svg+xml", "png": "image/png"}

# Au-delà, Pillow lève DecompressionBombError au lieu d'un simple avertissement.
Image.MAX_IMAGE_PIXELS = PIXELS_MAX


class PhotoInvalide(ValueError):
    """Fichier illisible, d'un format refusé ou trop grand."""


def traiter_photo(donnees: bytes) -> bytes:
    """JPEG carré de TAILLE_PHOTO pixels, sans aucune métadonnée."""
    try:
        img = Image.open(BytesIO(donnees))
        # Image.open ne lit que l'en-tête : la taille se contrôle avant tout décodage.
        if img.format not in FORMATS_PHOTO or img.width * img.height > PIXELS_MAX:
            raise PhotoInvalide
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            fond = Image.new("RGB", img.size, (255, 255, 255))
            rgba = img.convert("RGBA")
            fond.paste(rgba, mask=rgba.getchannel("A"))
            img = fond
        img = ImageOps.fit(img.convert("RGB"), (TAILLE_PHOTO, TAILLE_PHOTO),
                           Image.Resampling.LANCZOS)
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise PhotoInvalide from exc
    # Image neuve, `info` vide : Pillow reprendrait sinon le profil ICC de l'original.
    propre = Image.new("RGB", img.size)
    propre.paste(img)
    sortie = BytesIO()
    propre.save(sortie, "JPEG", quality=85, optimize=True)
    return sortie.getvalue()


def enregistrer_photo(dossier: Path, donnees: bytes) -> str:
    """Écrit la photo (atomiquement) et renvoie son nom."""
    nom = hashlib.sha256(donnees).hexdigest()[:16] + ".jpg"
    dossier.mkdir(parents=True, exist_ok=True)
    descripteur, temporaire = tempfile.mkstemp(dir=dossier, suffix=".tmp")
    with os.fdopen(descripteur, "wb") as f:
        f.write(donnees)
    os.replace(temporaire, dossier / nom)
    return nom


def chemin_photo(config, nom: str | None) -> Path | None:
    """Fichier de la photo nommée, s'il existe et si son nom est bien formé."""
    if not nom or not NOM_PHOTO.fullmatch(nom):
        return None
    chemin = config.DOSSIER_PHOTOS / nom
    return chemin if chemin.is_file() else None


def lire_photo(session, config) -> bytes | None:
    """Contenu de la photo du profil, pour l'incorporer au PDF."""
    profil = session.get(Profil, 1)
    chemin = chemin_photo(config, profil.photo_fichier if profil else None)
    return chemin.read_bytes() if chemin else None


def effacer_photo(config, nom: str | None) -> None:
    chemin = chemin_photo(config, nom)
    if chemin is not None:
        chemin.unlink(missing_ok=True)


def servir_photo(session, config, nom: str):
    """La photo courante du profil, et aucun autre fichier. Rien n'est journalisé."""
    profil = session.get(Profil, 1)
    chemin = chemin_photo(config, nom)
    if chemin is None or profil is None or profil.photo_fichier != nom:
        abort(404)
    reponse = send_file(chemin, mimetype="image/jpeg", max_age=31536000)
    reponse.cache_control.immutable = True
    return reponse


def url_version(config, slug: str, lang: str, src: str | None = None) -> str:
    """Adresse publique d'une version, `?src=` en option (visites venues du papier)."""
    prefixe = "/en" if lang == "en" else ""
    return f"{config.URL_SITE}{prefixe}/{slug}" + (f"?src={src}" if src else "")


def qr(url: str, format: str) -> bytes:
    """QR code de `url`, en SVG ou en PNG (format dans FORMATS_QR)."""
    sortie = BytesIO()
    segno.make(url, error="m").save(sortie, kind=format, scale=8 if format == "svg" else 12,
                                    border=4, light="#fff")
    return sortie.getvalue()
