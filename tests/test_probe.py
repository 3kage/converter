from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from converter.probe import analyze_file


class ProbeTests(unittest.TestCase):
    def test_zero_size_is_preserved(self) -> None:
        payload = {
            "format": {"size": "0", "duration": "1.0"},
            "streams": [],
            "chapters": [],
        }
        with patch("converter.probe.run_ffprobe", return_value=payload):
            info = analyze_file(Path("/tmp/empty.mp4"))
        self.assertEqual(info.size_bytes, 0)


if __name__ == "__main__":
    unittest.main()
