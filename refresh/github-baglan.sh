#!/usr/bin/env bash
# Genç — GitHub bağlantı yardımcısı.
#
# Bu betik yerel depoyu bir GitHub reposuna bağlar, repoyu (yoksa) oluşturur ve
# ilk kez gönderir. Böylece `.github/workflows/veri-yenileme.yml` her gün
# otomatik çalışmaya başlar.
#
# Gereken ortam değişkenleri (token'ı komut satırına YAZMAYIN, ortamdan okunur):
#   GITHUB_TOKEN   GitHub erişim anahtarı (klasik: "repo"; ince ayarlı: Contents read/write)
#   GITHUB_OWNER   GitHub kullanıcı adı ya da kuruluş adı (ör. ahmet)
#   GITHUB_REPO    Repo adı (ör. genc)
#
# İsteğe bağlı:
#   GITHUB_PRIVATE 1 (varsayılan) özel repo, 0 açık repo
#   GITHUB_BRANCH  Gönderilecek dal (varsayılan: master)
#
# Kullanım:
#   GITHUB_OWNER=ahmet GITHUB_REPO=genc ./refresh/github-baglan.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

: "${GITHUB_TOKEN:?GITHUB_TOKEN tanımlı değil}"
: "${GITHUB_OWNER:?GITHUB_OWNER tanımlı değil (GitHub kullanıcı adı)}"
: "${GITHUB_REPO:?GITHUB_REPO tanımlı değil (repo adı)}"
PRIVATE="${GITHUB_PRIVATE:-1}"
BRANCH="${GITHUB_BRANCH:-master}"
API="https://api.github.com"
AUTH=(-H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json")

api() { curl -s -o /tmp/gh_resp.json -w "%{http_code}" "$@"; }

echo "→ Anahtar doğrulanıyor…"
code=$(api "${AUTH[@]}" "$API/user")
if [ "$code" != "200" ]; then
  echo "✗ Anahtar geçersiz (HTTP $code). PAT'ı ve izinlerini kontrol edin." >&2
  head -c 300 /tmp/gh_resp.json >&2; echo >&2; exit 1
fi
LOGIN=$(python3 -c "import json;print(json.load(open('/tmp/gh_resp.json')).get('login',''))")
echo "✓ Anahtar geçerli: $LOGIN"

echo "→ Depo kontrol ediliyor: $GITHUB_OWNER/$GITHUB_REPO"
code=$(api "${AUTH[@]}" "$API/repos/$GITHUB_OWNER/$GITHUB_REPO")
if [ "$code" = "200" ]; then
  echo "✓ Depo mevcut."
elif [ "$code" = "404" ]; then
  echo "→ Depo yok, oluşturuluyor…"
  PRIV=$([ "$PRIVATE" = "1" ] && echo true || echo false)
  # Kullanıcı adıysa /user/repos, kuruluşsa /orgs/{org}/repos uç noktası gerekir.
  if [ "$GITHUB_OWNER" = "$LOGIN" ]; then
    url="$API/user/repos"
  else
    url="$API/orgs/$GITHUB_OWNER/repos"
  fi
  code=$(api "${AUTH[@]}" -X POST "$url" -d "{\"name\":\"$GITHUB_REPO\",\"private\":$PRIV,\"description\":\"Genç — etkinlik keşif uygulaması\"}")
  if [ "$code" != "201" ]; then
    echo "✗ Depo oluşturulamadı (HTTP $code). Anahtarın 'repo' izni var mı?" >&2
    head -c 400 /tmp/gh_resp.json >&2; echo >&2; exit 1
  fi
  echo "✓ Depo oluşturuldu."
else
  echo "✗ Depo sorgulanamadı (HTTP $code)." >&2
  head -c 400 /tmp/gh_resp.json >&2; echo >&2; exit 1
fi

# Remote'u temiz adresle ayarla (token .git/config'e YAZILMAZ).
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/$GITHUB_OWNER/$GITHUB_REPO.git"
else
  git remote add origin "https://github.com/$GITHUB_OWNER/$GITHUB_REPO.git"
fi
echo "✓ origin: $(git remote get-url origin)"

echo "→ Gönderiliyor ($BRANCH)…"
# Token yalnızca bu tek komut için kullanılır; diske yazılmaz.
if git push -u "https://x-access-token:$GITHUB_TOKEN@github.com/$GITHUB_OWNER/$GITHUB_REPO.git" "$BRANCH:$BRANCH" 2>/tmp/gh_push.err; then
  echo "✓ Gönderildi."
else
  echo "✗ Gönderilemedi:" >&2
  sed -E 's#https://[^@]*@#https://***@#g' /tmp/gh_push.err >&2
  exit 1
fi

echo
echo "Tamam. Sıradaki adımlar:"
echo "  1) Repo → Settings → Actions → General → Workflow permissions"
echo "     → 'Read and write permissions' seçin (otomatik commit için)."
echo "  2) Repo → Actions sekmesi → 'Veri yenileme' → 'Run workflow' ile bir kez elle deneyin."
echo "  3) Bundan sonra her gün 04:30 TRT'de kendiliğinden çalışır."
echo
echo "Bağlantıyı kaldırmak için: git remote remove origin"
