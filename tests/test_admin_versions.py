"""Admin : versions, version par défaut, suppression et aperçu."""
import pytest
from sqlalchemy import func, select

from cv.models import Version, VersionElement, Visite
from cv.vue import assembler_vue

ORIGINE = {"Origin": "http://localhost"}


def _session(admin):
    return admin.application.extensions["cv_sessions"]()


def _id(admin, slug):
    with _session(admin) as s:
        return s.scalar(select(Version.id).where(Version.slug == slug))


def _brouillon(admin):
    """La version brouillon posée par la fixture."""
    return _id(admin, "brouillon")


def _defaut(admin):
    with _session(admin) as s:
        return s.scalars(select(Version.slug).where(Version.par_defaut.is_(True))).all()


def test_liste_versions(admin):
    _brouillon(admin)
    corps = admin.get("/admin/versions").get_data(as_text=True)
    assert all(s in corps for s in ("devops", "lead-tech", "brouillon", "par défaut"))
    assert 'href="/admin/versions/nouvelle"' in corps


def test_creer_version(admin):
    r = admin.post("/admin/versions/nouvelle", headers=ORIGINE,
                   data={"slug": "acme", "statut": "non_listee", "titre_fr": "Pour ACME"})
    id_ = _id(admin, "acme")
    assert r.status_code == 303 and r.headers["Location"] == f"/admin/versions/{id_}?ok=enregistre"
    assert admin.get(f"/admin/versions/{id_}").status_code == 200


@pytest.mark.parametrize("slug", ["", "Acme", "a b", "a_b", "x" * 41, "en", "contact",
                                  "static", "admin", "devops"])
def test_slug_refuse(admin, slug):
    r = admin.post("/admin/versions/nouvelle", headers=ORIGINE,
                   data={"slug": slug, "statut": "publiee", "titre_fr": "T"})
    assert r.status_code == 400
    with _session(admin) as s:
        assert s.scalar(select(func.count()).select_from(Version)) == 3


def test_message_du_slug_refuse(admin):
    corps = admin.post("/admin/versions/nouvelle", headers=ORIGINE,
                       data={"slug": "admin", "statut": "publiee", "titre_fr": "T"}
                       ).get_data(as_text=True)
    assert "Ce slug est réservé." in corps and 'value="admin"' in corps
    corps = admin.post("/admin/versions/nouvelle", headers=ORIGINE,
                       data={"slug": "lead-tech", "statut": "publiee", "titre_fr": "T"}
                       ).get_data(as_text=True)
    assert "Ce slug est déjà utilisé." in corps


def test_modifier_garde_son_slug(admin):
    id_ = _id(admin, "devops")
    r = admin.post(f"/admin/versions/{id_}", headers=ORIGINE,
                   data={"slug": "devops", "statut": "publiee", "titre_fr": "DevOps senior"})
    assert r.status_code == 303 and r.headers["Location"] == f"/admin/versions/{id_}?ok=enregistre"
    with _session(admin) as s:
        assert s.get(Version, id_).titre_fr == "DevOps senior"


def test_version_inconnue_404(admin):
    assert admin.get("/admin/versions/9999").status_code == 404
    assert admin.get("/admin/versions/9999/apercu").status_code == 404
    assert admin.post("/admin/versions/9999/par-defaut", headers=ORIGINE).status_code == 404
    assert admin.post("/admin/versions/9999/supprimer", headers=ORIGINE).status_code == 404


def test_changer_la_version_par_defaut(admin):
    r = admin.post(f"/admin/versions/{_id(admin, 'lead-tech')}/par-defaut", headers=ORIGINE)
    assert r.status_code == 303 and r.headers["Location"] == "/admin/versions?ok=par-defaut"
    assert _defaut(admin) == ["lead-tech"]
    with _session(admin) as s:
        assert assembler_vue(s, None, "fr").slug == "lead-tech"


def test_brouillon_jamais_par_defaut(admin):
    r = admin.post(f"/admin/versions/{_brouillon(admin)}/par-defaut", headers=ORIGINE)
    assert r.headers["Location"] == "/admin/versions?ok=defaut-brouillon"
    assert _defaut(admin) == ["devops"]
    r = admin.post(f"/admin/versions/{_id(admin, 'devops')}", headers=ORIGINE,
                   data={"slug": "devops", "statut": "brouillon", "titre_fr": "DevOps"})
    assert r.status_code == 400
    assert "La version par défaut ne peut pas être un brouillon." in r.get_data(as_text=True)
    with _session(admin) as s:
        assert s.get(Version, _id(admin, "devops")).statut == "publiee"


def test_supprimer_version(admin):
    id_ = _id(admin, "lead-tech")
    r = admin.post(f"/admin/versions/{id_}/supprimer", headers=ORIGINE)
    assert r.status_code == 303 and r.headers["Location"] == "/admin/versions?ok=supprime"
    with _session(admin) as s:
        assert s.get(Version, id_) is None
        assert s.scalars(select(VersionElement).where(VersionElement.version_id == id_)).all() == []
    r = admin.post(f"/admin/versions/{_id(admin, 'devops')}/supprimer", headers=ORIGINE)
    assert r.headers["Location"] == "/admin/versions?ok=defaut-protege"
    assert _id(admin, "devops") is not None


def test_apercu_brouillon_sans_journal(admin):
    id_ = _brouillon(admin)
    r = admin.get(f"/admin/versions/{id_}/apercu",
                  headers={"User-Agent": "Mozilla/5.0 (X11; Linux)"})
    corps = r.get_data(as_text=True)
    assert r.status_code == 200 and "Aperçu — version « brouillon »" in corps
    assert '<html lang="fr">' in corps
    with _session(admin) as s:
        assert s.scalars(select(Visite)).all() == []


def test_apercu_en_anglais(admin):
    id_ = _id(admin, "devops")
    corps = admin.get(f"/admin/versions/{id_}/apercu?lang=en").get_data(as_text=True)
    assert '<html lang="en">' in corps and f"/admin/versions/{id_}/apercu?lang=fr" in corps
    corps = admin.get(f"/admin/versions/{id_}/apercu?lang=xx").get_data(as_text=True)
    assert '<html lang="fr">' in corps and f"/admin/versions/{id_}/apercu?lang=en" in corps


def test_pas_de_bandeau_d_apercu_en_public(fabrique_app):
    corps = fabrique_app().test_client().get("/devops").get_data(as_text=True)
    assert "Aperçu —" not in corps and 'class="apercu"' not in corps
