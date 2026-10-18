"""Demande de contact : validation, limites, message construit, envoi SMTP."""
import ssl
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from cv import courriel
from cv.config import Config
from cv.contact import (construire_message, enregistrer, envoyer_demande, limite_atteinte,
                        message_de_test, renvoyable, valider)
from cv.courriel import EnvoiSMTP
from cv.models import DemandeContact
from tests.fabriques import FauxEnvoi

T = datetime(2026, 10, 18, 9, 5)
OK = {"email": "r@ex.fr", "message": "Bonjour", "nom": "Alice", "entreprise": "ACME"}


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("CV_EMAIL_DESTINATAIRE", "dest@test.invalid")
    monkeypatch.setenv("CV_SMTP_HOTE", "smtp.test.invalid")
    return Config()


def _demande(**champs):
    valeurs = dict(email="r@ex.fr", nom="Alice", entreprise="ACME", message="Bonjour",
                   version_slug="lead-tech", langue="en", cree_le=T, empreinte="e" * 32)
    valeurs.update(champs)
    return DemandeContact(**valeurs)


def test_formulaire_valide():
    formulaire, erreurs = valider({**OK, "email": "  r@ex.fr ", "nom": " Alice "})
    assert erreurs == {}
    assert (formulaire.email, formulaire.nom, formulaire.piege) == ("r@ex.fr", "Alice", "")


@pytest.mark.parametrize("email", ["", "pas-un-email", "a@b", "a@b.fr\r\nBcc: x@y.fr",
                                   "a@b.fr, c@d.fr", "Nom <a@b.fr>", "a\x00b@c.fr",
                                   "a" * 250 + "@b.fr", "rené@ex.fr"])
def test_email_refuse(email):
    assert "email" in valider({**OK, "email": email})[1]


def test_message_obligatoire_et_borne():
    assert "message" in valider({**OK, "message": "   "})[1]
    assert "message" in valider({**OK, "message": "x" * 2001})[1]
    assert valider({**OK, "message": "x" * 2000})[1] == {}


def test_saut_de_ligne_compte_pour_un_caractere():
    # Le navigateur envoie \r\n mais son maxlength compte 1 caractère par saut de ligne.
    message = ("x" * 99 + "\r\n") * 19 + "x" * 99 + "\r\n"
    formulaire, erreurs = valider({**OK, "message": message})
    assert erreurs == {} and "\r" not in formulaire.message


@pytest.mark.parametrize("champ", ["nom", "entreprise"])
def test_nom_et_entreprise_sur_une_ligne(champ):
    assert champ in valider({**OK, champ: "A\r\nBcc: x@y.fr"})[1]
    for separateur in ("\u2028", "\u2029", "\x85", "\x0b"):
        assert champ in valider({**OK, champ: f"A{separateur}B"})[1]
    assert champ in valider({**OK, champ: "x" * 101})[1]
    assert valider({**OK, champ: ""})[1] == {}


def test_champ_piege_lu():
    assert valider({**OK, "site_web": "http://spam.example"})[0].piege == "http://spam.example"


def test_message_construit(config):
    m = construire_message(_demande(), config)
    assert m["Reply-To"] == "r@ex.fr" and m["To"] == "dest@test.invalid"
    assert m["From"] == "cv@nanodeus.com"
    assert m["Subject"] == "[CV · lead-tech] Demande de contact — Alice (ACME)"
    corps = m.get_content()
    assert "18/10/2026 09:05 UTC" in corps and "Bonjour" in corps and "lead-tech" in corps
    assert len(m.get_all("Reply-To")) == 1 and m["Cc"] is None and m["Bcc"] is None


def test_objet_sans_nom_ni_entreprise(config):
    m = construire_message(_demande(nom="", entreprise=""), config)
    assert m["Subject"] == "[CV · lead-tech] Demande de contact — r@ex.fr"


def test_limites_par_visiteur_et_globale(session):
    def ajouter(n, il_y_a, empreinte="e" * 32):
        session.add_all(_demande(cree_le=T - il_y_a, empreinte=empreinte) for _ in range(n))
        session.commit()

    ajouter(2, timedelta(minutes=10))
    ajouter(7, timedelta(hours=3))
    assert limite_atteinte(session, "e" * 32, T) is False      # 2 en 1 h, 9 en 24 h
    ajouter(1, timedelta(minutes=5))
    assert limite_atteinte(session, "e" * 32, T) is True       # 3 en 1 h
    assert limite_atteinte(session, "f" * 32, T) is False
    ajouter(1, timedelta(hours=23), empreinte="g" * 32)
    ajouter(9, timedelta(hours=2), empreinte="g" * 32)
    assert limite_atteinte(session, "g" * 32, T) is True       # 10 en 24 h
    ajouter(30, timedelta(hours=12), empreinte="h" * 32)
    assert limite_atteinte(session, "i" * 32, T) is True       # 50 au total en 24 h
    assert limite_atteinte(session, "i" * 32, T + timedelta(days=2)) is False


def _enregistree(session):
    formulaire, _ = valider(OK)
    return enregistrer(session, formulaire, "lead-tech", "en", "e" * 32, T)


def test_demande_enregistree_en_attente(session):
    d = _enregistree(session)
    assert session.get(DemandeContact, d.id).statut == "en_attente"


