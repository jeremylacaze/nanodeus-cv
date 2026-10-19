"""Routes du site public : une URL par version, en français et en anglais."""
import re

from flask import (Blueprint, abort, current_app, g, jsonify, make_response, redirect,
                   render_template, request)

from cv.app import veut_json
from flask_babel import gettext as _
from sqlalchemy import select

from cv.contact import Formulaire, enregistrer, envoyer_demande, limite_atteinte, valider
from cv.journal import empreinte, journaliser, maintenant_utc
from cv.langue import suggerer_anglais
from cv.medias import lire_photo, servir_photo
from cv.models import SLUG, Version
from cv.pdf import html_pdf, pdf_en_cache
from cv.vue import assembler_vue, champ, version_publique

bp = Blueprint("public", __name__)
_SLUG = re.compile(SLUG)


def _racine() -> str:
    return current_app.config["CV"].URL_PUBLIQUE or request.host_url.rstrip("/")


def _page(slug: str | None):
    if slug is not None and not _SLUG.fullmatch(slug):
        abort(404)
    vue = assembler_vue(g.db, slug, g.lang, config=current_app.config["CV"])
    if vue is None:
        abort(404)
    racine = _racine()
    reponse = make_response(render_template(
        "cv.html", vue=vue, suggestion_en=suggerer_anglais(request),
        url_canonique=racine + request.path,
        url_pdf=f"{'/en' if g.lang == 'en' else ''}/{vue.slug}.pdf",
        url_og_image=racine + vue.photo_url if vue.photo_url else ""))
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


@bp.get("/robots.txt")
def robots():
    reponse = make_response(f"User-agent: *\nDisallow:\n\nSitemap: {_racine()}/sitemap.xml\n")
    reponse.mimetype = "text/plain"
    return reponse


@bp.get("/sitemap.xml")
def sitemap():
    """Pages à indexer : / et chaque version publiée, sauf celle par défaut (servie
    sur /). Une version non listée porte noindex : elle n'a rien à faire ici."""
    slugs = g.db.scalars(select(Version.slug).where(
        Version.statut == "publiee", Version.par_defaut.is_(False)).order_by(Version.slug))
    reponse = make_response(render_template(
        "sitemap.xml", racine=_racine(), chemins=["/", *(f"/{slug}" for slug in slugs)]))
    reponse.mimetype = "application/xml"
    return reponse


@bp.get("/<slug>.pdf")
@bp.get("/en/<slug>.pdf")
def version_pdf(slug):
    if not _SLUG.fullmatch(slug):
        abort(404)
    vue = assembler_vue(g.db, slug, g.lang)
    if vue is None:
        abort(404)
    config = current_app.config["CV"]
    contenu, etag = pdf_en_cache(config.DOSSIER_CACHE_PDF,
                                 html_pdf(vue, config, lire_photo(g.db, config)))
    reponse = make_response(contenu)
    reponse.mimetype = "application/pdf"
    reponse.set_etag(etag)
    reponse.headers["Content-Disposition"] = f'inline; filename="cv-{vue.slug}-{g.lang}.pdf"'
    # Toujours revalidé : l'ETag suit le contenu, un PDF périmé n'est jamais resservi.
    reponse.headers["Cache-Control"] = "no-cache"
    if vue.noindex:
        reponse.headers["X-Robots-Tag"] = "noindex"
    journaliser(g.db, request, config, "pdf", vue.slug, g.lang)
    return reponse.make_conditional(request)


@bp.get("/photo/<nom>")
def photo(nom):
    return servir_photo(g.db, current_app.config["CV"], nom)


@bp.get("/en")
def en_sans_barre():
    # La query string suit (un QR code imprimé vers /en?src=qr garde sa source).
    requete = request.query_string.decode("latin-1")
    return redirect("/en/" + (f"?{requete}" if requete else ""), 308)


@bp.get("/<slug>")
@bp.get("/en/<slug>")
def version(slug):
    return _page(slug)


def _version_ou_404(slug: str) -> Version:
    version = version_publique(g.db, slug) if _SLUG.fullmatch(slug) else None
    if version is None:
        abort(404)
    return version


def _prefixe() -> str:
    return "/en" if g.lang == "en" else ""


def _reponse_contact(version: Version, statut: int, ok: bool, message: str = "",
                     erreurs: dict | None = None, formulaire: Formulaire | None = None):
    """JSON pour la modale, page HTML sans JavaScript. Sans `formulaire`, la page
    est une confirmation : rien à renvoyer, donc pas de doublon possible."""
    erreurs = erreurs or {}
    if veut_json():
        reponse = jsonify(ok=ok, message=message, erreurs=erreurs)
    else:
        reponse = make_response(render_template(
            "contact.html", titre_version=champ(version, "titre", g.lang),
            retour=f"{_prefixe()}/{version.slug}", action=f"{_prefixe()}/{version.slug}/contact",
            valeurs=formulaire, erreurs=erreurs, message=message))
    reponse.status_code = statut
    reponse.vary.add("Accept")  # JSON ou HTML selon cet en-tête : un cache doit le savoir
    reponse.headers["X-Robots-Tag"] = "noindex"
    return reponse


@bp.get("/<slug>/contact")
@bp.get("/en/<slug>/contact")
def contact(slug):
    version = _version_ou_404(slug)
    journaliser(g.db, request, current_app.config["CV"], "contact", version.slug, g.lang)
    return _reponse_contact(version, 200, True, formulaire=Formulaire())


@bp.post("/<slug>/contact/ouverture")
@bp.post("/en/<slug>/contact/ouverture")
def ouverture_contact(slug):
    """Balise de la modale (sendBeacon) : l'ouverture compte comme une visite du contact."""
    version = _version_ou_404(slug)
    journaliser(g.db, request, current_app.config["CV"], "contact", version.slug, g.lang)
    return "", 204


@bp.post("/<slug>/contact")
@bp.post("/en/<slug>/contact")
def envoyer_contact(slug):
    version = _version_ou_404(slug)
    merci = _("Merci ! Jeremy vous répondra à l'adresse indiquée.")
    formulaire, erreurs = valider(request.form)
    if formulaire.piege:
        # Un robot a rempli le champ invisible : il croit avoir réussi, rien ne part.
        return _reponse_contact(version, 200, True, merci)
    if erreurs:
        return _reponse_contact(version, 400, False, _("Vérifiez les champs signalés."),
                                erreurs, formulaire)
    config, maintenant = current_app.config["CV"], maintenant_utc()
    # IP seule (le User-Agent se change trop facilement) ; elle n'est ni stockée ni loguée.
    cle = empreinte(g.db, config.SEL_HMAC, request.remote_addr or "", maintenant=maintenant)
    if limite_atteinte(g.db, cle, maintenant):
        return _reponse_contact(version, 429, False,
                                _("Trop de demandes pour le moment. Réessayez plus tard."),
                                formulaire=formulaire)
    demande = enregistrer(g.db, formulaire, version.slug, g.lang, cle, maintenant)
    if envoyer_demande(g.db, demande, config, current_app.extensions["cv_envoi"]):
        return _reponse_contact(version, 200, True, merci)
    return _reponse_contact(version, 202, False, _(
        "L'envoi n'a pas abouti, mais votre demande est bien enregistrée : Jeremy la verra."))
