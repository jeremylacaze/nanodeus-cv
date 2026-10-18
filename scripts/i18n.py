#!/usr/bin/env python3
"""Outillage des traductions de l'interface (Babel).

  python scripts/i18n.py extract [--sortie F]  textes marqués → translations/messages.pot
  python scripts/i18n.py update                extract, puis fusion dans chaque .po
                                               (entrées obsolètes retirées)
  python scripts/i18n.py compile               .po → .mo (aussi fait au démarrage de l'app)

Après `update` : traduire les msgstr vides de translations/en/LC_MESSAGES/messages.po
et relire les entrées `#, fuzzy` (puis retirer la marque) ; le test
tests/test_i18n_catalogue.py refuse les deux.

Le contenu du CV (postes, missions…) n'est pas ici : il est saisi dans l'admin,
en deux langues. Ce catalogue ne couvre que les textes de l'interface.
"""
import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TRADUCTIONS = RACINE / "translations"
POT = TRADUCTIONS / "messages.pot"
MOTS_CLES = ["_", "gettext", "ngettext:1,2"]
DOSSIERS_IGNORES = ".* _* tests alembic docs scripts translations data"


def _pybabel(*args):
    from babel.messages.frontend import CommandLineInterface
    CommandLineInterface().run(["pybabel", "-q", *args])


def extract(sortie=POT):
    mots = [arg for k in MOTS_CLES for arg in ("-k", k)]
    _pybabel("extract", "-F", str(RACINE / "babel.cfg"),
             "--no-default-keywords", *mots,
             "--no-location", "--sort-output", "--no-wrap",
             "--ignore-dirs", DOSSIERS_IGNORES,
             "--project", "nanodeus-cv", "-o", str(sortie), str(RACINE))


def update():
    extract()
    # --no-fuzzy-matching : mieux vaut une entrée vide, que le test de complétude
    # signale, qu'une traduction devinée sur une chaîne voisine.
    _pybabel("update", "-i", str(POT), "-d", str(TRADUCTIONS),
             "--ignore-obsolete", "--no-wrap", "--no-fuzzy-matching")


def compile_():
    sys.path.insert(0, str(RACINE))
    from cv.langue import compiler_catalogues
    for mo in compiler_catalogues(TRADUCTIONS, force=True):
        print(f"compilé : {mo.relative_to(RACINE)}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = p.add_subparsers(dest="cmd", required=True)
    ex = sous.add_parser("extract")
    ex.add_argument("--sortie", type=Path, default=POT)
    sous.add_parser("update")
    sous.add_parser("compile")
    a = p.parse_args()
    if a.cmd == "extract":
        extract(a.sortie)
    elif a.cmd == "update":
        update()
    else:
        compile_()


if __name__ == "__main__":
    main()
