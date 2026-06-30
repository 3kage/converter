from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ffmpeg_utils import run_ffprobe


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _fmt_bitrate(value: str | int | None) -> str:
    if value in (None, "", "N/A"):
        return "—"
    bits = int(value)
    if bits >= 1_000_000:
        return f"{bits / 1_000_000:.2f} Mbps"
    if bits >= 1_000:
        return f"{bits / 1_000:.1f} kbps"
    return f"{bits} bps"


def _fmt_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, "", "N/A"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fps(stream: dict[str, Any]) -> str:
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or ""
    if not rate or rate == "0/0":
        return "—"
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            num_f = float(num)
            den_f = float(den)
            if den_f:
                return f"{num_f / den_f:.3f} fps"
        except ValueError:
            pass
    return rate


@dataclass
class StreamInfo:
    index: int
    kind: str
    codec: str
    profile: str
    language: str
    title: str
    details: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class MediaInfo:
    path: Path
    container: str
    format_long_name: str
    duration_sec: float | None
    size_bytes: int | None
    overall_bitrate: str
    streams: list[StreamInfo]
    tags: dict[str, str]
    chapters: int


def analyze_file(input_path: Path) -> MediaInfo:
    data = run_ffprobe(input_path)
    fmt = data.get("format", {})
    streams_raw = data.get("streams", [])
    chapters = data.get("chapters") or []

    streams: list[StreamInfo] = []
    for stream in streams_raw:
        codec_type = stream.get("codec_type", "unknown")
        tags = stream.get("tags") or {}
        language = tags.get("language") or tags.get("LANGUAGE") or "—"
        title = tags.get("title") or tags.get("handler_name") or "—"
        profile = stream.get("profile") or "—"
        codec = stream.get("codec_name") or stream.get("codec_tag_string") or "—"

        details: list[tuple[str, str]] = []
        if codec_type == "video":
            width = stream.get("width")
            height = stream.get("height")
            details.extend(
                [
                    ("Роздільність", f"{width}x{height}" if width and height else "—"),
                    ("Частота кадрів", _fps(stream)),
                    ("Pixel format", stream.get("pix_fmt") or "—"),
                    ("Бітрейт", _fmt_bitrate(stream.get("bit_rate"))),
                    ("Aspect ratio", stream.get("display_aspect_ratio") or "—"),
                    ("Color space", stream.get("color_space") or "—"),
                    ("Bit depth", str(stream.get("bits_per_raw_sample") or "—")),
                ]
            )
        elif codec_type == "audio":
            channels = stream.get("channels")
            layout = stream.get("channel_layout") or "—"
            details.extend(
                [
                    ("Канали", str(channels) if channels is not None else "—"),
                    ("Layout", layout),
                    ("Sample rate", f"{stream.get('sample_rate')} Hz" if stream.get("sample_rate") else "—"),
                    ("Sample format", stream.get("sample_fmt") or "—"),
                    ("Бітрейт", _fmt_bitrate(stream.get("bit_rate"))),
                ]
            )
        elif codec_type == "subtitle":
            details.append(("Формат", stream.get("codec_long_name") or codec))
        else:
            details.append(("Тип", codec_type))

        streams.append(
            StreamInfo(
                index=int(stream.get("index", 0)),
                kind=codec_type,
                codec=codec,
                profile=profile,
                language=language,
                title=title,
                details=details,
            )
        )

    tags = fmt.get("tags") or {}
    return MediaInfo(
        path=input_path,
        container=fmt.get("format_name") or "—",
        format_long_name=fmt.get("format_long_name") or "—",
        duration_sec=_safe_float(fmt.get("duration")),
        size_bytes=int(fmt["size"]) if fmt.get("size") is not None else None,
        overall_bitrate=_fmt_bitrate(fmt.get("bit_rate")),
        streams=streams,
        tags={str(k): str(v) for k, v in tags.items()},
        chapters=len(chapters),
    )


def render_media_info(info: MediaInfo) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"Файл: {info.path}")
    lines.append("=" * 72)
    lines.append(f"Контейнер:        {info.container}")
    lines.append(f"Опис формату:     {info.format_long_name}")
    lines.append(f"Тривалість:       {_fmt_duration(info.duration_sec)}")
    lines.append(f"Розмір:           {_fmt_size(info.size_bytes)}")
    lines.append(f"Загальний бітрейт: {info.overall_bitrate}")
    lines.append(f"Розділів (chapters): {info.chapters}")

    if info.tags:
        lines.append("")
        lines.append("Метадані контейнера:")
        for key, value in sorted(info.tags.items()):
            lines.append(f"  {key}: {value}")

    for stream in info.streams:
        kind_label = {
            "video": "Відео",
            "audio": "Аудіо",
            "subtitle": "Субтитри",
        }.get(stream.kind, stream.kind.capitalize())
        lines.append("")
        lines.append("-" * 72)
        lines.append(
            f"Потік #{stream.index} — {kind_label}: {stream.codec} "
            f"(profile: {stream.profile}, мова: {stream.language})"
        )
        if stream.title != "—":
            lines.append(f"  Назва: {stream.title}")
        for label, value in stream.details:
            lines.append(f"  {label:<16} {value}")

    lines.append("=" * 72)
    return "\n".join(lines)
