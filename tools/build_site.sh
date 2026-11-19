#!/usr/bin/env bash
# Statik yayın paketini hazırlar: kökteki yayın dosyalarını dist/ içine toplar.
# Cloudflare Workers (statik varlık) derlemesi bu dizini yayınlar; saf statik
# barındırma (Pages, Netlify, GitHub Pages) bu betiğe gerek duymaz.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"

rm -rf "$OUT"
mkdir -p "$OUT"

for f in Genc.html index.html manifest.json sw.js version.json _headers; do
  [ -f "$ROOT/$f" ] && cp "$ROOT/$f" "$OUT/"
done
for d in icons img; do
  [ -d "$ROOT/$d" ] && cp -r "$ROOT/$d" "$OUT/"
done
# Veri: uygulama il başına data/cities/<il>.json ve data/index.json okur.
# data/tickets.json (27 MB) yalnızca veri boru hattının ara dosyasıdır; yayına
# girmez çünkü Cloudflare Pages tek dosya için 25 MiB sınırı koyuyor.
mkdir -p "$OUT/data"
for f in "$ROOT"/data/*.json; do
  case "$(basename "$f")" in tickets.json|events.json) continue;; esac
  cp "$f" "$OUT/data/"
done
[ -d "$ROOT/data/cities" ] && cp -r "$ROOT/data/cities" "$OUT/data/"
# APK da yayına girer: bazı ağlarda GitHub indirme sunucusu engelli olduğundan
# uygulama kurulum dosyası site üzerinden de erişilebilir kalmalı.
if [ -f "$ROOT/indir/Genc.apk" ]; then
  mkdir -p "$OUT/indir"
  cp "$ROOT/indir/Genc.apk" "$OUT/indir/"
fi

echo "Yayın paketi hazır: $OUT"
