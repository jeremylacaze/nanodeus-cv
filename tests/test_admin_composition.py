"""Admin : composition d'une version (coches, ordre, surcharge des missions)."""
import pytest
from sqlalchemy import select

from cv.admin.versions import elements_du_stock
from cv.models import Competence, Entree, SoftSkill, Version, VersionElement
from cv.vue import assembler_vue

ORIGINE = {"Origin": "http://localhost"}


def _session(admin):
    return admin.application.extensions["cv_sessions"]()


def _id(admin, slug):
    with _session(admin) as s:
        return s.scalar(select(Version.id).where(Version.slug == slug))


def _formulaire_actuel(admin, id_version) -> dict:
    """Le formulaire tel que la page le pré-remplit : coches, ordres, surcharges."""
    with _session(admin) as s:
        lignes = elements_du_stock(s, s.get(Version, id_version))
    donnees = {}
    for type_element, liste in lignes.items():
        for ligne in liste:
            cle = f"{type_element}-{ligne.element_id}"
            if ligne.coche:
                donnees[f"coche-{cle}"] = "1"
            donnees[f"ordre-{cle}"] = str(ligne.ordre)
            if type_element == "entree":
                donnees[f"missions_fr-{ligne.element_id}"] = ligne.missions_fr
                donnees[f"missions_en-{ligne.element_id}"] = ligne.missions_en
    return donnees


def _composer(admin, id_version, donnees):
    return admin.post(f"/admin/versions/{id_version}/composition", headers=ORIGINE, data=donnees)


def _vue(admin, slug):
    with _session(admin) as s:
        return assembler_vue(s, slug, "fr")


def test_formulaire_inchange_ne_change_rien(admin):
    id_ = _id(admin, "devops")
    avant = _vue(admin, "devops")
    r = _composer(admin, id_, _formulaire_actuel(admin, id_))
    assert r.status_code == 303
    assert r.headers["Location"] == f"/admin/versions/{id_}?ok=enregistre#composition"
    assert _vue(admin, "devops") == avant


def test_page_de_la_version_montre_la_composition(admin):
    corps = admin.get(f"/admin/versions/{_id(admin, 'devops')}").get_data(as_text=True)
    assert 'id="composition"' in corps and "Administrateur applicatif" in corps
    assert 'name="coche-soft_skill-' in corps and 'name="missions_fr-' in corps


def test_decocher_retire_de_la_version(admin):
    id_ = _id(admin, "devops")
    nom = _vue(admin, "devops").soft_skills[0][0]
    with _session(admin) as s:
        skill_id = s.scalar(select(SoftSkill.id).where(SoftSkill.nom_fr == nom))
    donnees = _formulaire_actuel(admin, id_)
    del donnees[f"coche-soft_skill-{skill_id}"]
    assert _composer(admin, id_, donnees).status_code == 303
    with _session(admin) as s:
        assert s.scalar(select(VersionElement).where(
            VersionElement.version_id == id_, VersionElement.type_element == "soft_skill",
            VersionElement.element_id == skill_id)) is None
    assert nom not in [n for n, _ in _vue(admin, "devops").soft_skills]
    assert nom in [n for n, _ in _vue(admin, "lead-tech").soft_skills]


def test_ordre_des_chiffres(admin):
    id_ = _id(admin, "devops")
    avant = _vue(admin, "devops").chiffres
    assert len(avant) > 1
    donnees = _formulaire_actuel(admin, id_)
    with _session(admin) as s:
        lignes = [ligne for ligne in elements_du_stock(s, s.get(Version, id_))["chiffre"]
                  if ligne.coche]
    for rang, ligne in enumerate(reversed(lignes)):
        donnees[f"ordre-chiffre-{ligne.element_id}"] = str(rang)
    assert _composer(admin, id_, donnees).status_code == 303
    assert _vue(admin, "devops").chiffres == list(reversed(avant))


def _poste_sqli(admin):
    with _session(admin) as s:
        return s.scalar(select(Entree.id).where(Entree.organisation == "SQLI · ADS",
                                                Entree.type == "poste")
                        .order_by(Entree.debut.desc()))


