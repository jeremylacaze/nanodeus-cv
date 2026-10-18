"""Socle : pragmas SQLite, contraintes du schéma, alignement des migrations."""
from datetime import date, datetime

import alembic.command
import alembic.config
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from cv.models import DemandeContact, SelJournalier, Version, VersionElement, Visite


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


@pytest.mark.parametrize("slug", ["Mauvais Slug", "", "a" * 41, "accentué", "../x"])
def test_slug_invalide_refuse_en_base(session, slug):
    # Un slug que la route ne pourrait jamais servir est refusé dès l'écriture.
    session.add(Version(slug=slug, statut="publiee", titre_fr="A"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_slug_valide_accepte(session):
    session.add(Version(slug="lead-tech-2", statut="publiee", titre_fr="A"))
    session.flush()


def test_motif_de_slug_partage():
    # Une seule définition du slug, reprise par les routes et le lien d'autre langue.
    from cv import langue, public
    from cv.models import SLUG
    assert SLUG in public._SLUG.pattern and SLUG in langue._CHEMIN_DE_PAGE.pattern


def test_statut_de_demande_controle(session):
    session.add(DemandeContact(cree_le=datetime(2026, 10, 18), email="r@ex.fr", message="m",
                               version_slug="devops", langue="fr", statut="perdue",
                               empreinte="0" * 32))
    with pytest.raises(IntegrityError):
        session.flush()


def test_type_de_visite_controle(session):
    session.add(Visite(horodatage=datetime(2026, 10, 18), type="clic", version_slug="devops",
                       langue="fr", source="direct", appareil="mobile", empreinte="0" * 32))
    with pytest.raises(IntegrityError):
        session.flush()


def test_un_seul_sel_par_jour(session):
    session.add(SelJournalier(jour=date(2026, 10, 18), valeur=b"a" * 32))
    session.flush()
    session.expunge_all()
    session.add(SelJournalier(jour=date(2026, 10, 18), valeur=b"b" * 32))
    with pytest.raises(IntegrityError):
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
