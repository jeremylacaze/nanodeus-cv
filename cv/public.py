"""Routes du site public : une URL par version, en français et en anglais."""
import re

from flask import (Blueprint, abort, current_app, g, make_response, redirect,
                   render_template, request)

from cv.journal import journaliser
from cv.langue import suggerer_anglais
from cv.models import SLUG
from cv.vue import assembler_vue

bp = Blueprint("public", __name__)
_SLUG = re.compile(SLUG)


def _page(slug: str | None):
    if slug is not None and not _SLUG.fullmatch(slug):
        abort(404)
    vue = assembler_vue(g.db, slug, g.lang)
    if vue is None:
        abort(404)
    racine = current_app.config["CV"].URL_PUBLIQUE
    reponse = make_response(render_template(
        "cv.html", vue=vue, suggestion_en=suggerer_anglais(request),
        url_canonique=racine + request.path if racine else request.base_url))
    # Le bandeau « View in English » dépend de cet en-tête : un cache doit le savoir.
    reponse.vary.add("Accept-Language")
    if vue.noindex:
        reponse.headers["X-Robots-Tag"] = "noindex"
    journaliser(g.db, request, current_app.config["CV"], "page", vue.slug, g.lang)
    return reponse


@bp.get("/")
@bp.get("/en/")
def accueil():
    return _page(None)


@bp.get("/en")
def en_sans_barre():
    # La query string suit (un QR code imprimé vers /en?src=qr garde sa source).
    requete = request.query_string.decode("latin-1")
    return redirect("/en/" + (f"?{requete}" if requete else ""), 308)


@bp.get("/<slug>")
@bp.get("/en/<slug>")
def version(slug):
    return _page(slug)
