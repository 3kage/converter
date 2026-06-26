from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .batch import build_batch_items, run_batch
from .convert import ConvertOptions, convert_video, list_supported_formats
from .presets import list_quality_presets
from .ffmpeg_utils import FFmpegNotFoundError
from .probe import analyze_file, render_media_info


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-converter",
        description="Аналіз та конвертація відеофайлів (MOV, MP4, MKV та ін.) через FFmpeg.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser(
        "info",
        help="Показати детальну інформацію про відеофайл.",
        description="Виводить дані про контейнер, відео-, аудіо- та субтитрові потоки.",
    )
    info_parser.add_argument("input", type=Path, help="Шлях до відеофайлу")
    info_parser.add_argument(
        "--json",
        action="store_true",
        help="Вивести сирі дані ffprobe у форматі JSON.",
    )
    info_parser.set_defaults(func=cmd_info)

    convert_parser = subparsers.add_parser(
        "convert",
        help="Конвертувати відео в інший формат.",
        description="Конвертація з MOV/MP4/MKV та інших форматів у будь-який підтримуваний FFmpeg.",
    )
    convert_parser.add_argument("input", type=Path, help="Вхідний відеофайл")
    convert_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Шлях до вихідного файлу (за замовчуванням: <ім'я>_converted.<формат>)",
    )
    convert_parser.add_argument(
        "-f",
        "--format",
        dest="output_format",
        default="mp4",
        help="Формат виходу без крапки (за замовчуванням: mp4)",
    )
    convert_parser.add_argument(
        "--vcodec",
        dest="video_codec",
        default=None,
        help="Відеокодек (наприклад: libx264, libx265, copy)",
    )
    convert_parser.add_argument(
        "--acodec",
        dest="audio_codec",
        default=None,
        help="Аудіокодек (наприклад: aac, mp3, copy)",
    )
    convert_parser.add_argument(
        "--video-bitrate",
        default=None,
        help="Бітрейт відео, наприклад 5M або 2500k",
    )
    convert_parser.add_argument(
        "--audio-bitrate",
        default=None,
        help="Бітрейт аудіо, наприклад 192k",
    )
    convert_parser.add_argument(
        "--crf",
        type=int,
        default=23,
        help="Якість відео для x264/x265 (0=найкраща, 51=найгірша, за замовчуванням: 23)",
    )
    convert_parser.add_argument(
        "--preset",
        default="medium",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
        help="Швидкість кодування x264 (за замовчуванням: medium)",
    )
    convert_parser.add_argument(
        "--audio-stream",
        type=int,
        default=None,
        help="Індекс аудіопотоку для конвертації (0 — перший)",
    )
    convert_parser.add_argument(
        "--video-stream",
        type=int,
        default=None,
        help="Індекс відеопотоку для конвертації (0 — перший)",
    )
    convert_parser.add_argument(
        "--copy",
        action="store_true",
        help="Копіювати потоки без перекодування (швидко, той самий кодек)",
    )
    convert_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Перезаписати вихідний файл, якщо він існує",
    )
    convert_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показати команду ffmpeg без виконання",
    )
    convert_parser.add_argument("--quality-preset", choices=list_quality_presets(), default=None)
    convert_parser.add_argument("--scale", default=None, help="Роздільність, напр. 1920:1080")
    convert_parser.add_argument("--start", dest="start_time", default=None, help="Початок HH:MM:SS")
    convert_parser.add_argument("--end", dest="end_time", default=None, help="Кінець HH:MM:SS")
    convert_parser.add_argument("--hw", dest="hardware_encode", action="store_true", help="GPU кодування")
    convert_parser.add_argument("--extract-audio", action="store_true")
    convert_parser.add_argument("--extract-subtitles", action="store_true")
    convert_parser.add_argument("--external-audio", type=Path, default=None)
    convert_parser.add_argument("--subtitle", type=Path, default=None)
    convert_parser.add_argument("--normalize-audio", action="store_true")
    convert_parser.add_argument("--gif", dest="gif_mode", action="store_true")
    convert_parser.add_argument("--strip-metadata", action="store_true")
    convert_parser.add_argument("--metadata-title", default=None)
    convert_parser.add_argument("--metadata-author", default=None)
    convert_parser.add_argument("--metadata-date", default=None)
    convert_parser.add_argument("--hevc", dest="prefer_hevc", action="store_true")
    convert_parser.add_argument("--crop", default=None, help="crop=w:h:x:y")
    convert_parser.add_argument("--rotation", type=int, choices=[90, 180, 270], default=None)
    convert_parser.add_argument("--fps", default=None)
    convert_parser.add_argument("--watermark", type=Path, default=None)
    convert_parser.add_argument("--watermark-pos", default="10:10")
    convert_parser.add_argument("--two-pass", action="store_true")
    convert_parser.add_argument("--merge", nargs="*", type=Path, default=None, help="Додаткові файли для склейки")
    convert_parser.add_argument("--no-verify", action="store_true")
    convert_parser.add_argument("--show-info", action="store_true", help="Показати інформацію про файл")
    convert_parser.set_defaults(func=cmd_convert)

    batch_parser = subparsers.add_parser("batch", help="Пакетна конвертація файлів")
    batch_parser.add_argument("inputs", nargs="+", type=Path, help="Вхідні файли")
    batch_parser.add_argument("-o", "--output-dir", type=Path, default=None)
    batch_parser.add_argument("-f", "--format", dest="output_format", default="mp4")
    batch_parser.add_argument("--quality-preset", choices=list_quality_presets(), default=None)
    batch_parser.add_argument("--overwrite", action="store_true")
    batch_parser.add_argument("--hw", dest="hardware_encode", action="store_true")
    batch_parser.set_defaults(func=cmd_batch)

    formats_parser = subparsers.add_parser(
        "formats",
        help="Список підтримуваних форматів виходу.",
    )
    formats_parser.set_defaults(func=cmd_formats)

    for sub in (info_parser, convert_parser, formats_parser):
        sub.epilog = _examples_for(sub.prog.split()[-1])

    return parser


