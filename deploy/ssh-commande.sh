#!/usr/bin/env bash
# Commande forcée de la clé de déploiement de cv.nanodeus.com, dans
# ~deploy/.ssh/authorized_keys :
#
#   command="/opt/nanodeus-cv/ssh-commande.sh",restrict ssh-ed25519 AAAA… nanodeus-cv-ci
#
# Quoi que la pipeline demande, seules deux commandes passent, au caractère
# près : la sauvegarde avant déploiement et le déploiement d'une image figée.
# La commande reçue n'est jamais interprétée par un shell (aucun eval) : elle
# est comparée, puis l'argument validé est passé tel quel à `exec`.
set -euo pipefail

ROOT="${CV_ROOT:-/opt/nanodeus-cv}"
MOTIF='^ghcr\.io/jeremylacaze/nanodeus-cv:[0-9a-f]{40}$'
COMMANDE="${SSH_ORIGINAL_COMMAND-}"

if [ "$COMMANDE" = "$ROOT/backup.sh --db-only" ]; then
  exec "$ROOT/backup.sh" --db-only
fi
PREFIXE="$ROOT/deploy.sh "
if [[ "$COMMANDE" == "$PREFIXE"* ]]; then
  IMAGE="${COMMANDE#"$PREFIXE"}"
  if [[ "$IMAGE" =~ $MOTIF ]]; then
    exec "$ROOT/deploy.sh" "$IMAGE"
  fi
fi

echo "❌ commande refusée" >&2
exit 1
