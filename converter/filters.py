from __future__ import annotations


def build_video_filters(
    *,
    scale: str | None = None,
    crop: str | None = None,
    rotation: int | None = None,
    fps: str | None = None,
    gif_mode: bool = False,
    deinterlace: bool = False,
    denoise: bool = False,
    subtitle_burn_in: str | None = None,
) -> list[str]:
    parts: list[str] = []
    if deinterlace:
        parts.append("yadif")
    if denoise:
        parts.append("hqdn3d=4:3:6:4.5")
    if scale:
        parts.append(f"scale={scale}")
    if crop:
        parts.append(f"crop={crop}")
    rotation_map = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}
    if rotation in rotation_map:
        parts.append(rotation_map[rotation])
    if fps:
        parts.append(f"fps={fps}")
    if gif_mode:
        parts.extend(["fps=12", "scale=480:-1:flags=lanczos"])
    if subtitle_burn_in:
        escaped = subtitle_burn_in.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        parts.append(f"subtitles='{escaped}'")
    return parts


def join_filters(parts: list[str]) -> str | None:
    return ",".join(parts) if parts else None