def _examples_for(command: str) -> str:
    examples = {
        "info": """
Приклади:
  python -m converter info video.mov
  python -m converter info clip.mp4 --json
""",
        "convert": """
Приклади:
  python -m converter convert video.mov
  python -m converter convert video.mov -f mp4 -o result.mp4
  python -m converter convert input.mkv -f webm --crf 28
  python -m converter convert video.mov --copy -f mp4
  python -m converter convert video.mov --audio-stream 1 -f mp4
  python -m converter convert video.mov --dry-run
""",
        "formats": """
Приклади:
  python -m converter formats
""",
    }
    return examples.get(command, "").strip()


def cmd_info(args: argparse.Namespace) -> int:
    if args.json:
        from .ffmpeg_utils import run_ffprobe
        import json

        data = run_ffprobe(args.input)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    info = analyze_file(args.input)
    print(render_media_info(info))
    return 0


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
        external_audio_path=getattr(args, "external_audio", None),
        subtitle_path=getattr(args, "subtitle", None),
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
        two_pass=getattr(args, "two_pass", False),
    )


def cmd_convert(args: argparse.Namespace) -> int:
    if args.show_info:
        info = analyze_file(args.input)
        print(render_media_info(info))
        print()

    options = _options_from_args(args, args.input)

    output_path, cmd = convert_video(options)

    if args.dry_run:
        print("Команда ffmpeg (dry-run):")
        print(" ".join(f'"{part}"' if " " in part else part for part in cmd))
        print(f"\nВихідний файл: {output_path}")
        return 0

    print(f"Готово: {output_path}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    out_dir = args.output_dir
    items = build_batch_items(args.inputs, output_dir=out_dir, output_format=args.output_format)
    base = _options_from_args(args, items[0].input_path, items[0].output_path)
    results = run_batch(items, base)
    for output_path, _ in results:
        print(output_path)
    print(f"Готово: {len(results)} файлів")
    return 0


def cmd_formats(_: argparse.Namespace) -> int:
    print("Підтримувані формати виходу:")
    for fmt in list_supported_formats():
        print(f"  .{fmt}")
    print("\nFFmpeg підтримує й інші формати — вкажіть розширення у --output.")
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
