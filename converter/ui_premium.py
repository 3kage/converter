from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk


def _theme_json_path() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = Path(meipass) / "converter" / "assets" / "premium-theme.json"
            if bundled.is_file():
                return bundled
    return Path(__file__).resolve().parent / "assets" / "premium-theme.json"


THEME_JSON = _theme_json_path()
CORNER_RADIUS = 14
CORNER_RADIUS_SM = 10
PAD = 12
PAD_SM = 8

FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_HERO = ("Segoe UI", 18, "bold")
FONT_MONO = ("Consolas", 11)

# (light, dark) — CTkButton theme uses white text for filled buttons; outlined buttons need explicit contrast.
_BTN_OUTLINE_TEXT = ("#1e3a8a", "#e8eaf0")
_BTN_OUTLINE_BORDER = ("#4f7cff", "#6b9aff")
_BTN_OUTLINE_HOVER = ("#dbeafe", "#2a2a3d")
_BTN_OUTLINE_TEXT_DISABLED = ("#94a3b8", "#6b7280")


def init_premium_theme(*, follow_system: bool, dark_manual: bool) -> None:
    if THEME_JSON.is_file():
        ctk.set_default_color_theme(str(THEME_JSON))
    else:
        ctk.set_default_color_theme("blue")
    if follow_system:
        ctk.set_appearance_mode("system")
    else:
        ctk.set_appearance_mode("dark" if dark_manual else "light")


def sync_appearance(*, follow_system: bool, dark_manual: bool) -> None:
    init_premium_theme(follow_system=follow_system, dark_manual=dark_manual)


def card(parent: ctk.CTkBaseClass, *, border: bool = True) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        corner_radius=CORNER_RADIUS,
        border_width=1 if border else 0,
    )


def section_title(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_TITLE, anchor="w")


def primary_button(parent: ctk.CTkBaseClass, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(parent, corner_radius=CORNER_RADIUS_SM, height=36, font=FONT_BODY, **kwargs)


def secondary_button(parent: ctk.CTkBaseClass, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        corner_radius=CORNER_RADIUS_SM,
        height=34,
        font=FONT_BODY,
        fg_color="transparent",
        border_width=2,
        text_color=_BTN_OUTLINE_TEXT,
        border_color=_BTN_OUTLINE_BORDER,
        hover_color=_BTN_OUTLINE_HOVER,
        text_color_disabled=_BTN_OUTLINE_TEXT_DISABLED,
        **kwargs,
    )


def animate_progress(bar: ctk.CTkProgressBar, value: float, steps: int = 8) -> None:
    target = max(0.0, min(1.0, value / 100.0))
    current = float(bar.get())

    def step(count: int = 0, cur: float = current) -> None:
        if count >= steps:
            bar.set(target)
            return
        nxt = cur + (target - cur) * 0.35
        bar.set(nxt)
        bar.after(20, lambda: step(count + 1, nxt))

    step()
