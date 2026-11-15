#!/usr/bin/env bash
# Genç Android derleme araç zincirini kurar (JDK, Android SDK, Gradle).
# Çalışma alanı dışındaki araçlar temizlenebildiği için betik idempotenttir:
# kurulu olanı atlar, eksik olanı indirir. build-apk.sh bunları varsayılan
# yollardan (/home/openhands/...) bekler.
set -euo pipefail

SDK="${ANDROID_HOME:-/home/openhands/android-sdk}"
GRADLE_DIR="${GRADLE_HOME:-/home/openhands/gradle-8.7}"
GRADLE_VER="8.7"
CMDTOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-16111833_latest.zip"
GRADLE_URL="https://services.gradle.org/distributions/gradle-${GRADLE_VER}-bin.zip"

need_sudo(){ [ "$(id -u)" -ne 0 ] && echo sudo || echo ""; }
SUDO="$(need_sudo)"

# 1) JDK 21
if ! command -v java >/dev/null 2>&1; then
  echo ">> JDK kuruluyor"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq openjdk-21-jdk-headless
fi
export JAVA_HOME="${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")}"
echo ">> Java: $(java -version 2>&1 | head -1)"

# 2) Android SDK (cmdline-tools + platform 34 + build-tools 34)
if [ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
  echo ">> Android cmdline-tools indiriliyor"
  tmp="$(mktemp -d)"
  curl -sL -o "$tmp/cmdtools.zip" "$CMDTOOLS_URL"
  python3 -c "import zipfile;zipfile.ZipFile('$tmp/cmdtools.zip').extractall('$tmp/x')"
  mkdir -p "$SDK/cmdline-tools"
  rm -rf "$SDK/cmdline-tools/latest"
  mv "$tmp/x/cmdline-tools" "$SDK/cmdline-tools/latest"
  chmod +x "$SDK/cmdline-tools/latest/bin/"*
  rm -rf "$tmp"
fi
export ANDROID_HOME="$SDK" ANDROID_SDK_ROOT="$SDK"
if [ ! -d "$SDK/platforms/android-34" ] || [ ! -d "$SDK/build-tools/34.0.0" ]; then
  echo ">> Android SDK paketleri kuruluyor"
  yes | "$SDK/cmdline-tools/latest/bin/sdkmanager" --licenses >/dev/null 2>&1 || true
  "$SDK/cmdline-tools/latest/bin/sdkmanager" "platform-tools" "platforms;android-34" "build-tools;34.0.0" >/dev/null
fi

# 3) Gradle
if [ ! -x "$GRADLE_DIR/bin/gradle" ]; then
  echo ">> Gradle $GRADLE_VER indiriliyor"
  tmp="$(mktemp -d)"
  curl -sL -o "$tmp/gradle.zip" "$GRADLE_URL"
  python3 -c "import zipfile;zipfile.ZipFile('$tmp/gradle.zip').extractall('$(dirname "$GRADLE_DIR")')"
  chmod +x "$GRADLE_DIR/bin/gradle"
  rm -rf "$tmp"
fi

echo ">> Hazır. ANDROID_HOME=$SDK  GRADLE=$GRADLE_DIR/bin/gradle"
