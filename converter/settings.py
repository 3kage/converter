from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .presets import QualityPreset


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Local" / "VideoConverter"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "VideoConverter"
    else:
        base = Path.home() / ".local" / "share" / "video-converter"
    base.mkdir(parents=True, exist_ok=True)
    return base


def settings_path() -> Path:
    return _config_dir() / "settings.json"


def custom_presets_path() -> Path:
    return _config_dir() / "custom_presets.json"


def pending_batch_path() -> Path:
    return _config_dir() / "pending_batch.json"


@dataclass
class AppSettings:
    lang: str = "uk"
    dark: bool = False
    follow_system_theme: bool = True
    check_updates_on_startup: bool = True
    notify_on_complete: bool = True
    recursive_batch: bool = True
    parallel_batch: int = 1
    preserve_chapters: bool = True
    last_input_dir: str = ""
    last_output_dir: str = ""
    watch_folder: str = ""
    watch_enabled: bool = False
    watch_interval_sec: int = 5
    video_codec: str = ""
    audio_codec: str = ""
    video_bitrate: str = ""
    audio_bitrate: str = ""
    watermark_position: str = "10:10"
    extract_subtitle_format: str = "srt"


def load_settings() -> AppSettings:
    path = settings_path()
    if not path.is_file():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = AppSettings.__dataclass_fields__
        kwargs = {k: v for k, v in data.items() if k in fields}
        if "follow_system_theme" not in data and data.get("dark") is not None:
            kwargs["follow_system_theme"] = False
        return AppSettings(**kwargs)
    except (json.JSONDecodeError, OSError, TypeError):
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    settings_path().write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")


def load_custom_presets() -> dict[str, dict]:
    path = custom_presets_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_custom_presets(presets: dict[str, dict]) -> None:
    custom_presets_path().write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")


def add_custom_preset(name: str, preset: QualityPreset) -> None:
    presets = load_custom_presets()
    presets[name] = {
        "id": name,
        "crf": preset.crf,
        "preset": preset.preset,
        "video_bitrate": preset.video_bitrate,
        "audio_bitrate": preset.audio_bitrate,
        "scale": preset.scale,
        "format": preset.format,
    }
    save_custom_presets(presets)


def quality_preset_from_dict(data: dict) -> QualityPreset:
    return QualityPreset(
        id=data.get("id", "custom"),
        crf=data.get("crf"),
        preset=data.get("preset", "medium"),
        video_bitrate=data.get("video_bitrate"),
        audio_bitrate=data.get("audio_bitrate"),
        scale=data.get("scale"),
        format=data.get("format", "mp4"),
    )
