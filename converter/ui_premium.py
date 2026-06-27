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
CORNER_RADIUS = 16
CORNER_RADIUS_SM = 12
CORNER_RADIUS_LG = 20
PAD = 14
PAD_SM = 8
PAD_LG = 18
NAV_WIDTH = 220

FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_CAPTION = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_HERO = ("Segoe UI", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 12)
FONT_NAV = ("Segoe UI", 12)
FONT_MONO = ("Consolas", 11)

TAB_ICONS: dict[str, str] = {
    "tab_convert": "▶",
    "tab_audio": "♫",
    "tab_trim": "⎔",
    "tab_advanced": "⚙",
    "tab_batch": "☰",
    "tab_watch": "◎",
    "tab_history": "↺",
}

# (light, dark)
_ACCENT = ("#4f7cff", "#5b8cff")
_ACCENT_HOVER = ("#3d6ae8", "#4a7df5")
_MUTED = ("#64748b", "#94a3b8")
_SURFACE = ("#ffffff", "#1c1c28")
_SURFACE_ALT = ("#eef1f8", "#232334")
_SIDEBAR = ("#f8f9fc", "#181824")

_NAV_ACTIVE_FG = _ACCENT
_NAV_ACTIVE_TEXT = ("#ffffff", "#ffffff")
_NAV_ACTIVE_HOVER = _ACCENT_HOVER
_NAV_IDLE_FG = ("transparent", "transparent")
_NAV_IDLE_TEXT = ("#334155", "#c8ccd8")
_NAV_IDLE_HOVER = ("#e8eeff", "#2a2a3d")

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


def nav_label(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text.upper(),
        font=FONT_CAPTION,
        text_color=_MUTED,
        anchor="w",
    )


def nav_button(parent: ctk.CTkBaseClass, *, icon: str, text: str, command, **kwargs) -> ctk.CTkButton:
    btn = ctk.CTkButton(
        parent,
        text=f" {icon}   {text}",
        anchor="w",
        height=44,
        corner_radius=CORNER_RADIUS_SM,
        font=FONT_NAV,
        fg_color=_NAV_IDLE_FG,
        text_color=_NAV_IDLE_TEXT,
        hover_color=_NAV_IDLE_HOVER,
        command=command,
        **kwargs,
    )
    btn._nav_icon = icon  # type: ignore[attr-defined]
    return btn


def set_nav_active(btn: ctk.CTkButton, active: bool) -> None:
    if active:
        btn.configure(
            fg_color=_NAV_ACTIVE_FG,
            text_color=_NAV_ACTIVE_TEXT,
            hover_color=_NAV_ACTIVE_HOVER,
        )
    else:
        btn.configure(
            fg_color=_NAV_IDLE_FG,
            text_color=_NAV_IDLE_TEXT,
            hover_color=_NAV_IDLE_HOVER,
        )


def nav_text(icon: str, label: str) -> str:
    return f" {icon}   {label}"


def card(parent: ctk.CTkBaseClass, *, border: bool = True, fg_color=_SURFACE) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        corner_radius=CORNER_RADIUS,
        border_width=1 if border else 0,
        fg_color=fg_color,
    )


def sidebar_panel(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        width=NAV_WIDTH,
        corner_radius=CORNER_RADIUS,
        border_width=1,
        fg_color=_SIDEBAR,
    )


def section_title(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_TITLE, anchor="w")


def page_title(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_HERO, anchor="w")


def page_subtitle(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_SUBTITLE, text_color=_MUTED, anchor="w")


def badge(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        font=FONT_CAPTION,
        corner_radius=999,
        fg_color=_SURFACE_ALT,
        text_color=_MUTED,
        padx=10,
        pady=2,
    )


def brand_mark(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(parent, width=48, height=48, corner_radius=24, fg_color=_ACCENT)
    ctk.CTkLabel(frame, text="▶", font=("Segoe UI", 22), text_color="#ffffff").place(relx=0.5, rely=0.5, anchor="center")
    frame.pack_propagate(False)
    return frame


def primary_button(parent: ctk.CTkBaseClass, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        corner_radius=CORNER_RADIUS_SM,
        height=40,
        font=FONT_BODY,
        **kwargs,
    )


def secondary_button(parent: ctk.CTkBaseClass, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        corner_radius=CORNER_RADIUS_SM,
        height=38,
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
