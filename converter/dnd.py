from __future__ import annotations

import sys
from collections.abc import Callable


def bind_file_drop(widget, callback: Callable[[list[str]], None]) -> None:
    """Drag-and-drop: best effort on Windows via windnd if installed."""
    if sys.platform != "win32":
        return
    try:
        import windnd  # type: ignore[import-untyped]

        def _handler(files) -> None:
            paths = [f.decode("utf-8") if isinstance(f, bytes) else str(f) for f in files]
            callback(paths)

        windnd.hook_dropfiles(widget, func=_handler)
    except ImportError:
        return
