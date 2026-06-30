from __future__ import annotations

import shutil
import sys
from pathlib import Path

_APP_ROOT: Path | None = None
_DATA_DIR: Path | None = None
_MIGRATED = False

_LEGACY_FILES = (
    "settings.json",
    "custom_presets.json",
    "pending_batch.json",
    "history.json",
    "errors.log",
    "crash.log",
    "startup.json",
)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Корінь програми: папка з .exe / бінарником або корінь репозиторію в dev-режимі."""
    global _APP_ROOT
    if _APP_ROOT is not None:
        return _APP_ROOT
    if is_frozen():
        _APP_ROOT = Path(sys.executable).resolve().parent
    else:
        _APP_ROOT = Path(__file__).resolve().parent.parent
    return _APP_ROOT


def _resolve_data_path() -> Path:
    if is_frozen() and sys.platform == "darwin":
        exe = Path(sys.executable).resolve()
        for index, part in enumerate(exe.parts):
            if part.endswith(".app"):
                bundle = Path(*exe.parts[: index + 1])
                return bundle.parent / "VideoConverter-data"
    return app_root() / "data"


def data_dir() -> Path:
    """Портативна папка даних поруч із програмою."""
    global _DATA_DIR, _MIGRATED
    if _DATA_DIR is not None:
        return _DATA_DIR
    path = _resolve_data_path()
    path.mkdir(parents=True, exist_ok=True)
    _DATA_DIR = path
    if not _MIGRATED:
        _migrate_legacy_data(path)
        _MIGRATED = True
    return _DATA_DIR


def temp_dir() -> Path:
    path = data_dir() / "temp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def legacy_config_dir() -> Path | None:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Local" / "VideoConverter"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "VideoConverter"
    else:
        base = Path.home() / ".local" / "share" / "video-converter"
    return base if base.is_dir() else None


def _migrate_legacy_data(target: Path) -> None:
    legacy = legacy_config_dir()
    if legacy is None:
        return
    for name in _LEGACY_FILES:
        dst = target / name
        if dst.exists():
            continue
        src = legacy / name
        if src.is_file():
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass


def reset_paths_for_tests() -> None:
    global _APP_ROOT, _DATA_DIR, _MIGRATED
    _APP_ROOT = None
    _DATA_DIR = None
    _MIGRATED = False
