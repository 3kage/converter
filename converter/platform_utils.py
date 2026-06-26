from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def open_path(path: Path) -> None:
    """Відкрити файл або папку у системному провіднику."""
    target = str(path.resolve())
    if sys.platform == "win32":
        import os

        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", target], check=True)
    else:
        subprocess.run(["xdg-open", target], check=True)
