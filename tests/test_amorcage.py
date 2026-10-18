"""Amorçage de la base depuis le CV actuel (cv/amorcage.py)."""
import re
from pathlib import Path

from sqlalchemy import select

from cv.amorcage import amorcer
from cv.models import (Chiffre, Competence, Entree, Profil, SoftSkill, Version,
                       VersionElement)
from cv.vue import assembler_vue


def test_amorcer_base_vide(session):
    assert amorcer(session) is True
    vue = assembler_vue(session, None, "fr")
    assert vue.slug == "devops" and len(vue.postes) == 3 and len(vue.projets) == 1
    assert [n for n, _ in vue.soft_skills] == ["Porteur d'idées", "Pédagogie"]
    assert [j.intitule for j in vue.postes] == [
        "Ingénieur DevOps", "Administrateur Atlassian", "Administrateur applicatif"]
    assert len(vue.formations) == 2
    assert vue.accroche == "Porteur d'idées, autonome, je fais grandir les équipes avec pédagogie."


def test_lead_tech_non_listee_avec_tout_coche(session):
    amorcer(session)
    vue = assembler_vue(session, "lead-tech", "fr")
    assert vue.noindex is True and vue.prochaine_mission == "Lead tech"
    nb_elements = sum(len(session.scalars(select(m)).all())
                      for m in (Entree, SoftSkill, Competence, Chiffre))
    for version in session.scalars(select(Version)):
        coches = session.scalars(select(VersionElement)
                                 .where(VersionElement.version_id == version.id)).all()
        assert len(coches) == nb_elements


def test_amorcer_ne_reecrit_jamais(session):
    amorcer(session)
    session.get(Profil, 1).localisation = "Paris"
    session.commit()
    assert amorcer(session) is False
    assert session.get(Profil, 1).localisation == "Paris"


def test_profil_sans_coordonnees(session):
    amorcer(session)
    profil = session.get(Profil, 1)
    assert (profil.telephone, profil.email, profil.date_naissance) == (None, None, None)


def test_donnees_amorcage_sans_coordonnees():
    source = Path("cv/donnees_amorcage.py").read_text()
    assert "@" not in source and not re.search(r"0[67](\s?\d{2}){4}", source)
    assert not re.search(r"\+33", source)


def test_anglais_rempli_pour_chaque_texte(session):
    amorcer(session)
    manquants = []
    for modele in (Profil, Entree, SoftSkill, Competence, Chiffre, Version):
        for obj in session.scalars(select(modele)):
            for colonne in modele.__table__.columns.keys():
                if not colonne.endswith("_en"):
                    continue
                francais = getattr(obj, colonne[:-3] + "_fr")
                if francais and not getattr(obj, colonne):
                    manquants.append(f"{modele.__name__}.{colonne}")
    assert manquants == []
