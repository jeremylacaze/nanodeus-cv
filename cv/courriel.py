"""Transport SMTP générique : changer de fournisseur n'est qu'une affaire de config."""
import smtplib
import ssl
from email.message import EmailMessage

DELAI = 10  # secondes : l'envoi se fait pendant la requête du recruteur


class EnvoiNonConfigure(RuntimeError):
    """Hôte SMTP ou destinataire absent de la configuration."""


class EnvoiSMTP:
    def __init__(self, config):
        self.config = config

    def envoyer(self, message: EmailMessage) -> None:
        c = self.config
        if not c.SMTP_HOTE or not c.EMAIL_DESTINATAIRE:
            raise EnvoiNonConfigure("CV_SMTP_HOTE ou CV_EMAIL_DESTINATAIRE vide")
        # Contexte qui vérifie certificat et nom d'hôte : smtplib, sans lui, ne vérifie rien.
        contexte = ssl.create_default_context()
        if c.SMTP_TLS == "ssl":
            connexion = smtplib.SMTP_SSL(c.SMTP_HOTE, c.SMTP_PORT, timeout=DELAI,
                                         context=contexte)
        else:
            connexion = smtplib.SMTP(c.SMTP_HOTE, c.SMTP_PORT, timeout=DELAI)
        with connexion as smtp:
            if c.SMTP_TLS == "starttls":
                smtp.starttls(context=contexte)
            if c.SMTP_UTILISATEUR:
                smtp.login(c.SMTP_UTILISATEUR, c.SMTP_MOT_DE_PASSE)
            smtp.send_message(message)
