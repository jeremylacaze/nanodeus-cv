"""Admin : édition du profil, du stock et des versions."""
import flask_babel
from flask import abort, current_app, g, make_response, redirect, render_template, request
from sqlalchemy import select
from werkzeug.exceptions import RequestEntityTooLarge

from cv.admin import bp
from cv.admin.formulaires import MAX_TEXTE, Champ, appliquer, lire, valeurs_de
from cv.admin.stock import PAR_ELEMENT, TYPES, supprimer_element
from cv.admin.versions import (CHAMPS_VERSION, composer, definir_par_defaut,
                               elements_du_stock, supprimer_version, verifier_version)
from cv.medias import (FORMATS_QR, PhotoInvalide, effacer_photo, enregistrer_photo,
                       lire_photo, qr, servir_photo, traiter_photo, url_version)
from cv.models import Profil, Version
from cv.pdf import html_pdf, nom_fichier, pdf_en_cache, rendre_pdf, vider_cache
from cv.vue import assembler_vue

ERREUR_PHOTO = ("Ce fichier n'est pas une photo lisible (JPEG, PNG ou WEBP, "
                "40 mégapixels au plus).")
ERREUR_PHOTO_LOURDE = "Cette photo dépasse 16 Mio : envoyez une version plus légère."
ERREUR_SANS_PROFIL = "Enregistrez d'abord le profil, puis ajoutez la photo."
PRIVE = "Privé : sert seulement au PDF complet, jamais au site public."

CHAMPS_PROFIL = (
    Champ("nom_complet", "Nom complet", max=120, requis=True),
    Champ("localisation", "Localisation", max=120),
    Champ("date_naissance", "Date de naissance", type="date"),
    Champ("afficher_age", "Afficher l'âge", type="case"),
    Champ("permis", "Permis", max=60),
    Champ("ouvert_opportunites", "Ouvert aux opportunités", type="case"),
    Champ("interets_fr", "Centres d'intérêt (FR)", type="texte", max=MAX_TEXTE,
          aide="Un par ligne."),
    Champ("interets_en", "Centres d'intérêt (EN)", type="texte", max=MAX_TEXTE,
          aide="Un par ligne ; vide = repli sur le français."),
    Champ("linkedin_url", "LinkedIn", type="url", max=300),
    Champ("github_url", "GitHub", type="url", max=300),
    Champ("telephone", "Téléphone", max=40, aide=PRIVE),
    Champ("email", "Email", max=200, aide=PRIVE),
)


# Plus grand entier de SQLite (signé sur 64 bits) : au-delà, la requête lèverait.
ID_MAX = 2**63 - 1


def trouver(modele, id_: int):
    """Ligne désignée par l'URL, ou 404 (y compris pour un id que SQLite ne lit pas)."""
    if id_ > ID_MAX:
        abort(404)
    return g.db.get(modele, id_) or abort(404)


def ok(chemin: str, code: str = "enregistre"):
    """Redirection après écriture : le message est choisi par son code (MESSAGES)."""
    separateur = "&" if "?" in chemin else "?"
    ancre = ""
    if "#" in chemin:
        chemin, ancre = chemin.split("#", 1)
        ancre = "#" + ancre
    return redirect(f"{chemin}{separateur}ok={code}{ancre}", 303)


@bp.route("/profil", methods=["GET", "POST"])
def profil():
    actuel = g.db.get(Profil, 1)
    if request.method == "POST":
        valeurs, erreurs = lire(request.form, CHAMPS_PROFIL)
        if not erreurs:
            if actuel is None:
                actuel = Profil(id=1)
                g.db.add(actuel)
            appliquer(actuel, valeurs)
            g.db.commit()
            return ok("/admin/profil")
        return _page_profil(actuel, request.form.to_dict(), erreurs, statut=400)
    return _page_profil(actuel, valeurs_de(actuel, CHAMPS_PROFIL), {})


def _page_profil(actuel: Profil | None, valeurs: dict, erreurs: dict,
                 erreur_photo: str = "", statut: int = 200):
    return render_template("admin/profil.html", liste=CHAMPS_PROFIL, valeurs=valeurs,
                           erreurs=erreurs, photo=actuel.photo_fichier if actuel else None,
                           erreur_photo=erreur_photo), statut


