from __future__ import annotations

import shutil
import subprocess
import sys


def notify(title: str, message: str) -> None:
    title = title.replace('"', "'").replace("\n", " ")
    message = message.replace('"', "'").replace("\n", " ")
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                check=False,
                timeout=5,
            )
        elif sys.platform == "linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False, timeout=5)
        elif sys.platform == "win32":
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                "ContentType = WindowsRuntime] | Out-Null; "
                "$t=@"
                "<toast><visual><binding template='ToastText02'>"
                f"<text id='1'>{title}</text><text id='2'>{message}</text>"
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
