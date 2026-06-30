from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .batch import BatchItem, clear_pending_batch, run_batch
from .convert import ConvertOptions
from .notifications import notify
from .options_io import options_from_dict
from .settings import pending_batch_path


def spawn_background_batch(items: list[BatchItem], base_options: ConvertOptions) -> None:
    payload = {
        "items": [{"input": str(i.input_path), "output": str(i.output_path)} for i in items],
        "options": _options_payload(base_options, items[0]),
    }
    path = pending_batch_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    cmd = [sys.executable, "-m", "converter", "batch-resume", str(path)]
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        **kwargs,
    )


def _options_payload(base: ConvertOptions, item: BatchItem) -> dict:
    from dataclasses import replace

    from .options_io import options_to_dict

    return options_to_dict(replace(base, input_path=item.input_path, output_path=item.output_path))


def run_saved_batch(job_path: Path | None = None) -> int:
    path = pending_batch_path() if job_path is None else job_path
    if not path.is_file():
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    items = [
        BatchItem(input_path=Path(row["input"]), output_path=Path(row["output"]))
        for row in data.get("items", [])
    ]
    if not items:
        return 1
    for item in items:
        if not item.input_path.is_file():
            return 1
    options = options_from_dict(data["options"])
    results = run_batch(items, options)
    clear_pending_batch()
    notify("Video Converter", f"Background batch done: {len(results)} files")
    return 0
