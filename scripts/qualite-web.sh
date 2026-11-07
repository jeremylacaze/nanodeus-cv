#!/usr/bin/env bash
# Qualité web sur l'application amorcée, servie par gunicorn comme en prod :
#   1. accessibilité (pa11y : axe et HTML_CodeSniffer, WCAG 2 AA), chaque thème ;
#   2. comportement du parcours et de la modale de contact dans Chromium ;
#   3. Lighthouse CI (rapports dans .lighthouseci/, jamais publiés).
# Même script en local et en CI. Rien ne reste à la fin, hors .lighthouseci/.
#
#   scripts/qualite-web.sh        (BIN=… : dossier d'alembic, flask et gunicorn ;
#                                  par défaut .venv/bin s'il existe, sinon le PATH)
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE"
if [ -z "${BIN:-}" ] && [ -x .venv/bin/gunicorn ]; then BIN="$RACINE/.venv/bin"; fi
BIN="${BIN:+$BIN/}"
export CV_PUBLIC="http://127.0.0.1:18020" CV_ADMIN="http://localhost:18021"
TMP="$(mktemp -d)"
PIDS=()

# shellcheck disable=SC2329 # appelée par le trap EXIT ci-dessous
nettoyer() {
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    wait 2>/dev/null || true
    rm -rf "$TMP"
}
trap nettoyer EXIT

echec() {
    echo "ÉCHEC : $*" >&2
    tail -n 40 "$TMP"/*.log >&2 2>/dev/null || true
    exit 1
}

export CV_DATA_DIR="$TMP/donnees"
mkdir -p "$CV_DATA_DIR"
"${BIN}alembic" upgrade head >"$TMP/alembic.log" 2>&1 || echec "migrations"
"${BIN}flask" --app cv.app amorcer >/dev/null || echec "amorçage"

servir() {   # servir <rôle> <port>
    CV_ROLE="$1" "${BIN}gunicorn" -k gthread -w 1 --threads 4 --no-control-socket \
        -b "127.0.0.1:$2" "cv.app:create_app()" >"$TMP/$1.log" 2>&1 &
    PIDS+=("$!")
}
servir public 18020
servir admin 18021

for url in "$CV_PUBLIC/" "$CV_ADMIN/admin/"; do
    for _ in $(seq 50); do
        curl -fsS -o /dev/null "$url" 2>/dev/null && continue 2
        sleep 0.2
    done
    echec "$url ne répond pas"
done

cd qualite-web
# Chrome de Puppeteer, à la révision qu'il attend ; Lighthouse s'en sert aussi.
npx --no-install puppeteer browsers install chrome >/dev/null
CHROME_PATH="$(node --input-type=module -e 'import p from "puppeteer"; console.log(await p.executablePath())')"
export CHROME_PATH

code=0
node a11y.mjs || code=1
node parcours.mjs || code=1
npx --no-install lhci autorun --config=lighthouserc.json || code=1
exit "$code"
