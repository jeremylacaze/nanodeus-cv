"""Copie cohérente de la base SQLite, prise à chaud pour la sauvegarde restic.

Copier le fichier tel quel perdrait les écritures encore dans le journal WAL, ou
saisirait une page à moitié écrite. L'API de sauvegarde de SQLite lit une image
cohérente de la base, WAL compris, sans arrêter les services.

    python -m cv.sauvegarde <source> <destination>
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


def copier_base(source: Path, destination: Path) -> None:
    """Copie `source` dans `destination`, qui n'apparaît qu'une fois complète."""
    # Lecture seule : une source absente lève une erreur au lieu de créer une base vide.
    origine = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descripteur, temporaire = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
        os.close(descripteur)
        try:
            cible = sqlite3.connect(temporaire)
            try:
                origine.backup(cible)
            finally:
                cible.close()
            os.replace(temporaire, destination)
        except BaseException:
            Path(temporaire).unlink(missing_ok=True)
            raise
    finally:
        origine.close()


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print("usage : python -m cv.sauvegarde <source> <destination>", file=sys.stderr)
        return 2
    source, destination = Path(arguments[0]), Path(arguments[1])
    if not source.is_file():
        print(f"Base introuvable : {source}", file=sys.stderr)
        return 1
    copier_base(source, destination)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
