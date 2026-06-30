from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .paths import data_dir, is_frozen
from .updater import can_auto_update, get_install_paths

ROLLBACK_ENV = "VIDEO_CONVERTER_ROLLBACK"
BACKUP_DIR_NAME = "VideoConverter_previous"


def _state_dir() -> Path:
    return data_dir()


def _crash_log() -> Path:
    return _state_dir() / "crash.log"


def _startup_state() -> Path:
    return _state_dir() / "startup.json"


def backup_install_root(install_root: Path) -> Path:
    backup = install_root.parent / BACKUP_DIR_NAME
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    if sys.platform == "win32":
        result = subprocess.run(
            [
                "robocopy",
                str(install_root),
                str(backup),
                "/MIR",
                "/R:2",
                "/W:1",
                "/NFL",
                "/NDL",
                "/NJH",
                "/NJS",
                "/NP",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode >= 8:
            raise RuntimeError(f"Backup failed (robocopy exit {result.returncode})")
    else:
        shutil.copytree(install_root, backup, symlinks=True)
    return backup


def rollback_to_previous_install() -> bool:
    if not is_frozen():
        return False
    install_root, _executable = get_install_paths()
    backup = install_root.parent / BACKUP_DIR_NAME
    if not backup.is_dir():
        return False
    if sys.platform == "win32":
        result = subprocess.run(
            [
                "robocopy",
                str(backup),
                str(install_root),
                "/MIR",
                "/R:3",
                "/W:2",
                "/NFL",
                "/NDL",
                "/NJH",
                "/NJS",
                "/NP",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode >= 8:
            return False
    elif sys.platform == "darwin":
        if install_root.suffix == ".app":
            shutil.rmtree(install_root, ignore_errors=True)
            shutil.copytree(backup, install_root, symlinks=True)
            subprocess.run(["xattr", "-cr", str(install_root)], check=False)
        else:
            shutil.copytree(backup, install_root, dirs_exist_ok=True)
    elif sys.platform.startswith("linux"):
        shutil.copytree(backup, install_root, dirs_exist_ok=True)
    else:
        return False
    return True


def mark_startup_ok(version: str | None = None) -> None:
    payload = {
        "version": version or __version__,
        "time": datetime.now(UTC).isoformat(),
    }
    _startup_state().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.environ.pop(ROLLBACK_ENV, None)


def _log_crash(exc: BaseException) -> None:
    stamp = datetime.now(UTC).isoformat()
    text = f"\n[{stamp}] v{__version__}\n{traceback.format_exc()}\n"
    with _crash_log().open("a", encoding="utf-8") as handle:
        handle.write(text)


def _restart_app() -> None:
    _, executable = get_install_paths()
    env = os.environ.copy()
    env[ROLLBACK_ENV] = "1"
    if sys.platform == "win32":
        subprocess.Popen([str(executable)], close_fds=True, env=env)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-n", str(executable)], close_fds=True, env=env)
    else:
        subprocess.Popen([str(executable)], close_fds=True, start_new_session=True, env=env)


def _show_fatal_message(title: str, message: str) -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
            return
        except OSError:
            pass
    print(f"{title}\n\n{message}", file=sys.stderr)


def handle_startup_failure(exc: BaseException) -> bool:
    """Return True if the app was restarted after rollback."""
    _log_crash(exc)
    if not is_frozen() or not can_auto_update():
        return False
    if os.environ.get(ROLLBACK_ENV) == "1":
        _show_fatal_message(
            "Video Converter",
            "The application failed to start even after restoring the previous version.\n\n"
            f"Details were saved to:\n{_crash_log()}",
        )
        return False
    if not rollback_to_previous_install():
        _show_fatal_message(
            "Video Converter",
            "The application failed to start and no previous installation backup was found.\n\n"
            f"Details were saved to:\n{_crash_log()}",
        )
        return False
    _restart_app()
    return True
