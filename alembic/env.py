"""Environnement Alembic : base désignée par cv.config.Config."""
from alembic import context

from cv.config import Config
from cv.db import Base, creer_moteur
import cv.models  # noqa: F401  (enregistre les tables)

cible = Base.metadata


def run_migrations_online():
    config = Config()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    moteur = creer_moteur(config.DATABASE_URL)
    with moteur.connect() as connexion:
        # render_as_batch : SQLite ne sait pas modifier une colonne en place.
        context.configure(connection=connexion, target_metadata=cible,
                          render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
