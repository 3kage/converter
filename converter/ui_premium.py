from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
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
CORNER_RADIUS = 10
CORNER_RADIUS_SM = 8
CORNER_RADIUS_LG = 12
PAD = 10
PAD_SM = 5
PAD_LG = 12
NAV_WIDTH = 68
NAV_BTN = 40

FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_CAPTION = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_HERO = ("Segoe UI", 17, "bold")
FONT_SUBTITLE = ("Segoe UI", 11)
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

# Classic minimal palette — (light, dark)
_ACCENT = ("#0071e3", "#0a84ff")
_ACCENT_HOVER = ("#0077ed", "#409cff")
_MUTED = ("#86868b", "#98989d")
_TEXT = ("#1d1d1f", "#f5f5f7")
_SURFACE = ("#ffffff", "#2c2c2e")
_SURFACE_ALT = ("#f5f5f7", "#1c1c1e")
_SIDEBAR = ("#fafafa", "#242426")
_BORDER = ("#d2d2d7", "#38383a")
_TABLE_SHELL = ("#ffffff", "#2c2c2e")

_NAV_ACTIVE_FG = ("#e5e5ea", "#3a3a3c")
_NAV_ACTIVE_TEXT = _TEXT
_NAV_ACTIVE_HOVER = ("#d1d1d6", "#48484a")
_NAV_IDLE_FG = "transparent"
_NAV_IDLE_TEXT = ("#6e6e73", "#98989d")
_NAV_IDLE_HOVER = ("#f0f0f5", "#2c2c2e")

_BTN_OUTLINE_TEXT = ("#1d1d1f", "#f5f5f7")
_BTN_OUTLINE_BORDER = _BORDER
_BTN_OUTLINE_HOVER = ("#f0f0f5", "#3a3a3c")
_BTN_OUTLINE_TEXT_DISABLED = ("#aeaeb2", "#636366")

TREE_STYLE = "Minimal.Treeview"
_TAB_ANIM_MS = 14
_TAB_ANIM_STEPS = 12


def data_palette(*, dark: bool) -> dict[str, str]:
    if dark:
        return {
            "row": "#1c1c1e",
            "row_alt": "#242426",
            "fg": "#f5f5f7",
            "heading_bg": "#2c2c2e",
            "heading_fg": "#f5f5f7",
            "select_bg": "#0a84ff",
            "select_fg": "#ffffff",
            "border": "#48484a",
        }
    return {
        "row": "#ffffff",
        "row_alt": "#f5f5f7",
        "fg": "#1d1d1f",
        "heading_bg": "#f5f5f7",
        "heading_fg": "#1d1d1f",
        "select_bg": "#0071e3",
        "select_fg": "#ffffff",
        "border": "#d2d2d7",
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
        rowheight=28,
        font=FONT_MONO,
    )
    style.configure(
        f"{TREE_STYLE}.Heading",
        background=c["heading_bg"],
        foreground=c["heading_fg"],
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 11, "bold"),
        padding=(8, 6),
    )
    style.map(
        TREE_STYLE,
        background=[("selected", c["select_bg"])],
        foreground=[("selected", c["select_fg"])],
    )


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


def animate_tab_switch(
    host: ctk.CTkBaseClass,
    outgoing: ctk.CTkBaseClass | None,
    incoming: ctk.CTkBaseClass,
    *,
    on_done: Callable[[], None] | None = None,
    steps: int = _TAB_ANIM_STEPS,
) -> None:
    """Slide/fade-style tab transition using place() interpolation."""
    incoming.lift()
    incoming.place(relx=0.018, rely=0, relwidth=1, relheight=1)
    if outgoing is not None:
        outgoing.lift()
        outgoing.place(relx=0, rely=0, relwidth=1, relheight=1)

    def ease_out(t: float) -> float:
        return 1 - (1 - t) ** 3

    def step(index: int = 0) -> None:
        t = ease_out(index / steps)
        incoming.place(relx=0.018 * (1 - t), rely=0, relwidth=1, relheight=1)
        if outgoing is not None:
            outgoing.place(relx=-0.014 * t, rely=0, relwidth=1, relheight=1)
        if index >= steps:
            incoming.place_forget()
            incoming.pack(fill=tk.BOTH, expand=True)
            if outgoing is not None:
                outgoing.place_forget()
                outgoing.pack_forget()
            if on_done is not None:
                on_done()
            return
        host.after(_TAB_ANIM_MS, lambda: step(index + 1))

    step()


def data_table_shell(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        corner_radius=CORNER_RADIUS_SM,
        border_width=1,
        border_color=_BORDER,
        fg_color=_TABLE_SHELL,
    )


def nav_divider(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, height=1, fg_color=_BORDER)


