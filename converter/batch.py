from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path

from .convert import ConvertOptions, convert_video, verify_output
from .options_io import options_from_dict, options_to_dict
from .settings import pending_batch_path

_pause_event = threading.Event()
_pause_event.set()


def pause_batch() -> None:
    _pause_event.clear()


def resume_batch() -> None:
    _pause_event.set()


def is_batch_paused() -> bool:
    return not _pause_event.is_set()


@dataclass
class BatchItem:
    input_path: Path
    output_path: Path


def build_batch_items(
    inputs: Iterable[Path],
    *,
    output_dir: Path | None,
    output_format: str,
    suffix: str = "_converted",
) -> list[BatchItem]:
    fmt = output_format.lstrip(".")
    items: list[BatchItem] = []
    for input_path in inputs:
        out_dir = output_dir or input_path.parent
        items.append(
            BatchItem(
                input_path=input_path,
                output_path=out_dir / f"{input_path.stem}{suffix}.{fmt}",
            )
        )
    return items


def save_pending_batch(items: list[BatchItem], base_options: ConvertOptions) -> Path:
    payload = {
        "items": [{"input": str(i.input_path), "output": str(i.output_path)} for i in items],
        "options": options_to_dict(replace(base_options, input_path=items[0].input_path, output_path=items[0].output_path)),
    }
    path = pending_batch_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_pending_batch() -> tuple[list[BatchItem], ConvertOptions] | None:
    path = pending_batch_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = [
            BatchItem(input_path=Path(row["input"]), output_path=Path(row["output"]))
            for row in data.get("items", [])
        ]
        if not items:
            return None
        options = options_from_dict(data["options"])
        return items, options
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        return None


def clear_pending_batch() -> None:
    path = pending_batch_path()
    if path.is_file():
        path.unlink(missing_ok=True)


def _wait_if_paused(pause_event: threading.Event, cancel_check: Callable[[], bool] | None) -> None:
    while not pause_event.is_set():
        if cancel_check and cancel_check():
            raise RuntimeError("Пакетну конвертацію скасовано.")
        time.sleep(0.25)


def _convert_item(
    index: int,
    total: int,
    item: BatchItem,
    base_options: ConvertOptions,
    *,
    on_progress: Callable[[float, str], None] | None,
    cancel_check: Callable[[], bool] | None,
    pause_event: threading.Event,
) -> tuple[Path, list[str]]:
    _wait_if_paused(pause_event, cancel_check)
    if cancel_check and cancel_check():
        raise RuntimeError("Пакетну конвертацію скасовано.")

    options = replace(base_options, input_path=item.input_path, output_path=item.output_path)

    def wrapped_progress(percent: float, message: str) -> None:
        if on_progress:
            overall = ((index - 1) / total * 100) + (percent / total)
            on_progress(overall, f"[{index}/{total}] {message}")

    output_path, cmd = convert_video(options, on_progress=wrapped_progress, cancel_check=cancel_check)
    if options.verify_output:
        verify_output(output_path)
    return output_path, cmd


def run_batch(
    items: list[BatchItem],
    base_options: ConvertOptions,
    *,
    on_file_start: Callable[[int, int, Path], None] | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    pause_event: threading.Event | None = None,
    max_workers: int = 1,
) -> list[tuple[Path, list[str]]]:
    pause_event = pause_event or _pause_event
    total = len(items)
    results: list[tuple[Path, list[str]]] = []

    if max_workers <= 1:
        for index, item in enumerate(items, start=1):
            if on_file_start:
                on_file_start(index, total, item.input_path)
            results.append(
                _convert_item(
                    index,
                    total,
                    item,
                    base_options,
                    on_progress=on_progress,
                    cancel_check=cancel_check,
                    pause_event=pause_event,
                )
            )
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for index, item in enumerate(items, start=1):
            if on_file_start:
                on_file_start(index, total, item.input_path)
            future = pool.submit(
                _convert_item,
                index,
                total,
                item,
                base_options,
                on_progress=on_progress,
                cancel_check=cancel_check,
                pause_event=pause_event,
            )
            futures[future] = index
        ordered: dict[int, tuple[Path, list[str]]] = {}
        for future in as_completed(futures):
            ordered[futures[future]] = future.result()
        for index in sorted(ordered):
            results.append(ordered[index])
    return results
