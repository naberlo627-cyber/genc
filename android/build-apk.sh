#!/usr/bin/env bash
# Genç APK derleme betiği.
# Web varlıklarını (Genc.html, manifest, sw.js, ikonlar) Android assets'e kopyalar,
# sonra imzalı sürüm APK'sını üretir ve indirilebilir klasöre taşır.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID_DIR="$ROOT/android"
ASSETS="$ANDROID_DIR/app/src/main/assets/www"
export ANDROID_HOME="${ANDROID_HOME:-/home/openhands/android-sdk}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
GRADLE="${GRADLE:-/home/openhands/gradle-8.7/bin/gradle}"

mkdir -p "$ASSETS/icons" "$ASSETS/img"
cp "$ROOT/Genc.html" "$ROOT/manifest.json" "$ROOT/sw.js" "$ASSETS/"
cp "$ROOT"/icons/*.png "$ASSETS/icons/"
cp "$ROOT"/img/*.jpg "$ASSETS/img/"

# Sürüm tek kaynaktan yönetilir: Genc.html içindeki APP_VERSION.
# versionName buradan alınır, versionCode türetilir ve version.json üretilir.
VER="$(sed -n "s/.*var APP_VERSION='\([0-9.]*\)'.*/\1/p" "$ROOT/Genc.html" | head -1)"
if [ -z "$VER" ]; then echo "APP_VERSION bulunamadı" >&2; exit 1; fi
IFS='.' read -r V_MAJOR V_MINOR V_PATCH <<< "$VER"
V_MAJOR="${V_MAJOR:-0}"; V_MINOR="${V_MINOR:-0}"; V_PATCH="${V_PATCH:-0}"
VCODE=$(( V_MAJOR * 10000 + V_MINOR * 100 + V_PATCH ))
echo "Sürüm: $VER (versionCode $VCODE)"

sed -i "s/versionCode [0-9]*/versionCode $VCODE/" "$ANDROID_DIR/app/build.gradle"
sed -i "s/versionName \"[^\"]*\"/versionName \"$VER\"/" "$ANDROID_DIR/app/build.gradle"

NOTES="$(sed -n 's/.*"notes": "\([^"]*\)".*/\1/p' "$ROOT/version.json" 2>/dev/null | head -1)"
[ -z "$NOTES" ] && NOTES="Genç güncellemesi."
cat > "$ROOT/version.json" <<JSON
{
  "version": "$VER",
  "versionCode": $VCODE,
  "notes": "$NOTES",
  "apk": "indir/Genc.apk"
}
JSON
cp "$ROOT/version.json" "$ASSETS/"

cd "$ANDROID_DIR"
"$GRADLE" --no-daemon "${1:-assembleRelease}"

OUT="$ANDROID_DIR/app/build/outputs/apk"
mkdir -p "$ROOT/indir"
cp "$OUT/release/app-release.apk" "$ROOT/indir/Genc.apk"
echo "APK hazır: $ROOT/indir/Genc.apk"
