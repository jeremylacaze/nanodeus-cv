"""Configuration lue dans l'environnement, au démarrage."""
import os
import re
from pathlib import Path

ROLES = ("public", "admin")
MODES_TLS = ("starttls", "ssl", "aucun")


class Config:
    def __init__(self):
        self.DATA_DIR = Path(os.environ.get("CV_DATA_DIR", "./data"))
        self.ROLE = os.environ.get("CV_ROLE", "public")
        if self.ROLE not in ROLES:
            raise ValueError(f"CV_ROLE inconnu : {self.ROLE!r}")
        self.SECRET_KEY = os.environ.get("SECRET_KEY", "dev-uniquement")
        # Secret serveur combiné au sel du jour pour les empreintes (cv/journal.py).
        self.SEL_HMAC = os.environ.get("CV_SEL_HMAC", "dev-uniquement")
        self.TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
        # Adresse canonique (og:url) : sans elle, l'en-tête Host de la requête ferait foi.
        self.URL_PUBLIQUE = os.environ.get("CV_URL_PUBLIQUE", "").rstrip("/")
        if self.URL_PUBLIQUE and not re.fullmatch(r"https?://[^/\s]+", self.URL_PUBLIQUE):
            raise ValueError(f"CV_URL_PUBLIQUE invalide : {self.URL_PUBLIQUE!r}")
        # Envoi des demandes de contact : SMTP générique (Brevo, ou tout autre relais).
        self.SMTP_HOTE = os.environ.get("CV_SMTP_HOTE", "")
        self.SMTP_PORT = int(os.environ.get("CV_SMTP_PORT", "587"))
        self.SMTP_UTILISATEUR = os.environ.get("CV_SMTP_UTILISATEUR", "")
        self.SMTP_MOT_DE_PASSE = os.environ.get("CV_SMTP_MOT_DE_PASSE", "")
        self.SMTP_TLS = os.environ.get("CV_SMTP_TLS", "starttls")
        if self.SMTP_TLS not in MODES_TLS:
            raise ValueError(f"CV_SMTP_TLS inconnu : {self.SMTP_TLS!r}")
        self.EMAIL_EXPEDITEUR = os.environ.get("CV_EMAIL_EXPEDITEUR", "cv@nanodeus.com")
        # Boîte perso de Jeremy : posée sur le serveur seulement, jamais dans le dépôt.
        self.EMAIL_DESTINATAIRE = os.environ.get("CV_EMAIL_DESTINATAIRE", "")

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.DATA_DIR / 'cv.sqlite3'}"
