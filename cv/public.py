"""Routes du site public : une URL par version, en français et en anglais."""
import re

from flask import Blueprint, abort, g, make_response, redirect, render_template, request

from cv.langue import suggerer_anglais
from cv.vue import assembler_vue

bp = Blueprint("public", __name__)
_SLUG = re.compile(r"[a-z0-9-]{1,40}")


def _page(slug: str | None):
    if slug is not None and not _SLUG.fullmatch(slug):
        abort(404)
    vue = assembler_vue(g.db, slug, g.lang)
    if vue is None:
        abort(404)
    reponse = make_response(render_template(
        "cv.html", vue=vue, suggestion_en=suggerer_anglais(request)))
    if vue.noindex:
        reponse.headers["X-Robots-Tag"] = "noindex"
    return reponse


@bp.get("/")
@bp.get("/en/")
def accueil():
    return _page(None)


@bp.get("/en")
def en_sans_barre():
    return redirect("/en/", 308)


@bp.get("/<slug>")
@bp.get("/en/<slug>")
def version(slug):
    return _page(slug)
