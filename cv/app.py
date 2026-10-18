"""Fabrique de l'application.

Une seule image, deux rôles : `public` (derrière Traefik) n'enregistre aucune
route d'admin ; `admin` (tailnet uniquement) viendra au plan 3.
"""
from pathlib import Path

import click
from flask import Flask, g, render_template
from flask_babel import Babel
from flask_babel import gettext as _

from cv.amorcage import amorcer
from cv.config import Config
from cv.courriel import EnvoiSMTP
from cv.db import creer_moteur, fabrique_sessions
from cv.langue import compiler_catalogues, init_langue, locale_selector
from cv.securite import init_securite

RACINE = Path(__file__).resolve().parent.parent


def _page_erreur(titre: str, message: str) -> str:
    return render_template("erreur.html", titre=titre, message=message)


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
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def _refuse(_e):
        return _page_erreur(_("Requête refusée"), _("Cette requête n'a pas pu être acceptée.")), 403

    @app.errorhandler(413)
    def _trop_gros(_e):
        return _page_erreur(_("Requête trop volumineuse"),
                            _("Le formulaire envoyé est trop volumineux.")), 413

    @app.errorhandler(429)
    def _trop_de_demandes(_e):
        return _page_erreur(_("Trop de demandes"),
                            _("Trop de demandes pour le moment. Réessayez plus tard.")), 429

    @app.errorhandler(500)
    def _erreur(_e):
        # Page générique : ni trace, ni contenu du profil.
        return render_template("500.html"), 500

    @app.cli.command("amorcer")
    def _amorcer():
        """Pré-remplit une base vide avec le CV actuel."""
        with sessions() as s:
            click.echo("Base amorcée." if amorcer(s) else "Profil déjà présent : rien à faire.")

    if config.ROLE == "public":
        from cv.public import bp
        app.register_blueprint(bp)
    return app
