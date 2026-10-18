"""Demande de contact : validation, limites anti-abus, message et envoi.

La demande est toujours enregistrée avant l'envoi : si le relais SMTP est en
panne, elle reste en base en « echec » et l'admin pourra la renvoyer.
"""
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask_babel import gettext as _
from sqlalchemy import func, select

from cv.journal import maintenant_utc
from cv.models import DemandeContact

MAX_EMAIL, MAX_MESSAGE, MAX_LIGNE = 254, 2000, 100
# Par visiteur : 3 par heure et 10 par jour ; au total : 50 par jour.
LIMITES = ((timedelta(hours=1), 3, True), (timedelta(days=1), 10, True),
           (timedelta(days=1), 50, False))
_INTERDIT = r"@\s<>()\[\],;:\"\\\x00-\x1f\x7f"
_EMAIL = re.compile(f"[^{_INTERDIT}]+@[^{_INTERDIT}]+\\.[^{_INTERDIT}]+")
# Contrôles C0 et C1, plus les séparateurs de ligne Unicode : str.splitlines() coupe
# sur chacun, et email.policy refuserait alors l'en-tête au moment de l'envoi.
CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")


@dataclass
class Formulaire:
    email: str = ""
    message: str = ""
    nom: str = ""
    entreprise: str = ""
    piege: str = ""


def valider(donnees: Mapping[str, str]) -> tuple[Formulaire, dict[str, str]]:
    """Formulaire nettoyé et erreurs par champ (textes affichables, traduits)."""
    f = Formulaire(**{champ: (donnees.get(cle) or "").strip() for champ, cle in (
        ("email", "email"), ("message", "message"), ("nom", "nom"),
        ("entreprise", "entreprise"), ("piege", "site_web"))})
    # Un saut de ligne vaut un caractère, comme pour le maxlength du navigateur.
    f.message = f.message.replace("\r\n", "\n").replace("\r", "\n")
    erreurs = {}
    if len(f.email) > MAX_EMAIL or not _EMAIL.fullmatch(f.email):
        erreurs["email"] = _("Indiquez une adresse email valide.")
    if not f.message:
        erreurs["message"] = _("Écrivez un message.")
    elif len(f.message) > MAX_MESSAGE:
        erreurs["message"] = _("Le message dépasse %(n)s caractères.", n=MAX_MESSAGE)
    for champ in ("nom", "entreprise"):
        valeur = getattr(f, champ)
        if len(valeur) > MAX_LIGNE or CONTROLE.search(valeur):
            erreurs[champ] = _("Une seule ligne, %(n)s caractères au plus.", n=MAX_LIGNE)
    return f, erreurs


def limite_atteinte(session, empreinte: str, maintenant: datetime) -> bool:
    for duree, plafond, par_visiteur in LIMITES:
        requete = (select(func.count()).select_from(DemandeContact)
                   .where(DemandeContact.cree_le > maintenant - duree))
        if par_visiteur:
            requete = requete.where(DemandeContact.empreinte == empreinte)
        if session.scalar(requete) >= plafond:
            return True
    return False


def enregistrer(session, formulaire: Formulaire, version_slug: str, langue: str,
                empreinte: str, maintenant: datetime) -> DemandeContact:
    demande = DemandeContact(
        cree_le=maintenant, email=formulaire.email, nom=formulaire.nom,
        entreprise=formulaire.entreprise, message=formulaire.message,
        version_slug=version_slug, langue=langue, empreinte=empreinte)
    session.add(demande)
    session.commit()
    return demande


def construire_message(demande: DemandeContact, config) -> EmailMessage:
    """Email à Jeremy : « Répondre » écrit directement au recruteur (Reply-To)."""
    qui = demande.nom or demande.email
    if demande.entreprise:
        qui += f" ({demande.entreprise})"
    m = EmailMessage()
    m["From"] = config.EMAIL_EXPEDITEUR
    m["To"] = config.EMAIL_DESTINATAIRE
    m["Reply-To"] = demande.email
    m["Subject"] = f"[CV · {demande.version_slug}] Demande de contact — {qui}"
    m.set_content(
        f"{demande.message}\n\n"
        "—\n"
        f"Nom : {demande.nom or '-'}\n"
        f"Entreprise : {demande.entreprise or '-'}\n"
        f"Email : {demande.email}\n"
        f"Version : {demande.version_slug} ({demande.langue})\n"
        f"Date : {demande.cree_le:%d/%m/%Y %H:%M} UTC\n\n"
        "« Répondre » écrit directement à cette personne.\n")
    return m


def envoyer_demande(session, demande: DemandeContact, config, envoi) -> bool:
    """Envoie la demande et note le résultat en base. Ne lève jamais."""
    try:
        envoi.envoyer(construire_message(demande, config))
    except Exception as exc:  # noqa: BLE001 — l'échec est noté, l'admin renverra
        demande.statut, demande.erreur = "echec", f"{exc.__class__.__name__}: {exc}"[:300]
    else:
        demande.statut, demande.erreur, demande.envoyee_le = "envoyee", None, maintenant_utc()
    session.commit()
    return demande.statut == "envoyee"
