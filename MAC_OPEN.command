#!/bin/bash
# Double-click this file on macOS to remove Gatekeeper quarantine and launch Video Converter.
# Подвійний клік — зняти «карантин» macOS і відкрити Video Converter.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

APP="$DIR/VideoConverter.app"

if [[ ! -d "$APP" ]]; then
  osascript <<'APPLESCRIPT'
display dialog "VideoConverter.app not found in this folder.

Place this script next to VideoConverter.app (same folder as after unzipping).

Не знайдено VideoConverter.app — покладіть цей файл поруч із програмою." buttons {"OK"} default button 1 with icon caution
APPLESCRIPT
  exit 1
fi

echo "Removing macOS quarantine (fixes «damaged» / «повреждено»)..."
xattr -cr "$APP" 2>/dev/null || true

echo "Launching Video Converter..."
open "$APP"

sleep 2
