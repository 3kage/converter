from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from converter.updater import download_with_progress, extract_release, get_release_download_url


class UpdaterSecurityTests(unittest.TestCase):
    def test_get_release_download_url_rejects_untrusted_asset(self) -> None:
        assets = [
            {
                "name": "VideoConverter-linux.zip",
                "browser_download_url": "https://evil.example.com/VideoConverter-linux.zip",
            }
        ]
        with patch("converter.updater._fetch_latest_release", return_value={"assets": assets}):
            self.assertIsNone(get_release_download_url("linux"))

    def test_download_with_progress_rejects_untrusted_url(self) -> None:
        with self.assertRaises(RuntimeError):
            download_with_progress("https://evil.example.com/file.zip", Path("/tmp/file.zip"))

    def test_extract_release_blocks_zip_slip(self) -> None:
        import io
        import zipfile
        from tempfile import TemporaryDirectory

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("../evil.txt", "bad")
        buffer.seek(0)
        archive = Path("/tmp/malicious.zip")
        archive.write_bytes(buffer.getvalue())
        with TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                extract_release(archive, Path(tmp))


if __name__ == "__main__":
    unittest.main()
