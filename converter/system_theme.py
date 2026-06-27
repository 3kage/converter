from __future__ import annotations

import subprocess
import sys


def is_dark_mode() -> bool:
    if sys.platform == "win32":
        return _windows_is_dark()
    if sys.platform == "darwin":
        return _macos_is_dark()
    return _linux_is_dark()


def _windows_is_dark() -> bool:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
    except OSError:
        return False


def _macos_is_dark() -> bool:
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return result.returncode == 0 and "dark" in result.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def _linux_is_dark() -> bool:
    for args in (
        ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
        ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
    ):
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=2, check=False)
            if result.returncode == 0 and "dark" in result.stdout.lower():
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False
