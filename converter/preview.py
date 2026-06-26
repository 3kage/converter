from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .ffmpeg_utils import ensure_ffmpeg


def generate_preview(input_path: Path, at_sec: float = 1.0) -> Path | None:
    ffmpeg, _ = ensure_ffmpeg()
    if not input_path.is_file():
        return None
    out = Path(tempfile.gettempdir()) / f"vc_preview_{input_path.stem}.png"
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        str(at_sec),
        "-i",
        str(input_path),
        "-vframes",
        "1",
        "-f",
        "image2",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0 and out.is_file():
        return out
    return None
