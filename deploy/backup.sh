#!/usr/bin/env bash
# Sauvegarde de cv.nanodeus.com dans le dépôt restic de ReadLN.
#
# Copié à la main en /opt/nanodeus-cv/backup.sh. Deux modes :
#   - sans argument : sauvegarde complète (base + photos), chaque nuit par
#     nanodeus-cv-nuit.timer ;
#   - `--db-only` : la base seule, par la pipeline avant tout déploiement.
#
# Le dépôt est celui de ReadLN (/opt/readln/restic) : un seul mot de passe à
# garder, une seule déduplication. `--host nanodeus-cv` isole nos snapshots :
# les rotations de ReadLN (`--host readln`) n'y touchent jamais, et les nôtres
# jamais aux siens. Pas de `--prune` ici : la purge nocturne de ReadLN porte sur
# tout le dépôt et libère nos blocs aussi.
set -euo pipefail

MODE=complet
case "${1-}" in
  "")        ;;
  --db-only) MODE=db-only ;;
  *)
    echo "❌ Argument inconnu : $1" >&2
    echo "   Usage : backup.sh [--db-only]" >&2
    exit 2
    ;;
esac

ROOT="${CV_ROOT:-/opt/nanodeus-cv}"
REPO="${CV_RESTIC_REPO:-/opt/readln/restic}"
PASSWORD_FILE="${CV_RESTIC_PASSWORD_FILE:-/opt/readln/restic-password}"
CACHE="${CV_RESTIC_CACHE:-$ROOT/restic-cache}"
# Même image que ReadLN, épinglée par digest : l'outil qui écrit les
# sauvegardes ne change pas sans que personne ne l'ait décidé.
RESTIC_IMAGE="restic/restic:0.19.1@sha256:136600b6ff6843d61d355f7f71f460a166429f35de6fd11b568fece3c9a4d510"
VOLUME=nanodeus-cv-donnees

# Le mot de passe appartient à ReadLN : il est seulement lu, monté en lecture
# seule, jamais créé ni réécrit ici.
if [ ! -r "$PASSWORD_FILE" ]; then
  echo "❌ Mot de passe restic illisible : $PASSWORD_FILE" >&2
  exit 1
fi
if [ ! -f "$REPO/config" ]; then
  echo "❌ Aucun dépôt restic dans $REPO" >&2
  exit 1
fi
# Avant le tout premier déploiement, la pipeline sauvegarde déjà : rien n'existe.
if ! docker volume inspect "$VOLUME" > /dev/null 2>&1; then
  echo "ℹ️  Première mise en ligne : rien à sauvegarder."
  exit 0
fi

CV_IMAGE="$(sed -n 's/^CV_IMAGE=//p' "$ROOT/.env" | tail -n 1)"
if [ -z "$CV_IMAGE" ]; then
  echo "❌ CV_IMAGE absente de $ROOT/.env" >&2
  exit 1
fi
if ! MKDIR_ERR="$(mkdir -p "$CACHE" 2>&1)"; then
  echo "❌ Impossible de créer le cache restic $CACHE : $MKDIR_ERR" >&2
  exit 1
fi

if [ "$MODE" = db-only ]; then
  FAMILLE=pre-deploy
else
  FAMILLE=nightly
fi

# Copie cohérente de la base, WAL compris, par l'API de sauvegarde de SQLite.
# Un `docker run` nu et non un `docker compose run public` : ce dernier
# porterait les labels Traefik, qui lui enverrait du trafic.
echo "💾 Copie de la base ($FAMILLE)"
docker run --rm --network none --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges:true \
  -v "$VOLUME:/data" "$CV_IMAGE" \
  python -m cv.sauvegarde /data/cv.sqlite3 /data/.sauvegarde/cv.sqlite3

restic_() {
  docker run --rm --hostname nanodeus-cv \
    -v "$REPO:/repo" \
    -v "$PASSWORD_FILE:/run/secrets/restic-password:ro" \
    -v "$CACHE:/cache" \
    -e RESTIC_REPOSITORY=/repo \
    -e RESTIC_PASSWORD_FILE=/run/secrets/restic-password \
    -e RESTIC_CACHE_DIR=/cache \
    "$@"
}

if [ "$MODE" = db-only ]; then
  restic_ -v "$VOLUME:/data:ro" "$RESTIC_IMAGE" \
    backup --host nanodeus-cv --retry-lock 5m --tag cv --tag pre-deploy \
    /data/.sauvegarde/cv.sqlite3
  # Un échec de rotation ne bloque pas le déploiement : la sauvegarde est faite.
  restic_ "$RESTIC_IMAGE" forget --host nanodeus-cv --retry-lock 5m \
    --tag cv,pre-deploy --group-by host,tags --keep-last 10 \
    || echo "⚠️  Rotation des sauvegardes avant déploiement en échec : sauvegarde non affectée." >&2
  echo "✅ Sauvegarde avant déploiement terminée (tags cv,pre-deploy)."
  exit 0
fi

# Tout /data sauf la base vivante (sa copie cohérente est dans .sauvegarde) et
# le cache des PDF, qui se régénère à la demande.
restic_ -v "$VOLUME:/data:ro" "$RESTIC_IMAGE" \
  backup --host nanodeus-cv --retry-lock 5m --tag cv --tag nightly \
  --exclude /data/cv.sqlite3 --exclude /data/cv.sqlite3-wal \
  --exclude /data/cv.sqlite3-shm --exclude /data/cache-pdf \
  /data
restic_ "$RESTIC_IMAGE" forget --host nanodeus-cv --retry-lock 5m \
  --tag cv,nightly --group-by host,tags \
  --keep-daily 7 --keep-weekly 4 --keep-monthly 6
echo "✅ Sauvegarde nocturne terminée (tags cv,nightly)."
