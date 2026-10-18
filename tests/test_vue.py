"""Assemblage de la vue publique d'une version (cv/vue.py)."""
import dataclasses
from datetime import date
from types import SimpleNamespace

from cv.vue import VueCV, assembler_vue, champ
from tests import fabriques as f


def test_vuecv_na_aucun_champ_de_coordonnees():
    noms = {c.name for c in dataclasses.fields(VueCV)}
    assert not noms & {"telephone", "email", "phone"}


def test_version_par_defaut_et_brouillon(session):
    f.profil(session)
    f.version(session, "devops", par_defaut=True)
    f.version(session, "brouillon", statut="brouillon")
    assert assembler_vue(session, None, "fr").slug == "devops"
    assert assembler_vue(session, "brouillon", "fr") is None
    assert assembler_vue(session, "inconnue", "fr") is None


def test_sans_version_par_defaut(session):
    f.profil(session)
    f.version(session, "devops")
    assert assembler_vue(session, None, "fr") is None


def test_par_defaut_en_brouillon_donne_none(session):
    f.profil(session)
    f.version(session, "devops", statut="brouillon", par_defaut=True)
    assert assembler_vue(session, None, "fr") is None


def test_repli_francais_si_anglais_vide(session):
    f.profil(session)
    e = f.entree(session, intitule_fr="Ingénieur DevOps", intitule_en=None)
    f.version(session, elements=[e])
    assert assembler_vue(session, "devops", "en").postes[0].intitule == "Ingénieur DevOps"


def test_anglais_utilise_si_rempli(session):
    f.profil(session)
    e = f.entree(session, intitule_fr="Ingénieur DevOps", intitule_en="DevOps engineer")
    f.version(session, elements=[e], titre_en="Application administrator")
    vue = assembler_vue(session, "devops", "en")
    assert vue.postes[0].intitule == "DevOps engineer"
    assert vue.titre == "Application administrator"
    assert vue.lang == "en"


def test_champ_vide_partout_donne_chaine_vide():
    assert champ(SimpleNamespace(titre_fr=None, titre_en=""), "titre", "en") == ""
    assert champ(SimpleNamespace(titre_fr=None, titre_en=None), "titre", "fr") == ""


def test_soft_skill_sans_preuve_exclue(session):
    f.profil(session)
    a = f.soft_skill(session, nom_fr="Pédagogie", preuve_fr="Forme les utilisateurs.")
    b = f.soft_skill(session, nom_fr="Autonomie", preuve_fr=None)
    c = f.soft_skill(session, nom_fr="Rigueur", preuve_fr="  ")
    f.version(session, elements=[a, b, c])
    assert assembler_vue(session, "devops", "fr").soft_skills == [
        ("Pédagogie", "Forme les utilisateurs.")]


def test_surcharge_des_missions_par_version(session):
    f.profil(session)
    e = f.entree(session, missions_fr="Support\nMaintenance")
    v = f.version(session)
    f.cocher(session, v, e, missions_fr="Encadrement\n\nFormation de l'équipe")
    assert assembler_vue(session, "devops", "fr").postes[0].missions == [
        "Encadrement", "Formation de l'équipe"]


def test_stock_anglais_avant_surcharge_francaise(session):
    # Une surcharge écrite en français seulement ne masque pas l'anglais du stock.
    f.profil(session)
    e = f.entree(session, missions_fr="Support", missions_en="Support desk")
    v = f.version(session)
    f.cocher(session, v, e, missions_fr="Encadrement")
    assert assembler_vue(session, "devops", "en").postes[0].missions == ["Support desk"]
    assert assembler_vue(session, "devops", "fr").postes[0].missions == ["Encadrement"]


def test_surcharge_anglaise_avant_tout(session):
    f.profil(session)
    e = f.entree(session, missions_fr="Support", missions_en="Support desk")
    v = f.version(session)
    f.cocher(session, v, e, missions_fr="Encadrement", missions_en="Team lead")
    assert assembler_vue(session, "devops", "en").postes[0].missions == ["Team lead"]


def test_surcharge_francaise_si_aucun_anglais(session):
    f.profil(session)
    e = f.entree(session, missions_fr="Support", missions_en=None)
    v = f.version(session)
    f.cocher(session, v, e, missions_fr="Encadrement")
    assert assembler_vue(session, "devops", "en").postes[0].missions == ["Encadrement"]


def test_missions_du_stock_sans_surcharge(session):
    f.profil(session)
    e = f.entree(session, missions_fr="Support\n\n  Maintenance  \n")
    f.version(session, elements=[e])
    assert assembler_vue(session, "devops", "fr").postes[0].missions == ["Support", "Maintenance"]


