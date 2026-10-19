# Plan 4 — Docker, CI et mise en ligne sur le netcup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** mettre cv.nanodeus.com en ligne depuis une image `ghcr.io/jeremylacaze/nanodeus-cv:<sha>`,
bâtie et vérifiée par GitHub Actions, déployée par SSH, sauvegardée chaque nuit et avant
chaque déploiement.

**Architecture :** une image, trois services Compose (`migrate`, `public`, `admin`) sur un
volume nommé. `public` est derrière Traefik (réseau `proxy`), `admin` publie son port sur
l'IP tailnet uniquement. Les scripts serveur (`deploy.sh`, `backup.sh`, `ssh-commande.sh`)
reprennent ceux de ReadLN, en plus court. La sauvegarde écrit dans le dépôt restic existant
de ReadLN, sous un hôte restic distinct.

**Tech Stack :** Docker (python:3.14-slim, gunicorn), Docker Compose, Traefik v3 (déjà en
place), GitHub Actions, GHCR, restic (image officielle épinglée), systemd.

**Spec :** `docs/superpowers/specs/2026-10-18-cv-pipeline-design.md` (§ 2, 9, 11, 13).

## Global Constraints

- **Le tag est le contrat :** image `ghcr.io/jeremylacaze/nanodeus-cv:<sha de 40 caractères>`,
  jamais `latest` ; `deploy.sh` refuse tout autre tag.
- **Dépôt public :** ni téléphone, ni email personnel, ni photo, ni IP du serveur dans le
  code, la doc ou l'historique. L'IP tailnet s'écrit `<ip-tailnet>`, l'hôte `<netcup>`.
  Seules adresses email admises : `cv@nanodeus.com` et l'adresse noreply des commits.
- **Les secrets naissent et restent sur le serveur** (`/opt/nanodeus-cv/.env`, `chmod 600`).
  Ils ne passent jamais par un commit, un rapport ou un terminal ; `docker compose config`
  se redirige vers `/dev/null`.
- **Ne jamais toucher à `/opt/readln/restic-password`** : il est seulement monté en lecture.
- **L'admin n'est jamais publiée sur Internet :** ni route Traefik, ni port public. Elle
  écoute sur `<ip-tailnet>:8780` (variable `CV_ADMIN_ECOUTE` du `.env`, port libre :
  3000, 8090 et 9000 sont déjà pris).
- **`TRUST_PROXY=1` sur `public` seulement**, posé dans `compose.yml`, jamais dans le `.env`
  partagé : `cv/config.py` refuse de démarrer l'admin avec.
- Routeurs et services Traefik nommés `nanodeus-cv` (le routeur `cv` appartient à l'ancien
  `/opt/cv`). Labels : `Host(\`cv.nanodeus.com\`)`, entrypoint `websecure`, certresolver `le`.
- Les fichiers de `/opt/nanodeus-cv/` ne sont pas déployés par la pipeline : `scp` manuel,
  documenté.
- Actions GitHub épinglées par SHA (les mêmes que ReadLN), jetons en lecture seule par
  défaut, `persist-credentials: false`.
- Code, commentaires et commits en français ; `FEAT(scope):`, `CHORE:`… ; commits avec
  `git -c user.email=254094035+jeremylacaze@users.noreply.github.com commit`.
- Aucun push, tag, secret GitHub ou geste sur le serveur hors de la tâche 6, et dans la
  tâche 6, chaque geste extérieur se fait après accord de Jeremy.

## Review Focus

1. **Polices de l'image ≠ polices du Mac :** le PDF vérifié sur une page avec Helvetica Neue
   peut déborder sur deux pages avec DejaVu. Le test de fumée compte les pages de chaque
   version, en FR et en EN (tâche 2).
2. **Système de fichiers en lecture seule :** fontconfig, gunicorn et la compilation des
   `.mo` écrivent au démarrage. Le test de fumée tourne avec le même `read_only` que la
   prod et génère un PDF (tâche 2).
3. **Volume neuf :** le premier démarrage crée la base dans un volume vide ; l'UID 1000 doit
   pouvoir y écrire (tâche 2, fumée sur volume vierge).
4. **`.env` réécrit par `deploy.sh` :** une erreur de lecture ne doit jamais le réduire à
   la seule ligne `CV_IMAGE`. Testé, avec les droits 600 (tâche 3).
5. **Copie d'une base en WAL :** des écritures pas encore reportées dans le fichier
   principal doivent figurer dans la copie (tâche 1).

