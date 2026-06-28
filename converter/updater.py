from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
import zipfile
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .security import is_trusted_release_url, require_trusted_release_url, safe_extract_zip

REPO = "3kage/converter"
ProgressCallback = Callable[[int, int], None]


def _fetch_latest_release(timeout: float = 10.0) -> dict:
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "VideoConverter"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_for_updates(timeout: float = 10.0) -> tuple[bool, str, str]:
    data = _fetch_latest_release(timeout=timeout)
    latest = (data.get("tag_name") or data.get("name") or "").lstrip("v")
    page = data.get("html_url") or f"https://github.com/{REPO}/releases"
    if not latest:
        return False, __version__, page
    return _version_tuple(latest) > _version_tuple(__version__), latest, page


def get_release_download_url(platform: str | None = None) -> str | None:
    platform_key = platform or sys.platform
    data = _fetch_latest_release()
    if platform_key == "win32":
        needle = "windows"
    elif platform_key == "darwin":
        needle = "mac"
    else:
        needle = "linux"
    for asset in data.get("assets", []):
        name = (asset.get("name") or "").lower()
        if needle in name and name.endswith(".zip"):
            url = asset.get("browser_download_url")
            if url and is_trusted_release_url(url):
                return url
    return None


def open_latest_release_download() -> str | None:
    url = get_release_download_url(sys.platform)
    page = f"https://github.com/{REPO}/releases/latest"
    webbrowser.open(url if url is None else url)
    return url or page


def download_latest_release(dest_dir: Path | None = None) -> Path:
    url = get_release_download_url(sys.platform)
    if not url:
        raise RuntimeError("No release asset found. Check GitHub Releases page.")
    target_dir = dest_dir or Path(tempfile.gettempdir())
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    target = target_dir / filename
    require_trusted_release_url(url)
    urllib.request.urlretrieve(url, target)
    return target


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_install_paths() -> tuple[Path, Path]:
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin" and ".app" in exe.as_posix():
        parts = exe.parts
        for index, part in enumerate(parts):
            if part.endswith(".app"):
                app_root = Path(*parts[: index + 1])
                return app_root, exe
    return exe.parent, exe


def can_auto_update() -> bool:
    if not is_frozen():
        return False
    install_root, exe = get_install_paths()
    if sys.platform == "win32":
        return exe.suffix.lower() == ".exe"
    if sys.platform == "darwin":
        return install_root.suffix == ".app"
    if sys.platform.startswith("linux"):
        return exe.name == "VideoConverter" and install_root.name == "VideoConverter"
    return False


def download_with_progress(
    url: str,
    target: Path,
    progress: ProgressCallback | None = None,
) -> Path:
    require_trusted_release_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "VideoConverter"})
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=120) as response:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        chunk_size = 256 * 1024
        with target.open("wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress(downloaded, total)
    return target


def extract_release(archive: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        safe_extract_zip(zf, dest_dir)
    return find_payload_root(dest_dir)


def find_payload_root(extract_dir: Path) -> Path:
    if sys.platform == "win32":
        candidate = extract_dir / "VideoConverter"
        if candidate.is_dir():
            return candidate
    if sys.platform == "darwin":
        direct = extract_dir / "VideoConverter.app"
        if direct.is_dir():
            return direct
        for app in extract_dir.rglob("VideoConverter.app"):
            if app.is_dir():
                return app
    if sys.platform.startswith("linux"):
        candidate = extract_dir / "VideoConverter"
        if candidate.is_dir():
            exe = candidate / "VideoConverter"
            if exe.is_file() or (candidate / "_internal").is_dir():
                return candidate
    raise RuntimeError("Unsupported release archive layout.")


def _quote(value: Path) -> str:
    return f'"{value}"'


def _launch_windows_updater(source: Path, install_root: Path, executable: Path) -> None:
    script_dir = Path(tempfile.gettempdir()) / "VideoConverter-update"
    script_dir.mkdir(parents=True, exist_ok=True)
    backup_root = install_root.parent / "VideoConverter_previous"
    script_path = script_dir / "apply_update.bat"
    script_path.write_text(
        "\n".join(
            [
                "@echo off",
                "setlocal EnableExtensions",
                "ping 127.0.0.1 -n 3 >nul",
                f'if exist {_quote(backup_root)} rmdir /s /q {_quote(backup_root)}',
                f'robocopy {_quote(install_root)} {_quote(backup_root)} /MIR /R:3 /W:2 /NFL /NDL /NJH /NJS /NP',
                f'robocopy {_quote(source)} {_quote(install_root)} /MIR /R:5 /W:2 /NFL /NDL /NJH /NJS /NP',
                "if %ERRORLEVEL% GEQ 8 exit /b 1",
                f'start "" {_quote(executable)}',
                "del /f /q %~f0",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path)],
        close_fds=True,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
    )


def _launch_macos_updater(source: Path, install_root: Path) -> None:
    script_dir = Path(tempfile.gettempdir()) / "VideoConverter-update"
    script_dir.mkdir(parents=True, exist_ok=True)
    backup_root = install_root.parent / "VideoConverter_previous"
    script_path = script_dir / "apply_update.command"
    script_path.write_text(
        "\n".join(
            [
                "#!/bin/bash",
                "set -e",
                "sleep 2",
                f"rm -rf {_quote(backup_root)}",
                f"ditto {_quote(install_root)} {_quote(backup_root)}",
                f"ditto {_quote(source)} {_quote(install_root)}",
                f"xattr -cr {_quote(install_root)}",
                f"open {_quote(install_root)}",
                f"rm -f {_quote(script_path)}",
            ]
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    subprocess.Popen(["/bin/bash", str(script_path)], close_fds=True, start_new_session=True)


def apply_update(source_root: Path) -> None:
    if not can_auto_update():
        raise RuntimeError("Auto-update is only available in the installed application build.")
    install_root, executable = get_install_paths()
    if sys.platform == "win32":
        _launch_windows_updater(source_root, install_root, executable)
        return
    if sys.platform == "darwin":
        _launch_macos_updater(source_root, install_root)
        return
    raise RuntimeError(f"Auto-update is not supported on {sys.platform}.")


def install_latest_update(
    progress: ProgressCallback | None = None,
    work_dir: Path | None = None,
) -> tuple[str, Path]:
    url = get_release_download_url(sys.platform)
    if not url:
        raise RuntimeError("No release asset found for this platform.")
    base_dir = work_dir or Path(tempfile.gettempdir()) / "VideoConverter-update"
    if base_dir.exists():
        shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)

    archive = base_dir / url.rsplit("/", 1)[-1]
    download_with_progress(url, archive, progress)

    extract_dir = base_dir / "extracted"
    payload = extract_release(archive, extract_dir)
    apply_update(payload)

    latest = check_for_updates()[1]
    return latest, payload


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in value.replace("-", ".").split("."):
        if piece.isdigit():
            parts.append(int(piece))
    return tuple(parts) or (0,)
