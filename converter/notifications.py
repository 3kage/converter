from __future__ import annotations

import shutil
import subprocess
import sys


from .security import escape_applescript_string, escape_xml


def notify(title: str, message: str) -> None:
    title = title.replace("\n", " ").strip()
    message = message.replace("\n", " ").strip()
    try:
        if sys.platform == "darwin":
            title_esc = escape_applescript_string(title)
            message_esc = escape_applescript_string(message)
            subprocess.run(
                ["osascript", "-e", f'display notification "{message_esc}" with title "{title_esc}"'],
                check=False,
                timeout=5,
            )
        elif sys.platform == "linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False, timeout=5)
        elif sys.platform == "win32":
            title_xml = escape_xml(title)
            message_xml = escape_xml(message)
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                "ContentType = WindowsRuntime] | Out-Null; "
                "$t=@"
                "<toast><visual><binding template='ToastText02'>"
                f"<text id='1'>{title_xml}</text><text id='2'>{message_xml}</text>"
                "</binding></visual></toast>"
                '"@; '
                "$x=New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($t); "
                "$n=[Windows.UI.Notifications.ToastNotification]::new($x); "
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('VideoConverter').Show($n)"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                check=False,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except (OSError, subprocess.SubprocessError):
        pass
