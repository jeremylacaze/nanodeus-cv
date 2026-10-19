"""Admin : accueil, demandes de contact et visites."""
from datetime import timedelta

from flask import current_app, g, render_template, request
from sqlalchemy import func, or_, select

from cv.admin import bp
from cv.admin.suivi import Filtres, lire_filtres, serie_jours, totaux, valeurs_presentes, visites
from cv.admin.vues_contenu import ok, trouver
from cv.contact import envoyer_demande, message_de_test, renvoyable
from cv.journal import maintenant_utc
from cv.models import TYPES_VISITE, DemandeContact, SoftSkill, Version, Visite

JOURS_ACCUEIL = 14
BORNE_GRAPHIQUE = 90  # jours au plus dans l'histogramme de la page Visites


@bp.get("/")
def accueil():
    db = g.db
    compte = lambda requete: db.scalar(select(func.count()).select_from(requete))  # noqa: E731
    aujourd_hui = maintenant_utc().date()
    periode = Filtres(aujourd_hui - timedelta(days=JOURS_ACCUEIL - 1), aujourd_hui, "", "", "")
    return render_template(
        "admin/accueil.html",
        versions=db.scalars(select(Version).order_by(Version.par_defaut.desc(),
                                                     Version.slug)).all(),
        dernieres=db.scalars(select(DemandeContact).order_by(
            DemandeContact.cree_le.desc(), DemandeContact.id.desc()).limit(3)).all(),
        serie=serie_jours(periode.du, periode.au, totaux(db, periode).uniques_par_jour),
        demandes=compte(select(DemandeContact).where(DemandeContact.statut != "envoyee")
                        .subquery()),
        visites=compte(select(Visite).where(
            Visite.horodatage >= maintenant_utc() - timedelta(days=7),
            Visite.type != "apercu_linkedin").subquery()),
        a_completer=compte(select(SoftSkill).where(
            or_(SoftSkill.preuve_fr.is_(None), func.trim(SoftSkill.preuve_fr) == ""))
            .subquery()))


def _demande(id_: int) -> DemandeContact:
    return trouver(DemandeContact, id_)


def _page_demandes(erreur_test: str | None = None):
    demandes = g.db.scalars(select(DemandeContact)
                            .order_by(DemandeContact.cree_le.desc(), DemandeContact.id.desc())).all()
    maintenant = maintenant_utc()
    return render_template("admin/demandes.html", demandes=demandes,
                           renvoyables={d.id for d in demandes if renvoyable(d, maintenant)},
                           erreur_test=erreur_test)


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
        # Rendu direct pour montrer l'erreur ; un rechargement ne renvoie qu'un échec.
        return _page_demandes(erreur_test=f"{exc.__class__.__name__}: {exc}"[:300])
    return ok("/admin/demandes", "test-envoye")


LIMITE_VISITES = 200


@bp.get("/visites")
def page_visites():
    filtres = lire_filtres(request.args, maintenant_utc().date())
    liste = visites(g.db, filtres, LIMITE_VISITES)
    versions, sources = valeurs_presentes(g.db)
    chiffres = totaux(g.db, filtres)
    return render_template("admin/visites.html", filtres=filtres, visites=liste,
                           totaux=chiffres, versions=versions, sources=sources,
                           serie=serie_jours(filtres.du, filtres.au, chiffres.uniques_par_jour,
                                             borne=BORNE_GRAPHIQUE),
                           types=TYPES_VISITE, tronque=len(liste) == LIMITE_VISITES)
