#!/usr/bin/env bash
# Genç sitesini genc.surge.sh adresine yükler.
#
# Kullanım:
#   SURGE_TOKEN=<token> SURGE_LOGIN=<eposta> tools/deploy_surge.sh
#
# Token almak için: npx surge token
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${SURGE_DOMAIN:-genc.surge.sh}"

[ -n "${SURGE_TOKEN:-}" ] || { echo "SURGE_TOKEN tanımlı değil." >&2; exit 1; }
[ -n "${SURGE_LOGIN:-}" ] || { echo "SURGE_LOGIN tanımlı değil." >&2; exit 1; }

bash "$ROOT/tools/build_site.sh"
cd "$ROOT/dist"
printf '%s\n' "$DOMAIN" > CNAME

npx --yes surge . "$DOMAIN"
echo "Yayınlandı: https://$DOMAIN"
