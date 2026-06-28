from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .paths import app_root, is_frozen

ProgressCallback = Callable[[float, str], None]


class FFmpegNotFoundError(RuntimeError):
    """FFmpeg або ffprobe не знайдено в PATH."""


def _bundled_bin_dirs() -> list[Path]:
    dirs: list[Path] = []
    if is_frozen():
        dirs.append(app_root() / "ffmpeg")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass) / "ffmpeg")
    dirs.append(app_root() / "ffmpeg")
    return dirs


def _resolve_tool(name: str) -> str:
    for directory in _bundled_bin_dirs():
        candidate = directory / f"{name}.exe" if sys.platform == "win32" else directory / name
        if candidate.is_file():
            return str(candidate)

    path = shutil.which(name)
    if path is None and sys.platform == "darwin":
        for prefix in ("/opt/homebrew/bin", "/usr/local/bin"):
            candidate = Path(prefix) / name
            if candidate.is_file():
                return str(candidate)

    if path is None:
        raise FFmpegNotFoundError(
            f"Утиліту «{name}» не знайдено. Встановіть FFmpeg і додайте його до PATH.\n"
            "Windows: winget install Gyan.FFmpeg\n"
            "macOS:   brew install ffmpeg\n"
            "Linux:   sudo apt install ffmpeg"
        )
    return path


def ensure_ffmpeg() -> tuple[str, str]:
    return _resolve_tool("ffmpeg"), _resolve_tool("ffprobe")


def run_ffprobe(input_path: Path) -> dict[str, Any]:
    _, ffprobe = ensure_ffmpeg()
    if not input_path.is_file():
        raise FileNotFoundError(f"Файл не знайдено: {input_path}")

    cmd = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"ffprobe не зміг прочитати файл: {stderr or 'невідома помилка'}")

    return json.loads(result.stdout)


def _parse_ffmpeg_time(value: str) -> float | None:
    match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)", value)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def run_ffmpeg(
    args: list[str],
    *,
    dry_run: bool = False,
    duration_sec: float | None = None,
    on_progress: ProgressCallback | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[str]:
    ffmpeg, _ = ensure_ffmpeg()
    cmd = [ffmpeg, *args]
    if dry_run:
        return cmd

    if on_progress is None:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"ffmpeg завершився з помилкою: {stderr or 'невідома помилка'}")
        return cmd

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stderr is not None

    while True:
        if cancel_check and cancel_check():
            process.terminate()
            process.wait(timeout=5)
            raise RuntimeError("Конвертацію скасовано.")

        line = process.stderr.readline()
        if not line and process.poll() is not None:
            break

        current_time = _parse_ffmpeg_time(line)
        if current_time is not None and duration_sec and duration_sec > 0:
            percent = min(current_time / duration_sec * 100.0, 100.0)
            on_progress(percent, line.strip())

    if process.returncode != 0:
        stderr_tail = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"ffmpeg завершився з помилкою: {stderr_tail.strip() or 'невідома помилка'}")

    on_progress(100.0, "Готово")
    return cmd