@bp.post("/profil/photo")
def profil_photo():
    actuel = g.db.get(Profil, 1)

    def refus(message, statut):
        return _page_profil(actuel, valeurs_de(actuel, CHAMPS_PROFIL), {}, message, statut)

    if actuel is None:
        return refus(ERREUR_SANS_PROFIL, 400)
    try:
        fichier = request.files.get("photo")
    except RequestEntityTooLarge:
        return refus(ERREUR_PHOTO_LOURDE, 413)
    try:
        if fichier is None:
            raise PhotoInvalide
        donnees = traiter_photo(fichier.read())
    except PhotoInvalide:
        return refus(ERREUR_PHOTO, 400)
    config = current_app.config["CV"]
    nom = enregistrer_photo(config.DOSSIER_PHOTOS, donnees)
    ancien, actuel.photo_fichier = actuel.photo_fichier, nom
    g.db.commit()
    if ancien != nom:
        effacer_photo(config, ancien)
        vider_cache(config.DOSSIER_CACHE_PDF)
    return ok("/admin/profil", "photo-enregistree")


@bp.post("/profil/photo/supprimer")
def profil_photo_supprimer():
    actuel = g.db.get(Profil, 1)
    if actuel is not None and actuel.photo_fichier:
        ancien, actuel.photo_fichier = actuel.photo_fichier, None
        g.db.commit()
        effacer_photo(current_app.config["CV"], ancien)
        vider_cache(current_app.config["CV"].DOSSIER_CACHE_PDF)
    return ok("/admin/profil", "photo-supprimee")


@bp.get("/photo/<nom>")
def photo(nom):
    return servir_photo(g.db, current_app.config["CV"], nom)


def _type_stock(cle: str):
    return TYPES.get(cle) or abort(404)


def _element(type_stock, id_: int):
    return trouver(type_stock.modele, id_)


@bp.get("/stock/<cle>")
def stock_liste(cle):
    t = _type_stock(cle)
    elements = g.db.scalars(select(t.modele).order_by(*t.tri)).all()
    return render_template("admin/stock_liste.html", t=t, elements=elements)


def _editer(t, obj):
    """Création (obj None) ou modification d'un élément du stock."""
    if request.method == "POST":
        valeurs, erreurs = lire(request.form, t.champs)
        if not erreurs and t.verifier:
            erreurs = t.verifier(valeurs)
        if not erreurs:
            if obj is None:
                obj = t.modele()
                g.db.add(obj)
            appliquer(obj, valeurs)
            g.db.commit()
            return ok(f"/admin/stock/{t.cle}")
        return render_template("admin/stock_element.html", t=t, obj=obj,
                               valeurs=request.form.to_dict(), erreurs=erreurs), 400
    return render_template("admin/stock_element.html", t=t, obj=obj,
                           valeurs=valeurs_de(obj, t.champs) if obj else {}, erreurs={})


@bp.route("/stock/<cle>/nouveau", methods=["GET", "POST"])
def stock_nouveau(cle):
    return _editer(_type_stock(cle), None)


@bp.route("/stock/<cle>/<int:id_>", methods=["GET", "POST"])
def stock_element(cle, id_):
    t = _type_stock(cle)
    return _editer(t, _element(t, id_))


@bp.post("/stock/<cle>/<int:id_>/supprimer")
def stock_supprimer(cle, id_):
    t = _type_stock(cle)
    supprimer_element(g.db, t, _element(t, id_))
    return ok(f"/admin/stock/{t.cle}", "supprime")


def _version(id_: int) -> Version:
    return trouver(Version, id_)


@bp.get("/versions")
def versions():
    liste = g.db.scalars(select(Version).order_by(Version.par_defaut.desc(), Version.slug)).all()
    return render_template("admin/versions.html", versions=liste)


def _page_version(version: Version | None, valeurs: dict, erreurs: dict,
                  composition: dict | None = None, erreurs_composition: dict | None = None,
                  statut: int = 200):
    """Page d'une version. `composition` : valeurs soumises à réafficher après une erreur."""
    lignes = elements_du_stock(g.db, version) if version else {}
    config = current_app.config["CV"]
    urls_qr = {lang: url_version(config, version.slug, lang, "qr")
               for lang in ("fr", "en")} if version else {}
    return render_template(
        "admin/version.html", version=version, champs_version=CHAMPS_VERSION, urls_qr=urls_qr,
        valeurs=valeurs, erreurs=erreurs, lignes=lignes, composition=composition,
        erreurs_composition=erreurs_composition or {}, titres={
            te: t.titre for te, t in PAR_ELEMENT.items()}), statut


