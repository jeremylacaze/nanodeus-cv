#!/usr/bin/env bash
# Sonde externe du site public, vu d'Internet comme un visiteur (.github/workflows/
# sonde.yml, toutes les 30 min). Son User-Agent est celui d'un robot : le journal
# des visites l'ignore.
#
#   scripts/sonde.sh [https://cv.nanodeus.com]
#
# Échoue si une page, le PDF ou la carte d'aperçu ne répond pas comme il faut, si
# l'admin répond au public, si la réponse est lente ou si le certificat expire
# dans moins de 14 jours. Une erreur réseau passagère est retentée deux fois.
set -euo pipefail

SITE="${1:-https://cv.nanodeus.com}"
SITE="${SITE%/}"
UA="nanodeus-cv-sonde/1 (uptime monitor; curl)"
LENTEUR_MAX=5          # secondes, pour la page d'accueil
JOURS_CERTIFICAT=14
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fautes=0

ok()    { echo "ok    $*"; }
faute() { echo "FAUTE $*" >&2; fautes=$((fautes + 1)); }

# obtenir <chemin> : corps dans $TMP/corps, en-têtes dans $TMP/entetes ; affiche
# « code durée ».
obtenir() {
    curl -sS --max-time 20 --retry 2 --retry-all-errors --retry-delay 5 -A "$UA" \
        -o "$TMP/corps" -D "$TMP/entetes" -w '%{http_code} %{time_total}' "$SITE$1" \
        2>"$TMP/erreur" || echo "000 0"
}

verifier() {   # verifier <chemin> <code attendu> [signature des 4 premiers octets]
    local resultat code duree
    resultat="$(obtenir "$1")"
    code="${resultat% *}" duree="${resultat#* }"
    if [ "$code" != "$2" ]; then
        faute "$1 : HTTP $code au lieu de $2 $(cat "$TMP/erreur")"
        return 1
    fi
    if [ -n "${3:-}" ] && ! head -c 8 "$TMP/corps" | LC_ALL=C grep -q "$3"; then
        faute "$1 : le contenu n'est pas $3"
        return 1
    fi
    ok "$1 ($code, ${duree}s)"
    echo "$duree" >"$TMP/duree"
}

if verifier / 200; then
    grep -qi '^content-security-policy:' "$TMP/entetes" || faute "/ : aucune CSP"
    if grep -qi '^set-cookie:' "$TMP/entetes"; then faute "/ : cookie posé"; fi
    awk -v max="$LENTEUR_MAX" '{ exit !($1 > max) }' "$TMP/duree" \
        && faute "/ : $(cat "$TMP/duree")s, plus de ${LENTEUR_MAX}s"
    # Le PDF et la carte d'aperçu de la version par défaut, tels que la page les lie.
    pdf="$(grep -o 'href="/[a-z0-9-]*\.pdf"' "$TMP/corps" | head -n 1 | cut -d'"' -f2 || true)"
    carte="$(grep -o '<meta property="og:image" content="[^"]*"' "$TMP/corps" | head -n 1 \
        | sed -E 's/.*content="https?:\/\/[^/]+//; s/"$//' || true)"
    commit="$(grep -o '/commit/[0-9a-f]\{40\}"' "$TMP/corps" | head -n 1 | cut -c9-15 || true)"
    if [ -n "$pdf" ]; then verifier "$pdf" 200 "%PDF" || true; else faute "/ : aucun lien vers le PDF"; fi
    if [ -z "$carte" ]; then
        faute "/ : aucune og:image"
    elif verifier "$carte" 200 && ! grep -qi '^content-type: *image/' "$TMP/entetes"; then
        faute "$carte : og:image n'est pas une image"
    fi
    if [ -n "$commit" ]; then ok "commit déployé : $commit"; fi
fi
verifier /en/ 200 || true
if verifier /.well-known/security.txt 200; then
    # Expires glisse à chaque requête : une date passée trahirait une horloge ou un
    # cache figés.
    expire="$(sed -n 's/^Expires: *//p' "$TMP/corps" | tr -d '\r')"
    if [ -z "$expire" ] || [ "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \> "$expire" ]; then
        faute "security.txt : Expires absente ou passée ($expire)"
    fi
fi
verifier /sante 200 || true
verifier /admin/ 404 || true

if [[ "$SITE" == https://* ]]; then
    hote="${SITE#https://}" hote="${hote%%/*}"
    if echo | openssl s_client -connect "$hote:443" -servername "$hote" 2>/dev/null \
        | openssl x509 -noout -checkend $((JOURS_CERTIFICAT * 86400)) >/dev/null; then
        ok "certificat valable au moins $JOURS_CERTIFICAT jours"
    else
        faute "certificat : expire dans moins de $JOURS_CERTIFICAT jours (ou illisible)"
    fi
fi

if [ "$fautes" -gt 0 ]; then
    echo "$fautes faute(s) sur $SITE" >&2
    exit 1
fi
echo "Sonde OK : $SITE"
