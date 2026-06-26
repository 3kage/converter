from __future__ import annotations

import json
import urllib.request

from . import __version__

REPO = "3kage/converter"


def check_for_updates(timeout: float = 8.0) -> tuple[bool, str, str]:
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "VideoConverter"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    latest = (data.get("tag_name") or data.get("name") or "").lstrip("v")
    page = data.get("html_url") or f"https://github.com/{REPO}/releases"
    if not latest:
        return False, __version__, page
    return _version_tuple(latest) > _version_tuple(__version__), latest, page


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in value.replace("-", ".").split("."):
        if piece.isdigit():
            parts.append(int(piece))
    return tuple(parts) or (0,)