def _editer_version(version: Version | None):
    if request.method == "POST":
        valeurs, erreurs = lire(request.form, CHAMPS_VERSION)
        if not erreurs:
            erreurs = verifier_version(g.db, valeurs, version)
        if not erreurs:
            if version is None:
                version = Version()
                g.db.add(version)
            appliquer(version, valeurs)
            g.db.commit()
            return ok(f"/admin/versions/{version.id}")
        return _page_version(version, request.form.to_dict(), erreurs, statut=400)
    valeurs = valeurs_de(version, CHAMPS_VERSION) if version else {"statut": "brouillon"}
    return _page_version(version, valeurs, {})


@bp.route("/versions/nouvelle", methods=["GET", "POST"])
def version_nouvelle():
    return _editer_version(None)


@bp.route("/versions/<int:id_>", methods=["GET", "POST"])
def version(id_):
    return _editer_version(_version(id_))


@bp.post("/versions/<int:id_>/composition")
def version_composition(id_):
    version = _version(id_)
    erreurs = composer(g.db, version, request.form)
    if not erreurs:
        return ok(f"/admin/versions/{version.id}#composition")
    return _page_version(version, valeurs_de(version, CHAMPS_VERSION), {},
                         request.form.to_dict(), erreurs, 400)


@bp.post("/versions/<int:id_>/par-defaut")
def version_par_defaut(id_):
    fait = definir_par_defaut(g.db, _version(id_))
    return ok("/admin/versions", "par-defaut" if fait else "defaut-brouillon")


@bp.post("/versions/<int:id_>/supprimer")
def version_supprimer(id_):
    fait = supprimer_version(g.db, _version(id_))
    return ok("/admin/versions", "supprime" if fait else "defaut-protege")


@bp.get("/versions/<int:id_>/qr.<fmt>")
def version_qr(id_, fmt):
    """QR code vers l'adresse publique, brouillon compris : on prépare l'impression."""
    if fmt not in FORMATS_QR:
        abort(404)
    version = _version(id_)
    lang = "en" if request.args.get("lang") == "en" else "fr"
    reponse = make_response(qr(url_version(current_app.config["CV"], version.slug, lang, "qr"),
                               fmt))
    reponse.mimetype = FORMATS_QR[fmt]
    if request.args.get("telecharger") == "1":
        nom = f"qr-{version.slug}{'-en' if lang == 'en' else ''}.{fmt}"
        reponse.headers["Content-Disposition"] = f'attachment; filename="{nom}"'
    return reponse


def _langue_demandee() -> str:
    g.lang = "en" if request.args.get("lang") == "en" else "fr"
    flask_babel.refresh()  # la langue de Babel suit g.lang
    return g.lang


@bp.get("/versions/<int:id_>/cv.pdf")
def version_pdf(id_):
    """PDF public (brouillon compris), ou complet avec téléphone et email : celui-ci
    n'est jamais écrit sur disque."""
    version = _version(id_)
    lang = _langue_demandee()
    vue = assembler_vue(g.db, version.slug, lang, apercu=True)
    config = current_app.config["CV"]
    photo = lire_photo(g.db, config)
    complet = request.args.get("complet") == "1"
    if complet:
        profil = g.db.get(Profil, 1) or Profil()
        contenu = rendre_pdf(html_pdf(vue, config, photo,
                                      (profil.telephone or "", profil.email or "")))
    else:
        contenu = pdf_en_cache(config.DOSSIER_CACHE_PDF, html_pdf(vue, config, photo))[0]
    reponse = make_response(contenu)
    reponse.mimetype = "application/pdf"
    reponse.headers["Content-Disposition"] = f'attachment; filename="{nom_fichier(vue, complet)}"'
    return reponse


@bp.get("/versions/<int:id_>/apercu")
def version_apercu(id_):
    """La page publique telle qu'elle sera, brouillon compris. Rien n'est journalisé."""
    version = _version(id_)
    _langue_demandee()
    vue = assembler_vue(g.db, version.slug, g.lang, apercu=True, prefixe_medias="/admin",
                        config=current_app.config["CV"])
    autre = "fr" if g.lang == "en" else "en"
    return render_template("cv.html", vue=vue, apercu=True, suggestion_en=False,
                           brouillon=version.statut == "brouillon",
                           url_canonique="",
                           url_pdf=f"/admin/versions/{version.id}/cv.pdf?lang={g.lang}",
                           url_autre_langue=f"/admin/versions/{version.id}/apercu?lang={autre}")
