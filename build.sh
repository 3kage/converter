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

resolve_tool() {
  command -v "$1" 2>/dev/null || true
}

FFMPEG_PATH="$(resolve_tool ffmpeg)"
FFPROBE_PATH="$(resolve_tool ffprobe)"

if [[ -z "$FFMPEG_PATH" || -z "$FFPROBE_PATH" ]]; then
  echo "FFmpeg not found. Installing via Homebrew..."
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required. Install from https://brew.sh"
    exit 1
  fi
  brew install ffmpeg
  FFMPEG_PATH="$(resolve_tool ffmpeg)"
  FFPROBE_PATH="$(resolve_tool ffprobe)"
fi

if [[ -z "$FFMPEG_PATH" || -z "$FFPROBE_PATH" ]]; then
  echo "FFmpeg not found. Install with: brew install ffmpeg"
  exit 1
fi

echo "Copying FFmpeg binaries..."
cp "$FFMPEG_PATH" "$FFMPEG_DIR/ffmpeg"
cp "$FFPROBE_PATH" "$FFMPEG_DIR/ffprobe"
chmod +x "$FFMPEG_DIR/ffmpeg" "$FFMPEG_DIR/ffprobe"

echo "Building VideoConverter.app with PyInstaller..."
python3 -m PyInstaller VideoConverter-mac.spec --noconfirm --clean

APP_MACOS="$PROJECT_ROOT/dist/VideoConverter.app/Contents/MacOS"
TARGET_FFMPEG="$APP_MACOS/ffmpeg"
mkdir -p "$TARGET_FFMPEG"
cp "$FFMPEG_DIR/ffmpeg" "$TARGET_FFMPEG/ffmpeg"
cp "$FFMPEG_DIR/ffprobe" "$TARGET_FFMPEG/ffprobe"
chmod +x "$TARGET_FFMPEG/ffmpeg" "$TARGET_FFMPEG/ffprobe"

echo ""
echo "Build complete."
echo "Run: open \"$PROJECT_ROOT/dist/VideoConverter.app\""
echo "Or:  \"$APP_MACOS/VideoConverter\""
