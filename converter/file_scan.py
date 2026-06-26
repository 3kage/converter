from __future__ import annotations

from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mov",
    ".mp4",
    ".mkv",
    ".avi",
    ".webm",
    ".wmv",
    ".flv",
    ".m4v",
    ".mpeg",
    ".mpg",
    ".ts",
    ".ogv",
}


def scan_videos(root: Path, *, recursive: bool = True) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    if recursive:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                found.append(path)
    else:
        for ext in VIDEO_EXTENSIONS:
            found.extend(root.glob(f"*{ext}"))
    return sorted({p.resolve() for p in found})
