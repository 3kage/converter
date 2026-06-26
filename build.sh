#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is for macOS only. Use build.ps1 on Windows."
  exit 1
fi

echo "Installing build dependencies..."
python3 -m pip install -e . -q
python3 -m pip install -r requirements-dev.txt -q

FFMPEG_DIR="$PROJECT_ROOT/ffmpeg"
mkdir -p "$FFMPEG_DIR"

download_static_ffmpeg() {
  local arch_tag release_tag
  if [[ "$(uname -m)" == "arm64" ]]; then
    arch_tag="darwin-arm64"
  else
    arch_tag="darwin-x64"
  fi
  release_tag="b6.1.1"

  echo "Downloading static FFmpeg (${arch_tag})..."
  curl -L -o "${FFMPEG_DIR}/ffmpeg.gz" \
    "https://github.com/eugeneware/ffmpeg-static/releases/download/${release_tag}/ffmpeg-${arch_tag}.gz"
  curl -L -o "${FFMPEG_DIR}/ffprobe.gz" \
    "https://github.com/eugeneware/ffmpeg-static/releases/download/${release_tag}/ffprobe-${arch_tag}.gz"

  gunzip -cf "${FFMPEG_DIR}/ffmpeg.gz" > "${FFMPEG_DIR}/ffmpeg"
  gunzip -cf "${FFMPEG_DIR}/ffprobe.gz" > "${FFMPEG_DIR}/ffprobe"
  rm -f "${FFMPEG_DIR}/ffmpeg.gz" "${FFMPEG_DIR}/ffprobe.gz"
  chmod +x "${FFMPEG_DIR}/ffmpeg" "${FFMPEG_DIR}/ffprobe"
}

download_static_ffmpeg

echo "Verifying bundled FFmpeg..."
"${FFMPEG_DIR}/ffmpeg" -version >/dev/null
"${FFMPEG_DIR}/ffprobe" -version >/dev/null

echo "Building VideoConverter.app with PyInstaller..."
python3 -m PyInstaller VideoConverter-mac.spec --noconfirm --clean

APP_MACOS="$PROJECT_ROOT/dist/VideoConverter.app/Contents/MacOS"
TARGET_FFMPEG="$APP_MACOS/ffmpeg"
mkdir -p "$TARGET_FFMPEG"
cp "$FFMPEG_DIR/ffmpeg" "$TARGET_FFMPEG/ffmpeg"
cp "$FFMPEG_DIR/ffprobe" "$TARGET_FFMPEG/ffprobe"
chmod +x "$TARGET_FFMPEG/ffmpeg" "$TARGET_FFMPEG/ffprobe"

echo "Smoke test: bundled FFmpeg inside app..."
"${TARGET_FFMPEG}/ffmpeg" -version >/dev/null
"${TARGET_FFMPEG}/ffprobe" -version >/dev/null

echo ""
echo "Build complete."
echo "Run: open \"$PROJECT_ROOT/dist/VideoConverter.app\""
echo "Or:  \"$APP_MACOS/VideoConverter\""
