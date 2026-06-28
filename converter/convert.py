from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from .ffmpeg_utils import run_ffmpeg, run_ffprobe
from .filters import build_video_filters, join_filters
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

SUBTITLE_EXTENSIONS = {".srt", ".ass", ".vtt", ".ssa"}


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
    prefer_hevc: bool = False
    extract_audio: bool = False
    extract_subtitles: bool = False
    external_audio_path: Path | None = None
    subtitle_path: Path | None = None
    subtitle_stream: int | None = None
    subtitle_burn_in: bool = False
    extract_subtitle_format: str = "srt"
    normalize_audio: bool = False
    gif_mode: bool = False
    metadata_title: str | None = None
    metadata_author: str | None = None
    metadata_date: str | None = None
    strip_metadata: bool = False
    verify_output: bool = True
    merge_inputs: list[Path] = field(default_factory=list)
    crop: str | None = None
    rotation: int | None = None
    fps: str | None = None
    watermark_path: Path | None = None
    watermark_position: str = "10:10"
    two_pass: bool = False
    cover_art_path: Path | None = None
    preserve_chapters: bool = True
    deinterlace: bool = False
    denoise: bool = False
    extra_audio_tracks: list[int] = field(default_factory=list)
    replace_audio: bool = False
    audio_delay_ms: int = 0


def list_supported_formats() -> list[str]:
    return sorted(k for k in OUTPUT_PRESETS if k not in {"mp3", "aac", "wav"})


def list_audio_formats() -> list[str]:
    return ["mp3", "aac", "wav"]


