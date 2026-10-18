"""Configuration lue dans l'environnement, au démarrage."""
import os
from pathlib import Path

ROLES = ("public", "admin")


class Config:
    def __init__(self):
        self.DATA_DIR = Path(os.environ.get("CV_DATA_DIR", "./data"))
        self.ROLE = os.environ.get("CV_ROLE", "public")
        if self.ROLE not in ROLES:
            raise ValueError(f"CV_ROLE inconnu : {self.ROLE!r}")
        self.SECRET_KEY = os.environ.get("SECRET_KEY", "dev-uniquement")
        self.TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.DATA_DIR / 'cv.sqlite3'}"
