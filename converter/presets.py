from __future__ import annotations

from dataclasses import dataclass

RESOLUTIONS: dict[str, str | None] = {
    "original": None,
    "4k": "3840:2160",
    "1080p": "1920:1080",
    "720p": "1280:720",
    "480p": "854:480",
}


@dataclass(frozen=True)
class QualityPreset:
    id: str
    crf: int | None = None
    preset: str = "medium"
    video_bitrate: str | None = None
    audio_bitrate: str | None = None
    scale: str | None = None
    format: str = "mp4"


QUALITY_PRESETS: dict[str, QualityPreset] = {
    "custom": QualityPreset(id="custom"),
    "youtube": QualityPreset(
        id="youtube", crf=18, preset="slow", video_bitrate="8M", audio_bitrate="192k", scale="1920:1080"
    ),
    "telegram": QualityPreset(
        id="telegram", crf=23, preset="medium", video_bitrate="2M", audio_bitrate="128k", scale="1280:720"
    ),
    "max_quality": QualityPreset(id="max_quality", crf=15, preset="slow"),
    "min_size": QualityPreset(
        id="min_size", crf=32, preset="veryfast", video_bitrate="1M", audio_bitrate="96k", scale="854:480"
    ),
    "iphone": QualityPreset(
        id="iphone", crf=20, preset="medium", video_bitrate="5M", audio_bitrate="160k", scale="1920:1080", format="mp4"
    ),
    "tv": QualityPreset(
        id="tv", crf=18, preset="slow", video_bitrate="12M", audio_bitrate="192k", scale="1920:1080", format="mp4"
    ),
    "webm_short": QualityPreset(
        id="webm_short", crf=30, preset="fast", video_bitrate="1M", audio_bitrate="96k", scale="640:-2", format="webm"
    ),
}


def list_quality_presets() -> list[str]:
    from .settings import load_custom_presets

    return list(QUALITY_PRESETS.keys()) + list(load_custom_presets().keys())


def apply_quality_preset(preset_id: str) -> QualityPreset:
    if preset_id in QUALITY_PRESETS:
        return QUALITY_PRESETS[preset_id]
    from .settings import load_custom_presets, quality_preset_from_dict

    custom = load_custom_presets().get(preset_id)
    if custom:
        return quality_preset_from_dict(custom)
    return QUALITY_PRESETS["custom"]
