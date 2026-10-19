"""Copie de la base SQLite à chaud, pour la sauvegarde restic."""
import sqlite3
import subprocess
import sys

import pytest

from cv import sauvegarde
from cv.sauvegarde import copier_base


def _base_en_wal(chemin):
    connexion = sqlite3.connect(chemin)
    connexion.execute("PRAGMA journal_mode=WAL")
    # Sans checkpoint automatique, les écritures restent dans le fichier -wal.
    connexion.execute("PRAGMA wal_autocheckpoint=0")
    connexion.execute("CREATE TABLE t (x TEXT)")
    connexion.execute("INSERT INTO t VALUES ('dans le wal')")
    connexion.commit()
    return connexion


def test_copie_contient_les_ecritures_du_wal(tmp_path):
    source = tmp_path / "cv.sqlite3"
    connexion = _base_en_wal(source)  # reste ouverte : le WAL n'est pas reporté
    assert (tmp_path / "cv.sqlite3-wal").stat().st_size > 0
    destination = tmp_path / "copie" / "cv.sqlite3"
    copier_base(source, destination)
    connexion.close()
    copie = sqlite3.connect(destination)
    assert copie.execute("SELECT x FROM t").fetchall() == [("dans le wal",)]
    assert copie.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    copie.close()


def test_copie_atomique_sans_tmp(tmp_path, monkeypatch):
    source = tmp_path / "cv.sqlite3"
    _base_en_wal(source).close()
    destination = tmp_path / "copie" / "cv.sqlite3"

    def echec(*args):
        raise OSError("disque plein")
    monkeypatch.setattr(sauvegarde.os, "replace", echec)
    with pytest.raises(OSError):
        copier_base(source, destination)
    assert list(destination.parent.iterdir()) == []


def test_source_absente_code_1(tmp_path):
    absente, destination = tmp_path / "absente.sqlite3", tmp_path / "copie.sqlite3"
    r = subprocess.run([sys.executable, "-m", "cv.sauvegarde", str(absente), str(destination)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and r.stderr.strip()
    assert not absente.exists() and not destination.exists()
