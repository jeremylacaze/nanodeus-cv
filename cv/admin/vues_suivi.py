"""Admin : accueil, demandes de contact et visites."""
from datetime import timedelta

from flask import abort, current_app, g, render_template
from sqlalchemy import func, or_, select

from cv.admin import bp
from cv.admin.vues_contenu import ok
from cv.contact import envoyer_demande, message_de_test, renvoyable
from cv.journal import maintenant_utc
from cv.models import DemandeContact, SoftSkill, Visite


@bp.get("/")
def accueil():
    db = g.db
    compte = lambda requete: db.scalar(select(func.count()).select_from(requete))  # noqa: E731
    return render_template(
        "admin/accueil.html",
        demandes=compte(select(DemandeContact).where(DemandeContact.statut != "envoyee")
                        .subquery()),
        visites=compte(select(Visite).where(
            Visite.horodatage >= maintenant_utc() - timedelta(days=7),
            Visite.type != "apercu_linkedin").subquery()),
        a_completer=compte(select(SoftSkill).where(
            or_(SoftSkill.preuve_fr.is_(None), func.trim(SoftSkill.preuve_fr) == ""))
            .subquery()))


def _demande(id_: int) -> DemandeContact:
    return g.db.get(DemandeContact, id_) or abort(404)


def _page_demandes(resultat_test: str | None = None, erreur_test: str | None = None):
    demandes = g.db.scalars(select(DemandeContact)
                            .order_by(DemandeContact.cree_le.desc(), DemandeContact.id.desc())).all()
    maintenant = maintenant_utc()
    return render_template("admin/demandes.html", demandes=demandes,
                           renvoyables={d.id for d in demandes if renvoyable(d, maintenant)},
                           resultat_test=resultat_test, erreur_test=erreur_test)


@bp.get("/demandes")
def demandes():
    return _page_demandes()


@bp.post("/demandes/<int:id_>/renvoyer")
def demande_renvoyer(id_):
    demande = _demande(id_)
    if not renvoyable(demande, maintenant_utc()):
        return ok("/admin/demandes", "deja-envoyee")
    envoye = envoyer_demande(g.db, demande, current_app.config["CV"],
                             current_app.extensions["cv_envoi"])
    return ok("/admin/demandes", "renvoyee" if envoye else "echec-envoi")


@bp.post("/demandes/<int:id_>/supprimer")
def demande_supprimer(id_):
    g.db.delete(_demande(id_))
    g.db.commit()
    return ok("/admin/demandes", "supprime")


@bp.post("/demandes/test")
def demande_test():
    try:
        current_app.extensions["cv_envoi"].envoyer(
            message_de_test(current_app.config["CV"], maintenant_utc()))
    except Exception as exc:  # noqa: BLE001 — l'échec est affiché, c'est le but du test
        return _page_demandes(erreur_test=f"{exc.__class__.__name__}: {exc}"[:300])
    return _page_demandes(resultat_test="Email de test envoyé.")
