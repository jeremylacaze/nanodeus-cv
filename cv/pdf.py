"""PDF du CV : un template dédié, rendu par WeasyPrint, en cache selon le contenu.

Le PDF public ne porte aucune coordonnée. Le PDF complet (admin seulement) porte le
téléphone et l'email : il n'est jamais écrit sur disque.
"""
import base64
import hashlib
import os
from pathlib import Path

from flask import render_template
from PIL import ImageFile
from weasyprint import HTML, URLFetcher

from cv.medias import ecrire_atomiquement, qr, url_version

# WeasyPrint passe ce réglage global à True dès son import : une photo tronquée serait
# alors acceptée et complétée en gris. Le PDF n'incorpore que des images déjà propres.
ImageFile.LOAD_TRUNCATED_IMAGES = False

CACHE_MAX = 40


def _data_uri(type_mime: str, contenu: bytes) -> str:
    return f"data:{type_mime};base64,{base64.b64encode(contenu).decode('ascii')}"


def html_pdf(vue, config, photo: bytes | None,
             coordonnees: tuple[str, str] | None = None) -> str:
    """Document autonome : photo, QR et feuille de style y sont incorporés, si bien que
    tout changement de contenu change le HTML, donc la clé du cache."""
    lien = url_version(config, vue.slug, vue.lang, "pdf")
    return render_template(
        "pdf.html", vue=vue, lang=vue.lang, coordonnees=coordonnees,
        photo_uri=_data_uri("image/jpeg", photo) if photo else "",
        qr_uri=_data_uri("image/svg+xml", qr(url_version(config, vue.slug, vue.lang, "qr"),
                                             "svg")),
        lien=lien, adresse=url_version(config, vue.slug, vue.lang).split("://", 1)[-1])


def rendre_pdf(html: str) -> bytes:
    """Rien n'est cherché au-dehors : seules les URI data: sont lues. Une ressource
    refusée est signalée par WeasyPrint sans faire échouer le rendu."""
    return HTML(string=html, url_fetcher=URLFetcher(allowed_protocols=("data",))).write_pdf()


def _date(chemin: Path) -> int:
    try:
        return chemin.stat().st_mtime_ns
    except FileNotFoundError:  # supprimé entre-temps par un autre processus
        return 0


def pdf_en_cache(dossier: Path, html: str) -> tuple[bytes, str]:
    """PDF de ce HTML, rendu une seule fois ; renvoie aussi son ETag."""
    etag = hashlib.sha256(html.encode()).hexdigest()[:32]
    chemin = dossier / f"{etag}.pdf"
    try:
        contenu = chemin.read_bytes()
    except FileNotFoundError:
        pass
    else:
        try:
            os.utime(chemin)  # récent : l'élagage le garde
        except FileNotFoundError:
            pass  # élagué entre-temps par l'autre processus : le contenu est déjà lu
        return contenu, etag
    contenu = rendre_pdf(html)
    ecrire_atomiquement(chemin, contenu)
    anciens = sorted(dossier.glob("*.pdf"), key=_date, reverse=True)[CACHE_MAX:]
    for ancien in anciens:
        if ancien != chemin:
            ancien.unlink(missing_ok=True)
    return contenu, etag


def vider_cache(dossier: Path) -> None:
    """Les PDF en cache incorporent la photo : ils partent quand elle change."""
    for fichier in dossier.glob("*.pdf"):
        fichier.unlink(missing_ok=True)
