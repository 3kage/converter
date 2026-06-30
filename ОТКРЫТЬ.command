#!/bin/bash
# То же самое, что MAC_OPEN.command — для пользователей с русской системой.
# Подвойной клик → снять карантин → открыть программу.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

APP="$DIR/VideoConverter.app"

if [[ ! -d "$APP" ]]; then
  osascript <<'APPLESCRIPT'
display dialog "Не найден VideoConverter.app в этой папке.

Положите этот файл рядом с VideoConverter.app (в одну папку после распаковки)." buttons {"OK"} default button 1 with icon caution
APPLESCRIPT
  exit 1
fi

echo "Снимаем карантин macOS (исправляет «повреждено»)..."
xattr -cr "$APP" 2>/dev/null || true

echo "Запуск Video Converter..."
open "$APP"

sleep 2
