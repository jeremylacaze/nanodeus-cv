"""Transport SMTP générique : changer de fournisseur n'est qu'une affaire de config."""
import smtplib
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
        classe = smtplib.SMTP_SSL if c.SMTP_TLS == "ssl" else smtplib.SMTP
        with classe(c.SMTP_HOTE, c.SMTP_PORT, timeout=DELAI) as smtp:
            if c.SMTP_TLS == "starttls":
                smtp.starttls()
            if c.SMTP_UTILISATEUR:
                smtp.login(c.SMTP_UTILISATEUR, c.SMTP_MOT_DE_PASSE)
            smtp.send_message(message)
