from __future__ import annotations

from pathlib import Path

from .ffmpeg_utils import run_ffprobe


def list_selectable_streams(input_path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]], list[tuple[int, str]]]:
    data = run_ffprobe(input_path)
    video: list[tuple[int, str]] = []
    audio: list[tuple[int, str]] = []
    subtitles: list[tuple[int, str]] = []
    vi = ai = si = 0
    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        codec = stream.get("codec_name", "?")
        if kind == "video":
            w, h = stream.get("width"), stream.get("height")
            label = f"{vi}: {codec} {w}x{h}"
            video.append((vi, label))
            vi += 1
        elif kind == "audio":
            ch = stream.get("channels", "?")
            label = f"{ai}: {codec} {ch}ch"
            audio.append((ai, label))
            ai += 1
        elif kind == "subtitle":
            lang = stream.get("tags", {}).get("language", "")
            suffix = f" ({lang})" if lang else ""
            label = f"{si}: {codec}{suffix}"
            subtitles.append((si, label))
            si += 1
    return video, audio, subtitles
