from __future__ import annotations

import json
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

from . import __version__

REPO = "3kage/converter"


def _fetch_latest_release() -> dict:
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "VideoConverter"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def check_for_updates(timeout: float = 10.0) -> tuple[bool, str, str]:
    data = _fetch_latest_release()
    latest = (data.get("tag_name") or data.get("name") or "").lstrip("v")
    page = data.get("html_url") or f"https://github.com/{REPO}/releases"
    if not latest:
        return False, __version__, page
    return _version_tuple(latest) > _version_tuple(__version__), latest, page


def get_release_download_url(platform: str) -> str | None:
    data = _fetch_latest_release()
    needle = "windows" if platform == "win32" else "mac"
    for asset in data.get("assets", []):
        name = (asset.get("name") or "").lower()
        if needle in name and name.endswith(".zip"):
            return asset.get("browser_download_url")
    return None


def open_latest_release_download() -> str | None:
    import sys

    url = get_release_download_url(sys.platform)
    page = f"https://github.com/{REPO}/releases/latest"
    webbrowser.open(url if url is None else url)
    return url or page


def download_latest_release(dest_dir: Path | None = None) -> Path:
    import sys

    url = get_release_download_url(sys.platform)
    if not url:
        raise RuntimeError("No release asset found. Check GitHub Releases page.")
    target_dir = dest_dir or Path(tempfile.gettempdir())
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    target = target_dir / filename
    urllib.request.urlretrieve(url, target)
    return target


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in value.replace("-", ".").split("."):
        if piece.isdigit():
            parts.append(int(piece))
    return tuple(parts) or (0,)