def test_surcharge_des_missions(admin):
    id_, poste = _id(admin, "devops"), _poste_sqli(admin)
    donnees = _formulaire_actuel(admin, id_)
    assert f"coche-entree-{poste}" in donnees
    stock = next(j for j in _vue(admin, "devops").postes if j.cle == f"e{poste}").missions
    donnees[f"missions_fr-{poste}"] = "Encadrement\r\nMentorat"
    assert _composer(admin, id_, donnees).status_code == 303
    job = next(j for j in _vue(admin, "devops").postes if j.cle == f"e{poste}")
    assert job.missions == ["Encadrement", "Mentorat"]
    donnees[f"missions_fr-{poste}"] = "   "
    assert _composer(admin, id_, donnees).status_code == 303
    job = next(j for j in _vue(admin, "devops").postes if j.cle == f"e{poste}")
    assert job.missions == stock
    with _session(admin) as s:
        coche = s.scalar(select(VersionElement).where(
            VersionElement.version_id == id_, VersionElement.type_element == "entree",
            VersionElement.element_id == poste))
        assert coche.missions_fr is None


@pytest.mark.parametrize("ordre", ["abc", "-1", "1000", "1.5"])
def test_ordre_invalide_400_sans_ecriture(admin, ordre):
    id_ = _id(admin, "devops")
    avant = _vue(admin, "devops")
    donnees = _formulaire_actuel(admin, id_)
    cle_chiffre = next(k for k in donnees if k.startswith("coche-chiffre-"))
    premiere_skill = next(k for k in donnees if k.startswith("coche-soft_skill-"))
    del donnees[premiere_skill]  # une autre modification, qui ne doit pas passer non plus
    cle_ordre = cle_chiffre.replace("coche-", "ordre-")
    donnees[cle_ordre] = ordre
    r = _composer(admin, id_, donnees)
    corps = r.get_data(as_text=True)
    assert r.status_code == 400 and f'value="{ordre}"' in corps
    assert _vue(admin, "devops") == avant


def test_ordre_vide_vaut_zero(admin):
    id_ = _id(admin, "devops")
    donnees = _formulaire_actuel(admin, id_)
    cle = next(k for k in donnees if k.startswith("coche-chiffre-")).replace("coche-", "ordre-")
    donnees[cle] = ""
    assert _composer(admin, id_, donnees).status_code == 303


def test_id_inconnu_ignore(admin):
    id_ = _id(admin, "devops")
    donnees = {**_formulaire_actuel(admin, id_), "coche-entree-9999": "1",
               "coche-inconnu-1": "1", "missions_fr-9999": "x"}
    assert _composer(admin, id_, donnees).status_code == 303
    with _session(admin) as s:
        assert s.scalars(select(VersionElement).where(VersionElement.element_id == 9999)).all() == []


def test_elements_du_stock_listes_non_coches(admin):
    with _session(admin) as s:
        s.add(Competence(nom_fr="Rust", categorie_fr="Langages"))
        s.commit()
        lignes = elements_du_stock(s, s.get(Version, _id(admin, "devops")))
    assert list(lignes) == ["entree", "soft_skill", "competence", "chiffre"]
    rust = next(ligne for ligne in lignes["competence"] if ligne.libelle.startswith("Rust"))
    assert rust.coche is False
    coches = [ligne.coche for ligne in lignes["competence"]]
    assert coches == sorted(coches, reverse=True)  # cochés d'abord


def test_cocher_un_nouvel_element(admin):
    id_ = _id(admin, "devops")
    with _session(admin) as s:
        c = Competence(nom_fr="Rust", categorie_fr="Langages")
        s.add(c)
        s.commit()
        cid = c.id
    donnees = {**_formulaire_actuel(admin, id_), f"coche-competence-{cid}": "1"}
    assert _composer(admin, id_, donnees).status_code == 303
    assert "Rust" in _vue(admin, "devops").competences["Langages"]


def test_version_inconnue_404(admin):
    assert _composer(admin, 9999, {}).status_code == 404
