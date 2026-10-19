#!/usr/bin/env bash
# Test de fumée d'une image : réglages de la prod (CV_PROD=1, lecture seule, volume
# neuf), mais projet, volume et ports à part. Rien ne reste à la fin.
#
#   scripts/fumee-image.sh <image>        (PYTHON=… : interpréteur qui a pypdf)
set -euo pipefail

IMAGE="${1:?usage : scripts/fumee-image.sh <image>}"
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
PUBLIC="http://127.0.0.1:18010"
TMP="$(mktemp -d)"
RESEAU_CREE=0

dc() {
    docker compose --project-directory "$TMP" -f "$TMP/compose.yml" \
        -f "$TMP/compose.fumee.yml" "$@"
}

nettoyer() {
    dc down -v --remove-orphans >/dev/null 2>&1 || true
    if [ "$RESEAU_CREE" = 1 ]; then docker network rm proxy >/dev/null 2>&1 || true; fi
    rm -rf "$TMP"
}
trap nettoyer EXIT

echec() {
    echo "ÉCHEC : $*" >&2
    dc logs --no-color --tail 60 >&2 || true
    exit 1
}

# Requête GET sur le public : corps dans $TMP/corps, en-têtes dans $TMP/entetes.
obtenir() {
    local code
    code="$(curl -sS -o "$TMP/corps" -D "$TMP/entetes" -w '%{http_code}' "$PUBLIC$1")" \
        || echec "$1 injoignable"
    [ "$code" = "$2" ] || echec "$1 : HTTP $code au lieu de $2"
}

# Comme en prod : compose.yml et .env côte à côte dans le dossier du projet.
cp "$RACINE/deploy/compose.yml" "$RACINE/deploy/compose.fumee.yml" "$TMP/"
umask 077
cat > "$TMP/.env" <<FIN
CV_IMAGE=$IMAGE
CV_PROD=1
SECRET_KEY=$(openssl rand -hex 32)
CV_SEL_HMAC=$(openssl rand -hex 32)
CV_URL_PUBLIQUE=https://cv.nanodeus.com
CV_ADMIN_ECOUTE=127.0.0.1:18780
CV_ADMIN_HOTES=127.0.0.1
FIN

if ! docker network inspect proxy >/dev/null 2>&1; then
    docker network create proxy >/dev/null
    RESEAU_CREE=1
fi

dc up -d --pull never >"$TMP/up.log" 2>&1 || { cat "$TMP/up.log" >&2; echec "démarrage des services"; }

etat=""
for _ in $(seq 60); do
    etat="$(docker inspect -f '{{.State.Health.Status}}' "$(dc ps -q public)")"
    [ "$etat" = healthy ] && break
    sleep 2
done
[ "$etat" = healthy ] || echec "public n'est pas healthy ($etat)"

obtenir / 200
grep -qi '^content-security-policy:' "$TMP/entetes" || echec "/ : aucune CSP"
if grep -qi '^set-cookie:' "$TMP/entetes"; then echec "/ : cookie posé"; fi

obtenir /admin/ 404

for pdf in /devops.pdf /en/devops.pdf /lead-tech.pdf /en/lead-tech.pdf; do
    obtenir "$pdf" 200
    [ "$(head -c 4 "$TMP/corps")" = "%PDF" ] || echec "$pdf : ce n'est pas un PDF"
    pages="$("$PYTHON" -c 'import sys, pypdf; print(len(pypdf.PdfReader(sys.argv[1]).pages))' \
        "$TMP/corps")"
    [ "$pages" = 1 ] || echec "$pdf : $pages pages au lieu d'une"
done

dc exec -T admin python -c "
import urllib.request
assert urllib.request.urlopen('http://127.0.0.1:8000/admin/', timeout=10).status == 200
" || echec "admin : /admin/ ne répond pas 200 depuis le conteneur"
# Depuis l'hôte, l'adresse source vue peut être la passerelle Docker (refus 403) :
# seule compte ici une réponse HTTP sur le port publié.
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:18780/admin/" || true)"
[ "$code" != 000 ] || echec "admin : port publié muet"

[ "$(dc exec -T public id -u)" = 1000 ] || echec "public ne tourne pas en UID 1000"
# $HOME appartient à l'UID 1000 : seule la lecture seule peut y refuser l'écriture.
# shellcheck disable=SC2016 # $HOME se développe dans le conteneur, pas ici.
if dc exec -T public sh -c 'touch "$HOME/essai"' 2>/dev/null; then
    echec "système de fichiers inscriptible"
fi

# Une erreur non fatale (écriture refusée par la lecture seule…) ne casse pas le
# healthcheck, mais trahit un réglage manquant.
if dc logs --no-color 2>&1 | grep -E '\[ERROR\]|Traceback|Read-only file system'; then
    echec "erreur dans les journaux"
fi

echo "Fumée OK : $IMAGE"
