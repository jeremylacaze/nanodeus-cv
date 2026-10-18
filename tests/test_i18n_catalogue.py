"""Catalogue anglais : complet, sans entrée devinée, aligné sur le code.

C'est ce test qui empêche de livrer une chaîne marquée puis oubliée. En cas
d'échec : `python scripts/i18n.py update`, puis traduire les msgstr vides et
relire (puis retirer) les `#, fuzzy` de translations/en/LC_MESSAGES/messages.po."""
import re
import subprocess
import sys
from pathlib import Path

from babel.messages.pofile import read_po

RACINE = Path(__file__).resolve().parent.parent
PO = RACINE / "translations" / "en" / "LC_MESSAGES" / "messages.po"
_VAR = re.compile(r"%\((\w+)\)[sd]")


def _lire(chemin):
    with chemin.open("rb") as f:
        return [m for m in read_po(f) if m.id]


def _cle(m):
    return m.id if isinstance(m.id, str) else m.id[0]


def _formes(m):
    return list(m.string) if m.pluralizable else [m.string]


def test_toutes_les_entrees_sont_traduites():
    assert [_cle(m) for m in _lire(PO) if not all(_formes(m))] == []


def test_aucune_entree_fuzzy():
    assert [_cle(m) for m in _lire(PO) if m.fuzzy] == []


def test_variables_identiques_entre_msgid_et_msgstr():
    fautives = []
    for m in _lire(PO):
        ids = [m.id] if isinstance(m.id, str) else list(m.id)
        attendues = set(_VAR.findall(ids[-1])) | set(_VAR.findall(ids[0]))
        for forme in _formes(m):
            if forme and set(_VAR.findall(forme)) != attendues:
                fautives.append(_cle(m))
    assert fautives == []


def test_catalogue_aligne_sur_le_code(tmp_path):
    pot = tmp_path / "messages.pot"
    subprocess.run([sys.executable, str(RACINE / "scripts" / "i18n.py"),
                    "extract", "--sortie", str(pot)], check=True, cwd=RACINE)
    extraites = {_cle(m) for m in _lire(pot)}
    presentes = {_cle(m) for m in _lire(PO)}
    assert extraites - presentes == set(), "chaînes marquées absentes du .po"
    assert presentes - extraites == set(), "entrées obsolètes dans le .po"
