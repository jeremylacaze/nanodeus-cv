"""Admin : candidatures, leur lien ?src=, leur QR code et leur activité."""
from flask import abort, current_app, g, make_response, render_template, request
from sqlalchemy import select

from cv.admin import bp
from cv.admin.candidatures import activite, champs, phrase_activite, resumes, verifier
from cv.admin.formulaires import appliquer, lire, valeurs_de
from cv.admin.vues_contenu import ok, trouver
from cv.journal import maintenant_utc
from cv.medias import FORMATS_QR, qr, url_version
from cv.models import Candidature


def _lien(c: Candidature) -> str:
    return url_version(current_app.config["CV"], c.version_slug, c.langue, c.source)


@bp.get("/candidatures")
def candidatures():
    liste = g.db.scalars(select(Candidature).order_by(
        Candidature.envoyee_le.desc().nulls_first(), Candidature.id.desc())).all()
    return render_template("admin/candidatures.html", candidatures=liste,
                           resumes=resumes(g.db, liste))


def _page(c: Candidature | None, valeurs: dict, erreurs: dict, statut: int = 200):
    evenements = activite(g.db, c) if c else []
    return render_template(
        "admin/candidature.html", c=c, champs=champs(g.db), valeurs=valeurs, erreurs=erreurs,
        lien_candidature=_lien(c) if c else "", evenements=evenements,
        phrase=phrase_activite(c.entreprise, evenements) if c else ""), statut


def _editer(c: Candidature | None):
    if request.method == "POST":
        liste = champs(g.db)
        valeurs, erreurs = lire(request.form, liste)
        if not erreurs:
            erreurs = verifier(g.db, valeurs, c)
        if not erreurs:
            if c is None:
                c = Candidature(cree_le=maintenant_utc())
                g.db.add(c)
            appliquer(c, valeurs)
            g.db.commit()
            return ok(f"/admin/candidatures/{c.id}")
        return _page(c, request.form.to_dict(), erreurs, 400)
    if c:
        return _page(c, valeurs_de(c, champs(g.db)), {})
    return _page(None, {"statut": "envoyee", "langue": "fr",
                        "envoyee_le": maintenant_utc().date()}, {})


@bp.route("/candidatures/nouvelle", methods=["GET", "POST"])
def candidature_nouvelle():
    return _editer(None)


@bp.route("/candidatures/<int:id_>", methods=["GET", "POST"])
def candidature(id_):
    return _editer(trouver(Candidature, id_))


@bp.post("/candidatures/<int:id_>/supprimer")
def candidature_supprimer(id_):
    g.db.delete(trouver(Candidature, id_))
    g.db.commit()
    return ok("/admin/candidatures", "supprime")


@bp.get("/candidatures/<int:id_>/qr.<fmt>")
def candidature_qr(id_, fmt):
    if fmt not in FORMATS_QR:
        abort(404)
    c = trouver(Candidature, id_)
    reponse = make_response(qr(_lien(c), fmt))
    reponse.mimetype = FORMATS_QR[fmt]
    if request.args.get("telecharger") == "1":
        reponse.headers["Content-Disposition"] = f'attachment; filename="qr-{c.source}.{fmt}"'
    return reponse
