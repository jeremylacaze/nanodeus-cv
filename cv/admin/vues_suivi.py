"""Admin : accueil, demandes de contact et visites."""
from datetime import timedelta

from flask import g, render_template
from sqlalchemy import func, or_, select

from cv.admin import bp
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
