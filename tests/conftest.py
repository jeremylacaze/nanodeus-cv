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
