#!/usr/bin/env bash
# Déploie une image de cv.nanodeus.com sur le serveur : /opt/nanodeus-cv/deploy.sh <image>
#
# Lancé par la pipeline (release.yml) au travers de la commande SSH forcée
# (ssh-commande.sh), après `backup.sh --db-only`. Copié à la main par scp : la
# pipeline ne dépose jamais ce fichier.
#
#   1. refuse tout tag mouvant : le tag est le contrat, un `latest` rendrait le
#      retour arrière illusoire ;
#   2. tire l'image AVANT de toucher au .env : un pull raté ne change rien ;
#   3. réécrit la seule ligne CV_IMAGE du .env, atomiquement ;
#   4. rejoue `up -d` (le service migrate passe d'abord) et attend la santé ;
#   5. en cas d'échec, affiche la commande de retour arrière sans l'exécuter.
set -euo pipefail

ROOT="${CV_ROOT:-/opt/nanodeus-cv}"
ENV_FICHIER="$ROOT/.env"
MOTIF='^ghcr\.io/jeremylacaze/nanodeus-cv:[0-9a-f]{40}$'

IMAGE="${1-}"
if [ "$#" -ne 1 ] || [[ ! "$IMAGE" =~ $MOTIF ]]; then
  echo "❌ Image refusée : ghcr.io/jeremylacaze/nanodeus-cv:<sha de 40 caractères> attendu." >&2
  echo "   Usage : deploy.sh <image>" >&2
  exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
  echo "❌ deploy.sh ne tourne pas en root : utiliser le compte deploy." >&2
  exit 1
fi
if [ ! -r "$ENV_FICHIER" ]; then
  echo "❌ $ENV_FICHIER illisible : le créer d'abord (voir docs/DEPLOIEMENT.md)." >&2
  exit 1
fi

DC=(docker compose --project-directory "$ROOT" -f "$ROOT/compose.yml")
PRECEDENTE="$(sed -n 's/^CV_IMAGE=//p' "$ENV_FICHIER" | tail -n 1)"

echo "📦 Récupération de $IMAGE"
docker pull "$IMAGE"

retour_arriere() {
  if [ -n "$PRECEDENTE" ]; then
    echo "   Retour arrière : $ROOT/deploy.sh $PRECEDENTE" >&2
    echo "   (une migration a pu tourner : la sauvegarde pre-deploy restaure la base)" >&2
  else
    echo "   Aucune image précédente dans le .env : premier déploiement." >&2
  fi
}
echec() {
  echo "❌ Déploiement de $IMAGE en échec." >&2
  "${DC[@]}" logs --tail 50 public admin >&2 || true
  retour_arriere
  exit 1
}

# Réécriture atomique : un .env à moitié écrit perdrait les secrets, qui
# n'existent nulle part ailleurs. Temporaire dans le même dossier (même système
# de fichiers, donc `mv` atomique), droits fermés avant d'y écrire.
TMP="$(mktemp "$ROOT/.env.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
chmod 600 "$TMP"
# grep rend 1 quand il ne garde aucune ligne : ce n'est pas une erreur.
grep -v '^CV_IMAGE=' "$ENV_FICHIER" > "$TMP" || [ $? -eq 1 ]
printf 'CV_IMAGE=%s\n' "$IMAGE" >> "$TMP"
mv "$TMP" "$ENV_FICHIER"
trap - EXIT

# À partir d'ici le .env désigne la nouvelle image : tout échec, ou une
# interruption, doit dire comment revenir en arrière.
trap echec ERR
trap 'echo "❌ Interrompu." >&2; retour_arriere; exit 130' INT
trap 'echo "❌ Interrompu." >&2; retour_arriere; exit 143' TERM
trap 'echo "❌ Interrompu." >&2; retour_arriere; exit 129' HUP

echo "🚀 Démarrage"
"${DC[@]}" up -d

etat_de() {  # etat_de <service> <format>
  local cid
  cid="$("${DC[@]}" ps -q "$1")"
  if [ -z "$cid" ]; then
    echo absent
  else
    docker inspect -f "$2" "$cid"
  fi
}

SAIN=0
for _ in $(seq 60); do
  case "$(etat_de public '{{.State.Health.Status}}')" in
    healthy) SAIN=1; break ;;
    unhealthy) echec ;;
  esac
  sleep 5
done
[ "$SAIN" -eq 1 ] || { echo "❌ public n'est pas devenu sain en 5 minutes." >&2; echec; }
[ "$(etat_de admin '{{.State.Status}}')" = running ] \
  || { echo "❌ admin ne tourne pas." >&2; echec; }

trap - ERR INT TERM HUP
echo "✅ $IMAGE en ligne."

# Les anciennes images du seul dépôt de l'application : un retour arrière les
# retire de ghcr.io, rien ne sert de les garder sur le disque.
docker images "${IMAGE%:*}" --format '{{.Repository}}:{{.Tag}}' \
  | { grep -vx "$IMAGE" || true; } \
  | xargs -r docker rmi \
  || echo "⚠️  Purge des anciennes images en échec : sans effet sur le déploiement." >&2