def test_envoi_reussi(session, config):
    envoi = FauxEnvoi()
    d = _enregistree(session)
    assert envoyer_demande(session, d, config, envoi) is True
    assert (d.statut, d.erreur) == ("envoyee", None) and d.envoyee_le is not None
    assert envoi.messages[0]["Reply-To"] == "r@ex.fr"


def test_envoi_en_echec_garde_la_demande(session, config):
    d = _enregistree(session)
    assert envoyer_demande(session, d, config, FauxEnvoi(TimeoutError("trop lent"))) is False
    session.expire_all()
    (en_base,) = session.scalars(select(DemandeContact)).all()
    assert en_base.statut == "echec" and en_base.erreur == "TimeoutError: trop lent"


def test_envoi_non_configure(session, monkeypatch):
    monkeypatch.delenv("CV_SMTP_HOTE", raising=False)
    config = Config()
    d = _enregistree(session)
    assert envoyer_demande(session, d, config, EnvoiSMTP(config)) is False
    assert d.erreur.startswith("EnvoiNonConfigure")


class FauxSMTP:
    instances = []

    def __init__(self, hote, port, timeout, context=None):
        self.appels, self.contextes = [("connexion", hote, port, timeout)], [context]
        FauxSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.appels.append(("fermeture",))

    def starttls(self, context=None):
        self.appels.append(("starttls",))
        self.contextes.append(context)

    def login(self, utilisateur, mot_de_passe):
        self.appels.append(("login", utilisateur, mot_de_passe))

    def send_message(self, message):
        self.appels.append(("envoi", message["Subject"]))


def test_transport_smtp(config, monkeypatch):
    monkeypatch.setenv("CV_SMTP_UTILISATEUR", "u")
    monkeypatch.setenv("CV_SMTP_MOT_DE_PASSE", "p")
    monkeypatch.setattr(courriel.smtplib, "SMTP", FauxSMTP)
    FauxSMTP.instances.clear()
    config = Config()
    EnvoiSMTP(config).envoyer(construire_message(_demande(), config))
    assert FauxSMTP.instances[0].appels == [
        ("connexion", "smtp.test.invalid", 587, 10), ("starttls",), ("login", "u", "p"),
        ("envoi", "[CV · lead-tech] Demande de contact — Alice (ACME)"), ("fermeture",)]
    _verifie(FauxSMTP.instances[0].contextes[1])


def _verifie(contexte):
    # Sans contexte, smtplib chiffre sans vérifier le certificat : le mot de passe
    # partirait chez n'importe quel intermédiaire.
    assert isinstance(contexte, ssl.SSLContext)
    assert contexte.verify_mode == ssl.CERT_REQUIRED and contexte.check_hostname


def test_transport_smtp_ssl_verifie(config, monkeypatch):
    monkeypatch.setenv("CV_SMTP_TLS", "ssl")
    monkeypatch.setattr(courriel.smtplib, "SMTP_SSL", FauxSMTP)
    FauxSMTP.instances.clear()
    config = Config()
    EnvoiSMTP(config).envoyer(construire_message(_demande(), config))
    _verifie(FauxSMTP.instances[0].contextes[0])


def test_login_sans_chiffrement_refuse(monkeypatch):
    monkeypatch.setenv("CV_SMTP_TLS", "aucun")
    monkeypatch.setenv("CV_SMTP_UTILISATEUR", "u")
    with pytest.raises(ValueError):
        Config()


def test_transport_smtp_sans_tls_ni_login(config, monkeypatch):
    monkeypatch.setenv("CV_SMTP_TLS", "aucun")
    monkeypatch.setenv("CV_SMTP_PORT", "25")
    monkeypatch.setattr(courriel.smtplib, "SMTP", FauxSMTP)
    FauxSMTP.instances.clear()
    config = Config()
    EnvoiSMTP(config).envoyer(construire_message(_demande(), config))
    assert [a[0] for a in FauxSMTP.instances[0].appels] == ["connexion", "envoi", "fermeture"]
    assert FauxSMTP.instances[0].appels[0][2] == 25


def test_smtp_tls_invalide_refuse(monkeypatch):
    monkeypatch.setenv("CV_SMTP_TLS", "oui")
    with pytest.raises(ValueError):
        Config()


@pytest.mark.parametrize("statut, age, attendu", [
    ("echec", timedelta(0), True), ("envoyee", timedelta(days=1), False),
    ("en_attente", timedelta(minutes=1), False), ("en_attente", timedelta(minutes=3), True)])
def test_renvoyable(statut, age, attendu):
    assert renvoyable(_demande(statut=statut, cree_le=T - age), T) is attendu


def test_message_de_test(config):
    m = message_de_test(config, T)
    assert (m["To"], m["From"], m["Subject"]) == ("dest@test.invalid", "cv@nanodeus.com",
                                                 "[CV] Email de test")
    assert m["Reply-To"] is None and "18/10/2026 09:05 UTC" in m.get_content()


def test_domaine_accentue_converti(config):
    # Un domaine accentué part en punycode : en clair, il ferait un en-tête invalide.
    formulaire, erreurs = valider({**OK, "email": "r@exémple.fr"})
    assert erreurs == {} and formulaire.email == "r@xn--exmple-cva.fr"
    assert "Reply-To: r@xn--exmple-cva.fr" in construire_message(
        _demande(email=formulaire.email), config).as_string()