def test_ordre_et_repartition_des_voies(session):
    f.profil(session)
    recent = f.entree(session, intitule_fr="Récent", debut=date(2025, 5, 1))
    ancien = f.entree(session, intitule_fr="Ancien", debut=date(2023, 10, 1),
                      fin=date(2024, 2, 1))
    readln = f.entree(session, type="projet", voie="parallele", intitule_fr="ReadLN",
                      debut=date(2025, 1, 1))
    master = f.entree(session, type="formation", intitule_fr="Mastère", debut=date(2023, 6, 1))
    licence = f.entree(session, type="formation", intitule_fr="Licence", debut=date(2020, 6, 1))
    non_coche = f.entree(session, intitule_fr="Caché")
    f.version(session, elements=[recent, readln, master, ancien, licence])
    vue = assembler_vue(session, "devops", "fr")
    assert [j.intitule for j in vue.postes] == ["Ancien", "Récent"]
    assert [j.intitule for j in vue.projets] == ["ReadLN"]
    assert [j.intitule for j in vue.formations] == ["Licence", "Mastère"]
    assert vue.postes[0].cle == f"e{ancien.id}"
    assert non_coche.id not in {int(j.cle[1:]) for j in vue.postes}


def test_job_calcule_periode_et_duree(session):
    f.profil(session)
    e = f.entree(session, organisation="SQLI · ADS", via="Astek",
                 debut=date(2024, 2, 1), fin=date(2025, 5, 1))
    en_cours = f.entree(session, debut=date(2025, 5, 1))
    f.version(session, elements=[e, en_cours])
    vue = assembler_vue(session, "devops", "fr", aujourd_hui=date(2026, 10, 18))
    job, actuel = vue.postes
    assert (job.periode, job.duree, job.en_cours) == ("févr. 2024 → mai 2025", "1 an 3 m", False)
    assert (job.organisation, job.via) == ("SQLI · ADS", "Astek")
    assert (actuel.duree, actuel.en_cours) == ("1 an 5 m", True)


def test_ordre_des_soft_skills_suit_la_version(session):
    f.profil(session)
    a = f.soft_skill(session, nom_fr="A", preuve_fr="pa")
    b = f.soft_skill(session, nom_fr="B", preuve_fr="pb")
    f.version(session, elements=[b, a])
    assert [n for n, _ in assembler_vue(session, "devops", "fr").soft_skills] == ["B", "A"]


def test_competences_par_categorie_et_chiffres(session):
    f.profil(session)
    docker = f.competence(session, nom_fr="Docker", categorie_fr="Ops")
    py = f.competence(session, nom_fr="Python", categorie_fr="Développement")
    k8s = f.competence(session, nom_fr="Kubernetes", categorie_fr="Ops")
    sans = f.competence(session, nom_fr="Anglais technique")
    xp = f.chiffre(session, valeur_fr="3 ans", libelle_fr="d'expérience")
    f.version(session, elements=[docker, py, k8s, sans, xp])
    vue = assembler_vue(session, "devops", "fr")
    assert vue.competences == {"Ops": ["Docker", "Kubernetes"], "Développement": ["Python"],
                               "": ["Anglais technique"]}
    assert vue.chiffres == [("3 ans", "d'expérience")]


def test_age_masque_par_defaut(session):
    f.profil(session, date_naissance=date(1997, 3, 1))
    f.version(session)
    assert assembler_vue(session, "devops", "fr").age is None


def test_age_affiche_si_demande(session):
    f.profil(session, date_naissance=date(1997, 3, 1), afficher_age=True)
    f.version(session)
    assert assembler_vue(session, "devops", "fr", aujourd_hui=date(2026, 10, 18)).age == 29


def test_non_listee_noindex(session):
    f.profil(session)
    f.version(session, "lead-tech", statut="non_listee")
    f.version(session, "devops")
    assert assembler_vue(session, "lead-tech", "fr").noindex is True
    assert assembler_vue(session, "devops", "fr").noindex is False


def test_profil_et_interets(session):
    f.profil(session, interets_fr="Musique\nDessin", linkedin_url="https://linkedin.example/x")
    f.version(session, accroche_fr="Porteur d'idées.", prochaine_mission_fr="Lead tech")
    vue = assembler_vue(session, "devops", "fr")
    assert vue.nom == "Jeremy LACAZE-RUSQUES"
    assert vue.interets == ["Musique", "Dessin"]
    assert (vue.accroche, vue.prochaine_mission) == ("Porteur d'idées.", "Lead tech")
    assert vue.linkedin_url == "https://linkedin.example/x"
    assert vue.photo_url is None


def test_annee_affichee_pour_les_formations(session):
    f.profil(session)
    licence = f.entree(session, type="formation", debut=date(2019, 9, 1), fin=date(2020, 6, 1))
    sans_fin = f.entree(session, type="formation", debut=date(2023, 9, 1))
    f.version(session, elements=[licence, sans_fin])
    assert [j.annee for j in assembler_vue(session, "devops", "fr").formations] == ["2020", "2023"]


def test_liens_non_https_ignores(session):
    f.profil(session, linkedin_url="javascript:alert(1)", github_url="https://github.com/x")
    f.version(session)
    vue = assembler_vue(session, "devops", "fr")
    assert (vue.linkedin_url, vue.github_url) == ("", "https://github.com/x")
