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
  local arch_tag extract_dir tarball_url
  if [[ "$(uname -m)" == "arm64" ]]; then
    arch_tag="macosarm64"
  else
    arch_tag="macos64"
  fi

  extract_dir="$(mktemp -d /tmp/ffmpeg-build.XXXXXX)"
  tarball_url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-${arch_tag}-gpl.tar.xz"

  echo "Downloading static FFmpeg (${arch_tag})..."
  curl -L -o "${extract_dir}/ffmpeg.tar.xz" "$tarball_url"
  tar -xJf "${extract_dir}/ffmpeg.tar.xz" -C "$extract_dir"

  local ffmpeg_bin ffprobe_bin
  ffmpeg_bin="$(find "$extract_dir" -type f -name ffmpeg | head -n 1)"
  ffprobe_bin="$(find "$extract_dir" -type f -name ffprobe | head -n 1)"

  if [[ -z "$ffmpeg_bin" || -z "$ffprobe_bin" ]]; then
    echo "Failed to find ffmpeg/ffprobe in downloaded archive."
    exit 1
  fi

  cp "$ffmpeg_bin" "$FFMPEG_DIR/ffmpeg"
  cp "$ffprobe_bin" "$FFMPEG_DIR/ffprobe"
  chmod +x "$FFMPEG_DIR/ffmpeg" "$FFMPEG_DIR/ffprobe"
  rm -rf "$extract_dir"
}

download_static_ffmpeg

echo "Verifying bundled FFmpeg..."
"$FFMPEG_DIR/ffmpeg" -version >/dev/null
"$FFMPEG_DIR/ffprobe" -version >/dev/null

echo "Building VideoConverter.app with PyInstaller..."
python3 -m PyInstaller VideoConverter-mac.spec --noconfirm --clean

APP_MACOS="$PROJECT_ROOT/dist/VideoConverter.app/Contents/MacOS"
TARGET_FFMPEG="$APP_MACOS/ffmpeg"
mkdir -p "$TARGET_FFMPEG"
cp "$FFMPEG_DIR/ffmpeg" "$TARGET_FFMPEG/ffmpeg"
cp "$FFMPEG_DIR/ffprobe" "$TARGET_FFMPEG/ffprobe"
chmod +x "$TARGET_FFMPEG/ffmpeg" "$TARGET_FFMPEG/ffprobe"

echo "Smoke test: bundled FFmpeg inside app..."
"$TARGET_FFMPEG/ffmpeg" -version >/dev/null
"$TARGET_FFMPEG/ffprobe" -version >/dev/null

echo ""
echo "Build complete."
echo "Run: open \"$PROJECT_ROOT/dist/VideoConverter.app\""
echo "Or:  \"$APP_MACOS/VideoConverter\""
