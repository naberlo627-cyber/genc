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

cd "$ANDROID_DIR"
"$GRADLE" --no-daemon "${1:-assembleRelease}"

OUT="$ANDROID_DIR/app/build/outputs/apk"
mkdir -p "$ROOT/indir"
cp "$OUT/release/app-release.apk" "$ROOT/indir/Genc.apk"
echo "APK hazır: $ROOT/indir/Genc.apk"
