from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _history_path() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Local" / "VideoConverter"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "VideoConverter"
    else:
        base = Path.home() / ".local" / "share" / "video-converter"
    base.mkdir(parents=True, exist_ok=True)
    return base / "history.json"


def _log_path() -> Path:
    return _history_path().parent / "errors.log"


def load_history(limit: int = 50) -> list[dict]:
    path = _history_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[-limit:]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def append_history(entry: dict) -> None:
    items = load_history(limit=200)
    entry["time"] = datetime.now(timezone.utc).isoformat()
    items.append(entry)
    _history_path().write_text(json.dumps(items[-100:], ensure_ascii=False, indent=2), encoding="utf-8")


def log_error(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _log_path().open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def log_path() -> Path:
    return _log_path()