---

### Task 1 : l'application prête pour la production

**Files :**
- Modify : `cv/config.py`, `cv/app.py`, `requirements.txt`
- Create : `cv/sauvegarde.py`
- Test : `tests/test_config.py` (nouveau), `tests/test_public.py`, `tests/test_sauvegarde.py` (nouveau)

**Interfaces :**
- Produces :
  - `CV_PROD=1` : `Config()` lève `ValueError` si `SECRET_KEY` ou `CV_SEL_HMAC` valent
    `dev-uniquement` (ou sont vides), ou si `CV_URL_PUBLIQUE` est absente.
  - Route `GET /sante` en rôle public seulement : `200`, `text/plain`, corps `ok`, après un
    `SELECT 1` ; aucun journal de visite, aucun cookie. Absente en rôle admin (404).
  - `copier_base(source: Path, destination: Path) -> None` dans `cv/sauvegarde.py`, et
    `python -m cv.sauvegarde <source> <destination>` (code 1 et message sur stderr si la
    source n'existe pas).
  - `gunicorn` épinglé dans `requirements.txt` (26.2.0 ou la dernière au moment de
    l'implémentation).

- [ ] **Step 1 : tests en échec**

`tests/test_config.py` :

```python
def test_prod_refuse_les_secrets_de_dev(monkeypatch):  # paramétré : SECRET_KEY, CV_SEL_HMAC
    monkeypatch.setenv("CV_PROD", "1"); ...  # l'autre secret et l'URL sont valides
    with pytest.raises(ValueError, match=variable):
        Config()

def test_prod_exige_l_url_publique(monkeypatch): ...      # ValueError, match="CV_URL_PUBLIQUE"
def test_prod_complete_demarre(monkeypatch): ...           # Config() sans erreur
def test_hors_prod_les_defauts_restent(monkeypatch): ...   # CV_PROD absent : défauts de dev
```

`tests/test_public.py` :

```python
def test_sante_public(client):
    r = client.get("/sante")
    assert r.status_code == 200 and r.data == b"ok" and r.mimetype == "text/plain"
    assert "Set-Cookie" not in r.headers
    # compter les lignes de la table des visites avant et après : aucune ajoutée

def test_sante_absente_en_admin(admin):
    assert admin.get("/sante").status_code == 404
```

`tests/test_sauvegarde.py` :

```python
def test_copie_contient_les_ecritures_du_wal(tmp_path):
    # base en WAL, une connexion garde le WAL ouvert après un INSERT validé
    # (pas de checkpoint) : la copie, ouverte à part, contient la ligne.
def test_copie_atomique_sans_tmp(tmp_path, monkeypatch):
    # os.replace qui échoue : aucun fichier .tmp dans le dossier de destination
def test_source_absente_code_1(tmp_path):
    # subprocess [sys.executable, "-m", "cv.sauvegarde", absente, dest] : code 1, stderr non vide,
    # destination non créée
```

- [ ] **Step 2 : lancer les tests**

Run : `.venv/bin/pytest -q tests/test_config.py tests/test_public.py tests/test_sauvegarde.py`
Expected : les nouveaux tests échouent (`ValueError` non levée, `/sante` en 404,
`cv.sauvegarde` introuvable).

- [ ] **Step 3 : implémenter**

- `cv/config.py` : `self.PROD = os.environ.get("CV_PROD") == "1"`, contrôles en fin
  d'`__init__`.
- `cv/app.py` : `/sante` enregistrée dans la branche `config.ROLE == "public"`.
- `cv/sauvegarde.py` : API `sqlite3.Connection.backup` (copie cohérente en ligne, WAL
  compris) vers un temporaire du dossier cible, puis `os.replace`. Réutiliser
  `ecrire_atomiquement` n'est pas possible (backup écrit dans un fichier), reprendre son
  motif (mkstemp, nettoyage sur `BaseException`). La source est ouverte en lecture seule
  (`file:…?mode=ro`, `uri=True`) : une source absente ne doit pas créer de base vide.
- `requirements.txt` : `gunicorn==<version>`.

- [ ] **Step 4 : suite complète et lint**

Run : `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected : tout passe (451 + nouveaux).

- [ ] **Step 5 : commit** — `FEAT(prod): mode production, sonde de santé et copie de la base`

---

### Task 2 : image Docker, Compose et test de fumée

**Files :**
- Create : `Dockerfile`, `.dockerignore`, `.hadolint.yaml`, `deploy/compose.yml`,
  `deploy/compose.fumee.yml`, `scripts/fumee-image.sh`

**Interfaces :**
- Consumes : `/sante`, `CV_PROD`, `python -m cv.sauvegarde` (tâche 1).
- Produces :
  - Image : utilisateur `1000`, `WORKDIR /app`, `/data` créé et possédé par 1000,
    `CV_DATA_DIR=/data`, `.mo` compilés au build, port 8000.
  - `deploy/compose.yml` : projet `name: nanodeus-cv`, volume `name: nanodeus-cv-donnees`
    monté sur `/data`, image `${CV_IMAGE:?}`, `env_file: .env`.
  - `scripts/fumee-image.sh <image>` : code 0 si toutes les vérifications passent.

- [ ] **Step 1 : écrire `scripts/fumee-image.sh` (le test) avant l'image**

Contrat du script (`set -euo pipefail`, nettoyage par `trap … EXIT` : `down -v` et dossier
temporaire) :
1. Dossier temporaire avec un `.env` : `CV_IMAGE=$1`, `CV_PROD=1`, `SECRET_KEY` et
   `CV_SEL_HMAC` aléatoires (`openssl rand -hex 32`), `CV_URL_PUBLIQUE=https://cv.nanodeus.com`,
   `CV_ADMIN_ECOUTE=127.0.0.1:18780`, `CV_ADMIN_HOTES=127.0.0.1`.
2. Crée le réseau `proxy` s'il manque (et le supprime à la fin s'il l'a créé).
3. `docker compose -f deploy/compose.yml -f deploy/compose.fumee.yml --project-directory <tmp> up -d`
   (le fichier fumée publie `public` sur `127.0.0.1:18010` et change le nom du projet et
   du volume en `nanodeus-cv-fumee`, pour ne jamais toucher un volume réel).
4. Attend `healthy` sur `public` (60 × 2 s), sinon affiche les journaux et échoue.
5. Vérifie, en échouant au premier écart avec un message clair :
   - `GET /` → 200, en-tête `Content-Security-Policy` présent, aucun `Set-Cookie` ;
   - `GET /admin/` sur public → 404 ;
   - `GET /devops.pdf`, `/en/devops.pdf`, `/lead-tech.pdf`, `/en/lead-tech.pdf` → 200,
     commence par `%PDF`, **une seule page** (compté avec
     `"${PYTHON:-python3}" -c 'import pypdf…'`) ;
   - admin : `docker compose exec -T admin python -c` qui appelle
     `http://127.0.0.1:8000/admin/` → 200 ; et le port publié `127.0.0.1:18780` répond ;
   - `docker compose exec -T public id -u` → `1000` ;
   - `docker compose exec -T public sh -c 'touch /app/x'` échoue (lecture seule).

- [ ] **Step 2 : lancer la fumée sans image**

Docker Desktop doit tourner (`open -a Docker`). Run : `scripts/fumee-image.sh nanodeus-cv:local`
Expected : échec (image introuvable).

- [ ] **Step 3 : écrire l'image et le Compose**

`Dockerfile`, sur le modèle de celui de ReadLN :
- `FROM python:3.14-slim` ;
- `apt-get install --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0
  libharfbuzz-subset0 fonts-dejavu-core` (sans build-essential, sans curl) ;
- `pip install --no-cache-dir -r requirements.txt` avant `COPY . .` (cache de couche) ;
- `python scripts/i18n.py compile`, `useradd -u 1000`, `mkdir /data && chown 1000 /data`,
  `USER 1000` ;
- `ENV CV_DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 XDG_CACHE_HOME=/tmp/cache` ;
- `CMD ["gunicorn", "-k", "gthread", "-w", "2", "--threads", "4", "--timeout", "60",
  "--worker-tmp-dir", "/dev/shm", "-b", "0.0.0.0:8000", "cv.app:create_app()"]`.
  Aucun `--access-logfile` : pas de journal d'accès, donc aucune IP dans les logs
  (spec § 7). Le timeout de 60 s couvre la génération d'un PDF.

`.dockerignore` : `.git`, `.venv`, `data`, `tests`, `docs`, `deploy`, `.github`,
`.superpowers`, caches, `*.mo`, `.env*`.

`.hadolint.yaml` : `failure-threshold: info`, `ignored: [DL3008]` (comme ReadLN).

`deploy/compose.yml` (valeurs fixées par la spec ; commentaires en français à ajouter) :

```yaml
name: nanodeus-cv

x-commun: &commun
  image: ${CV_IMAGE:?CV_IMAGE manquante dans .env}
  env_file: .env
  volumes: ["donnees:/data"]
  read_only: true
  tmpfs: ["/tmp"]
  security_opt: ["no-new-privileges:true"]
  cap_drop: [ALL]
  logging: {driver: json-file, options: {max-size: "10m", max-file: "3"}}

services:
  migrate:
    <<: *commun
    command: ["sh", "-c", "alembic upgrade head && flask --app cv.app amorcer"]
    restart: "no"
    network_mode: none
  public:
    <<: *commun
    restart: unless-stopped
    environment: {CV_ROLE: public, TRUST_PROXY: "1"}
    depends_on: {migrate: {condition: service_completed_successfully}}
    networks: [proxy]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/sante', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    labels:
      - traefik.enable=true
      - traefik.docker.network=proxy
      - traefik.http.routers.nanodeus-cv.rule=Host(`cv.nanodeus.com`)
      - traefik.http.routers.nanodeus-cv.entrypoints=websecure
      - traefik.http.routers.nanodeus-cv.tls.certresolver=le
      - traefik.http.services.nanodeus-cv.loadbalancer.server.port=8000
  admin:
    <<: *commun
    restart: unless-stopped
    environment: {CV_ROLE: admin}
    depends_on: {migrate: {condition: service_completed_successfully}}
    ports: ["${CV_ADMIN_ECOUTE:?CV_ADMIN_ECOUTE manquante dans .env}:8000"]

volumes:
  donnees: {name: nanodeus-cv-donnees}

networks:
  proxy: {external: true}
```

`deploy/compose.fumee.yml` : `name: nanodeus-cv-fumee`, volume `name: nanodeus-cv-fumee`,
`public.ports: ["127.0.0.1:18010:8000"]`.

- [ ] **Step 4 : bâtir et rejouer la fumée**

Run : `docker build -t nanodeus-cv:local . && PYTHON=.venv/bin/python scripts/fumee-image.sh nanodeus-cv:local`
Expected : toutes les vérifications passent, code 0, rien ne reste (`docker volume ls`
sans `nanodeus-cv-fumee`). Si le PDF déborde sur deux pages avec DejaVu, resserrer
`templates/pdf.css` (taille de police ou interlignes), puis vérifier à l'œil un PDF de
l'image.

Si Docker ne peut pas tourner sur le Mac, le noter dans le ledger : la fumée sera d'abord
jugée par la CI (tâche 4).

- [ ] **Step 5 : hadolint**

Run : `docker run --rm -v "$PWD:/src:ro" -w /src hadolint/hadolint@sha256:9a3944b7fddcb947d1ffd90829ac1a6e5c30479223358f249d8b96c7d0019e27 hadolint --config .hadolint.yaml Dockerfile`
Expected : aucune sortie, code 0.

- [ ] **Step 6 : commit** — `FEAT(image): image Docker, Compose de production et test de fumée`

---

### Task 3 : scripts du serveur

**Files :**
- Create : `deploy/deploy.sh`, `deploy/backup.sh`, `deploy/ssh-commande.sh`,
  `deploy/nanodeus-cv-nuit.service`, `deploy/nanodeus-cv-nuit.timer`,
  `deploy/env.exemple` (noms des variables, valeurs factices)
- Modify : `requirements-dev.txt` (ajout de `shellcheck-py`, épinglé)
- Test : `tests/test_scripts_serveur.py` (nouveau)

**Interfaces :**
- Consumes : `deploy/compose.yml` (services `public`/`admin`, volume `nanodeus-cv-donnees`),
  `python -m cv.sauvegarde`.
- Produces :
  - `deploy.sh <image>` : racine `${CV_ROOT:-/opt/nanodeus-cv}`.
  - `backup.sh [--db-only]` : mêmes variables de racine.
  - `ssh-commande.sh` : lit `SSH_ORIGINAL_COMMAND`.

Comportements :

- **`deploy.sh`** (modèle : `deploy/deploy.sh` de ReadLN, sans la partie tts) :
  - image acceptée seulement si elle vérifie `^ghcr\.io/jeremylacaze/nanodeus-cv:[0-9a-f]{40}$` ;
  - refus de tourner en root ; `.env` lisible exigé ;
  - `docker pull` avant de toucher au `.env` ;
  - réécriture atomique de la ligne `CV_IMAGE=` (mktemp dans `$ROOT`, `chmod 600`,
    `grep -v … || [ $? -eq 1 ]`, `mv`) ;
  - `docker compose --project-directory "$ROOT" -f "$ROOT/compose.yml" up -d` ;
  - attente de `healthy` sur `public` (60 × 5 s) et de `running` sur `admin` ;
  - en cas d'échec après la bascule : affiche la commande de retour arrière avec l'image
    précédente, sans jamais l'exécuter ;
  - en cas de succès : supprime les anciennes images du seul dépôt `nanodeus-cv`.
- **`backup.sh`** (modèle : `deploy/backup.sh` de ReadLN) :
  - dépôt restic `${CV_RESTIC_REPO:-/opt/readln/restic}`, mot de passe
    `${CV_RESTIC_PASSWORD_FILE:-/opt/readln/restic-password}` monté en `:ro`, cache
    `${CV_RESTIC_CACHE:-$ROOT/restic-cache}`, même image restic épinglée par digest que
    ReadLN ;
  - si le volume `nanodeus-cv-donnees` n'existe pas encore : « Première mise en ligne :
    rien à sauvegarder », code 0 ;
  - sinon, copie de la base par `docker run --rm --network none -v nanodeus-cv-donnees:/data
    "$CV_IMAGE" python -m cv.sauvegarde /data/cv.sqlite3 /data/.sauvegarde/cv.sqlite3`
    (`CV_IMAGE` lu dans le `.env`). Un `docker compose run` de `public` est exclu : il
    porterait les labels Traefik, et Traefik lui enverrait du trafic ;
  - restic avec `--host nanodeus-cv --tag cv --tag pre-deploy|nightly --retry-lock 5m`, en
    lisant le volume en `:ro`. `--db-only` sauvegarde `/data/.sauvegarde/cv.sqlite3` ; le
    mode complet sauvegarde aussi `/data/photos`, jamais `/data/cache-pdf` ;
  - rotation `forget --host nanodeus-cv` : `--keep-last 10` pour `pre-deploy`,
    `7/4/6` (jour/semaine/mois) pour `nightly`. **Sans `--prune`** : la purge nocturne de
    ReadLN, qui porte sur tout le dépôt, libère les blocs.
- **`ssh-commande.sh`** : commande forcée de la clé de déploiement (`authorized_keys`).
  Il n'exécute (par `exec`) que `$ROOT/backup.sh --db-only` ou
  `$ROOT/deploy.sh <image valide>`, avec la même expression régulière que `deploy.sh`.
  Toute autre commande donne « commande refusée » sur stderr et le code 1. Les arguments
  ne passent jamais par `eval`.
- **Timer** : `OnCalendar=*-*-* 04:15:00`, `Persistent=true`, `RandomizedDelaySec=300`
  (ReadLN tourne à 03:30). Service `Type=oneshot`, `User=deploy`, `TimeoutStartSec=1800`.
  Il lance d'abord `ExecStart=/opt/nanodeus-cv/backup.sh`, puis
  `ExecStart=/usr/bin/docker compose --project-directory /opt/nanodeus-cv exec -T public
  flask --app cv.app purger`.

- [ ] **Step 1 : tests en échec**

`tests/test_scripts_serveur.py` exécute les scripts par `subprocess` avec un faux `docker`
placé en tête du `PATH`. Ce faux `docker` est un script shell : il note ses arguments dans
un fichier, répond `cid` à `ps -q`, et répond à `inspect` avec `$FAUX_ETAT`. Un
`volume inspect` échoue quand `$FAUX_VOLUME` est vide. `CV_ROOT` pointe sur `tmp_path`.

```python
@pytest.mark.parametrize("image", ["ghcr.io/jeremylacaze/nanodeus-cv:latest",
    "ghcr.io/jeremylacaze/nanodeus-cv:abc123", "ghcr.io/autre/nanodeus-cv:" + "a" * 40,
    "ghcr.io/jeremylacaze/nanodeus-cv"])
def test_deploy_refuse_les_tags_mouvants(image, ...):  # code 1, docker jamais appelé
def test_deploy_sans_env(...):                          # code 1, message « .env »
def test_deploy_reussi_garde_les_secrets(...):          # FAUX_ETAT=healthy : code 0, .env garde
    # ses autres lignes, CV_IMAGE= remplacé (une seule ligne), droits 0o600, aucun .env.* restant
def test_deploy_malsain_propose_le_retour(...):         # FAUX_ETAT=unhealthy : code 1, stderr
    # contient « deploy.sh <image précédente> »
def test_backup_premiere_mise_en_ligne(...):            # volume absent : code 0, restic jamais lancé
def test_backup_sans_mot_de_passe(...):                 # fichier absent : code 1
@pytest.mark.parametrize("commande", ["", "bash", "/opt/x/deploy.sh", "backup.sh",
    "backup.sh --db-only; id", "deploy.sh ghcr.io/jeremylacaze/nanodeus-cv:latest",
    "deploy.sh ghcr.io/jeremylacaze/nanodeus-cv:" + "a" * 40 + " x"])
def test_ssh_refuse(commande, ...):                     # code 1, « commande refusée »
def test_ssh_accepte_backup_et_deploy(...):             # faux backup.sh/deploy.sh dans CV_ROOT
    # qui notent leurs arguments : reçus à l'identique
def test_shellcheck():                                  # shellcheck sur deploy/*.sh et
    # scripts/fumee-image.sh : code 0
```

La forme exacte des commandes acceptées par `ssh-commande.sh` est
`<CV_ROOT>/backup.sh --db-only` et `<CV_ROOT>/deploy.sh <image>`. Ce sont les chemins
absolus que la pipeline envoie.

- [ ] **Step 2 : lancer** — `.venv/bin/pytest -q tests/test_scripts_serveur.py` → échec (scripts absents).

- [ ] **Step 3 : écrire les scripts et les unités systemd**, `chmod +x` sur les `.sh`.
  Ajouter `deploy/env.exemple`, qui liste chaque variable du `.env` serveur avec une
  valeur factice et un commentaire : `CV_IMAGE`, `CV_PROD`, `SECRET_KEY`, `CV_SEL_HMAC`,
  `CV_URL_PUBLIQUE`, `CV_ADMIN_ECOUTE=<ip-tailnet>:8780`, `CV_ADMIN_HOTES=<ip-tailnet>`,
  `CV_ADMIN_RESEAUX`, `CV_SMTP_*`, `CV_EMAIL_EXPEDITEUR` et
  `CV_EMAIL_DESTINATAIRE=<boîte perso>`. Aucune valeur réelle.

- [ ] **Step 4 : lancer** — même commande, puis `.venv/bin/pytest -q` → tout passe.

- [ ] **Step 5 : commit** — `FEAT(deploy): scripts serveur, commande SSH forcée et sauvegarde nocturne`

---

### Task 4 : CI et release

**Files :**
- Create : `.github/workflows/verifications.yml`, `.github/workflows/ci.yml`,
  `.github/workflows/release.yml`, `.github/dependabot.yml`, `requirements-ci.txt`

**Interfaces :**
- Consumes : `scripts/fumee-image.sh` (tâche 2), `tests/test_scripts_serveur.py` (tâche 3).
- Produces : secrets attendus dans l'environnement GitHub `production` : `NETCUP_HOST`,
  `NETCUP_USER`, `NETCUP_SSH_KEY`, `NETCUP_KNOWN_HOSTS`.

Contenu :
- **`verifications.yml`** (`workflow_call`, entrée `cache-pip`, `permissions: contents: read`),
  trois jobs :
  - `tests` : Python 3.14, `apt-get install libpango-1.0-0 libpangoft2-1.0-0
    libharfbuzz-subset0 fonts-dejavu-core`, `pytest -q` ;
  - `controles` (`fetch-depth: 0`), chaque étape en `!cancelled()` :
    - `alembic upgrade head` puis `alembic check` (`CV_DATA_DIR` dans `$RUNNER_TEMP`) ;
    - `pip-audit -r requirements.txt -r requirements-dev.txt` ;
    - `zizmor --format=github .` ;
    - gitleaks, avec la même version et le même sha256 que ReadLN ;
    - `ruff check --output-format=github .` ;
  - `image` : hadolint (même digest que ReadLN), `docker build -t nanodeus-cv:ci .`,
    `pip install pypdf`, puis `scripts/fumee-image.sh nanodeus-cv:ci`.
- **`ci.yml`** : sur `push` (develop), `pull_request` et `workflow_dispatch`, appelle les
  vérifications. Le dépôt est public, les minutes sont illimitées : on vérifie tout à
  chaque fois, sans les économies de ReadLN.
- **`release.yml`** : sur `push: tags: ["v*"]`, avec
  `concurrency: {group: release-production, cancel-in-progress: false}`. Jobs successifs :
  1. `verifications` (`cache-pip: false`) ;
  2. `build` : `packages: write`, buildx, login GHCR par `GITHUB_TOKEN`, push de
     `ghcr.io/jeremylacaze/nanodeus-cv:${{ github.sha }}` (label
     `org.opencontainers.image.source` sur l'URL du dépôt) ;
  3. `backup` : `environment: production`, `permissions: {}`, ssh sur
     `/opt/nanodeus-cv/backup.sh --db-only` ;
  4. `deploy` : `environment: production`, `permissions: {}`, ssh sur
     `/opt/nanodeus-cv/deploy.sh <image>`, l'image passant par `env:` et jamais
     interpolée dans `run:`.

  Le SSH se configure comme dans ReadLN : `known_hosts` épinglé, `StrictHostKeyChecking=yes`,
  `IdentitiesOnly=yes`, `ServerAliveInterval=30`.
- **`dependabot.yml`** : `pip` et `github-actions`, hebdomadaires, vers `develop`,
  `cooldown: default-days: 7`, préfixe `CHORE`.
- **`requirements-ci.txt`** : `pip-audit` et `zizmor`, épinglés à la dernière version.

- [ ] **Step 1 : vérifier les workflows localement**

Run : `.venv/bin/pip install -r requirements-ci.txt && .venv/bin/zizmor . && .venv/bin/pip-audit -r requirements.txt -r requirements-dev.txt`
Expected : zizmor ne signale rien (sinon corriger) ; pip-audit ne trouve aucune faille.
Le premier vrai passage se fait au push de la tâche 6.

- [ ] **Step 2 : commit** — `CHORE(ci): vérifications, release et Dependabot`

---

### Task 5 : README vitrine, runbook et garde du dépôt public

**Files :**
- Create : `README.md`, `docs/DEPLOIEMENT.md`, `tests/test_depot_public.py`

**Interfaces :** aucune.

- [ ] **Step 1 : test en échec**

`tests/test_depot_public.py` parcourt `git ls-files` (fichiers texte ; images et polices
sautées) :

```python
def test_aucune_ipv4_hors_liste(): # toute IPv4 littérale ∈ {127.0.0.1, 0.0.0.0, 100.64.0.0,
    # 100.64.0.7, 100.127.255.254, 172.16.0.0, 192.168.0.0, 10.0.0.0} et les adresses de
    # documentation (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)
def test_aucun_email_hors_liste(): # cv@nanodeus.com, noreply@anthropic.com,
    # 254094035+jeremylacaze@users.noreply.github.com, domaines exemple.test/example.com
```

Ajuster la liste à ce que le dépôt contient légitimement (valeurs de test), sans jamais y
mettre l'IP réelle du serveur. Le test doit d'abord échouer sur un fichier piège temporaire
qu'on retire ensuite. Il le fait sans rien commiter : pour ce contrôle, il lit aussi les
fichiers non suivis passés par une variable d'environnement.

- [ ] **Step 2 : rédiger**

- **`README.md`** (vitrine pour un recruteur, en français, court) : ce que fait le site ;
  la pile ; les choix d'architecture (une image et deux rôles, l'admin réservée au tailnet,
  aucun cookie public, le journal sans IP, le PDF tiré des mêmes données) ; le
  développement local (`./dev.sh`, `pytest`) ; un lien vers `docs/DEPLOIEMENT.md`.
- **`docs/DEPLOIEMENT.md`** (runbook) :
  1. préparation du serveur (`/opt/nanodeus-cv`, `scp` des fichiers de `deploy/`, `.env`
     généré sur place) ;
  2. clé SSH dédiée avec commande forcée ;
  3. secrets et environnement GitHub `production` ;
  4. Brevo, étapes de la spec § 8 : compte, domaine `nanodeus.com` (DKIM, DMARC),
     expéditeur `cv@nanodeus.com`, clé SMTP dans le `.env` ;
  5. timer systemd, avec ses commandes `sudo` ;
  6. mise en ligne par tag `v*` ;
  7. retour arrière avec `deploy.sh <sha précédent>` ;
  8. restauration restic (`restore latest --host nanodeus-cv --tag cv`, arrêt des services,
     copie dans le volume par un conteneur, redémarrage) ;
  9. rappel : les fichiers de `/opt/nanodeus-cv` sont copiés à la main.

  Point de contrôle après chaque étape. Aucune IP, aucun email réel.

- [ ] **Step 3 : lancer** — `.venv/bin/pytest -q` → tout passe.

- [ ] **Step 4 : commit** — `DOCS: README vitrine et runbook de déploiement`

---

### Task 6 : mise en ligne (gestes extérieurs, chacun après accord de Jeremy)

Préalable : la réécriture de l'historique pour l'IP tailnet est décidée et faite. Les
commits 49ab7cc et 8fb006b la contiennent, voir le ledger. Sans elle, rien n'est poussé.

- [ ] **Step 1 : merge et push.** Merge de la branche dans `develop` en local,
  `pytest -q` vert, puis les contrôles d'avant-push :
  `git log --all --format='%ae %ce' | sort -u` et un grep IP/email/téléphone sur
  `git log -p --all`. Ensuite, **sur accord**, `git push origin develop`. La CI doit
  passer au vert. Point de contrôle : les 3 jobs sont verts.
- [ ] **Step 2 : serveur.** Avec le compte `deploy` (`~/.ssh/readln_deploy`) :
  - `scp` de `deploy/compose.yml`, `deploy.sh`, `backup.sh` et `ssh-commande.sh` vers
    `/opt/nanodeus-cv/` ;
  - `.env` généré **sur le serveur**, en `chmod 600`, avec des secrets produits sur place
    (`openssl rand -hex 32` redirigé dans le fichier, jamais affiché) ;
  - `CV_ADMIN_ECOUTE` et `CV_ADMIN_HOTES` lus depuis `tailscale ip -4` sur place ;
  - SMTP vide en attendant Brevo : les demandes sont enregistrées même si l'envoi échoue.

  Point de contrôle : `docker compose --project-directory /opt/nanodeus-cv config > /dev/null`
  rend 0.
- [ ] **Step 3 : clé et secrets GitHub (sur accord).**
  - Paire `~/.ssh/nanodeus_cv_deploy` générée sur le Mac.
  - Clé publique ajoutée au `authorized_keys` de `deploy`, préfixée par
    `command="/opt/nanodeus-cv/ssh-commande.sh",restrict`.
  - Environnement `production` créé, limité aux tags `v*`.
  - Secrets posés par `gh secret set --env production … < fichier`, sans rien afficher.

  Point de contrôle :
  - `ssh -i ~/.ssh/nanodeus_cv_deploy deploy@<netcup> id` → « commande refusée » ;
  - `… /opt/nanodeus-cv/backup.sh --db-only` → « Première mise en ligne ».
- [ ] **Step 4 : release (sur accord).** Tag `v1.0.0` sur `develop`, push du tag. La
  release doit passer au vert. Si le paquet GHCR est privé, le passer en public (vitrine,
  aucun secret dedans) ; le `docker login` existant du compte `deploy` permet le pull
  dans tous les cas.

  Points de contrôle :
  - `https://cv.nanodeus.com` répond, avec un certificat valide ;
  - `/admin/` y renvoie 404 ;
  - `http://<ip-tailnet>:8780/admin/` répond depuis le Mac par Tailscale.
- [ ] **Step 5 : IP source de l'admin (spec § 13).** Vérifier, depuis le Mac, que l'admin
  voit bien l'IP tailnet du client et non la passerelle Docker. Par exemple, avec un
  `CV_ADMIN_RESEAUX` réduit temporairement à `100.64.0.0/10` : si l'accès passe, le
  contrôle reste. Sinon, `CV_ADMIN_RESEAUX=` (vide), et le choix est noté dans
  `docs/DEPLOIEMENT.md`. Ne rien afficher de l'IP dans un fichier du dépôt.
- [ ] **Step 6 : sauvegarde.** `backup.sh` lancé à la main (mode complet), puis
  `restic snapshots --host nanodeus-cv` et une restauration d'essai de `cv.sqlite3` dans
  `~/` sur le serveur (`PRAGMA integrity_check` → `ok`), puis nettoyage. Ensuite, runbook
  pour Jeremy : `sudo cp` des unités, puis `systemctl enable --now nanodeus-cv-nuit.timer`.
  Point de contrôle : `systemctl list-timers` affiche le timer.
- [ ] **Step 7 : navigateurs.**
  - Playwright (Chromium et WebKit) sur `https://cv.nanodeus.com` : aucune violation CSP,
    PDF téléchargé, aucun cookie posé ;
  - à faire par Jeremy : ouverture du PDF dans un vrai Safari et un vrai Chrome, puis le
    lien Artefacts dans la WebView LinkedIn d'un téléphone.
- [ ] **Step 8 : mémoire et `/compact`.** Mettre à jour `nanodeus-cv-avancement.md`, puis
  rappeler `/compact`.
