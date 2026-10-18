"""Configuration lue dans l'environnement, au démarrage."""
import os
import re
from ipaddress import ip_network
from pathlib import Path

ROLES = ("public", "admin")
MODES_TLS = ("starttls", "ssl", "aucun")
# Tailscale (IPv4 CGNAT et IPv6 ULA du tailnet), plus le loopback pour ./dev.sh.
RESEAUX_PAR_DEFAUT = "100.64.0.0/10,fd7a:115c:a1e0::/48,127.0.0.0/8,::1/128"


def lire_reseaux(texte: str) -> tuple:
    """Réseaux CIDR séparés par des virgules ; lève ValueError sur une valeur invalide
    (y compris une adresse d'hôte comme 100.64.0.7/10, sans doute une faute de frappe)."""
    return tuple(ip_network(morceau.strip(), strict=True)
                 for morceau in texte.split(",") if morceau.strip())


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
        if self.ROLE == "admin" and self.TRUST_PROXY:
            # Sans proxy devant l'admin, un X-Forwarded-For forgé contournerait le
            # contrôle d'adresse source.
            raise ValueError("TRUST_PROXY=1 est interdit en rôle admin")
        # Adresses sources admises par l'admin ; une chaîne vide coupe le contrôle.
        self.ADMIN_RESEAUX = lire_reseaux(os.environ.get("CV_ADMIN_RESEAUX",
                                                         RESEAUX_PAR_DEFAUT))
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
        if self.SMTP_TLS == "aucun" and self.SMTP_UTILISATEUR:
            raise ValueError("CV_SMTP_TLS=aucun : le mot de passe SMTP circulerait en clair")
        self.EMAIL_EXPEDITEUR = os.environ.get("CV_EMAIL_EXPEDITEUR", "cv@nanodeus.com")
        # Boîte perso de Jeremy : posée sur le serveur seulement, jamais dans le dépôt.
        self.EMAIL_DESTINATAIRE = os.environ.get("CV_EMAIL_DESTINATAIRE", "")

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.DATA_DIR / 'cv.sqlite3'}"