def nav_button_compact(parent: ctk.CTkBaseClass, *, icon: str, command, **kwargs) -> ctk.CTkButton:
    width = kwargs.pop("width", NAV_BTN)
    height = kwargs.pop("height", NAV_BTN)
    btn = ctk.CTkButton(
        parent,
        text=icon,
        width=width,
        height=height,
        corner_radius=kwargs.pop("corner_radius", CORNER_RADIUS_SM),
        font=kwargs.pop("font", ("Segoe UI", 15)),
        fg_color=kwargs.pop("fg_color", _NAV_IDLE_FG),
        text_color=kwargs.pop("text_color", _NAV_IDLE_TEXT),
        hover_color=kwargs.pop("hover_color", _NAV_IDLE_HOVER),
        command=command,
        **kwargs,
    )
    btn._nav_icon = icon  # type: ignore[attr-defined]
    btn._nav_compact = True  # type: ignore[attr-defined]
    return btn


def bind_tooltip(widget: tk.Misc, text: str) -> None:
    state: dict[str, tk.Toplevel | None] = {"win": None}

    def hide(_event=None) -> None:
        if state["win"] is not None:
            state["win"].destroy()
            state["win"] = None

    def show(_event=None) -> None:
        hide()
        if not text:
            return
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        x = widget.winfo_rootx() + widget.winfo_width() + 8
        y = widget.winfo_rooty() + 4
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tip,
            text=text,
            bg="#1d1d1f",
            fg="#f5f5f7",
            font=("Segoe UI", 10),
            padx=8,
            pady=4,
        ).pack()
        state["win"] = tip

    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<ButtonPress>", hide, add="+")


def set_nav_active(btn: ctk.CTkButton, active: bool) -> None:
    if active:
        btn.configure(
            fg_color=_NAV_ACTIVE_FG,
            text_color=_NAV_ACTIVE_TEXT,
            hover_color=_NAV_ACTIVE_HOVER,
            border_width=0,
        )
    else:
        btn.configure(
            fg_color=_NAV_IDLE_FG,
            text_color=_NAV_IDLE_TEXT,
            hover_color=_NAV_IDLE_HOVER,
            border_width=0,
        )
    if getattr(btn, "_nav_compact", False):
        btn.configure(width=NAV_BTN, height=NAV_BTN)


def nav_text(icon: str, label: str) -> str:
    return icon


def card(parent: ctk.CTkBaseClass, *, border: bool = True, fg_color=_SURFACE) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        corner_radius=CORNER_RADIUS,
        border_width=1 if border else 0,
        border_color=_BORDER if border else _SURFACE,
        fg_color=fg_color,
    )


def panel(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, corner_radius=CORNER_RADIUS_SM, fg_color=_SURFACE_ALT, border_width=0)


def sidebar_panel(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        width=NAV_WIDTH,
        corner_radius=CORNER_RADIUS,
        border_width=1,
        border_color=_BORDER,
        fg_color=_SIDEBAR,
    )


def section_title(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_TITLE, anchor="w", text_color=_TEXT)


def section_caption(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_SMALL, text_color=_MUTED, anchor="w")


def page_title(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_TITLE, anchor="w", text_color=_TEXT)


def page_subtitle(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=f"· {text}", font=FONT_SUBTITLE, text_color=_MUTED, anchor="w")


def badge(parent: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        font=FONT_CAPTION,
        corner_radius=999,
        fg_color=_SURFACE_ALT,
        text_color=_MUTED,
        padx=8,
        pady=2,
    )


def brand_mark(parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
    outer = ctk.CTkFrame(
        parent,
        width=40,
        height=40,
        corner_radius=10,
        fg_color=_ACCENT,
        border_width=0,
    )
    ctk.CTkLabel(outer, text="▶", font=("Segoe UI", 16), text_color="#ffffff").place(
        relx=0.5, rely=0.5, anchor="center"
    )
    outer.pack_propagate(False)
    return outer


def primary_button(parent: ctk.CTkBaseClass, **kwargs) -> ctk.CTkButton:
    height = kwargs.pop("height", 36)
    return ctk.CTkButton(
        parent,
        corner_radius=kwargs.pop("corner_radius", CORNER_RADIUS_SM),
        height=height,
        font=kwargs.pop("font", FONT_BODY),
        border_width=0,
        **kwargs,
    )


def secondary_button(parent: ctk.CTkBaseClass, **kwargs) -> ctk.CTkButton:
    height = kwargs.pop("height", 34)
    return ctk.CTkButton(
        parent,
        corner_radius=kwargs.pop("corner_radius", CORNER_RADIUS_SM),
        height=height,
        font=kwargs.pop("font", FONT_BODY),
        fg_color=kwargs.pop("fg_color", "transparent"),
        border_width=kwargs.pop("border_width", 1),
        text_color=kwargs.pop("text_color", _BTN_OUTLINE_TEXT),
        border_color=kwargs.pop("border_color", _BTN_OUTLINE_BORDER),
        hover_color=kwargs.pop("hover_color", _BTN_OUTLINE_HOVER),
        text_color_disabled=kwargs.pop("text_color_disabled", _BTN_OUTLINE_TEXT_DISABLED),
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
