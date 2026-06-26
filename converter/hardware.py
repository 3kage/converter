from __future__ import annotations

import subprocess
import sys

from .ffmpeg_utils import ensure_ffmpeg


def list_video_encoders() -> list[str]:
    ffmpeg, _ = ensure_ffmpeg()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    )
    encoders: list[str] = []
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.append(parts[1])
    return encoders


def pick_hardware_encoder(prefer_hevc: bool = False) -> str | None:
    encoders = set(list_video_encoders())
    if sys.platform == "darwin":
        order = ["hevc_videotoolbox", "h264_videotoolbox"] if prefer_hevc else ["h264_videotoolbox", "hevc_videotoolbox"]
    elif sys.platform == "win32":
        order = ["h264_nvenc", "h264_qsv", "h264_amf", "hevc_nvenc"]
    else:
        order = ["h264_nvenc", "h264_vaapi", "h264_qsv"]
    for name in order:
        if name in encoders:
            return name
    return None
