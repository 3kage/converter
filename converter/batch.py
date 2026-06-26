from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from .convert import ConvertOptions, build_ffmpeg_args, convert_video, verify_output


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


def run_batch(
    items: list[BatchItem],
    base_options: ConvertOptions,
    *,
    on_file_start: Callable[[int, int, Path], None] | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[tuple[Path, list[str]]]:
    results: list[tuple[Path, list[str]]] = []
    total = len(items)
    for index, item in enumerate(items, start=1):
        if cancel_check and cancel_check():
            raise RuntimeError("Пакетну конвертацію скасовано.")
        if on_file_start:
            on_file_start(index, total, item.input_path)

        options = replace(base_options, input_path=item.input_path, output_path=item.output_path)

        def wrapped_progress(percent: float, message: str) -> None:
            if on_progress:
                overall = ((index - 1) / total * 100) + (percent / total)
                on_progress(overall, f"[{index}/{total}] {message}")

        output_path, cmd = convert_video(options, on_progress=wrapped_progress, cancel_check=cancel_check)
        if options.verify_output:
            verify_output(output_path)
        results.append((output_path, cmd))
    return results
