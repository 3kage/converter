from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .convert import ConvertOptions, convert_video, list_supported_formats
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
    convert_parser.add_argument(
        "--show-info",
        action="store_true",
        help="Показати інформацію про вхідний файл перед конвертацією",
    )
    convert_parser.set_defaults(func=cmd_convert)

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


def cmd_convert(args: argparse.Namespace) -> int:
    if args.show_info:
        info = analyze_file(args.input)
        print(render_media_info(info))
        print()

    options = ConvertOptions(
        input_path=args.input,
        output_path=args.output,
        output_format=args.output_format,
        video_codec=args.video_codec,
        audio_codec=args.audio_codec,
        video_bitrate=args.video_bitrate,
        audio_bitrate=args.audio_bitrate,
        crf=None if args.copy else args.crf,
        preset=args.preset,
        audio_stream=args.audio_stream,
        video_stream=args.video_stream,
        copy_streams=args.copy,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    output_path, cmd = convert_video(options)

    if args.dry_run:
        print("Команда ffmpeg (dry-run):")
        print(" ".join(f'"{part}"' if " " in part else part for part in cmd))
        print(f"\nВихідний файл: {output_path}")
        return 0

    print(f"Готово: {output_path}")
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
