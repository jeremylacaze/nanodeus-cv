"""Scripts du serveur (deploy/*.sh), exécutés avec un faux `docker` en tête du PATH."""
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DEPLOY = RACINE / "deploy"
IMAGE = "ghcr.io/jeremylacaze/nanodeus-cv:" + "a" * 40
PRECEDENTE = "ghcr.io/jeremylacaze/nanodeus-cv:" + "b" * 40

# Note ses arguments, répond `cid` à `ps -q`, `$FAUX_ETAT` à l'état de santé et
# `running` à l'état du conteneur. `volume inspect` échoue si FAUX_VOLUME est vide.
FAUX_DOCKER = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAUX_JOURNAL"
case "$*" in
  *"volume inspect"*) [ -n "$FAUX_VOLUME" ] || exit 1 ;;
  *"ps -q"*) echo cid ;;
  *Health*) echo "$FAUX_ETAT" ;;
  *inspect*) echo running ;;
esac
exit 0
"""


def _executable(chemin: Path, contenu: str) -> None:
    chemin.write_text(contenu)
    chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def serveur(tmp_path):
    """Racine CV_ROOT avec un .env, et l'environnement qui met le faux docker en tête."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _executable(bin_ / "docker", FAUX_DOCKER)
    racine = tmp_path / "racine"
    racine.mkdir()
    env_fichier = racine / ".env"
    env_fichier.write_text(f"SECRET_KEY=garde-moi\nCV_IMAGE={PRECEDENTE}\nCV_PROD=1\n")
    env_fichier.chmod(0o600)
    journal = tmp_path / "docker.log"
    depot = tmp_path / "restic"
    depot.mkdir()
    (depot / "config").write_text("")
    env = {
        "CV_RESTIC_REPO": str(depot),
        "PATH": f"{bin_}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "CV_ROOT": str(racine),
        "FAUX_JOURNAL": str(journal),
        "FAUX_ETAT": "healthy",
        "FAUX_VOLUME": "1",
    }
    return {"racine": racine, "env": env, "journal": journal}


def _lancer(script: str, *arguments, env, entree_ssh=None):
    if entree_ssh is not None:
        env = {**env, "SSH_ORIGINAL_COMMAND": entree_ssh}
    return subprocess.run(["bash", str(DEPLOY / script), *arguments], env=env,
                          capture_output=True, text=True, timeout=60)


def _appels(serveur) -> str:
    journal = serveur["journal"]
    return journal.read_text() if journal.exists() else ""


@pytest.mark.parametrize("image", [
    "ghcr.io/jeremylacaze/nanodeus-cv:latest", "ghcr.io/jeremylacaze/nanodeus-cv:abc123",
    "ghcr.io/autre/nanodeus-cv:" + "a" * 40, "ghcr.io/jeremylacaze/nanodeus-cv"])
def test_deploy_refuse_les_tags_mouvants(image, serveur):
    resultat = _lancer("deploy.sh", image, env=serveur["env"])
    assert resultat.returncode == 1
    assert _appels(serveur) == ""


def test_deploy_sans_env(serveur):
    (serveur["racine"] / ".env").unlink()
    resultat = _lancer("deploy.sh", IMAGE, env=serveur["env"])
    assert resultat.returncode == 1 and ".env" in resultat.stderr
    assert _appels(serveur) == ""


def test_deploy_reussi_garde_les_secrets(serveur):
    resultat = _lancer("deploy.sh", IMAGE, env=serveur["env"])
    assert resultat.returncode == 0, resultat.stderr
    env_fichier = serveur["racine"] / ".env"
    lignes = env_fichier.read_text().splitlines()
    assert "SECRET_KEY=garde-moi" in lignes and "CV_PROD=1" in lignes
    assert [ligne for ligne in lignes if ligne.startswith("CV_IMAGE=")] == [f"CV_IMAGE={IMAGE}"]
    assert stat.S_IMODE(env_fichier.stat().st_mode) == 0o600
    assert [f.name for f in serveur["racine"].iterdir() if f.name.startswith(".env.")] == []
    appels = _appels(serveur)
    assert appels.index(f"pull {IMAGE}") < appels.index("up -d")


def test_deploy_malsain_propose_le_retour(serveur):
    serveur["env"]["FAUX_ETAT"] = "unhealthy"
    resultat = _lancer("deploy.sh", IMAGE, env=serveur["env"])
    assert resultat.returncode == 1
    assert f"deploy.sh {PRECEDENTE}" in resultat.stderr
    # Le retour arrière est proposé, jamais exécuté.
    assert f"pull {PRECEDENTE}" not in _appels(serveur)


def test_backup_premiere_mise_en_ligne(serveur, tmp_path):
    (tmp_path / "mdp").write_text("x")
    serveur["env"].update(FAUX_VOLUME="", CV_RESTIC_PASSWORD_FILE=str(tmp_path / "mdp"))
    resultat = _lancer("backup.sh", "--db-only", env=serveur["env"])
    assert resultat.returncode == 0, resultat.stderr
    assert "Première mise en ligne" in resultat.stdout
    assert "restic" not in _appels(serveur)


def test_backup_sans_mot_de_passe(serveur, tmp_path):
    serveur["env"]["CV_RESTIC_PASSWORD_FILE"] = str(tmp_path / "absent")
    resultat = _lancer("backup.sh", "--db-only", env=serveur["env"])
    assert resultat.returncode == 1
    assert "restic" not in _appels(serveur)


@pytest.mark.parametrize("commande", [
    "", "bash", "/opt/x/deploy.sh", "backup.sh", "backup.sh --db-only; id",
    "deploy.sh ghcr.io/jeremylacaze/nanodeus-cv:latest",
    "deploy.sh ghcr.io/jeremylacaze/nanodeus-cv:" + "a" * 40 + " x"])
def test_ssh_refuse(commande, serveur):
    resultat = _lancer("ssh-commande.sh", env=serveur["env"], entree_ssh=commande)
    assert resultat.returncode == 1 and "commande refusée" in resultat.stderr


@pytest.mark.parametrize("commande", [
    "{racine}/backup.sh", "{racine}/backup.sh --db-only; id",
    "{racine}/deploy.sh " + IMAGE + " x", "{racine}/deploy.sh $(id)"])
def test_ssh_refuse_les_chemins_absolus_detournes(commande, serveur):
    entree = commande.format(racine=serveur["racine"])
    resultat = _lancer("ssh-commande.sh", env=serveur["env"], entree_ssh=entree)
    assert resultat.returncode == 1 and "commande refusée" in resultat.stderr


def test_ssh_accepte_backup_et_deploy(serveur, tmp_path):
    racine, recus = serveur["racine"], tmp_path / "recus"
    for nom in ("backup.sh", "deploy.sh"):
        _executable(racine / nom, f'#!/bin/sh\necho "{nom} $*" >> "{recus}"\n')
    for commande in (f"{racine}/backup.sh --db-only", f"{racine}/deploy.sh {IMAGE}"):
        resultat = _lancer("ssh-commande.sh", env=serveur["env"], entree_ssh=commande)
        assert resultat.returncode == 0, resultat.stderr
    assert recus.read_text().splitlines() == ["backup.sh --db-only", f"deploy.sh {IMAGE}"]


def test_shellcheck():
    scripts = sorted(DEPLOY.glob("*.sh")) + [RACINE / "scripts" / "fumee-image.sh"]
    assert len(scripts) == 4
    shellcheck = Path(sys.executable).parent / "shellcheck"
    resultat = subprocess.run([str(shellcheck), *map(str, scripts)],
                              capture_output=True, text=True)
    assert resultat.returncode == 0, resultat.stdout
