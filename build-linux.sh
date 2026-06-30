#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

python3 -m pip install -e ".[dev]" -q

FFMPEG_DIR="$ROOT/ffmpeg"
mkdir -p "$FFMPEG_DIR"

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "Install ffmpeg first, e.g.: sudo apt install ffmpeg"
  exit 1
fi

cp "$(command -v ffmpeg)" "$FFMPEG_DIR/ffmpeg"
cp "$(command -v ffprobe)" "$FFMPEG_DIR/ffprobe"
chmod +x "$FFMPEG_DIR/ffmpeg" "$FFMPEG_DIR/ffprobe"

python3 -m PyInstaller VideoConverter-linux.spec --noconfirm --clean

DIST="$ROOT/dist/VideoConverter"
mkdir -p "$DIST/ffmpeg"
cp "$FFMPEG_DIR/ffmpeg" "$DIST/ffmpeg/ffmpeg"
cp "$FFMPEG_DIR/ffprobe" "$DIST/ffmpeg/ffprobe"

echo "Build complete: $DIST/VideoConverter"
