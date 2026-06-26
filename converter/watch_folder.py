from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from .file_scan import scan_videos


class FolderWatcher:
    def __init__(
        self,
        folder: Path,
        *,
        interval_sec: int = 5,
        recursive: bool = True,
        on_new_file: Callable[[Path], None],
    ) -> None:
        self.folder = folder
        self.interval_sec = max(2, interval_sec)
        self.recursive = recursive
        self.on_new_file = on_new_file
        self._seen: set[str] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _seed_seen(self) -> None:
        for path in scan_videos(self.folder, recursive=self.recursive):
            self._seen.add(str(path.resolve()))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._seed_seen()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            for path in scan_videos(self.folder, recursive=self.recursive):
                key = str(path.resolve())
                if key not in self._seen:
                    self._seen.add(key)
                    self.on_new_file(path)
            self._stop.wait(self.interval_sec)
