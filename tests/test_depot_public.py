"""Garde du dépôt public : aucune IP, aucun email, aucun téléphone hors des valeurs de test.

Le dépôt est lu par des recruteurs : une coordonnée ou l'adresse du serveur qui s'y
glisse y reste pour toujours, l'historique compris. Les fichiers suivis par git sont
parcourus ; CV_DEPOT_EN_PLUS (chemins séparés par `os.pathsep`) en ajoute d'autres,
non suivis, pour éprouver le test sans rien commiter.
"""
import ipaddress
import os
import re
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BINAIRES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2", ".ttf",
            ".otf", ".pdf", ".mo"}

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Une version épinglée à quatre composantes (`shellcheck-py==0.11.0.1`) n'est pas une IP.
VERSION = re.compile(r"==\s*(?:\d+\.){3}\d+")
IPV4_ADMISES = {"0.0.0.0", "10.0.0.0", "172.16.0.0", "192.168.0.0", "100.64.0.0",
                "100.127.255.254", "100.128.0.1", "100.64.0.5", "100.64.0.7", "172.17.0.1"}
# Boucle locale et plages réservées à la documentation (RFC 5737).
RESEAUX_ADMIS = [ipaddress.ip_network(r) for r in
                 ("127.0.0.0/8", "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]

EMAIL = re.compile(r"[\w.%+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)
EMAILS_ADMIS = {"cv@nanodeus.com", "noreply@anthropic.com",
                "254094035+jeremylacaze@users.noreply.github.com"}
# Domaines des valeurs de test ; li.org vient de l'en-tête que Babel pose dans les .po.
DOMAINES_ADMIS = {"test.invalid", "exemple.test", "example.com", "ex.fr", "b.fr", "c.fr",
                  "d.fr", "y.fr", "exémple.fr", "xn--exmple-cva.fr", "li.org"}

TELEPHONE = re.compile(r"(?:\+33[ .]?|\b0)[1-9](?:[ .]?\d{2}){4}\b")
TELEPHONES_ADMIS = {"+33 6 99 88 77 66"}


def _fichiers() -> list[Path]:
    suivis = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE, capture_output=True,
                            check=True).stdout.decode().split("\0")
    en_plus = [p for p in os.environ.get("CV_DEPOT_EN_PLUS", "").split(os.pathsep) if p]
    chemins = [RACINE / p for p in suivis if p] + [Path(p) for p in en_plus]
    return [c for c in chemins if c.suffix.lower() not in BINAIRES and c.is_file()]


def _occurrences(motif: re.Pattern, nettoyer=lambda texte: texte) -> list[tuple[str, str]]:
    trouvees = []
    for chemin in _fichiers():
        texte = nettoyer(chemin.read_text(errors="replace"))
        trouvees += [(str(chemin), m.group()) for m in motif.finditer(texte)]
    return trouvees


def _ipv4_admise(adresse: str) -> bool:
    try:
        ip = ipaddress.ip_address(adresse)
    except ValueError:
        return True  # 999.1.2.3 : pas une adresse
    return adresse in IPV4_ADMISES or any(ip in reseau for reseau in RESEAUX_ADMIS)


def test_aucune_ipv4_hors_liste():
    fautives = [(f, ip) for f, ip in _occurrences(IPV4, lambda t: VERSION.sub("", t))
                if not _ipv4_admise(ip)]
    assert fautives == []


def test_aucun_email_hors_liste():
    fautifs = [(f, e) for f, e in _occurrences(EMAIL)
               if e.lower() not in EMAILS_ADMIS
               and e.lower().rsplit("@", 1)[1] not in DOMAINES_ADMIS]
    assert fautifs == []


def test_aucun_telephone_hors_liste():
    fautifs = [(f, t) for f, t in _occurrences(TELEPHONE) if t not in TELEPHONES_ADMIS]
    assert fautifs == []
