"""Socle : pragmas SQLite, contraintes du schéma, alignement des migrations."""
import alembic.command
import alembic.config
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from cv.models import Version, VersionElement


def test_wal_et_cles_etrangeres_actifs(session):
    assert session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_une_seule_version_par_defaut(session):
    session.add_all([
        Version(slug="a", statut="publiee", par_defaut=True, titre_fr="A"),
        Version(slug="b", statut="publiee", par_defaut=True, titre_fr="B"),
    ])
    with pytest.raises(IntegrityError):
        session.flush()


def test_plusieurs_versions_non_par_defaut(session):
    session.add_all([
        Version(slug="a", statut="publiee", par_defaut=False, titre_fr="A"),
        Version(slug="b", statut="publiee", par_defaut=False, titre_fr="B"),
    ])
    session.flush()


def test_supprimer_version_supprime_ses_elements(session):
    v = Version(slug="a", statut="publiee", par_defaut=True, titre_fr="A")
    session.add(v)
    session.flush()
    session.add(VersionElement(version_id=v.id, type_element="entree", element_id=1, ordre=0))
    session.commit()
    session.delete(v)
    session.commit()
    assert session.scalars(select(VersionElement)).all() == []


def test_migrations_alignees_sur_les_modeles(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_DATA_DIR", str(tmp_path))
    cfg = alembic.config.Config("alembic.ini")
    alembic.command.upgrade(cfg, "head")
    alembic.command.check(cfg)  # lève si un modèle diverge de la chaîne
