"""PDF du CV : un template dédié, rendu par WeasyPrint, en cache selon le contenu.

Le PDF public ne porte aucune coordonnée. Le PDF complet (admin seulement) porte le
téléphone et l'email : il n'est jamais écrit sur disque.
"""
import base64
import hashlib
import os
import re
import unicodedata
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


def nom_fichier(vue, complet: bool = False) -> str:
    """cv-<prénom-nom>-<slug>-<lang>[-complet].pdf, en ASCII : l'en-tête
    Content-Disposition n'admet pas d'accents sans encodage."""
    ascii_ = unicodedata.normalize("NFKD", vue.nom).encode("ascii", "ignore").decode()
    nom = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")
    morceaux = ["cv", nom, vue.slug, vue.lang] + (["complet"] if complet else [])
    return "-".join(m for m in morceaux if m) + ".pdf"


def rendu_pdf(html: str) -> tuple[bytes, int]:
    """PDF et nombre de pages. Rien n'est cherché au-dehors : seules les URI data: sont
    lues. Une ressource refusée est signalée par WeasyPrint sans faire échouer le rendu."""
    document = HTML(string=html,
                    url_fetcher=URLFetcher(allowed_protocols=("data",))).render()
    return document.write_pdf(), len(document.pages)


def rendre_pdf(html: str) -> bytes:
    return rendu_pdf(html)[0]


def _date(chemin: Path) -> int:
    try:
        return chemin.stat().st_mtime_ns
    except FileNotFoundError:  # supprimé entre-temps par un autre processus
        return 0


def pdf_en_cache(dossier: Path, html: str) -> tuple[bytes, str, int]:
    """PDF de ce HTML, rendu une seule fois ; renvoie aussi son ETag et son nombre de
    pages, gardé dans le nom du fichier : <etag>-<pages>.pdf."""
    etag = hashlib.sha256(html.encode()).hexdigest()[:32]
    for chemin in dossier.glob(f"{etag}-*.pdf"):
        try:
            contenu = chemin.read_bytes()
        except FileNotFoundError:  # élagué entre-temps par l'autre processus
            break
        try:
            os.utime(chemin)  # récent : l'élagage le garde
        except FileNotFoundError:
            pass  # élagué entre-temps par l'autre processus : le contenu est déjà lu
        return contenu, etag, int(chemin.stem.rsplit("-", 1)[1])
    contenu, pages = rendu_pdf(html)
    chemin = dossier / f"{etag}-{pages}.pdf"
    ecrire_atomiquement(chemin, contenu)
    anciens = sorted(dossier.glob("*.pdf"), key=_date, reverse=True)[CACHE_MAX:]
    for ancien in anciens:
        if ancien != chemin:
            ancien.unlink(missing_ok=True)
    return contenu, etag, pages


def vider_cache(dossier: Path) -> None:
    """Les PDF en cache incorporent la photo : ils partent quand elle change."""
    for fichier in dossier.glob("*.pdf"):
        fichier.unlink(missing_ok=True)
