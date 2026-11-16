#!/usr/bin/env bash
# Genç veri yenileme — kabuk sarmalayıcı.
#
# Tek işi etkinlik verisini yenilemektir. Zamanlanmış görevler (cron, systemd
# timer, CI) bu betiği çağırır. Python tarafı refresh/refresh.py'de; bu betik
# ortamı hazırlar, çalıştırır ve çıkış kodunu iletir.
#
# Kullanım:
#   ./refresh/run.sh              # tam yenileme
#   ./refresh/run.sh --limit 120  # ek seçenekler refresh.py'ye geçirilir
#
# Çıkış kodu: 0 başarı (veya başka çalışma sürüyor), 1 hata.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || { echo "python3 bulunamadı"; exit 1; }

mkdir -p refresh/logs

exec "$PY" refresh/refresh.py "$@"
