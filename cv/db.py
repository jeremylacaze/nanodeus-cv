"""Moteur SQLite (mode WAL, clés étrangères actives) et fabrique de sessions."""
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def creer_moteur(url: str) -> Engine:
    moteur = create_engine(url)

    @event.listens_for(moteur, "connect")
    def _pragmas(connexion, _):
        # WAL : le service public écrit (visites) pendant que l'admin édite.
        curseur = connexion.cursor()
        curseur.execute("PRAGMA journal_mode=WAL")
        curseur.execute("PRAGMA foreign_keys=ON")
        curseur.close()

    return moteur


def fabrique_sessions(moteur: Engine) -> sessionmaker:
    return sessionmaker(moteur, expire_on_commit=False)
