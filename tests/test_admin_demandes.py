"""Admin : demandes de contact (liste, renvoyer, supprimer, email de test)."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from cv.journal import maintenant_utc
from cv.models import DemandeContact
from tests.fabriques import FauxEnvoi

ORIGINE = {"Origin": "http://localhost"}


@pytest.fixture
def admin_et_envoi(fabrique_app, monkeypatch):
    monkeypatch.setenv("CV_EMAIL_DESTINATAIRE", "dest@test.invalid")
    maintenant = maintenant_utc()

    def demandes(s):
        s.add_all([
            DemandeContact(cree_le=maintenant - timedelta(days=2), email="ancien@ex.fr",
                           nom="Ancien", message="Premier", version_slug="devops", langue="fr",
                           statut="envoyee", empreinte="a" * 32),
            DemandeContact(cree_le=maintenant - timedelta(hours=1), email="r@ex.fr",
                           nom="Alice", entreprise="ACME", message="<script>x\nligne 2",
                           version_slug="lead-tech", langue="en", statut="echec",
                           erreur="TimeoutError: trop lent", empreinte="b" * 32)])

    app = fabrique_app(role="admin", modifier=demandes)
    envoi = FauxEnvoi()
    app.extensions["cv_envoi"] = envoi
    return app.test_client(), envoi


def _demande(client, email):
    with client.application.extensions["cv_sessions"]() as s:
        return s.scalar(select(DemandeContact).where(DemandeContact.email == email))


def test_liste_echappee_et_triee(admin_et_envoi):
    c, _ = admin_et_envoi
    corps = c.get("/admin/demandes").get_data(as_text=True)
    assert "&lt;script&gt;x" in corps and "<script>x" not in corps
    assert corps.index("Alice") < corps.index("Ancien")
    assert all(s in corps for s in ("ACME", "r@ex.fr", "lead-tech", "TimeoutError: trop lent"))
    # Renvoyer seulement pour l'échec.
    assert corps.count("/renvoyer") == 1


def test_renvoyer_un_echec(admin_et_envoi):
    c, envoi = admin_et_envoi
    id_ = _demande(c, "r@ex.fr").id
    r = c.post(f"/admin/demandes/{id_}/renvoyer", headers=ORIGINE)
    assert r.status_code == 303 and r.headers["Location"] == "/admin/demandes?ok=renvoyee"
    assert len(envoi.messages) == 1 and envoi.messages[0]["Reply-To"] == "r@ex.fr"
    d = _demande(c, "r@ex.fr")
    assert (d.statut, d.erreur) == ("envoyee", None)


def test_renvoyer_deja_envoyee_ne_renvoie_pas(admin_et_envoi):
    c, envoi = admin_et_envoi
    r = c.post(f"/admin/demandes/{_demande(c, 'ancien@ex.fr').id}/renvoyer", headers=ORIGINE)
    assert r.headers["Location"] == "/admin/demandes?ok=deja-envoyee" and envoi.messages == []


def test_renvoyer_echoue_encore(admin_et_envoi):
    c, envoi = admin_et_envoi
    envoi.erreur = OSError("refus")
    r = c.post(f"/admin/demandes/{_demande(c, 'r@ex.fr').id}/renvoyer", headers=ORIGINE)
    assert r.headers["Location"] == "/admin/demandes?ok=echec-envoi"
    assert _demande(c, "r@ex.fr").erreur == "OSError: refus"


def test_supprimer_demande(admin_et_envoi):
    c, _ = admin_et_envoi
    r = c.post(f"/admin/demandes/{_demande(c, 'r@ex.fr').id}/supprimer", headers=ORIGINE)
    assert r.status_code == 303 and r.headers["Location"] == "/admin/demandes?ok=supprime"
    assert _demande(c, "r@ex.fr") is None and _demande(c, "ancien@ex.fr") is not None


def test_demande_inconnue_404(admin_et_envoi):
    c, _ = admin_et_envoi
    assert c.post("/admin/demandes/9999/renvoyer", headers=ORIGINE).status_code == 404
    assert c.post("/admin/demandes/9999/supprimer", headers=ORIGINE).status_code == 404


def test_email_de_test(admin_et_envoi):
    c, envoi = admin_et_envoi
    r = c.post("/admin/demandes/test", headers=ORIGINE)
    # Redirection : recharger la page qui suit ne renvoie pas un second email.
    assert r.status_code == 303 and r.headers["Location"].endswith("?ok=test-envoye")
    assert "Email de test envoyé." in c.get(r.headers["Location"]).get_data(as_text=True)
    assert envoi.messages[0]["Subject"] == "[CV] Email de test"
    envoi.erreur = OSError("refus")
    corps = c.post("/admin/demandes/test", headers=ORIGINE).get_data(as_text=True)
    assert "L'email de test n'est pas parti : OSError: refus" in corps


def test_email_de_test_non_configure(fabrique_app, monkeypatch):
    monkeypatch.delenv("CV_SMTP_HOTE", raising=False)
    c = fabrique_app(role="admin").test_client()
    corps = c.post("/admin/demandes/test", headers=ORIGINE).get_data(as_text=True)
    assert "EnvoiNonConfigure" in corps


def test_id_hors_64_bits_404(admin_et_envoi):
    c, envoi = admin_et_envoi
    r = c.post(f"/admin/demandes/{2**64}/renvoyer", headers=ORIGINE)
    assert r.status_code == 404 and envoi.messages == []
