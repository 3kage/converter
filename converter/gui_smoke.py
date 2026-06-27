"""Smoke tests for GUI widgets — run before release builds."""

from __future__ import annotations

import customtkinter as ctk

from converter.ui_premium import init_premium_theme, nav_button_compact, primary_button, secondary_button


def run_gui_smoke() -> None:
    init_premium_theme(follow_system=False, dark_manual=True)
    root = ctk.CTk()
    root.withdraw()
    primary_button(root, text="Primary", width=140, height=34)
    secondary_button(root, text="Secondary", height=32)
    nav_button_compact(root, icon="▶", command=lambda: None)
    root.update()
    root.destroy()


if __name__ == "__main__":
    run_gui_smoke()
    print("GUI smoke OK")
