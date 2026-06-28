from __future__ import annotations

import io
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.security import (
    escape_applescript_string,
    escape_xml,
    is_trusted_release_url,
    require_trusted_release_url,
    safe_extract_zip,
)


class SecurityHelpersTests(unittest.TestCase):
    def test_trusted_release_url(self) -> None:
        self.assertTrue(
            is_trusted_release_url(
                "https://github.com/3kage/converter/releases/download/v1/VideoConverter-linux.zip"
            )
        )
        self.assertTrue(
            is_trusted_release_url(
                "https://objects.githubusercontent.com/github-production-release-asset-2e65be/abc"
            )
        )
        self.assertFalse(is_trusted_release_url("http://github.com/evil.zip"))
        self.assertFalse(is_trusted_release_url("https://evil.example.com/malware.zip"))

    def test_require_trusted_release_url_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            require_trusted_release_url("https://evil.example.com/update.zip")

    def test_escape_xml(self) -> None:
        self.assertEqual(escape_xml('Tom & "Jerry" <test>'), "Tom &amp; &quot;Jerry&quot; &lt;test&gt;")

    def test_escape_applescript_string(self) -> None:
        self.assertEqual(escape_applescript_string('say "hi"'), 'say \\"hi\\"')

    def test_safe_extract_zip_blocks_traversal(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("../escape.txt", "bad")
        buffer.seek(0)
        with TemporaryDirectory() as tmp:
            with zipfile.ZipFile(buffer) as zf:
                with self.assertRaises(RuntimeError):
                    safe_extract_zip(zf, Path(tmp))

    def test_safe_extract_zip_allows_normal_paths(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("VideoConverter/app.bin", "ok")
        buffer.seek(0)
        with TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with zipfile.ZipFile(buffer) as zf:
                safe_extract_zip(zf, dest)
            self.assertTrue((dest / "VideoConverter" / "app.bin").is_file())


if __name__ == "__main__":
    unittest.main()