def _guess_format(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "mp4"


def _resolve_output_path(options: ConvertOptions) -> Path:
    if options.output_path is not None:
        return options.output_path
    fmt = (options.output_format or "mp4").lower().lstrip(".")
    if options.extract_audio:
        fmt = options.output_format or "mp3"
    if options.gif_mode:
        fmt = "gif"
    if options.extract_subtitles:
        ext = options.extract_subtitle_format.lower().lstrip(".")
        if ext not in {"srt", "ass", "vtt"}:
            ext = "srt"
        return options.input_path.with_name(f"{options.input_path.stem}.{ext}")
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
    return replace(options, **updates)


def _parse_time(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    text = value.strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return text
    if re.fullmatch(r"\d{1,2}:\d{2}:\d{2}(\.\d+)?", text):
        return text
    raise ValueError(f"Невірний формат часу: {value}. Використовуйте HH:MM:SS або секунди.")


def _input_index(extra_audio: bool, extra_sub: bool, extra_wm: bool, extra_cover: bool) -> dict[str, int]:
    idx = 1
    mapping = {"audio": 0, "sub": 0, "wm": 0, "cover": 0}
    if extra_audio:
        mapping["audio"] = idx
        idx += 1
    if extra_sub:
        mapping["sub"] = idx
        idx += 1
    if extra_wm:
        mapping["wm"] = idx
        idx += 1
    if extra_cover:
        mapping["cover"] = idx
    return mapping


def build_ffmpeg_args(options: ConvertOptions, *, pass_number: int | None = None) -> list[str]:
    options = _apply_quality_preset(options)
    output_path = _resolve_output_path(options).resolve()
    output_format = _guess_format(output_path)

    if output_path.exists() and not options.overwrite and pass_number != 1:
        raise FileExistsError(f"Вихідний файл уже існує: {output_path}")

    args: list[str] = ["-y" if options.overwrite else "-n"]
    start = _parse_time(options.start_time)
    end = _parse_time(options.end_time)
    if start:
        args.extend(["-ss", start])
    if end:
        args.extend(["-to", end])

    video_inputs = [options.input_path.resolve(), *[p.resolve() for p in options.merge_inputs]]
    for path in video_inputs:
        args.extend(["-i", str(path)])

    extra_audio = options.external_audio_path is not None
    extra_sub = options.subtitle_path is not None and not options.extract_subtitles and not options.subtitle_burn_in
    extra_wm = options.watermark_path is not None and not options.gif_mode
    extra_cover = options.cover_art_path is not None and not options.gif_mode

    if extra_audio:
        args.extend(["-i", str(options.external_audio_path.resolve())])
    if extra_sub:
        args.extend(["-i", str(options.subtitle_path.resolve())])
    if extra_wm:
        args.extend(["-i", str(options.watermark_path.resolve())])
    if extra_cover:
        args.extend(["-i", str(options.cover_art_path.resolve())])

    if options.extract_audio:
        args.extend(["-vn", "-map", f"0:a:{options.audio_stream or 0}"])
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
        sub_idx = options.subtitle_stream if options.subtitle_stream is not None else 0
        sub_codec = options.extract_subtitle_format.lower().lstrip(".")
        if sub_codec not in {"srt", "ass", "vtt"}:
            sub_codec = "srt"
        args.extend(["-map", f"0:s:{sub_idx}", "-c:s", sub_codec])
        args.append(str(output_path))
        return args

    burn_path: str | None = None
    if options.subtitle_burn_in:
        if options.subtitle_path:
            burn_path = str(options.subtitle_path.resolve())
        elif options.subtitle_stream is not None:
            burn_path = f"{options.input_path.resolve()}:si={options.subtitle_stream}"

    idx_map = _input_index(extra_audio, extra_sub, extra_wm, extra_cover)
    merge_count = len(video_inputs)
    vf_parts = build_video_filters(
        scale=options.scale,
        crop=options.crop,
        rotation=options.rotation,
        fps=options.fps,
        gif_mode=options.gif_mode,
        deinterlace=options.deinterlace,
        denoise=options.denoise,
        subtitle_burn_in=burn_path,
    )
    vf_chain = join_filters(vf_parts)
    use_complex = merge_count > 1 or extra_wm

    if options.copy_streams and not use_complex and not vf_chain and not burn_path:
        v_idx = options.video_stream if options.video_stream is not None else 0
        args.extend(["-map", f"0:v:{v_idx}"])
        if extra_audio or options.replace_audio:
            args.extend(["-map", f"{idx_map['audio']}:a:0"])
        elif options.audio_stream is not None:
            args.extend(["-map", f"0:a:{options.audio_stream}"])
        elif not options.replace_audio:
            args.extend(["-map", "0:a?"])
        if extra_audio or options.replace_audio:
            args.extend(["-c:v", "copy"])
            acodec = options.audio_codec or str(
                OUTPUT_PRESETS.get(output_format, OUTPUT_PRESETS["mp4"])["acodec"]
            )
            if acodec:
                args.extend(["-c:a", acodec])
        else:
            args.extend(["-c", "copy"])
        args.append(str(output_path))
        return args

    if use_complex:
        filters: list[str] = []
        if merge_count > 1:
            streams = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(merge_count))
            filters.append(f"{streams}concat=n={merge_count}:v=1:a=1[v0][a0]")
            vsrc, asrc = "[v0]", "[a0]"
        else:
            vsrc, asrc = "[0:v:0]", "[0:a:0]"

        if vf_chain:
            filters.append(f"{vsrc}{vf_chain}[v1]")
            vsrc = "[v1]"

        if extra_wm:
            wm_i = idx_map["wm"]
            pos = options.watermark_position
            filters.append(f"{vsrc}[{wm_i}:v:0]overlay={pos}[vout]")
            vsrc = "[vout]"

        filters.append(f"{vsrc}null[vfinal]")
        filter_str = ";".join(filters)
        args.extend(["-filter_complex", filter_str, "-map", "[vfinal]"])
        if merge_count > 1:
            args.extend(["-map", "[a0]"])
        elif extra_audio or options.replace_audio:
            args.extend(["-map", f"{idx_map['audio']}:a:0"])
        elif options.audio_stream is not None:
            args.extend(["-map", f"0:a:{options.audio_stream}"])
        elif not options.replace_audio:
            args.extend(["-map", "0:a?"])
    else:
        v_idx = options.video_stream if options.video_stream is not None else 0
        args.extend(["-map", f"0:v:{v_idx}"])
        if extra_audio or options.replace_audio:
            args.extend(["-map", f"{idx_map['audio']}:a:0"])
        elif options.audio_stream is not None:
            args.extend(["-map", f"0:a:{options.audio_stream}"])
        elif not options.replace_audio:
            args.extend(["-map", "0:a?"])
        if vf_chain:
            args.extend(["-vf", vf_chain])

    if not options.replace_audio:
        for track in options.extra_audio_tracks:
            args.extend(["-map", f"0:a:{track}"])

    if extra_sub:
        sub_i = idx_map["sub"]
        sub_codec = "mov_text" if output_format in {"mp4", "mov", "m4v"} else "srt"
        args.extend(["-map", f"{sub_i}:s:0", "-c:s", sub_codec])
    elif options.subtitle_stream is not None and not options.subtitle_burn_in and not options.subtitle_path:
        sub_codec = "mov_text" if output_format in {"mp4", "mov", "m4v"} else "srt"
        args.extend(["-map", f"0:s:{options.subtitle_stream}", "-c:s", sub_codec])

    if extra_cover:
        cover_i = idx_map["cover"]
        args.extend(["-map", f"{cover_i}:v:0", "-c:v:1", "mjpeg", "-disposition:v:1", "attached_pic"])

    if options.preserve_chapters and not options.strip_metadata:
        args.extend(["-map_chapters", "0"])

    container = OUTPUT_PRESETS.get(output_format, OUTPUT_PRESETS["mp4"])
    vcodec = options.video_codec or str(container["vcodec"])
    acodec = options.audio_codec or str(container["acodec"])
    extra = list(container.get("extra") or [])

    if options.hardware_encode and not options.gif_mode:
        hw = pick_hardware_encoder(prefer_hevc=options.prefer_hevc)
        if hw:
            vcodec = hw

    if options.gif_mode:
        vcodec = "gif"
        acodec = ""

    if vcodec:
        args.extend(["-c:v", vcodec])
    if acodec:
        args.extend(["-c:a", acodec])

    if pass_number == 1:
        args.extend(["-pass", "1", "-an", "-f", "null", "-passlogfile", str(output_path.with_suffix(""))])
        args.append(os.devnull)
        return args

    if pass_number == 2:
        args.extend(["-pass", "2", "-passlogfile", str(output_path.with_suffix(""))])

    if options.two_pass and options.video_bitrate and vcodec:
        args.extend(["-b:v", options.video_bitrate])
    elif (
        options.crf is not None
        and vcodec not in ("copy", "gif")
        and "nvenc" not in vcodec
        and "videotoolbox" not in vcodec
        and not options.two_pass
    ):
        args.extend(["-crf", str(options.crf)])
    elif options.video_bitrate and vcodec:
        args.extend(["-b:v", options.video_bitrate])

    if options.audio_bitrate and acodec:
        args.extend(["-b:a", options.audio_bitrate])

    if vcodec == "libx264" and options.preset:
        args.extend(["-preset", options.preset])

    if options.normalize_audio and acodec:
        af = "loudnorm"
        if options.audio_delay_ms:
            af = f"adelay={options.audio_delay_ms}|{options.audio_delay_ms},{af}"
        args.extend(["-af", af])
    elif options.audio_delay_ms and acodec:
        args.extend(["-af", f"adelay={options.audio_delay_ms}|{options.audio_delay_ms}"])

    if options.strip_metadata:
        args.extend(["-map_metadata", "-1"])
    else:
        if options.metadata_title:
            args.extend(["-metadata", f"title={options.metadata_title}"])
        if options.metadata_author:
            args.extend(["-metadata", f"author={options.metadata_author}"])
        if options.metadata_date:
            args.extend(["-metadata", f"date={options.metadata_date}"])

    args.extend(extra)
    args.append(str(output_path))
    return args


def verify_output(output_path: Path) -> None:
    if output_path.suffix.lower() in {".srt", ".ass", ".vtt"}:
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
    if options.start_time or options.end_time or options.merge_inputs:
        duration_sec = None

    if (
        options.two_pass
        and options.video_bitrate
        and not options.dry_run
        and not options.copy_streams
        and not options.extract_audio
        and not options.extract_subtitles
        and not options.gif_mode
    ):
        pass1 = build_ffmpeg_args(options, pass_number=1)
        run_ffmpeg(pass1, dry_run=False, cancel_check=cancel_check)
        args = build_ffmpeg_args(options, pass_number=2)
    else:
        args = build_ffmpeg_args(options)

    if options.dry_run:
        return _resolve_output_path(options), args

    run_ffmpeg(
        args,
        dry_run=False,
        duration_sec=duration_sec,
        on_progress=on_progress,
        cancel_check=cancel_check,
    )
    output_path = _resolve_output_path(options)
    if options.verify_output:
        verify_output(output_path)
    return output_path, args
