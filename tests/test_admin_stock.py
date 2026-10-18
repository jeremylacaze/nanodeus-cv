"""Admin : édition du stock (parcours, soft skills, compétences, chiffres)."""
import pytest
from sqlalchemy import select

from cv.models import Competence, Entree, SoftSkill, VersionElement
from cv.vue import assembler_vue

ORIGINE = {"Origin": "http://localhost"}
ENTREE_OK = {"type": "poste", "voie": "principale", "intitule_fr": "Testeur logiciel",
             "organisation": "ACME", "debut": "2025-01-01", "fin": "",
             "missions_fr": "Tester\r\nCorriger"}


def _session(admin):
    return admin.application.extensions["cv_sessions"]()


def test_liste_parcours(admin):
    assert "Administrateur applicatif" in admin.get("/admin/stock/parcours").get_data(as_text=True)


@pytest.mark.parametrize("cle", ["parcours", "soft-skills", "competences", "chiffres"])
def test_listes_et_formulaires_vides(admin, cle):
    assert admin.get(f"/admin/stock/{cle}").status_code == 200
    assert admin.get(f"/admin/stock/{cle}/nouveau").status_code == 200


def test_type_ou_id_inconnu_404(admin):
    assert admin.get("/admin/stock/inconnu").status_code == 404
    assert admin.get("/admin/stock/parcours/9999").status_code == 404
    assert admin.post("/admin/stock/parcours/9999/supprimer", headers=ORIGINE).status_code == 404


def test_creer_entree(admin):
    r = admin.post("/admin/stock/parcours/nouveau", headers=ORIGINE, data=ENTREE_OK)
    assert r.status_code == 303 and r.headers["Location"] == "/admin/stock/parcours?ok=enregistre"
    with _session(admin) as s:
        e = s.scalars(select(Entree).where(Entree.intitule_fr == "Testeur logiciel")).one()
        assert e.fin is None and e.missions_fr == "Tester\nCorriger"


def test_modifier_entree(admin):
    with _session(admin) as s:
        id_ = s.scalars(select(Entree.id)).first()
    r = admin.post(f"/admin/stock/parcours/{id_}", headers=ORIGINE,
                   data={**ENTREE_OK, "intitule_fr": "Renommé"})
    assert r.status_code == 303
    with _session(admin) as s:
        assert s.get(Entree, id_).intitule_fr == "Renommé"


def test_fin_avant_debut_refusee(admin):
    r = admin.post("/admin/stock/parcours/nouveau", headers=ORIGINE,
                   data={**ENTREE_OK, "debut": "2024-05-01", "fin": "2024-01-01"})
    assert r.status_code == 400 and "La fin précède le début." in r.get_data(as_text=True)
    assert 'value="Testeur logiciel"' in r.get_data(as_text=True)


@pytest.mark.parametrize("champ, valeur", [("type", "autre"), ("voie", ""), ("debut", ""),
                                           ("intitule_fr", "")])
def test_entree_invalide_400(admin, champ, valeur):
    r = admin.post("/admin/stock/parcours/nouveau", headers=ORIGINE,
                   data={**ENTREE_OK, champ: valeur})
    assert r.status_code == 400


def test_modifier_soft_skill_preuve(admin):
    with _session(admin) as s:
        id_ = s.scalars(select(SoftSkill.id).where(SoftSkill.nom_fr == "Autonomie")).one()
        assert ("Autonomie", "Preuve") not in assembler_vue(s, "devops", "fr").soft_skills
    r = admin.post(f"/admin/stock/soft-skills/{id_}", headers=ORIGINE,
                   data={"nom_fr": "Autonomie", "preuve_fr": "Preuve"})
    assert r.status_code == 303
    with _session(admin) as s:
        assert ("Autonomie", "Preuve") in assembler_vue(s, "devops", "fr").soft_skills


def test_soft_skill_sans_preuve_a_completer(admin):
    assert "Autonomie — à compléter" in admin.get("/admin/stock/soft-skills").get_data(as_text=True)


def test_supprimer_retire_des_versions(admin):
    with _session(admin) as s:
        id_ = s.scalars(select(Entree.id).order_by(Entree.id)).first()
        assert s.get(SoftSkill, id_) is not None  # même numéro, autre type
        cle = f"e{id_}"
        assert any(j.cle == cle for j in assembler_vue(s, "devops", "fr").postes
                   + assembler_vue(s, "devops", "fr").formations
                   + assembler_vue(s, "devops", "fr").projets)
    r = admin.post(f"/admin/stock/parcours/{id_}/supprimer", headers=ORIGINE)
    assert r.status_code == 303 and r.headers["Location"] == "/admin/stock/parcours?ok=supprime"
    with _session(admin) as s:
        assert s.get(Entree, id_) is None
        coches = s.scalars(select(VersionElement).where(VersionElement.element_id == id_)).all()
        types = {c.type_element for c in coches}
        assert "entree" not in types and "soft_skill" in types  # les autres types restent
        vue = assembler_vue(s, "devops", "fr")
        assert all(j.cle != cle for j in vue.postes + vue.formations + vue.projets)


def test_contenu_echappe(admin):
    admin.post("/admin/stock/competences/nouveau", headers=ORIGINE, data={"nom_fr": "<script>x"})
    corps = admin.get("/admin/stock/competences").get_data(as_text=True)
    assert "&lt;script&gt;x" in corps and "<script>x" not in corps
    with _session(admin) as s:
        assert s.scalars(select(Competence).where(Competence.nom_fr == "<script>x")).one()


def test_id_hors_64_bits_404(admin):
    assert admin.get(f"/admin/stock/parcours/{2**64}").status_code == 404
    assert admin.get(f"/admin/stock/parcours/{2**63}").status_code == 404
