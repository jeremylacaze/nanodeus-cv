"""Langue de la page : portée par l'URL (/en/…), jamais par un cookie."""
import re
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from flask import g, request

LANGUES = ("fr", "en")
_CHEMIN_DE_PAGE = re.compile(r"/[a-z0-9-]{0,40}")


def langue_du_chemin(chemin: str) -> str:
    return "en" if chemin == "/en" or chemin.startswith("/en/") else "fr"


def url_autre_langue(chemin: str) -> str:
    """Même page dans l'autre langue : /devops ↔ /en/devops, / ↔ /en/.

    Seul un chemin de page réelle (/<slug>) est recopié ; tout autre chemin (404)
    renvoie à l'accueil de l'autre langue. Recopier un chemin arbitraire ouvrirait
    la porte à un lien vers un autre site (/en//ailleurs, /en/%09/ailleurs…)."""
    anglais = langue_du_chemin(chemin) == "en"
    reste = (chemin[3:] if anglais else chemin) or "/"
    if not _CHEMIN_DE_PAGE.fullmatch(reste):
        reste = "/"
    return reste if anglais else "/en" + reste


def locale_selector() -> str:
    return g.get("lang", "fr")


def suggerer_anglais(req) -> bool:
    """Page française consultée par un navigateur qui préfère l'anglais."""
    return (langue_du_chemin(req.path) == "fr"
            and req.accept_languages.best_match(list(LANGUES)) == "en")


def compiler_catalogues(dossier: Path, force: bool = False) -> list[Path]:
    """Compile chaque .po en .mo s'il manque ou est plus ancien (les .mo ne sont
    pas versionnés)."""
    compiles = []
    for po in sorted(dossier.glob("*/LC_MESSAGES/messages.po")):
        mo = po.with_suffix(".mo")
        if force or not mo.exists() or mo.stat().st_mtime < po.stat().st_mtime:
            with po.open("rb") as f:
                catalogue = read_po(f)
            with mo.open("wb") as f:
                write_mo(f, catalogue)
            compiles.append(mo)
    return compiles


def init_langue(app):
    @app.before_request
    def _poser_langue():
        g.lang = langue_du_chemin(request.path)

    @app.context_processor
    def _contexte_langue():
        return {"lang": g.get("lang", "fr"),
                "url_autre_langue": url_autre_langue(request.path)}
