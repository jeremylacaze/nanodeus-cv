"""Admin : édition du profil, coordonnées privées comprises."""
from cv.models import Profil
from cv.vue import assembler_vue
from tests.conftest import EMAIL, TELEPHONE

ORIGINE = {"Origin": "http://localhost"}
PROFIL_OK = {"nom_complet": "Jeremy LACAZE-RUSQUES", "localisation": "Toulouse, France",
             "date_naissance": "", "permis": "B", "interets_fr": "Lecture\r\nRando",
             "interets_en": "", "linkedin_url": "https://www.linkedin.com/in/x",
             "github_url": "", "telephone": TELEPHONE, "email": EMAIL}


def _profil(admin):
    with admin.application.extensions["cv_sessions"]() as s:
        return s.get(Profil, 1)


def test_profil_affiche_les_coordonnees_privees(admin):
    corps = admin.get("/admin/profil").get_data(as_text=True)
    assert TELEPHONE in corps and EMAIL in corps


def test_profil_enregistre(admin):
    r = admin.post("/admin/profil", headers=ORIGINE, data={**PROFIL_OK, "localisation": "Bordeaux"})
    assert r.status_code == 303 and r.headers["Location"] == "/admin/profil?ok=enregistre"
    with admin.application.extensions["cv_sessions"]() as s:
        assert assembler_vue(s, None, "fr").localisation == "Bordeaux"
    profil = _profil(admin)
    assert profil.ouvert_opportunites is False  # case absente de PROFIL_OK
    assert profil.interets_fr == "Lecture\nRando"


def test_profil_case_cochee_et_date(admin):
    admin.post("/admin/profil", headers=ORIGINE, data={
        **PROFIL_OK, "ouvert_opportunites": "1", "afficher_age": "1",
        "date_naissance": "1990-05-04"})
    profil = _profil(admin)
    assert profil.ouvert_opportunites is True and profil.afficher_age is True
    assert str(profil.date_naissance) == "1990-05-04"


def test_profil_erreur_400_valeurs_gardees(admin):
    r = admin.post("/admin/profil", headers=ORIGINE,
                   data={**PROFIL_OK, "linkedin_url": "http://x.fr", "localisation": "Pau"})
    corps = r.get_data(as_text=True)
    assert r.status_code == 400 and 'value="Pau"' in corps and 'value="http://x.fr"' in corps
    assert _profil(admin).localisation != "Pau"


def test_profil_valeurs_echappees(admin):
    r = admin.post("/admin/profil", headers=ORIGINE,
                   data={**PROFIL_OK, "nom_complet": "", "localisation": '"><script>x'})
    corps = r.get_data(as_text=True)
    assert r.status_code == 400 and "<script>x" not in corps and "Champ obligatoire." in corps


def test_ecriture_sans_origin_403(admin):
    assert admin.post("/admin/profil", data=PROFIL_OK).status_code == 403
