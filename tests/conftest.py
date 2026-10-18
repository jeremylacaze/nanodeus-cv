"""Fixtures communes : une base SQLite jetable par test, dans tmp_path."""
import pytest

from cv.db import Base, creer_moteur, fabrique_sessions
import cv.models  # noqa: F401  (enregistre les tables sur Base.metadata)


@pytest.fixture
def moteur(tmp_path):
    moteur = creer_moteur(f"sqlite:///{tmp_path / 'cv.sqlite3'}")
    Base.metadata.create_all(moteur)
    yield moteur
    moteur.dispose()


@pytest.fixture
def session(moteur):
    with fabrique_sessions(moteur)() as s:
        yield s


TELEPHONE, EMAIL = "+33 6 99 88 77 66", "fuite@test.invalid"


@pytest.fixture
def fabrique_app(tmp_path, monkeypatch):
    """App sur une base amorcée, avec de fausses coordonnées posées sur le profil
    (elles ne doivent jamais ressortir) et une version brouillon.

    `modifier(session)` ajuste le contenu avant le premier appel."""
    from cv.amorcage import amorcer
    from cv.app import create_app
    from cv.config import Config
    from cv.models import Profil, Version

    def fabriquer(role="public", modifier=None):
        monkeypatch.setenv("CV_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CV_ROLE", role)
        app = create_app(Config())
        Base.metadata.create_all(app.extensions["cv_moteur"])
        with app.extensions["cv_sessions"]() as s:
            amorcer(s)
            profil = s.get(Profil, 1)
            profil.telephone, profil.email = TELEPHONE, EMAIL
            s.add(Version(slug="brouillon", statut="brouillon", titre_fr="Brouillon"))
            if modifier:
                modifier(s)
            s.commit()
        return app

    return fabriquer


@pytest.fixture
def admin(fabrique_app):
    """Client de l'admin (adresse source par défaut du client de test : 127.0.0.1)."""
    return fabrique_app(role="admin").test_client()
