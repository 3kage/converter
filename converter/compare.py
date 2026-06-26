from __future__ import annotations

from pathlib import Path

from .probe import _fmt_bitrate, _fmt_size, analyze_file


def compare_conversion(input_path: Path, output_path: Path) -> str:
    src = analyze_file(input_path)
    dst = analyze_file(output_path)
    saved = 0.0
    if src.size_bytes and dst.size_bytes and src.size_bytes > 0:
        saved = (1 - dst.size_bytes / src.size_bytes) * 100
    lines = [
        "=== Порівняння до / після ===",
        f"Вхід:  {_fmt_size(src.size_bytes)} | {src.overall_bitrate}",
        f"Вихід: {_fmt_size(dst.size_bytes)} | {dst.overall_bitrate}",
        f"Економія розміру: {saved:.1f}%",
    ]
    if src.duration_sec and dst.duration_sec:
        lines.append(f"Тривалість: {_fmt_duration_short(src.duration_sec)} → {_fmt_duration_short(dst.duration_sec)}")
    return "\n".join(lines)


def _fmt_duration_short(seconds: float) -> str:
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
