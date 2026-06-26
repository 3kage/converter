from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .ffmpeg_utils import run_ffmpeg, run_ffprobe
from .hardware import pick_hardware_encoder
from .presets import QUALITY_PRESETS, QualityPreset, apply_quality_preset

OUTPUT_PRESETS: dict[str, dict[str, str | list[str]]] = {
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
    "mp3": {"vcodec": "", "acodec": "libmp3lame", "extra": []},
    "aac": {"vcodec": "", "acodec": "aac", "extra": []},
    "wav": {"vcodec": "", "acodec": "pcm_s16le", "extra": []},
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
    quality_preset_id: str | None = None
    scale: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    hardware_encode: bool = False
    extract_audio: bool = False
    extract_subtitles: bool = False
    external_audio_path: Path | None = None
    subtitle_path: Path | None = None
    normalize_audio: bool = False
    gif_mode: bool = False
    metadata_title: str | None = None
    metadata_author: str | None = None
    strip_metadata: bool = False
    verify_output: bool = True


def list_supported_formats() -> list[str]:
    return sorted(k for k in OUTPUT_PRESETS if k not in {"mp3", "aac", "wav"})


def list_audio_formats() -> list[str]:
    return ["mp3", "aac", "wav"]


def _guess_format(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return ext or "mp4"


def _resolve_output_path(options: ConvertOptions) -> Path:
    if options.output_path is not None:
        return options.output_path
    fmt = (options.output_format or "mp4").lower().lstrip(".")
    if options.extract_audio:
        fmt = options.output_format or "mp3"
    if options.gif_mode:
        fmt = "gif"
    return options.input_path.with_name(f"{options.input_path.stem}_converted.{fmt}")


def _apply_quality_preset(options: ConvertOptions) -> ConvertOptions:
    if not options.quality_preset_id or options.quality_preset_id == "custom":
        return options
    preset: QualityPreset = apply_quality_preset(options.quality_preset_id)
    updates: dict = {}
    if preset.crf is not None and options.crf is None:
        updates["crf"] = preset.crf
    if preset.preset and options.preset == "medium":
        updates["preset"] = preset.preset
    if preset.video_bitrate and not options.video_bitrate:
        updates["video_bitrate"] = preset.video_bitrate
    if preset.audio_bitrate and not options.audio_bitrate:
        updates["audio_bitrate"] = preset.audio_bitrate
    if preset.scale and not options.scale:
        updates["scale"] = preset.scale
    if preset.format and not options.output_format:
        updates["output_format"] = preset.format
    if not updates:
        return options
    return ConvertOptions(**{**options.__dict__, **updates})


def _parse_time(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    text = value.strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return text
    if re.fullmatch(r"\d{1,2}:\d{2}:\d{2}(\.\d+)?", text):
        return text
    raise ValueError(f"Невірний формат часу: {value}. Використовуйте HH:MM:SS або секунди.")


def build_ffmpeg_args(options: ConvertOptions) -> list[str]:
    options = _apply_quality_preset(options)
    input_path = options.input_path.resolve()
    output_path = _resolve_output_path(options).resolve()
    output_format = _guess_format(output_path)

    if output_path.exists() and not options.overwrite:
        raise FileExistsError(f"Вихідний файл уже існує: {output_path}")

    args: list[str] = ["-y" if options.overwrite else "-n"]
    start = _parse_time(options.start_time)
    end = _parse_time(options.end_time)

    if start:
        args.extend(["-ss", start])

    args.extend(["-i", str(input_path)])

    if options.external_audio_path:
        args.extend(["-i", str(options.external_audio_path.resolve())])

    if options.subtitle_path and not options.extract_subtitles:
        args.extend(["-i", str(options.subtitle_path.resolve())])

    if end:
        args.extend(["-to", end])

    if options.extract_audio:
        args.extend(["-vn"])
        fmt = output_format if output_format in list_audio_formats() else "mp3"
        acodec = OUTPUT_PRESETS.get(fmt, OUTPUT_PRESETS["mp3"])["acodec"]
        if acodec:
            args.extend(["-c:a", str(acodec)])
        if options.audio_bitrate:
            args.extend(["-b:a", options.audio_bitrate])
        if options.normalize_audio:
            args.extend(["-af", "loudnorm"])
        args.append(str(output_path))
        return args

    if options.extract_subtitles:
        args.extend(["-map", "0:s:0", "-c:s", "srt", str(output_path.with_suffix(".srt"))])
        return args

    if options.copy_streams and not any([options.scale, options.external_audio_path, options.subtitle_path, options.gif_mode]):
        if options.video_stream is not None:
            args.extend(["-map", f"0:v:{options.video_stream}"])
        else:
            args.extend(["-map", "0:v:0"])
        if options.external_audio_path:
            args.extend(["-map", "1:a:0"])
        elif options.audio_stream is not None:
            args.extend(["-map", f"0:a:{options.audio_stream}"])
        else:
            args.extend(["-map", "0:a?"])
        args.extend(["-c", "copy"])
        args.append(str(output_path))
        return args

    if options.video_stream is not None:
        args.extend(["-map", f"0:v:{options.video_stream}"])
    else:
        args.extend(["-map", "0:v:0"])

    if options.external_audio_path:
        args.extend(["-map", "1:a:0"])
    elif options.audio_stream is not None:
        args.extend(["-map", f"0:a:{options.audio_stream}"])
    else:
        args.extend(["-map", "0:a?"])

    if options.subtitle_path:
        args.extend(["-map", "2:s:0", "-c:s", "mov_text" if output_format in {"mp4", "mov", "m4v"} else "srt"])

    container = OUTPUT_PRESETS.get(output_format, OUTPUT_PRESETS["mp4"])
    vcodec = options.video_codec or str(container["vcodec"])
    acodec = options.audio_codec or str(container["acodec"])
    extra = list(container.get("extra") or [])

    if options.hardware_encode and not options.gif_mode:
        hw = pick_hardware_encoder()
        if hw:
            vcodec = hw

    if options.gif_mode:
        vcodec = "gif"
        acodec = ""

    filters: list[str] = []
    if options.scale:
        filters.append(f"scale={options.scale}")
    if options.gif_mode:
        filters.append("fps=12,scale=480:-1:flags=lanczos")
    if filters:
        args.extend(["-vf", ",".join(filters)])

    if vcodec:
        args.extend(["-c:v", vcodec])
    if acodec:
        args.extend(["-c:a", acodec])

    if options.crf is not None and vcodec not in ("copy", "gif") and "videotoolbox" not in vcodec and "nvenc" not in vcodec:
        args.extend(["-crf", str(options.crf)])
    elif options.video_bitrate and vcodec:
        args.extend(["-b:v", options.video_bitrate])
    elif options.video_bitrate and "videotoolbox" in vcodec:
        args.extend(["-b:v", options.video_bitrate])

    if options.audio_bitrate and acodec:
        args.extend(["-b:a", options.audio_bitrate])

    if vcodec == "libx264" and options.preset:
        args.extend(["-preset", options.preset])

    if options.normalize_audio and acodec:
        args.extend(["-af", "loudnorm"])

    if options.strip_metadata:
        args.extend(["-map_metadata", "-1"])
    else:
        if options.metadata_title:
            args.extend(["-metadata", f"title={options.metadata_title}"])
        if options.metadata_author:
            args.extend(["-metadata", f"author={options.metadata_author}"])

    args.extend(extra)
    args.append(str(output_path))
    return args


def verify_output(output_path: Path) -> None:
    if output_path.suffix.lower() == ".srt":
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Субтитри не створено: {output_path}")
        return
    run_ffprobe(output_path)


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

    if options.start_time or options.end_time:
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
    if options.extract_subtitles:
        output_path = output_path.with_suffix(".srt")
    if options.verify_output and not options.dry_run:
        verify_output(output_path)
    return output_path, args
