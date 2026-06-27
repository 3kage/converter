from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

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

# Cyberpunk palette — (light, dark)
_ACCENT = ("#0088bb", "#00eaff")
_ACCENT_HOVER = ("#006699", "#00cce6")
_ACCENT_GLOW = ("#ff0088", "#ff00aa")
_MUTED = ("#5a6a7a", "#7aa0b0")
_SURFACE = ("#ffffff", "#12121f")
_SURFACE_ALT = ("#e8f8ff", "#0a1520")
_SIDEBAR = ("#eef6ff", "#080810")
_NEON_BORDER = ("#00aacc", "#00eaff")
_TABLE_SHELL = ("#f4fbff", "#06060e")

_NAV_ACTIVE_FG = _ACCENT
_NAV_ACTIVE_TEXT = ("#ffffff", "#001018")
_NAV_ACTIVE_HOVER = _ACCENT_HOVER
_NAV_IDLE_FG = "transparent"
_NAV_IDLE_TEXT = ("#1a3040", "#9ec8d8")
_NAV_IDLE_HOVER = ("#d0f0ff", "#141428")

_BTN_OUTLINE_TEXT = ("#005577", "#00eaff")
_BTN_OUTLINE_BORDER = ("#00aacc", "#00eaff")
_BTN_OUTLINE_HOVER = ("#ccf0ff", "#141432")
_BTN_OUTLINE_TEXT_DISABLED = ("#94a3b8", "#4a6070")

TREE_STYLE = "Cyber.Treeview"


def data_palette(*, dark: bool) -> dict[str, str]:
    if dark:
        return {
            "row": "#0e0e18",
            "row_alt": "#141425",
            "fg": "#b8ecff",
            "heading_bg": "#0a1525",
            "heading_fg": "#00eaff",
            "select_bg": "#003344",
            "select_fg": "#00ffff",
            "border": "#00eaff",
        }
    return {
        "row": "#f8fdff",
        "row_alt": "#eef8ff",
        "fg": "#0a2030",
        "heading_bg": "#d0f0ff",
        "heading_fg": "#006688",
        "select_bg": "#00ccee",
        "select_fg": "#001018",
        "border": "#00aacc",
    }


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


def apply_data_widgets_theme(root: tk.Misc, *, dark: bool) -> None:
    c = data_palette(dark=dark)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        TREE_STYLE,
        background=c["row"],
        foreground=c["fg"],
        fieldbackground=c["row"],
        borderwidth=0,
        rowheight=30,
        font=FONT_MONO,
    )
    style.configure(
        f"{TREE_STYLE}.Heading",
        background=c["heading_bg"],
        foreground=c["heading_fg"],
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 11, "bold"),
        padding=(10, 8),
    )
    style.map(
        TREE_STYLE,
        background=[("selected", c["select_bg"])],
        foreground=[("selected", c["select_fg"])],
    )
    style.configure("Cyber.Vertical.TScrollbar", background=c["heading_bg"], troughcolor=c["row"])


def configure_tree_stripes(tree: ttk.Treeview, *, dark: bool) -> None:
    c = data_palette(dark=dark)
    tree.tag_configure("odd", background=c["row"])
    tree.tag_configure("even", background=c["row_alt"])


def configure_listbox(listbox: tk.Listbox, *, dark: bool) -> None:
    c = data_palette(dark=dark)
    listbox.configure(
        bg=c["row"],
        fg=c["fg"],
        selectbackground=c["select_bg"],
        selectforeground=c["select_fg"],
        highlightthickness=1,
        highlightbackground=c["border"],
        highlightcolor=c["border"],
        activestyle="none",
    )


def data_table_shell(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        corner_radius=CORNER_RADIUS_SM,
        border_width=2,
        border_color=_NEON_BORDER,
        fg_color=_TABLE_SHELL,
    )


def nav_label(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text.upper(),
        font=FONT_CAPTION,
        text_color=_ACCENT,
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
            border_width=1,
            border_color=_NEON_BORDER,
        )
    else:
        btn.configure(
            fg_color=_NAV_IDLE_FG,
            text_color=_NAV_IDLE_TEXT,
            hover_color=_NAV_IDLE_HOVER,
            border_width=0,
        )


def nav_text(icon: str, label: str) -> str:
    return f" {icon}   {label}"


def card(parent: ctk.CTkBaseClass, *, border: bool = True, fg_color=_SURFACE) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        corner_radius=CORNER_RADIUS,
        border_width=2 if border else 0,
        border_color=_NEON_BORDER if border else _SURFACE,
        fg_color=fg_color,
    )


def sidebar_panel(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        width=NAV_WIDTH,
        corner_radius=CORNER_RADIUS,
        border_width=2,
        border_color=_NEON_BORDER,
        fg_color=_SIDEBAR,
    )


def section_title(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_TITLE, anchor="w", text_color=_ACCENT)


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
        text_color=_ACCENT,
        padx=10,
        pady=2,
    )


def brand_mark(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    outer = ctk.CTkFrame(
        parent,
        width=52,
        height=52,
        corner_radius=26,
        fg_color=_ACCENT,
        border_width=2,
        border_color=_ACCENT_GLOW,
    )
    ctk.CTkLabel(outer, text="▶", font=("Segoe UI", 22), text_color="#001018").place(
        relx=0.5, rely=0.5, anchor="center"
    )
    outer.pack_propagate(False)
    return outer


def primary_button(parent: ctk.CTkBaseClass, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        corner_radius=CORNER_RADIUS_SM,
        height=40,
        font=FONT_BODY,
        border_width=1,
        border_color=_NEON_BORDER,
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
