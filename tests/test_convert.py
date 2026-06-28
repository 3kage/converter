from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from converter.convert import ConvertOptions, build_ffmpeg_args


class BuildFfmpegArgsTests(unittest.TestCase):
    def test_trim_places_end_before_input(self) -> None:
        options = ConvertOptions(
            input_path=Path("/tmp/video.mp4"),
            start_time="10",
            end_time="30",
            overwrite=True,
        )
        args = build_ffmpeg_args(options)
        ss_idx = args.index("-ss")
        to_idx = args.index("-to")
        input_idx = args.index("-i")
        self.assertLess(ss_idx, to_idx)
        self.assertLess(to_idx, input_idx)
        self.assertEqual(args[ss_idx + 1], "10")
        self.assertEqual(args[to_idx + 1], "30")

    def test_copy_streams_with_external_audio_encodes_audio(self) -> None:
        options = ConvertOptions(
            input_path=Path("/tmp/video.mp4"),
            external_audio_path=Path("/tmp/audio.mp3"),
            replace_audio=True,
            copy_streams=True,
            overwrite=True,
        )
        args = build_ffmpeg_args(options)
        self.assertIn("-c:v", args)
        self.assertIn("copy", args)
        self.assertIn("-c:a", args)
        self.assertNotIn("-c", args)

    def test_two_pass_requires_video_bitrate(self) -> None:
        options = ConvertOptions(
            input_path=Path("/tmp/video.mp4"),
            two_pass=True,
            crf=23,
            overwrite=True,
        )
        single_pass = build_ffmpeg_args(options)
        self.assertNotIn("-pass", single_pass)

        options_with_bitrate = ConvertOptions(
            input_path=Path("/tmp/video.mp4"),
            two_pass=True,
            video_bitrate="2M",
            overwrite=True,
        )
        pass1 = build_ffmpeg_args(options_with_bitrate, pass_number=1)
        pass2 = build_ffmpeg_args(options_with_bitrate, pass_number=2)
        self.assertIn("-pass", pass1)
        self.assertEqual(pass1[pass1.index("-pass") + 1], "1")
        self.assertIn("-pass", pass2)
        self.assertEqual(pass2[pass2.index("-pass") + 1], "2")
        self.assertIn("-b:v", pass2)
        self.assertNotIn("-crf", pass2)

    def test_convert_video_skips_two_pass_without_bitrate(self) -> None:
        from converter.convert import convert_video

        options = ConvertOptions(
            input_path=Path("/tmp/trim_test.mp4"),
            two_pass=True,
            crf=23,
            overwrite=True,
            output_path=Path("/tmp/twopass_skip.mp4"),
            verify_output=False,
        )
        with patch("converter.convert.run_ffprobe", return_value={"format": {"duration": "10"}}), patch(
            "converter.convert.run_ffmpeg", return_value=[]
        ) as run_mock:
            convert_video(options)
        self.assertEqual(run_mock.call_count, 1)


class BatchResumeTests(unittest.TestCase):
    def test_batch_resume_without_job_uses_pending_file(self) -> None:
        from converter.background import run_saved_batch
        from converter.settings import pending_batch_path

        pending = pending_batch_path()
        with patch.object(Path, "is_file", return_value=True), patch.object(
            Path, "read_text", return_value='{"items":[{"input":"/a.mp4","output":"/b.mp4"}],"options":{"input_path":"/a.mp4","output_path":"/b.mp4"}}'
        ), patch("converter.background.run_batch", return_value=[(Path("/b.mp4"), [])]), patch(
            "converter.background.clear_pending_batch"
        ), patch("converter.background.notify"):
            self.assertEqual(run_saved_batch(None), 0)

        with patch.object(Path, "is_file", return_value=False):
            self.assertEqual(run_saved_batch(Path()), 1)


class UpdaterTests(unittest.TestCase):
    def test_get_release_download_url_uses_platform_argument(self) -> None:
        from converter.updater import get_release_download_url

        assets = [
            {"name": "VideoConverter-windows.zip", "browser_download_url": "https://example/windows.zip"},
            {"name": "VideoConverter-mac.zip", "browser_download_url": "https://example/mac.zip"},
            {"name": "VideoConverter-linux.zip", "browser_download_url": "https://example/linux.zip"},
        ]
        with patch("converter.updater._fetch_latest_release", return_value={"assets": assets}):
            self.assertEqual(get_release_download_url("linux"), "https://example/linux.zip")
            self.assertEqual(get_release_download_url("win32"), "https://example/windows.zip")


if __name__ == "__main__":
    unittest.main()
