from __future__ import annotations

import sys
import webbrowser
from collections.abc import Callable


def bind_file_drop(widget, callback: Callable[[list[str]], None]) -> None:
    if sys.platform == "win32":
        try:
            import windnd  # type: ignore[import-untyped]

            def _handler(files) -> None:
                paths = [f.decode("utf-8") if isinstance(f, bytes) else str(f) for f in files]
                callback(paths)

            windnd.hook_dropfiles(widget, func=_handler)
        except ImportError:
            return
        return

    try:
        from tkinterdnd2 import DND_FILES  # type: ignore[import-untyped]

        def _drop(event) -> None:
            raw = event.data.strip()
            paths: list[str] = []
            if raw.startswith("{"):
                token = ""
                inside = False
                for char in raw:
                    if char == "{":
                        inside = True
                        token = ""
                    elif char == "}" and inside:
                        inside = False
                        if token:
                            paths.append(token)
                    elif inside:
                        token += char
            else:
                paths = raw.split()
            if paths:
                callback(paths)

        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", _drop)
    except (ImportError, AttributeError):
        return
