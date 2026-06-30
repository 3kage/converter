#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg not found. Install with: brew install ffmpeg"
  exit 1
fi

python3 -m pip install -e ".[gui]" -q
python3 video_converter_gui.py
