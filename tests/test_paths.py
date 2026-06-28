from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from converter.paths import app_root, data_dir, reset_paths_for_tests, temp_dir


class PathsTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_paths_for_tests()

    def test_dev_mode_uses_project_data_dir(self) -> None:
        reset_paths_for_tests()
        root = app_root()
        self.assertTrue((root / "converter").is_dir())
        with TemporaryDirectory() as tmp:
            with patch("converter.paths.app_root", return_value=Path(tmp)):
                reset_paths_for_tests()
                path = data_dir()
                self.assertEqual(path, Path(tmp) / "data")
                self.assertTrue(path.is_dir())

    def test_frozen_windows_uses_exe_folder_data(self) -> None:
        with TemporaryDirectory() as tmp:
            exe_dir = Path(tmp) / "VideoConverter"
            exe_dir.mkdir()
            fake_exe = exe_dir / "VideoConverter.exe"
            fake_exe.touch()
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(fake_exe)
            ), patch.object(sys, "platform", "win32"):
                reset_paths_for_tests()
                self.assertEqual(app_root(), exe_dir.resolve())
                self.assertEqual(data_dir(), (exe_dir / "data").resolve())

    def test_frozen_macos_uses_sibling_data_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "VideoConverter.app" / "Contents" / "MacOS"
            bundle.mkdir(parents=True)
            fake_exe = bundle / "VideoConverter"
            fake_exe.touch()
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(fake_exe)
            ), patch.object(sys, "platform", "darwin"):
                reset_paths_for_tests()
                expected = (Path(tmp) / "VideoConverter-data").resolve()
                self.assertEqual(data_dir(), expected)

    def test_temp_dir_inside_data(self) -> None:
        with TemporaryDirectory() as tmp:
            with patch("converter.paths.app_root", return_value=Path(tmp)):
                reset_paths_for_tests()
                tdir = temp_dir()
                self.assertEqual(tdir, Path(tmp) / "data" / "temp")
                self.assertTrue(tdir.is_dir())


if __name__ == "__main__":
    unittest.main()
