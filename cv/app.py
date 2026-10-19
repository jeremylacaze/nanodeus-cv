"""Fabrique de l'application.

Une seule image, deux rôles : `public` (derrière Traefik) n'enregistre aucune
route d'admin ; `admin` (tailnet uniquement) n'enregistre que l'admin, sous /admin.
"""
from pathlib import Path

import click
from flask import (Flask, Response, g, jsonify, make_response, redirect, render_template,
                   request)
from flask_babel import Babel
from flask_babel import gettext as _
from sqlalchemy import text

from cv.amorcage import amorcer
from cv.config import Config
from cv.courriel import EnvoiSMTP
from cv.db import creer_moteur, fabrique_sessions
from cv.journal import maintenant_utc, purger
from cv.langue import compiler_catalogues, init_langue, locale_selector
from cv.securite import init_securite

RACINE = Path(__file__).resolve().parent.parent


def veut_json() -> bool:
    """La modale de contact demande du JSON ; un navigateur sans JavaScript, du HTML."""
    return request.accept_mimetypes.best_match(["text/html", "application/json"]) \
        == "application/json"


def _erreur(statut: int, message: str, page):
    """Page d'erreur, ou JSON pour la modale : elle prendrait sinon une page HTML
    pour une panne réseau. `page` ne sert qu'au rendu HTML."""
    reponse = (jsonify(ok=False, message=message, erreurs={}) if veut_json()
               else make_response(page()))
    reponse.status_code = statut
    reponse.vary.add("Accept")
    return reponse


def _page_erreur(titre: str, message: str):
    return lambda: render_template("erreur.html", titre=titre, message=message)


def _sante():
    """Sonde de Traefik et du healthcheck Docker : la base répond. Rien n'est journalisé."""
    g.db.execute(text("SELECT 1"))
    return Response("ok", mimetype="text/plain")


def create_app(config: Config | None = None) -> Flask:
    config = config or Config()
    app = Flask(__name__, template_folder=str(RACINE / "templates"),
                static_folder=str(RACINE / "static"))
    app.config.update(CV=config, SECRET_KEY=config.SECRET_KEY,
                      BABEL_TRANSLATION_DIRECTORIES=str(RACINE / "translations"),
                      # Un formulaire de contact tient en quelques Kio : au-delà, 413.
                      MAX_CONTENT_LENGTH=64 * 1024)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    moteur = creer_moteur(config.DATABASE_URL)
    sessions = fabrique_sessions(moteur)
    app.extensions["cv_moteur"] = moteur
    app.extensions["cv_sessions"] = sessions
    # Lu à chaque envoi : les tests le remplacent par un faux transport.
    app.extensions["cv_envoi"] = EnvoiSMTP(config)

    compiler_catalogues(RACINE / "translations")
    Babel(app, locale_selector=locale_selector)
    init_langue(app)
    init_securite(app)
    if config.ROLE == "admin":
        from cv.admin.acces import init_acces
        init_acces(app)
        # Le profil tient en quelques Kio, mais une photo de téléphone dépasse le Mio.
        app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    @app.before_request
    def _ouvrir_session():
        g.db = sessions()

    @app.teardown_appcontext
    def _fermer_session(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def _introuvable(_e):
        return _erreur(404, _("Page introuvable."), lambda: render_template("404.html"))

    @app.errorhandler(403)
    def _refuse(_e):
        message = _("Cette requête n'a pas pu être acceptée.")
        return _erreur(403, message, _page_erreur(_("Requête refusée"), message))

    @app.errorhandler(413)
    def _trop_gros(_e):
        message = _("Le formulaire envoyé est trop volumineux.")
        return _erreur(413, message, _page_erreur(_("Requête trop volumineuse"), message))

    @app.errorhandler(500)
    def _plantage(_e):
        # Page générique : ni trace, ni contenu du profil. La demande a pu être
        # enregistrée avant l'erreur : le message déconseille un renvoi immédiat.
        return _erreur(500, _("Une erreur est survenue. Votre demande a peut-être été enregistrée : patientez quelques minutes avant de réessayer."),
                       lambda: render_template("500.html"))

    @app.cli.command("amorcer")
    def _amorcer():
        """Pré-remplit une base vide avec le CV actuel."""
        with sessions() as s:
            click.echo("Base amorcée." if amorcer(s) else "Profil déjà présent : rien à faire.")

    @app.cli.command("purger")
    def _purger():
        """Jette les sels passés et les visites de plus de 6 mois (timer quotidien)."""
        with sessions() as s:
            purger(s, maintenant_utc())
        click.echo("Purge faite.")

    if config.ROLE == "public":
        from cv.public import bp
        app.register_blueprint(bp)
        app.add_url_rule("/sante", "sante", _sante)
    else:
        from cv.admin import bp
        app.register_blueprint(bp)
        app.add_url_rule("/", "racine_admin", lambda: redirect("/admin/"))
    return app
