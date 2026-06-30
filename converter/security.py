from __future__ import annotations

import zipfile
from pathlib import Path
from urllib.parse import urlparse

TRUSTED_RELEASE_HOSTS = frozenset({"github.com", "objects.githubusercontent.com"})


def is_trusted_release_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    return parsed.hostname in TRUSTED_RELEASE_HOSTS


def require_trusted_release_url(url: str) -> str:
    if not is_trusted_release_url(url):
        raise RuntimeError(f"Untrusted update download URL: {url}")
    return url


def safe_extract_zip(archive: zipfile.ZipFile, dest_dir: Path) -> None:
    dest_root = dest_dir.resolve()
    for member in archive.namelist():
        target = (dest_dir / member).resolve()
        if target != dest_root and dest_root not in target.parents:
            raise RuntimeError(f"Unsafe path in release archive: {member}")
    archive.extractall(dest_dir)


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def escape_applescript_string(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
