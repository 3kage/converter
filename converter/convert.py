from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_utils import run_ffmpeg, run_ffprobe

# Популярні формати та рекомендовані кодеки
OUTPUT_PRESETS: dict[str, dict[str, str]] = {
    "mp4": {"vcodec": "libx264", "acodec": "aac", "extra": ["-movflags", "+faststart"]},
    "mkv": {"vcodec": "libx264", "acodec": "aac", "extra": []},
    "webm": {"vcodec": "libvpx-vp9", "acodec": "libopus", "extra": []},
    "avi": {"vcodec": "libx264", "acodec": "mp3", "extra": []},
    "mov": {"vcodec": "libx264", "acodec": "aac", "extra": ["-movflags", "+faststart"]},
    "wmv": {"vcodec": "wmv2", "acodec": "wmav2", "extra": []},
    "flv": {"vcodec": "libx264", "acodec": "aac", "extra": []},
    "mpeg": {"vcodec": "mpeg2video", "acodec": "mp2", "extra": []},
    "mpg": {"vcodec": "mpeg2video", "acodec": "mp2", "extra": []},
    "ts": {"vcodec": "libx264", "acodec": "aac", "extra": []},
    "m4v": {"vcodec": "libx264", "acodec": "aac", "extra": []},
    "ogv": {"vcodec": "libtheora", "acodec": "libvorbis", "extra": []},
    "gif": {"vcodec": "gif", "acodec": "", "extra": []},
}


@dataclass
class ConvertOptions:
    input_path: Path
    output_path: Path | None = None
    output_format: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    video_bitrate: str | None = None
    audio_bitrate: str | None = None
    crf: int | None = None
    preset: str = "medium"
    audio_stream: int | None = None
    video_stream: int | None = None
    copy_streams: bool = False
    overwrite: bool = False
    dry_run: bool = False


def list_supported_formats() -> list[str]:
    return sorted(OUTPUT_PRESETS.keys())


def _guess_format(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpeg":
        return "jpg"
    return ext or "mp4"


def _resolve_output_path(options: ConvertOptions) -> Path:
    if options.output_path is not None:
        return options.output_path

    fmt = (options.output_format or "mp4").lower().lstrip(".")
    stem = options.input_path.stem
    return options.input_path.with_name(f"{stem}_converted.{fmt}")


def build_ffmpeg_args(options: ConvertOptions) -> list[str]:
    input_path = options.input_path.resolve()
    output_path = _resolve_output_path(options).resolve()
    output_format = _guess_format(output_path)

    if output_path.exists() and not options.overwrite:
        raise FileExistsError(
            f"Вихідний файл уже існує: {output_path}\n"
            "Додайте --overwrite або вкажіть інший шлях через --output."
        )

    args: list[str] = []
    if options.overwrite:
        args.append("-y")
    else:
        args.append("-n")

    args.extend(["-i", str(input_path)])

    if options.video_stream is not None:
        args.extend(["-map", f"0:v:{options.video_stream}"])
    if options.audio_stream is not None:
        args.extend(["-map", f"0:a:{options.audio_stream}"])

    if options.copy_streams:
        args.extend(["-c", "copy"])
    else:
        preset = OUTPUT_PRESETS.get(output_format, OUTPUT_PRESETS["mp4"])
        vcodec = options.video_codec or preset["vcodec"]
        acodec = options.audio_codec or preset["acodec"]
        extra = list(preset["extra"])

        if vcodec:
            args.extend(["-c:v", vcodec])
        if acodec:
            args.extend(["-c:a", acodec])

        if options.crf is not None and vcodec not in ("copy", "gif"):
            args.extend(["-crf", str(options.crf)])
        elif options.video_bitrate:
            args.extend(["-b:v", options.video_bitrate])

        if options.audio_bitrate and acodec:
            args.extend(["-b:a", options.audio_bitrate])

        if vcodec == "libx264" and options.preset:
            args.extend(["-preset", options.preset])

        args.extend(extra)

    args.append(str(output_path))
    return args


def convert_video(
    options: ConvertOptions,
    *,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[Path, list[str]]:
    if not options.input_path.is_file():
        raise FileNotFoundError(f"Файл не знайдено: {options.input_path}")

    probe_data = run_ffprobe(options.input_path)
    duration_sec = None
    try:
        duration_sec = float(probe_data.get("format", {}).get("duration") or 0) or None
    except (TypeError, ValueError):
        duration_sec = None

    args = build_ffmpeg_args(options)
    run_ffmpeg(
        args,
        dry_run=options.dry_run,
        duration_sec=duration_sec,
        on_progress=on_progress,
        cancel_check=cancel_check,
    )
    output_path = _resolve_output_path(options)
    return output_path, args
