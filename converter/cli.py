from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .background import run_saved_batch
from .batch import build_batch_items, run_batch
from .convert import ConvertOptions, convert_video, list_supported_formats
from .file_scan import scan_videos
from .notifications import notify
from .presets import list_quality_presets
from .ffmpeg_utils import FFmpegNotFoundError
from .probe import analyze_file, render_media_info


def _add_convert_flags(parser: argparse.ArgumentParser, *, include_output: bool = True) -> None:
    if include_output:
        parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("-f", "--format", dest="output_format", default="mp4")
    parser.add_argument("--vcodec", dest="video_codec", default=None)
    parser.add_argument("--acodec", dest="audio_codec", default=None)
    parser.add_argument("--video-bitrate", default=None)
    parser.add_argument("--audio-bitrate", default=None)
    parser.add_argument("--crf", type=int, default=23)
    parser.add_argument(
        "--preset",
        default="medium",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
    )
    parser.add_argument("--audio-stream", type=int, default=None)
    parser.add_argument("--video-stream", type=int, default=None)
    parser.add_argument("--subtitle-stream", type=int, default=None)
    parser.add_argument("--copy", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quality-preset", choices=list_quality_presets(), default=None)
    parser.add_argument("--scale", default=None)
    parser.add_argument("--start", dest="start_time", default=None)
    parser.add_argument("--end", dest="end_time", default=None)
    parser.add_argument("--hw", dest="hardware_encode", action="store_true")
    parser.add_argument("--extract-audio", action="store_true")
    parser.add_argument("--extract-subtitles", action="store_true")
    parser.add_argument("--subtitle-format", dest="extract_subtitle_format", default="srt")
    parser.add_argument("--external-audio", type=Path, default=None)
    parser.add_argument("--subtitle", type=Path, default=None)
    parser.add_argument("--subtitle-burn-in", action="store_true")
    parser.add_argument("--normalize-audio", action="store_true")
    parser.add_argument("--gif", dest="gif_mode", action="store_true")
    parser.add_argument("--strip-metadata", action="store_true")
    parser.add_argument("--metadata-title", default=None)
    parser.add_argument("--metadata-author", default=None)
    parser.add_argument("--metadata-date", default=None)
    parser.add_argument("--hevc", dest="prefer_hevc", action="store_true")
    parser.add_argument("--crop", default=None)
    parser.add_argument("--rotation", type=int, choices=[90, 180, 270], default=None)
    parser.add_argument("--fps", default=None)
    parser.add_argument("--watermark", type=Path, default=None)
    parser.add_argument("--watermark-pos", default="10:10")
    parser.add_argument("--cover-art", type=Path, default=None)
    parser.add_argument("--no-chapters", action="store_true")
    parser.add_argument("--deinterlace", action="store_true")
    parser.add_argument("--denoise", action="store_true")
    parser.add_argument("--replace-audio", action="store_true")
    parser.add_argument("--audio-delay-ms", type=int, default=0)
    parser.add_argument("--extra-audio-tracks", default="", help="Comma-separated audio stream indices")
    parser.add_argument("--two-pass", action="store_true")
    parser.add_argument("--merge", nargs="*", type=Path, default=None)
    parser.add_argument("--no-verify", action="store_true")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-converter",
        description="Аналіз та конвертація відеофайлів (MOV, MP4, MKV та ін.) через FFmpeg.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser("info", help="Інформація про файл")
    info_parser.add_argument("input", type=Path)
    info_parser.add_argument("--json", action="store_true")
    info_parser.set_defaults(func=cmd_info)

    convert_parser = subparsers.add_parser("convert", help="Конвертувати відео")
    convert_parser.add_argument("input", type=Path)
    _add_convert_flags(convert_parser)
    convert_parser.add_argument("--show-info", action="store_true")
    convert_parser.set_defaults(func=cmd_convert)

    batch_parser = subparsers.add_parser("batch", help="Пакетна конвертація")
    batch_parser.add_argument("inputs", nargs="*", type=Path)
    batch_parser.add_argument("--input-dir", type=Path, default=None, help="Папка з відео")
    batch_parser.add_argument("--recursive", action="store_true")
    batch_parser.add_argument("-o", "--output-dir", type=Path, default=None)
    _add_convert_flags(batch_parser, include_output=False)
    batch_parser.add_argument("--parallel", type=int, default=1)
    batch_parser.add_argument("--notify", action="store_true")
    batch_parser.set_defaults(func=cmd_batch)

    resume_parser = subparsers.add_parser("batch-resume", help="Продовжити збережену пакетну чергу")
    resume_parser.add_argument("job", type=Path, nargs="?", default=None)
    resume_parser.set_defaults(func=cmd_batch_resume)

    formats_parser = subparsers.add_parser("formats", help="Список форматів")
    formats_parser.set_defaults(func=cmd_formats)

    return parser


def _parse_extra_audio(value: str) -> list[int]:
    tracks: list[int] = []
    for piece in value.split(","):
        piece = piece.strip()
        if piece.isdigit():
            tracks.append(int(piece))
    return tracks


def _options_from_args(args: argparse.Namespace, input_path: Path, output_path: Path | None = None) -> ConvertOptions:
    merge = list(args.merge) if getattr(args, "merge", None) else []
    return ConvertOptions(
        input_path=input_path,
        output_path=output_path or getattr(args, "output", None),
        output_format=getattr(args, "output_format", "mp4"),
        video_codec=getattr(args, "video_codec", None),
        audio_codec=getattr(args, "audio_codec", None),
        video_bitrate=getattr(args, "video_bitrate", None),
        audio_bitrate=getattr(args, "audio_bitrate", None),
        crf=None if getattr(args, "copy", False) else getattr(args, "crf", 23),
        preset=getattr(args, "preset", "medium"),
        audio_stream=getattr(args, "audio_stream", None),
        video_stream=getattr(args, "video_stream", None),
        subtitle_stream=getattr(args, "subtitle_stream", None),
        copy_streams=getattr(args, "copy", False),
        overwrite=getattr(args, "overwrite", False),
        dry_run=getattr(args, "dry_run", False),
        quality_preset_id=getattr(args, "quality_preset", None),
        scale=getattr(args, "scale", None),
        start_time=getattr(args, "start_time", None),
        end_time=getattr(args, "end_time", None),
        hardware_encode=getattr(args, "hardware_encode", False),
        prefer_hevc=getattr(args, "prefer_hevc", False),
        extract_audio=getattr(args, "extract_audio", False),
        extract_subtitles=getattr(args, "extract_subtitles", False),
        extract_subtitle_format=getattr(args, "extract_subtitle_format", "srt"),
        external_audio_path=getattr(args, "external_audio", None),
        subtitle_path=getattr(args, "subtitle", None),
        subtitle_burn_in=getattr(args, "subtitle_burn_in", False),
        normalize_audio=getattr(args, "normalize_audio", False),
        gif_mode=getattr(args, "gif_mode", False),
        metadata_title=getattr(args, "metadata_title", None),
        metadata_author=getattr(args, "metadata_author", None),
        metadata_date=getattr(args, "metadata_date", None),
        strip_metadata=getattr(args, "strip_metadata", False),
        verify_output=not getattr(args, "no_verify", False),
        merge_inputs=merge or [],
        crop=getattr(args, "crop", None),
        rotation=getattr(args, "rotation", None),
        fps=getattr(args, "fps", None),
        watermark_path=getattr(args, "watermark", None),
        watermark_position=getattr(args, "watermark_pos", "10:10"),
        cover_art_path=getattr(args, "cover_art", None),
        preserve_chapters=not getattr(args, "no_chapters", False),
        deinterlace=getattr(args, "deinterlace", False),
        denoise=getattr(args, "denoise", False),
        extra_audio_tracks=_parse_extra_audio(getattr(args, "extra_audio_tracks", "") or ""),
        replace_audio=getattr(args, "replace_audio", False),
        audio_delay_ms=getattr(args, "audio_delay_ms", 0) or 0,
        two_pass=getattr(args, "two_pass", False),
    )


def cmd_info(args: argparse.Namespace) -> int:
    if args.json:
        from .ffmpeg_utils import run_ffprobe
        import json

        print(json.dumps(run_ffprobe(args.input), ensure_ascii=False, indent=2))
        return 0
    print(render_media_info(analyze_file(args.input)))
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    if args.show_info:
        print(render_media_info(analyze_file(args.input)))
        print()
    options = _options_from_args(args, args.input)
    output_path, cmd = convert_video(options)
    if args.dry_run:
        print(" ".join(cmd))
        print(output_path)
        return 0
    print(f"Готово: {output_path}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    inputs: list[Path] = list(args.inputs)
    if args.input_dir:
        inputs.extend(scan_videos(args.input_dir, recursive=args.recursive))
    inputs = sorted({p.resolve() for p in inputs})
    if not inputs:
        raise RuntimeError("Не знайдено вхідних файлів.")
    items = build_batch_items(inputs, output_dir=args.output_dir, output_format=args.output_format)
    base = _options_from_args(args, items[0].input_path, items[0].output_path)
    results = run_batch(items, base, max_workers=max(1, args.parallel))
    for output_path, _ in results:
        print(output_path)
    if args.notify:
        notify("Video Converter", f"Batch done: {len(results)} files")
    print(f"Готово: {len(results)}")
    return 0


def cmd_batch_resume(args: argparse.Namespace) -> int:
    return run_saved_batch(args.job)


def cmd_formats(_: argparse.Namespace) -> int:
    for fmt in list_supported_formats():
        print(f".{fmt}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FFmpegNotFoundError as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
