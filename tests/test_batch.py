from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from converter.batch import BatchItem, run_batch
from converter.convert import ConvertOptions


class BatchProgressTests(unittest.TestCase):
    def test_parallel_batch_reports_progress(self) -> None:
        items = [
            BatchItem(input_path=Path(f"/tmp/in{i}.mp4"), output_path=Path(f"/tmp/out{i}.mp4"))
            for i in range(2)
        ]
        base = ConvertOptions(input_path=items[0].input_path, overwrite=True, verify_output=False)
        seen: list[str] = []

        def fake_convert(options, on_progress=None, cancel_check=None):
            if on_progress:
                on_progress(100.0, "done")
            return (options.output_path or Path("/tmp/out.mp4"), [])

        with patch("converter.batch.convert_video", side_effect=fake_convert):
            run_batch(items, base, on_progress=lambda _p, msg: seen.append(msg), max_workers=2)
        self.assertEqual(len(seen), 2)

    def test_parallel_batch_serializes_progress_callbacks(self) -> None:
        items = [
            BatchItem(input_path=Path(f"/tmp/in{i}.mp4"), output_path=Path(f"/tmp/out{i}.mp4"))
            for i in range(3)
        ]
        base = ConvertOptions(input_path=items[0].input_path, overwrite=True, verify_output=False)
        active = 0
        max_active = 0
        counter_lock = threading.Lock()

        def fake_convert(options, on_progress=None, cancel_check=None):
            if on_progress:
                on_progress(50.0, "half")
                on_progress(100.0, "done")
            return (options.output_path or Path("/tmp/out.mp4"), [])

        def on_progress(_percent: float, _message: str) -> None:
            nonlocal active, max_active
            with counter_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with counter_lock:
                active -= 1

        with patch("converter.batch.convert_video", side_effect=fake_convert):
            run_batch(items, base, on_progress=on_progress, max_workers=3)
        self.assertEqual(max_active, 1)


class BackgroundBatchValidationTests(unittest.TestCase):
    def test_run_saved_batch_rejects_missing_input_file(self) -> None:
        from converter.background import run_saved_batch

        payload = (
            '{"items":[{"input":"/missing/file.mp4","output":"/tmp/out.mp4"}],'
            '"options":{"input_path":"/missing/file.mp4","output_path":"/tmp/out.mp4"}}'
        )

        def fake_is_file(self) -> bool:
            return str(self) != "/missing/file.mp4"

        with patch.object(Path, "is_file", fake_is_file), patch.object(Path, "read_text", return_value=payload):
            self.assertEqual(run_saved_batch(Path("/tmp/job.json")), 1)


if __name__ == "__main__":
    unittest.main()
