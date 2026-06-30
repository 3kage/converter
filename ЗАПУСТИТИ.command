#!/bin/bash
# Подвійний клік — зняти карантин macOS і відкрити Video Converter.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

APP="$DIR/VideoConverter.app"

if [[ ! -d "$APP" ]]; then
  osascript <<'APPLESCRIPT'
display dialog "Не знайдено VideoConverter.app у цій папці.

Покладіть цей файл поруч із VideoConverter.app (після розархівування)." buttons {"OK"} default button 1 with icon caution
APPLESCRIPT
  exit 1
fi

echo "Знімаємо карантин macOS (виправляє «повреждено»)..."
xattr -cr "$APP" 2>/dev/null || true

echo "Запуск Video Converter..."
open "$APP"

sleep 2
