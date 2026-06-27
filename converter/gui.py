from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import customtkinter as ctk

from . import __version__
from .background import spawn_background_batch
from .batch import build_batch_items, pause_batch, resume_batch, run_batch
from .compare import compare_conversion
from .convert import ConvertOptions, build_ffmpeg_args, convert_video, list_audio_formats, list_supported_formats
from .dnd import bind_file_drop
from .ffmpeg_utils import FFmpegNotFoundError
from .file_scan import scan_videos
from .history import append_history, load_history, log_error, log_path
from .i18n import I18n
from .notifications import notify
from .options_io import options_from_dict, options_to_dict
from .platform_utils import open_path
from .presets import RESOLUTIONS, QualityPreset, list_quality_presets
from .settings import AppSettings, add_custom_preset, load_settings, save_settings
from .preview import generate_preview
from .probe import analyze_file, render_media_info
from .streams import list_selectable_streams
from .system_theme import is_dark_mode
from .watch_folder import FolderWatcher
from .ui_premium import (
    FONT_BODY,
    FONT_MONO,
    FONT_SMALL,
    PAD,
    PAD_LG,
    PAD_SM,
    TAB_ICONS,
    animate_progress,
    badge,
    brand_mark,
    card,
    init_premium_theme,
    nav_button,
    nav_label,
    nav_text,
    page_subtitle,
    page_title,
    primary_button,
    secondary_button,
    section_title,
    set_nav_active,
    sidebar_panel,
    sync_appearance,
)
from .updater import (
    can_auto_update,
    check_for_updates,
    install_latest_update,
    open_latest_release_download,
)

VIDEO_EXTS = {".mov", ".mp4", ".mkv", ".avi", ".webm", ".wmv", ".flv", ".m4v", ".mpeg", ".mpg", ".ts", ".ogv"}


class _VideoConverterMixin:
    def _init_app(self) -> None:
        settings = load_settings()
        self.i18n = I18n(settings.lang)
        init_premium_theme(follow_system=settings.follow_system_theme, dark_manual=settings.dark)
        self.title(f"{self.i18n.t('app_title')} v{__version__}")
        self.geometry("1120x900")
        self.minsize(880, 560)

        self._i18n_widgets: list[tuple[object, str, str]] = []
        self._tab_keys = [
            "tab_convert",
            "tab_audio",
            "tab_trim",
            "tab_advanced",
            "tab_batch",
            "tab_watch",
            "tab_history",
        ]
        self._current_tab_key = self._tab_keys[0]
        self._tab_pages: dict[str, ctk.CTkFrame] = {}
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._nav_sections: list[tuple[ctk.CTkLabel, str]] = []
        self._help_menu: tk.Menu | None = None
        self._menu: tk.Menu | None = None

        self._follow_system_theme = tk.BooleanVar(value=settings.follow_system_theme)
        self._dark = tk.BooleanVar(value=settings.dark)
        self._applied_dark: bool | None = None
        self._dark_theme_cb: ctk.CTkCheckBox | None = None
        self._lang = tk.StringVar(value=settings.lang)
        self._input_path = tk.StringVar()
        self._output_path = tk.StringVar()
        self._format = tk.StringVar(value="mp4")
        self._quality_preset = tk.StringVar(value="custom")
        self._resolution = tk.StringVar(value="original")
        self._crf = tk.IntVar(value=23)
        self._preset = tk.StringVar(value="medium")
        self._copy_streams = tk.BooleanVar(value=False)
        self._overwrite = tk.BooleanVar(value=True)
        self._hw_encode = tk.BooleanVar(value=False)
        self._prefer_hevc = tk.BooleanVar(value=False)
        self._verify = tk.BooleanVar(value=True)
        self._show_cmd = tk.BooleanVar(value=False)
        self._extract_audio = tk.BooleanVar(value=False)
        self._extract_sub = tk.BooleanVar(value=False)
        self._normalize = tk.BooleanVar(value=False)
        self._gif_mode = tk.BooleanVar(value=False)
        self._strip_meta = tk.BooleanVar(value=False)
        self._two_pass = tk.BooleanVar(value=False)
        self._audio_format = tk.StringVar(value="mp3")
        self._external_audio = tk.StringVar()
        self._subtitle_path = tk.StringVar()
        self._subtitle_stream_idx = tk.StringVar()
        self._subtitle_burn_in = tk.BooleanVar(value=False)
        self._extract_sub_format = tk.StringVar(value=settings.extract_subtitle_format)
        self._replace_audio = tk.BooleanVar(value=False)
        self._audio_delay_ms = tk.IntVar(value=0)
        self._extra_audio_tracks = tk.StringVar()
        self._cover_art_path = tk.StringVar()
        self._trim_start = tk.StringVar()
        self._trim_end = tk.StringVar()
        self._meta_title = tk.StringVar()
        self._meta_author = tk.StringVar()
        self._metadata_date = tk.StringVar()
        self._batch_output_dir = tk.StringVar()
        self._video_stream_idx = tk.StringVar()
        self._audio_stream_idx = tk.StringVar()
        self._crop = tk.StringVar()
        self._rotation = tk.StringVar(value="0")
        self._fps = tk.StringVar()
        self._watermark_path = tk.StringVar()
        self._watermark_position = tk.StringVar(value=settings.watermark_position)
        self._video_codec = tk.StringVar(value=settings.video_codec)
        self._audio_codec = tk.StringVar(value=settings.audio_codec)
        self._video_bitrate = tk.StringVar(value=settings.video_bitrate)
        self._preserve_chapters = tk.BooleanVar(value=settings.preserve_chapters)
        self._deinterlace = tk.BooleanVar(value=False)
        self._denoise = tk.BooleanVar(value=False)
        self._preview_pct = tk.DoubleVar(value=0.0)
        self._status = tk.StringVar(value=self.i18n.t("ready"))
        self._cmd_text = tk.StringVar(value="")
        self._comparison = tk.StringVar(value="")
        self._notify_on_complete = tk.BooleanVar(value=settings.notify_on_complete)
        self._recursive_batch = tk.BooleanVar(value=settings.recursive_batch)
        self._parallel_batch = tk.IntVar(value=settings.parallel_batch)
        self._watch_folder = tk.StringVar(value=settings.watch_folder)
        self._watch_enabled = tk.BooleanVar(value=settings.watch_enabled)
        self._watch_interval = tk.IntVar(value=settings.watch_interval_sec)

        self._cancel_requested = False
        self._worker: threading.Thread | None = None
        self._progress_start = 0.0
        self._preview_image: ctk.CTkImage | None = None
        self._preview_playing = False
        self._preview_after_id: str | None = None
        self._media_duration: float | None = None
        self._batch_files: list[Path] = []
        self._batch_items: list = []
        self._batch_base: ConvertOptions | None = None
        self._batch_running = False
        self._merge_files: list[Path] = []
        self._history_entries: list[dict] = []
        self._folder_watcher: FolderWatcher | None = None
        self._check_updates_on_startup = tk.BooleanVar(value=settings.check_updates_on_startup)
        self._update_in_progress = False

        self._build_ui()
        self.i18n.set_lang(settings.lang)
        self._update_dark_checkbox_state()
        self._apply_theme()
        self._schedule_theme_sync()
        if settings.watch_enabled and settings.watch_folder:
            self.after(500, self._watch_start)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._check_ffmpeg)
        self.after(1500, self._startup_update_check)
        bind_file_drop(self, self._on_drop)

    def _t(self, key: str) -> str:
        return self.i18n.t(key)

    def _add_i18n(self, widget: object, key: str, kind: str = "text") -> object:
        self._i18n_widgets.append((widget, key, kind))
        self._apply_i18n_widget(widget, key, kind)
        return widget

    def _apply_i18n_widget(self, widget: object, key: str, kind: str) -> None:
        text = self._t(key)
        if kind == "text":
            widget.configure(text=text)  # type: ignore[union-attr]
        elif kind == "label":
            widget.configure(text=text)  # type: ignore[union-attr]

    def _refresh_i18n(self) -> None:
        for widget, key, kind in self._i18n_widgets:
            self._apply_i18n_widget(widget, key, kind)
        for key, btn in self._nav_buttons.items():
            btn.configure(text=nav_text(TAB_ICONS[key], self._t(key)))
        for label, key in self._nav_sections:
            label.configure(text=self._t(key).upper())
        self._update_page_header()
        self._history_tree.heading("time", text=self._t("history_col_time"))
        self._history_tree.heading("input", text=self._t("history_col_in"))
        self._history_tree.heading("output", text=self._t("history_col_out"))
        if self._help_menu is not None:
            self._help_menu.entryconfigure(0, label=self._t("check_updates"))
            self._help_menu.entryconfigure(1, label=self._t("install_update"))
            self._help_menu.entryconfigure(2, label=self._t("download_update"))
            self._help_menu.entryconfigure(3, label=self._t("open_log_folder"))
        if self._menu is not None:
            self._menu.entryconfigure(0, label=self._t("help"))

    def _update_page_header(self) -> None:
        if hasattr(self, "_page_title"):
            self._page_title.configure(text=self._t(self._current_tab_key))
        if hasattr(self, "_page_subtitle"):
            self._page_subtitle.configure(text=self._t(f"{self._current_tab_key}_desc"))

    def _on_tab_selected(self, key: str) -> None:
        self._show_tab(key)

    def _show_tab(self, key: str) -> None:
        self._current_tab_key = key
        for tab_key, page in self._tab_pages.items():
            if tab_key == key:
                page.pack(fill=tk.BOTH, expand=True)
            else:
                page.pack_forget()
        for tab_key, btn in self._nav_buttons.items():
            set_nav_active(btn, tab_key == key)
        self._update_page_header()

    def _build_ui(self) -> None:
        self._build_menu()

        header = card(self)
        header.pack(fill=tk.X, padx=PAD, pady=(PAD, PAD_SM))
        header_row = ctk.CTkFrame(header, fg_color="transparent")
        header_row.pack(fill=tk.X, padx=PAD_LG, pady=PAD)
        brand_mark(header_row).pack(side=tk.LEFT)
        title_col = ctk.CTkFrame(header_row, fg_color="transparent")
        title_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(PAD, 0))
        title_row = ctk.CTkFrame(title_col, fg_color="transparent")
        title_row.pack(anchor="w")
        title_lbl = self._add_i18n(page_title(title_row, self._t("app_title")), "app_title")
        title_lbl.pack(side=tk.LEFT)
        badge(title_row, text=f"v{__version__}").pack(side=tk.LEFT, padx=(PAD_SM, 0))
        self._add_i18n(page_subtitle(title_col, self._t("app_tagline")), "app_tagline").pack(anchor="w", pady=(2, 0))

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=PAD_SM)

        sidebar = sidebar_panel(main)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, PAD_SM))
        sidebar.pack_propagate(False)

        nav_groups: list[tuple[str, list[str]]] = [
            ("nav_workflow", ["tab_convert", "tab_audio", "tab_trim", "tab_advanced"]),
            ("nav_automation", ["tab_batch", "tab_watch", "tab_history"]),
        ]
        for section_key, keys in nav_groups:
            sec = nav_label(sidebar, self._t(section_key))
            sec.pack(anchor="w", padx=PAD, pady=(PAD, PAD_SM))
            self._nav_sections.append((sec, section_key))
            for key in keys:
                btn = nav_button(
                    sidebar,
                    icon=TAB_ICONS[key],
                    text=self._t(key),
                    command=lambda k=key: self._on_tab_selected(k),
                )
                btn.pack(fill=tk.X, padx=PAD_SM, pady=2)
                self._nav_buttons[key] = btn

        settings_card = card(sidebar, fg_color=("transparent", "transparent"), border=False)
        settings_card.pack(side=tk.BOTTOM, fill=tk.X, padx=PAD_SM, pady=PAD)
        self._add_i18n(section_title(settings_card, self._t("settings")), "settings").pack(
            anchor="w", padx=PAD_SM, pady=(PAD_SM, 4)
        )
        self._add_i18n(
            ctk.CTkCheckBox(
                settings_card,
                text="",
                variable=self._follow_system_theme,
                command=self._on_system_theme_toggle,
                font=FONT_SMALL,
            ),
            "system_theme",
        ).pack(anchor="w", padx=PAD_SM, pady=2)
        self._dark_theme_cb = self._add_i18n(
            ctk.CTkCheckBox(
                settings_card,
                text="",
                variable=self._dark,
                command=self._on_dark_toggle,
                font=FONT_SMALL,
            ),
            "dark_theme",
        )
        self._dark_theme_cb.pack(anchor="w", padx=PAD_SM, pady=2)
        lang_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        lang_row.pack(fill=tk.X, padx=PAD_SM, pady=(PAD_SM, 2))
        self._add_i18n(ctk.CTkLabel(lang_row, text="", font=FONT_SMALL), "language").pack(side=tk.LEFT)
        ctk.CTkComboBox(
            lang_row,
            values=["uk", "en"],
            variable=self._lang,
            width=72,
            height=28,
            state="readonly",
            font=FONT_SMALL,
            command=lambda _v: self._change_language(),
        ).pack(side=tk.RIGHT)
        self._add_i18n(
            ctk.CTkCheckBox(
                settings_card,
                text="",
                variable=self._check_updates_on_startup,
                command=self._save_settings,
                font=FONT_SMALL,
            ),
            "update_on_startup",
        ).pack(anchor="w", padx=PAD_SM, pady=2)
        self._add_i18n(
            ctk.CTkCheckBox(
                settings_card,
                text="",
                variable=self._notify_on_complete,
                command=self._save_settings,
                font=FONT_SMALL,
            ),
            "notify_on_complete",
        ).pack(anchor="w", padx=PAD_SM, pady=2)
        self._add_i18n(
            secondary_button(settings_card, text="", command=self._save_custom_preset),
            "save_preset",
        ).pack(fill=tk.X, padx=PAD_SM, pady=(PAD_SM, PAD_SM))

        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        page_head = ctk.CTkFrame(content, fg_color="transparent")
        page_head.pack(fill=tk.X, padx=PAD_SM, pady=(0, PAD_SM))
        self._page_title = page_title(page_head, self._t(self._current_tab_key))
        self._page_title.pack(anchor="w")
        self._page_subtitle = page_subtitle(page_head, self._t(f"{self._current_tab_key}_desc"))
        self._page_subtitle.pack(anchor="w", pady=(2, 0))

        self._tab_stack = ctk.CTkFrame(content, fg_color="transparent")
        self._tab_stack.pack(fill=tk.BOTH, expand=True)
        tab_attr = {
            "tab_convert": "_tab_convert_body",
            "tab_audio": "_tab_audio_body",
            "tab_trim": "_tab_trim_body",
            "tab_advanced": "_tab_advanced_body",
            "tab_batch": "_tab_batch_body",
            "tab_watch": "_tab_watch_body",
            "tab_history": "_tab_history_body",
        }
        for key in self._tab_keys:
            page = ctk.CTkFrame(self._tab_stack, fg_color="transparent")
            body = ctk.CTkScrollableFrame(page, fg_color="transparent")
            body.pack(fill=tk.BOTH, expand=True)
            self._tab_pages[key] = page
            setattr(self, tab_attr[key], body)

        self._build_convert_tab()
        self._build_audio_tab()
        self._build_trim_tab()
        self._build_advanced_tab()
        self._build_batch_tab()
        self._build_watch_tab()
        self._build_history_tab()
        self._show_tab(self._current_tab_key)

        dock = card(self)
        dock.pack(fill=tk.X, padx=PAD, pady=(0, PAD))
        dock_inner = ctk.CTkFrame(dock, fg_color="transparent")
        dock_inner.pack(fill=tk.X, padx=PAD_LG, pady=PAD)
        self._progress = ctk.CTkProgressBar(dock_inner, height=10)
        self._progress.pack(fill=tk.X)
        self._progress.set(0)
        ctk.CTkLabel(dock_inner, textvariable=self._status, font=FONT_BODY, anchor="w").pack(
            fill=tk.X, pady=(PAD_SM, 0)
        )
        self._cmd_label = ctk.CTkLabel(
            dock_inner,
            textvariable=self._cmd_text,
            font=FONT_MONO,
            anchor="w",
            wraplength=980,
            justify="left",
        )
        self._cmd_label.pack(fill=tk.X)
        ctk.CTkLabel(
            dock_inner,
            textvariable=self._comparison,
            font=FONT_BODY,
            anchor="w",
            wraplength=980,
            justify="left",
        ).pack(fill=tk.X)

        btns = ctk.CTkFrame(dock_inner, fg_color="transparent")
        btns.pack(fill=tk.X, pady=(PAD, 0))
        self._convert_btn = self._add_i18n(
            primary_button(btns, text="", command=self._start_convert, width=160),
            "convert",
        )
        self._convert_btn.pack(side=tk.LEFT)
        self._add_i18n(secondary_button(btns, text="", command=self._dry_run), "dry_run").pack(
            side=tk.LEFT, padx=(PAD_SM, 0)
        )
        self._cancel_btn = self._add_i18n(
            secondary_button(btns, text="", command=self._cancel_convert, state="disabled"),
            "cancel",
        )
        self._cancel_btn.pack(side=tk.LEFT, padx=(PAD_SM, 0))
        self._add_i18n(secondary_button(btns, text="", command=self._open_output_folder), "open_folder").pack(
            side=tk.RIGHT
        )

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        self._menu = menu
        self._help_menu = tk.Menu(menu, tearoff=0)
        self._help_menu.add_command(label=self._t("check_updates"), command=self._check_updates)
        self._help_menu.add_command(label=self._t("install_update"), command=self._install_update)
        self._help_menu.add_command(label=self._t("download_update"), command=self._download_update)
        self._help_menu.add_command(label=self._t("open_log_folder"), command=self._open_log_folder)
        menu.add_cascade(label=self._t("help"), menu=self._help_menu)
        self.config(menu=menu)

    def _build_convert_tab(self) -> None:
        p = self._tab_convert_body
        inp = card(p)
        inp.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(inp, self._t("input_file")), "input_file").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        row = ctk.CTkFrame(inp, fg_color="transparent")
        row.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        ctk.CTkEntry(row, textvariable=self._input_path, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, PAD_SM)
        )
        self._add_i18n(secondary_button(row, text="", command=self._browse_input), "browse").pack(side=tk.LEFT)
        self._add_i18n(secondary_button(row, text="", command=self._analyze), "analyze").pack(
            side=tk.LEFT, padx=(PAD_SM, 0)
        )
        drop_lbl = ctk.CTkLabel(inp, text=self._t("drop_hint"), font=FONT_BODY, text_color="gray")
        drop_lbl.pack(anchor="w", padx=PAD, pady=(0, PAD_SM))
        self._add_i18n(drop_lbl, "drop_hint")

        body = ctk.CTkFrame(p, fg_color="transparent")
        body.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        prev_frame = card(body)
        prev_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, PAD_SM))
        self._add_i18n(section_title(prev_frame, self._t("preview")), "preview").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        self._preview_label = ctk.CTkLabel(prev_frame, text="—", width=224, height=126, font=FONT_BODY)
        self._preview_label.pack(padx=PAD, pady=(0, PAD_SM))
        preview_ctrl = ctk.CTkFrame(prev_frame, fg_color="transparent")
        preview_ctrl.pack(fill=tk.X, padx=PAD, pady=(0, PAD_SM))
        self._add_i18n(
            ctk.CTkLabel(preview_ctrl, text="", font=FONT_BODY, anchor="w"), "preview_position"
        ).pack(fill=tk.X)
        ctk.CTkSlider(
            preview_ctrl,
            from_=0,
            to=100,
            variable=self._preview_pct,
            command=self._on_preview_seek,
        ).pack(fill=tk.X, pady=(PAD_SM, 0))
        preview_btns = ctk.CTkFrame(preview_ctrl, fg_color="transparent")
        preview_btns.pack(fill=tk.X, pady=(PAD_SM, 0))
        self._add_i18n(secondary_button(preview_btns, text="", command=self._preview_play), "preview_play").pack(
            side=tk.LEFT, padx=(0, PAD_SM)
        )
        self._add_i18n(secondary_button(preview_btns, text="", command=self._preview_stop), "preview_stop").pack(
            side=tk.LEFT
        )

        info_frame = card(body)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._add_i18n(section_title(info_frame, self._t("file_info")), "file_info").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        self._info_text = ctk.CTkTextbox(info_frame, height=220, font=FONT_MONO, wrap="word")
        self._info_text.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD_SM))
        self._info_text.configure(state="disabled")

        settings = card(p)
        settings.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(settings, self._t("settings")), "settings").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        g = ctk.CTkFrame(settings, fg_color="transparent")
        g.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "format").grid(row=0, column=0, sticky=tk.W, padx=(0, PAD_SM))
        ctk.CTkComboBox(
            g, values=list_supported_formats(), variable=self._format, width=100, state="readonly", font=FONT_BODY
        ).grid(row=0, column=1, sticky=tk.W)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "quality_preset").grid(
            row=0, column=2, sticky=tk.W, padx=(PAD, PAD_SM)
        )
        self._quality_preset_cb = ctk.CTkComboBox(
            g,
            values=list_quality_presets(),
            variable=self._quality_preset,
            width=160,
            state="readonly",
            font=FONT_BODY,
        )
        self._quality_preset_cb.grid(row=0, column=3, sticky=tk.W)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "resolution").grid(
            row=1, column=0, sticky=tk.W, padx=(0, PAD_SM), pady=PAD_SM
        )
        ctk.CTkComboBox(
            g,
            values=list(RESOLUTIONS.keys()),
            variable=self._resolution,
            width=120,
            state="readonly",
            font=FONT_BODY,
        ).grid(row=1, column=1, sticky=tk.W, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "crf").grid(
            row=1, column=2, sticky=tk.W, padx=(PAD, PAD_SM), pady=PAD_SM
        )
        ctk.CTkSlider(g, from_=0, to=51, variable=self._crf, number_of_steps=51).grid(
            row=1, column=3, sticky=tk.EW, pady=PAD_SM
        )
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "video_stream").grid(row=2, column=0, sticky=tk.W, pady=PAD_SM)
        self._video_stream_cb = ctk.CTkComboBox(g, variable=self._video_stream_idx, state="readonly", font=FONT_BODY)
        self._video_stream_cb.grid(row=2, column=1, columnspan=3, sticky=tk.EW, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "audio_stream").grid(row=3, column=0, sticky=tk.W, pady=PAD_SM)
        self._audio_stream_cb = ctk.CTkComboBox(g, variable=self._audio_stream_idx, state="readonly", font=FONT_BODY)
        self._audio_stream_cb.grid(row=3, column=1, columnspan=3, sticky=tk.EW, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "video_codec").grid(row=4, column=0, sticky=tk.W, pady=PAD_SM)
        ctk.CTkEntry(g, textvariable=self._video_codec, width=120, font=FONT_BODY).grid(row=4, column=1, sticky=tk.W, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "audio_codec").grid(
            row=4, column=2, sticky=tk.W, padx=(PAD, PAD_SM), pady=PAD_SM
        )
        ctk.CTkEntry(g, textvariable=self._audio_codec, width=120, font=FONT_BODY).grid(row=4, column=3, sticky=tk.W, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(g, text="", font=FONT_BODY), "video_bitrate").grid(row=5, column=0, sticky=tk.W, pady=PAD_SM)
        ctk.CTkEntry(g, textvariable=self._video_bitrate, width=120, font=FONT_BODY).grid(row=5, column=1, sticky=tk.W, pady=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(g, text="", variable=self._copy_streams, font=FONT_BODY), "copy_streams"
        ).grid(row=6, column=0, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ctk.CTkCheckBox(g, text="", variable=self._overwrite, font=FONT_BODY), "overwrite"
        ).grid(row=6, column=2, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ctk.CTkCheckBox(g, text="", variable=self._hw_encode, font=FONT_BODY), "hw_encode"
        ).grid(row=7, column=0, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ctk.CTkCheckBox(g, text="", variable=self._prefer_hevc, font=FONT_BODY), "prefer_hevc"
        ).grid(row=7, column=2, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ctk.CTkCheckBox(g, text="", variable=self._verify, font=FONT_BODY), "verify"
        ).grid(row=8, column=0, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ctk.CTkCheckBox(g, text="", variable=self._show_cmd, font=FONT_BODY), "show_cmd"
        ).grid(row=8, column=2, columnspan=2, sticky=tk.W)
        g.columnconfigure(3, weight=1)

        out_row = ctk.CTkFrame(settings, fg_color="transparent")
        out_row.pack(fill=tk.X, padx=PAD, pady=(0, PAD_SM))
        self._add_i18n(ctk.CTkLabel(out_row, text="", font=FONT_BODY), "output").pack(side=tk.LEFT)
        ctk.CTkEntry(out_row, textvariable=self._output_path, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )
        secondary_button(out_row, text="...", width=40, command=self._browse_output).pack(side=tk.LEFT)

    def _build_audio_tab(self) -> None:
        p = self._tab_audio_body
        f = card(p)
        f.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(f, self._t("tab_audio")), "tab_audio").pack(anchor="w", padx=PAD, pady=(PAD_SM, 4))
        self._add_i18n(
            ctk.CTkCheckBox(f, text="", variable=self._extract_audio, font=FONT_BODY), "extract_audio"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row, text="", font=FONT_BODY), "audio_format").pack(side=tk.LEFT)
        ctk.CTkComboBox(
            row, values=list_audio_formats(), variable=self._audio_format, width=100, state="readonly", font=FONT_BODY
        ).pack(side=tk.LEFT, padx=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(f, text="", variable=self._normalize, font=FONT_BODY), "normalize"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row2, text="", font=FONT_BODY), "add_audio").pack(side=tk.LEFT)
        ctk.CTkEntry(row2, textvariable=self._external_audio, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )
        secondary_button(row2, text="...", width=40, command=self._browse_external_audio).pack(side=tk.LEFT)
        row3 = ctk.CTkFrame(f, fg_color="transparent")
        row3.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row3, text="", font=FONT_BODY), "embed_sub").pack(side=tk.LEFT)
        ctk.CTkEntry(row3, textvariable=self._subtitle_path, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )
        secondary_button(row3, text="...", width=40, command=self._browse_subtitle).pack(side=tk.LEFT)
        self._add_i18n(
            ctk.CTkCheckBox(f, text="", variable=self._extract_sub, font=FONT_BODY), "extract_sub"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        row4 = ctk.CTkFrame(f, fg_color="transparent")
        row4.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row4, text="", font=FONT_BODY), "subtitle_stream").pack(side=tk.LEFT)
        self._subtitle_stream_cb = ctk.CTkComboBox(
            row4, variable=self._subtitle_stream_idx, state="readonly", font=FONT_BODY
        )
        self._subtitle_stream_cb.pack(side=tk.LEFT, padx=PAD_SM, fill=tk.X, expand=True)
        self._add_i18n(
            ctk.CTkCheckBox(f, text="", variable=self._subtitle_burn_in, font=FONT_BODY), "subtitle_burn_in"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        row5 = ctk.CTkFrame(f, fg_color="transparent")
        row5.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row5, text="", font=FONT_BODY), "extract_sub_format").pack(side=tk.LEFT)
        ctk.CTkComboBox(
            row5,
            values=["srt", "ass", "vtt"],
            variable=self._extract_sub_format,
            width=100,
            state="readonly",
            font=FONT_BODY,
        ).pack(side=tk.LEFT, padx=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(f, text="", variable=self._replace_audio, font=FONT_BODY), "replace_audio"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        row6 = ctk.CTkFrame(f, fg_color="transparent")
        row6.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row6, text="", font=FONT_BODY), "audio_delay").pack(side=tk.LEFT)
        ctk.CTkEntry(row6, textvariable=self._audio_delay_ms, width=100, font=FONT_BODY).pack(side=tk.LEFT, padx=PAD_SM)
        row7 = ctk.CTkFrame(f, fg_color="transparent")
        row7.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row7, text="", font=FONT_BODY), "extra_audio_tracks").pack(side=tk.LEFT)
        ctk.CTkEntry(row7, textvariable=self._extra_audio_tracks, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )

    def _build_trim_tab(self) -> None:
        p = self._tab_trim_body
        f = card(p)
        f.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(f, self._t("tab_trim")), "tab_trim").pack(anchor="w", padx=PAD, pady=(PAD_SM, 4))
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(r1, text="", width=140, font=FONT_BODY), "trim_start").pack(side=tk.LEFT)
        ctk.CTkEntry(r1, textvariable=self._trim_start, width=120, font=FONT_BODY).pack(side=tk.LEFT, padx=PAD_SM)
        self._add_i18n(ctk.CTkLabel(r1, text="", font=FONT_BODY), "trim_end").pack(side=tk.LEFT, padx=(PAD, 0))
        ctk.CTkEntry(r1, textvariable=self._trim_end, width=120, font=FONT_BODY).pack(side=tk.LEFT, padx=PAD_SM)
        self._add_i18n(ctk.CTkLabel(f, text="", font=FONT_BODY), "preset_speed").pack(anchor="w", padx=PAD, pady=(PAD_SM, 0))
        ctk.CTkComboBox(
            f,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
            variable=self._preset,
            width=160,
            state="readonly",
            font=FONT_BODY,
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(f, text="", variable=self._gif_mode, font=FONT_BODY), "gif_mode"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        meta = card(p)
        meta.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(meta, self._t("metadata")), "metadata").pack(anchor="w", padx=PAD, pady=(PAD_SM, 4))
        r2 = ctk.CTkFrame(meta, fg_color="transparent")
        r2.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(r2, text="", width=100, font=FONT_BODY), "metadata_title").pack(side=tk.LEFT)
        ctk.CTkEntry(r2, textvariable=self._meta_title, font=FONT_BODY).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM)
        r3 = ctk.CTkFrame(meta, fg_color="transparent")
        r3.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(r3, text="", width=100, font=FONT_BODY), "metadata_author").pack(side=tk.LEFT)
        ctk.CTkEntry(r3, textvariable=self._meta_author, font=FONT_BODY).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM)
        r4 = ctk.CTkFrame(meta, fg_color="transparent")
        r4.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(r4, text="", width=100, font=FONT_BODY), "metadata_date").pack(side=tk.LEFT)
        ctk.CTkEntry(r4, textvariable=self._metadata_date, font=FONT_BODY).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(meta, text="", variable=self._strip_meta, font=FONT_BODY), "strip_meta"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        r5 = ctk.CTkFrame(meta, fg_color="transparent")
        r5.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(r5, text="", font=FONT_BODY), "cover_art").pack(side=tk.LEFT)
        ctk.CTkEntry(r5, textvariable=self._cover_art_path, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )
        self._add_i18n(secondary_button(r5, text="", command=self._browse_cover_art), "browse").pack(side=tk.LEFT)
        filt = card(p)
        filt.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(filt, self._t("tab_advanced")), "tab_advanced").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        self._add_i18n(
            ctk.CTkCheckBox(filt, text="", variable=self._preserve_chapters, command=self._save_settings, font=FONT_BODY),
            "preserve_chapters",
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(filt, text="", variable=self._deinterlace, font=FONT_BODY), "deinterlace"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(filt, text="", variable=self._denoise, font=FONT_BODY), "denoise"
        ).pack(anchor="w", padx=PAD, pady=PAD_SM)

    def _build_advanced_tab(self) -> None:
        p = self._tab_advanced_body
        merge_frame = card(p)
        merge_frame.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(merge_frame, self._t("merge_files")), "merge_files").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        merge_body = ctk.CTkFrame(merge_frame, fg_color="transparent")
        merge_body.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        list_wrap = ctk.CTkFrame(merge_body, corner_radius=10)
        list_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._merge_listbox = tk.Listbox(list_wrap, height=8, borderwidth=0, highlightthickness=0)
        self._merge_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        merge_sb = ttk.Scrollbar(list_wrap, orient=tk.VERTICAL, command=self._merge_listbox.yview)
        self._merge_listbox.configure(yscrollcommand=merge_sb.set)
        merge_sb.pack(side=tk.LEFT, fill=tk.Y, pady=4)
        merge_btns = ctk.CTkFrame(merge_body, fg_color="transparent")
        merge_btns.pack(side=tk.LEFT, padx=PAD_SM)
        self._add_i18n(secondary_button(merge_btns, text="", command=self._merge_add_files), "add_files").pack(
            fill=tk.X, pady=2
        )
        self._add_i18n(secondary_button(merge_btns, text="", command=self._merge_clear), "clear_queue").pack(
            fill=tk.X, pady=2
        )

        opts = card(p)
        opts.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(opts, self._t("tab_advanced")), "tab_advanced").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        og = ctk.CTkFrame(opts, fg_color="transparent")
        og.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(og, text="", font=FONT_BODY), "crop").grid(row=0, column=0, sticky=tk.W, padx=(0, PAD_SM))
        ctk.CTkEntry(og, textvariable=self._crop, width=220, font=FONT_BODY).grid(row=0, column=1, sticky=tk.W, pady=2)
        self._add_i18n(ctk.CTkLabel(og, text="", font=FONT_BODY), "rotation").grid(
            row=1, column=0, sticky=tk.W, padx=(0, PAD_SM), pady=2
        )
        ctk.CTkComboBox(
            og, values=["0", "90", "180", "270"], variable=self._rotation, width=100, state="readonly", font=FONT_BODY
        ).grid(row=1, column=1, sticky=tk.W, pady=2)
        self._add_i18n(ctk.CTkLabel(og, text="", font=FONT_BODY), "fps").grid(row=2, column=0, sticky=tk.W, padx=(0, PAD_SM), pady=2)
        ctk.CTkEntry(og, textvariable=self._fps, width=120, font=FONT_BODY).grid(row=2, column=1, sticky=tk.W, pady=2)
        wm_row = ctk.CTkFrame(opts, fg_color="transparent")
        wm_row.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(wm_row, text="", font=FONT_BODY), "watermark").pack(side=tk.LEFT)
        ctk.CTkEntry(wm_row, textvariable=self._watermark_path, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )
        self._add_i18n(secondary_button(wm_row, text="", command=self._browse_watermark), "browse").pack(side=tk.LEFT)
        wm_pos_row = ctk.CTkFrame(opts, fg_color="transparent")
        wm_pos_row.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(wm_pos_row, text="", font=FONT_BODY), "watermark_position").pack(side=tk.LEFT)
        ctk.CTkEntry(wm_pos_row, textvariable=self._watermark_position, width=120, font=FONT_BODY).pack(
            side=tk.LEFT, padx=PAD_SM
        )
        self._add_i18n(
            ctk.CTkCheckBox(opts, text="", variable=self._two_pass, font=FONT_BODY), "two_pass"
        ).pack(anchor="w", padx=PAD, pady=(0, PAD_SM))

    def _build_batch_tab(self) -> None:
        p = self._tab_batch_body
        f = card(p)
        f.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(f, self._t("batch_queue")), "batch_queue").pack(
            anchor="w", padx=PAD, pady=(PAD_SM, 4)
        )
        batch_body = ctk.CTkFrame(f, fg_color="transparent")
        batch_body.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        list_wrap = ctk.CTkFrame(batch_body, corner_radius=10)
        list_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._batch_list = tk.Listbox(list_wrap, height=12, borderwidth=0, highlightthickness=0)
        self._batch_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(list_wrap, orient=tk.VERTICAL, command=self._batch_list.yview)
        self._batch_list.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.LEFT, fill=tk.Y, pady=4)
        btns = ctk.CTkFrame(batch_body, fg_color="transparent")
        btns.pack(side=tk.LEFT, padx=PAD_SM, pady=PAD_SM)
        self._add_i18n(secondary_button(btns, text="", command=self._batch_add_files), "add_files").pack(
            fill=tk.X, pady=2
        )
        self._add_i18n(secondary_button(btns, text="", command=self._batch_add_folder), "browse_folder").pack(
            fill=tk.X, pady=2
        )
        self._add_i18n(secondary_button(btns, text="", command=self._batch_clear), "clear_queue").pack(fill=tk.X, pady=2)
        self._add_i18n(primary_button(btns, text="", command=self._start_batch), "convert").pack(fill=tk.X, pady=(PAD, 2))
        self._add_i18n(secondary_button(btns, text="", command=self._pause_batch), "pause_batch").pack(fill=tk.X, pady=2)
        self._add_i18n(secondary_button(btns, text="", command=self._resume_batch), "resume_batch").pack(fill=tk.X, pady=2)
        opts_row = ctk.CTkFrame(p, fg_color="transparent")
        opts_row.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(opts_row, text="", variable=self._recursive_batch, command=self._save_settings, font=FONT_BODY),
            "recursive_batch",
        ).pack(side=tk.LEFT)
        self._add_i18n(ctk.CTkLabel(opts_row, text="", font=FONT_BODY), "parallel_batch").pack(side=tk.LEFT, padx=(PAD, 4))
        ctk.CTkEntry(opts_row, textvariable=self._parallel_batch, width=60, font=FONT_BODY).pack(side=tk.LEFT)
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row, text="", font=FONT_BODY), "output_dir").pack(side=tk.LEFT)
        ctk.CTkEntry(row, textvariable=self._batch_output_dir, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )
        secondary_button(row, text="...", width=40, command=self._browse_batch_dir).pack(side=tk.LEFT)

    def _build_watch_tab(self) -> None:
        p = self._tab_watch_body
        f = card(p)
        f.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(section_title(f, self._t("tab_watch")), "tab_watch").pack(anchor="w", padx=PAD, pady=(PAD_SM, 4))
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(ctk.CTkLabel(row, text="", font=FONT_BODY), "watch_folder").pack(side=tk.LEFT)
        ctk.CTkEntry(row, textvariable=self._watch_folder, font=FONT_BODY).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_SM
        )
        self._add_i18n(secondary_button(row, text="", command=self._browse_watch_folder), "browse_folder").pack(
            side=tk.LEFT
        )
        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        self._add_i18n(
            ctk.CTkCheckBox(row2, text="", variable=self._watch_enabled, command=self._save_settings, font=FONT_BODY),
            "watch_enable",
        ).pack(side=tk.LEFT)
        self._add_i18n(ctk.CTkLabel(row2, text="", font=FONT_BODY), "watch_interval").pack(side=tk.LEFT, padx=(PAD, 4))
        ctk.CTkEntry(row2, textvariable=self._watch_interval, width=80, font=FONT_BODY).pack(side=tk.LEFT)
        row3 = ctk.CTkFrame(f, fg_color="transparent")
        row3.pack(fill=tk.X, padx=PAD, pady=PAD_SM)
        secondary_button(row3, text="Start", command=self._watch_start).pack(side=tk.LEFT, padx=(0, PAD_SM))
        secondary_button(row3, text="Stop", command=self._watch_stop).pack(side=tk.LEFT)

    def _build_history_tab(self) -> None:
        p = self._tab_history_body
        hist_card = card(p)
        hist_card.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=PAD_SM)
        tree_wrap = ctk.CTkFrame(hist_card, corner_radius=10)
        tree_wrap.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=PAD_SM)
        cols = ("time", "input", "output")
        self._history_tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=16)
        self._history_tree.heading("time", text=self._t("history_col_time"))
        self._history_tree.heading("input", text=self._t("history_col_in"))
        self._history_tree.heading("output", text=self._t("history_col_out"))
        self._history_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._history_tree.bind("<Double-1>", self._history_double_click)
        hist_btns = ctk.CTkFrame(p, fg_color="transparent")
        hist_btns.pack(pady=PAD_SM)
        self._add_i18n(secondary_button(hist_btns, text="", command=self._history_load), "history_load").pack(
            side=tk.LEFT, padx=4
        )
        self._add_i18n(secondary_button(hist_btns, text="", command=self._history_rerun), "history_rerun").pack(
            side=tk.LEFT, padx=4
        )
        self._add_i18n(secondary_button(hist_btns, text="", command=self._refresh_history), "refresh").pack(
            side=tk.LEFT, padx=4
        )
        self._refresh_history()
    def _uses_dark_theme(self) -> bool:
        if self._follow_system_theme.get():
            return is_dark_mode()
        return self._dark.get()

    def _update_dark_checkbox_state(self) -> None:
        if self._dark_theme_cb is not None:
            self._dark_theme_cb.configure(
                state="disabled" if self._follow_system_theme.get() else "normal"
            )

    def _schedule_theme_sync(self) -> None:
        if self._follow_system_theme.get():
            dark = is_dark_mode()
            if dark != self._applied_dark:
                self._apply_theme()
        self.after(3000, self._schedule_theme_sync)

    def _apply_theme(self) -> None:
        sync_appearance(
            follow_system=self._follow_system_theme.get(),
            dark_manual=self._dark.get(),
        )
        dark = self._uses_dark_theme()
        self._applied_dark = dark
        style = ttk.Style(self)
        if dark:
            bg, fg = "#1e1e1e", "#e0e0e0"
            list_bg = "#2d2d2d"
            style.theme_use("clam")
            style.configure("Treeview", background=list_bg, foreground=fg, fieldbackground=list_bg)
            style.configure("Treeview.Heading", background=bg, foreground=fg)
            style.map("Treeview", background=[("selected", "#404040")])
            self._batch_list.configure(bg=list_bg, fg=fg, selectbackground="#404040")
            self._merge_listbox.configure(bg=list_bg, fg=fg, selectbackground="#404040")
        else:
            style.theme_use("vista" if "vista" in style.theme_names() else "default")
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
            style.configure("Treeview.Heading", background="SystemButtonFace", foreground="black")
            self._batch_list.configure(bg="white", fg="black", selectbackground="SystemHighlight")
            self._merge_listbox.configure(bg="white", fg="black", selectbackground="SystemHighlight")

    def _on_system_theme_toggle(self) -> None:
        self._update_dark_checkbox_state()
        self._apply_theme()
        self._save_settings()

    def _on_dark_toggle(self) -> None:
        self._apply_theme()
        self._save_settings()

    def _save_settings(self) -> None:
        save_settings(
            AppSettings(
                lang=self._lang.get(),
                dark=self._dark.get(),
                follow_system_theme=self._follow_system_theme.get(),
                check_updates_on_startup=self._check_updates_on_startup.get(),
                notify_on_complete=self._notify_on_complete.get(),
                recursive_batch=self._recursive_batch.get(),
                parallel_batch=int(self._parallel_batch.get()),
                preserve_chapters=self._preserve_chapters.get(),
                watch_folder=self._watch_folder.get(),
                watch_enabled=self._watch_enabled.get(),
                watch_interval_sec=int(self._watch_interval.get()),
                video_codec=self._video_codec.get(),
                audio_codec=self._audio_codec.get(),
                video_bitrate=self._video_bitrate.get(),
                watermark_position=self._watermark_position.get(),
                extract_subtitle_format=self._extract_sub_format.get(),
            )
        )

    def _save_custom_preset(self) -> None:
        name = simpledialog.askstring(self._t("save_preset"), self._t("preset_name"), parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        scale = RESOLUTIONS.get(self._resolution.get())
        preset = QualityPreset(
            id=name,
            crf=None if self._copy_streams.get() else int(self._crf.get()),
            preset=self._preset.get(),
            video_bitrate=self._video_bitrate.get().strip() or None,
            scale=scale,
            format=self._format.get().lstrip("."),
        )
        add_custom_preset(name, preset)
        self._quality_preset_cb.configure(values=list_quality_presets())
        self._quality_preset.set(name)
        messagebox.showinfo(self._t("done"), name)

    def _change_language(self, _event=None) -> None:
        self.i18n.set_lang(self._lang.get())
        self.title(f"{self.i18n.t('app_title')} v{__version__}")
        self._refresh_i18n()
        self._save_settings()

    @staticmethod
    def _stream_index(var: tk.StringVar) -> int | None:
        text = var.get().strip()
        if not text:
            return None
        part = text.split(":", 1)[0].strip()
        try:
            return int(part)
        except ValueError:
            return None

    def _set_stream_by_index(self, var: tk.StringVar, cb: ctk.CTkComboBox, index: int | None) -> None:
        if index is None:
            var.set("")
            return
        for label in cb.cget("values"):
            if str(label).startswith(f"{index}:"):
                var.set(label)
                return
        var.set(str(index))

    def _parse_extra_audio_tracks(self) -> list[int]:
        text = self._extra_audio_tracks.get().strip()
        if not text:
            return []
        tracks: list[int] = []
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                tracks.append(int(part))
            except ValueError:
                continue
        return tracks

    def _on_drop(self, paths: list[str]) -> None:
        videos = [p for p in paths if Path(p).suffix.lower() in VIDEO_EXTS]
        if not videos:
            videos = paths
        if len(videos) == 1:
            self._input_path.set(videos[0])
            self._suggest_output_path(Path(videos[0]))
            self._analyze()
        else:
            for path in videos:
                self._batch_add_path(Path(path))

    def _set_info_text(self, text: str) -> None:
        self._info_text.configure(state="normal")
        self._info_text.delete("1.0", "end")
        self._info_text.insert("1.0", text)
        self._info_text.configure(state="disabled")

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Video", "*.mov *.mp4 *.mkv *.avi *.webm"), ("All", "*.*")])
        if path:
            self._input_path.set(path)
            self._suggest_output_path(Path(path))
            self._analyze()

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=f".{self._format.get()}", filetypes=[("Video", "*.*")])
        if path:
            self._output_path.set(path)

    def _browse_external_audio(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.aac *.wav *.m4a *.flac"), ("All", "*.*")])
        if path:
            self._external_audio.set(path)

    def _browse_subtitle(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Subtitles", "*.srt *.ass *.vtt"), ("All", "*.*")])
        if path:
            self._subtitle_path.set(path)

    def _browse_watermark(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Image", "*.png *.jpg *.jpeg *.gif"), ("All", "*.*")])
        if path:
            self._watermark_path.set(path)

    def _browse_cover_art(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Image", "*.png *.jpg *.jpeg *.gif"), ("All", "*.*")])
        if path:
            self._cover_art_path.set(path)

    def _browse_watch_folder(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self._watch_folder.set(path)
            self._save_settings()

    def _browse_batch_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self._batch_output_dir.set(path)

    def _merge_add_files(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=[("Video", "*.mov *.mp4 *.mkv *.avi *.webm"), ("All", "*.*")])
        for path in paths:
            p = Path(path)
            if p not in self._merge_files:
                self._merge_files.append(p)
                self._merge_listbox.insert(tk.END, str(p))

    def _merge_clear(self) -> None:
        self._merge_files.clear()
        self._merge_listbox.delete(0, tk.END)

    def _suggest_output_path(self, input_path: Path) -> None:
        fmt = self._audio_format.get() if self._extract_audio.get() else self._format.get().lstrip(".")
        if self._gif_mode.get():
            fmt = "gif"
        self._output_path.set(str(input_path.with_name(f"{input_path.stem}_converted.{fmt}")))

    def _populate_streams(self, path: Path) -> None:
        video, audio, subtitles = list_selectable_streams(path)
        v_labels = [label for _, label in video]
        a_labels = [label for _, label in audio]
        s_labels = [label for _, label in subtitles]
        self._video_stream_cb.configure(values=v_labels)
        self._audio_stream_cb.configure(values=a_labels)
        self._subtitle_stream_cb.configure(values=s_labels)
        self._video_stream_idx.set(v_labels[0] if v_labels else "")
        self._audio_stream_idx.set(a_labels[0] if a_labels else "")
        self._subtitle_stream_idx.set(s_labels[0] if s_labels else "")

    def _preview_play(self) -> None:
        if self._preview_playing:
            return
        self._preview_playing = True
        self._preview_tick()

    def _preview_stop(self) -> None:
        self._preview_playing = False
        if self._preview_after_id is not None:
            self.after_cancel(self._preview_after_id)
            self._preview_after_id = None

    def _preview_tick(self) -> None:
        if not self._preview_playing:
            return
        pct = self._preview_pct.get()
        pct = 0.0 if pct >= 100 else pct + 1.0
        self._preview_pct.set(pct)
        self._on_preview_seek()
        self._preview_after_id = self.after(250, self._preview_tick)

    def _update_preview(self, path: Path, at_sec: float) -> None:
        preview = generate_preview(path, at_sec=at_sec)
        if preview and preview.is_file():
            from PIL import Image

            pil_img = Image.open(str(preview))
            self._preview_image = ctk.CTkImage(pil_img, size=(224, 126))
            self._preview_label.configure(image=self._preview_image, text="")

    def _on_preview_seek(self, _value: str | None = None) -> None:
        text = self._input_path.get().strip()
        if not text or not self._media_duration:
            return
        pct = self._preview_pct.get()
        at_sec = max(0.0, self._media_duration * pct / 100.0)
        self._update_preview(Path(text), at_sec)

    def _analyze(self) -> None:
        text = self._input_path.get().strip()
        if not text:
            return
        path = Path(text)
        try:
            info = analyze_file(path)
            self._media_duration = info.duration_sec
            self._set_info_text(render_media_info(info))
            self._status.set(path.name)
            self._populate_streams(path)
            self._preview_pct.set(0.0)
            at_sec = 1.0
            if self._media_duration:
                at_sec = max(0.0, min(self._media_duration * 0.05, self._media_duration - 0.1))
            self._update_preview(path, at_sec)
            if not self._output_path.get().strip():
                self._suggest_output_path(path)
        except Exception as exc:
            messagebox.showerror(self._t("error"), str(exc))

    def _parse_rotation(self) -> int | None:
        value = self._rotation.get().strip()
        if value in ("90", "180", "270"):
            return int(value)
        return None

    def _build_options(
        self,
        input_path: Path,
        output_path: Path | None = None,
        *,
        dry_run: bool = False,
    ) -> ConvertOptions:
        scale = RESOLUTIONS.get(self._resolution.get())
        fmt = self._audio_format.get() if self._extract_audio.get() else self._format.get()
        if self._gif_mode.get():
            fmt = "gif"
        out = Path(output_path) if output_path else (Path(self._output_path.get()) if self._output_path.get().strip() else None)
        ext_audio = self._external_audio.get().strip()
        sub = self._subtitle_path.get().strip()
        wm = self._watermark_path.get().strip()
        cover = self._cover_art_path.get().strip()
        vcodec = self._video_codec.get().strip() or None
        acodec = self._audio_codec.get().strip() or None
        vbitrate = self._video_bitrate.get().strip() or None
        return ConvertOptions(
            input_path=input_path,
            output_path=out,
            output_format=fmt,
            video_codec=vcodec,
            audio_codec=acodec,
            video_bitrate=vbitrate,
            crf=None if self._copy_streams.get() else int(self._crf.get()),
            preset=self._preset.get(),
            copy_streams=self._copy_streams.get(),
            overwrite=self._overwrite.get(),
            dry_run=dry_run,
            quality_preset_id=self._quality_preset.get(),
            scale=scale,
            start_time=self._trim_start.get().strip() or None,
            end_time=self._trim_end.get().strip() or None,
            hardware_encode=self._hw_encode.get(),
            prefer_hevc=self._prefer_hevc.get(),
            extract_audio=self._extract_audio.get(),
            extract_subtitles=self._extract_sub.get(),
            external_audio_path=Path(ext_audio) if ext_audio else None,
            subtitle_path=Path(sub) if sub else None,
            subtitle_stream=self._stream_index(self._subtitle_stream_idx),
            subtitle_burn_in=self._subtitle_burn_in.get(),
            extract_subtitle_format=self._extract_sub_format.get(),
            normalize_audio=self._normalize.get(),
            gif_mode=self._gif_mode.get(),
            metadata_title=self._meta_title.get().strip() or None,
            metadata_author=self._meta_author.get().strip() or None,
            metadata_date=self._metadata_date.get().strip() or None,
            strip_metadata=self._strip_meta.get(),
            verify_output=self._verify.get(),
            merge_inputs=list(self._merge_files),
            crop=self._crop.get().strip() or None,
            rotation=self._parse_rotation(),
            fps=self._fps.get().strip() or None,
            watermark_path=Path(wm) if wm else None,
            watermark_position=self._watermark_position.get().strip() or "10:10",
            two_pass=self._two_pass.get(),
            cover_art_path=Path(cover) if cover else None,
            preserve_chapters=self._preserve_chapters.get(),
            deinterlace=self._deinterlace.get(),
            denoise=self._denoise.get(),
            extra_audio_tracks=self._parse_extra_audio_tracks(),
            replace_audio=self._replace_audio.get(),
            audio_delay_ms=int(self._audio_delay_ms.get() or 0),
            video_stream=self._stream_index(self._video_stream_idx),
            audio_stream=self._stream_index(self._audio_stream_idx),
        )

    def _show_ffmpeg_cmd(self, cmd: list[str]) -> None:
        from .ffmpeg_utils import ensure_ffmpeg

        ffmpeg, _ = ensure_ffmpeg()
        self._cmd_text.set(f"{ffmpeg} {' '.join(cmd)}")

    def _dry_run(self) -> None:
        inp = self._input_path.get().strip()
        if not inp:
            messagebox.showwarning(self._t("error"), self._t("ready"))
            return
        try:
            options = self._build_options(Path(inp), dry_run=True)
            _, cmd = convert_video(options)
            self._show_ffmpeg_cmd(cmd)
            self._status.set(self._t("dry_run"))
        except Exception as exc:
            messagebox.showerror(self._t("error"), str(exc))

    def _set_busy(self, busy: bool) -> None:
        self._convert_btn.configure(state="disabled" if busy else "normal")
        self._cancel_btn.configure(state="normal" if busy else "disabled")

    def _start_convert(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        inp = self._input_path.get().strip()
        if not inp:
            messagebox.showwarning(self._t("error"), self._t("ready"))
            return
        try:
            options = self._build_options(Path(inp))
            if self._show_cmd.get():
                self._show_ffmpeg_cmd(build_ffmpeg_args(options))
        except Exception as exc:
            messagebox.showerror(self._t("error"), str(exc))
            return
        self._cancel_requested = False
        self._progress_start = time.time()
        self._progress.set(0)
        self._comparison.set("")
        self._set_busy(True)
        self._worker = threading.Thread(target=self._convert_worker, args=(options,), daemon=True)
        self._worker.start()

    def _convert_worker(self, options: ConvertOptions) -> None:
        try:
            output_path, cmd = convert_video(
                options,
                on_progress=self._on_progress,
                cancel_check=lambda: self._cancel_requested,
            )
            cmp_text = ""
            if options.input_path.is_file() and output_path.is_file() and not options.extract_subtitles:
                cmp_text = compare_conversion(options.input_path, output_path)
            self.after(0, lambda: self._on_convert_done(output_path, cmd, cmp_text, options))
        except Exception as exc:
            log_error(str(exc))
            self.after(0, lambda: self._on_convert_failed(str(exc)))

    def _on_progress(self, percent: float, message: str) -> None:
        eta = ""
        if percent > 1:
            elapsed = time.time() - self._progress_start
            remaining = elapsed * (100 - percent) / max(percent, 0.1)
            eta = f" | ETA ~{int(remaining)}s"
        self.after(0, lambda: self._apply_progress(percent, f"{message[:80]}{eta}"))

    def _apply_progress(self, percent: float, message: str) -> None:
        animate_progress(self._progress, percent)
        self._status.set(message)

    def _on_convert_done(self, output_path: Path, cmd: list[str], cmp_text: str, options: ConvertOptions) -> None:
        self._progress.set(1.0)
        self._status.set(f"{self._t('done')}: {output_path.name}")
        self._comparison.set(cmp_text)
        if self._show_cmd.get():
            self._show_ffmpeg_cmd(cmd)
        append_history(
            {"input": str(options.input_path), "output": str(output_path), "mode": "single"},
            options=options_to_dict(options),
        )
        self._refresh_history()
        self._set_busy(False)
        if self._notify_on_complete.get():
            notify(self._t("app_title"), f"{self._t('done')}: {output_path.name}")
        messagebox.showinfo(self._t("done"), str(output_path))

    def _on_convert_failed(self, error: str) -> None:
        self._batch_running = False
        self._status.set(self._t("error"))
        self._set_busy(False)
        if "скасовано" not in error.lower() and "cancel" not in error.lower():
            messagebox.showerror(self._t("error"), error)

    def _cancel_convert(self) -> None:
        self._cancel_requested = True

    def _batch_add_path(self, path: Path) -> None:
        if path not in self._batch_files:
            self._batch_files.append(path)
            self._batch_list.insert(tk.END, str(path))

    def _batch_add_files(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=[("Video", "*.mov *.mp4 *.mkv *.avi *.webm")])
        for path in paths:
            self._batch_add_path(Path(path))

    def _batch_add_folder(self) -> None:
        folder = filedialog.askdirectory()
        if not folder:
            return
        for path in scan_videos(Path(folder), recursive=self._recursive_batch.get()):
            self._batch_add_path(path)

    def _batch_clear(self) -> None:
        self._batch_files.clear()
        self._batch_list.delete(0, tk.END)

    def _start_batch(self) -> None:
        if not self._batch_files:
            messagebox.showwarning(self._t("error"), self._t("batch_queue"))
            return
        if self._worker and self._worker.is_alive():
            return
        out_dir = Path(self._batch_output_dir.get()) if self._batch_output_dir.get().strip() else None
        items = build_batch_items(self._batch_files, output_dir=out_dir, output_format=self._format.get())
        base = self._build_options(self._batch_files[0], items[0].output_path)
        self._batch_items = items
        self._batch_base = base
        self._batch_running = True
        self._cancel_requested = False
        self._progress_start = time.time()
        self._set_busy(True)
        self._worker = threading.Thread(target=self._batch_worker, args=(items, base), daemon=True)
        self._worker.start()

    def _pause_batch(self) -> None:
        pause_batch()

    def _resume_batch(self) -> None:
        resume_batch()

    def _batch_worker(self, items, base: ConvertOptions) -> None:
        try:
            results = run_batch(
                items,
                base,
                on_progress=self._on_progress,
                cancel_check=lambda: self._cancel_requested,
                max_workers=int(self._parallel_batch.get()),
            )
            self.after(0, lambda: self._on_batch_done(results, base))
        except Exception as exc:
            log_error(str(exc))
            self.after(0, lambda: self._on_convert_failed(str(exc)))
            self.after(0, lambda: setattr(self, "_batch_running", False))

    def _on_batch_done(self, results, base: ConvertOptions) -> None:
        self._batch_running = False
        self._progress.set(1.0)
        self._status.set(f"{self._t('done')}: {len(results)} files")
        opts_dict = options_to_dict(base)
        for output_path, _ in results:
            append_history({"input": "batch", "output": str(output_path), "mode": "batch"}, options=opts_dict)
        self._refresh_history()
        self._set_busy(False)
        if self._notify_on_complete.get():
            notify(self._t("app_title"), f"{self._t('done')}: {len(results)} files")
        messagebox.showinfo(self._t("done"), f"{len(results)} files")

    def _refresh_history(self) -> None:
        for item in self._history_tree.get_children():
            self._history_tree.delete(item)
        self._history_entries = list(reversed(load_history()))
        for row in self._history_entries:
            self._history_tree.insert("", tk.END, values=(row.get("time", ""), row.get("input", ""), row.get("output", "")))

    def _history_get_selected_entry(self) -> dict | None:
        sel = self._history_tree.selection()
        if not sel:
            return None
        values = self._history_tree.item(sel[0], "values")
        if not values:
            return None
        for entry in self._history_entries:
            if (
                entry.get("time", "") == values[0]
                and entry.get("input", "") == values[1]
                and entry.get("output", "") == values[2]
            ):
                return entry
        return None

    def _apply_options_to_gui(self, options: ConvertOptions) -> None:
        self._input_path.set(str(options.input_path))
        self._output_path.set(str(options.output_path) if options.output_path else "")
        if options.output_format:
            self._format.set(options.output_format.lstrip("."))
        self._video_codec.set(options.video_codec or "")
        self._audio_codec.set(options.audio_codec or "")
        self._video_bitrate.set(options.video_bitrate or "")
        if options.crf is not None:
            self._crf.set(int(options.crf))
        self._preset.set(options.preset)
        self._copy_streams.set(options.copy_streams)
        self._overwrite.set(options.overwrite)
        if options.quality_preset_id:
            self._quality_preset.set(options.quality_preset_id)
        for key, val in RESOLUTIONS.items():
            if val == options.scale:
                self._resolution.set(key)
                break
        else:
            self._resolution.set("original")
        self._trim_start.set(options.start_time or "")
        self._trim_end.set(options.end_time or "")
        self._hw_encode.set(options.hardware_encode)
        self._prefer_hevc.set(options.prefer_hevc)
        self._extract_audio.set(options.extract_audio)
        self._extract_sub.set(options.extract_subtitles)
        self._external_audio.set(str(options.external_audio_path) if options.external_audio_path else "")
        self._subtitle_path.set(str(options.subtitle_path) if options.subtitle_path else "")
        self._subtitle_burn_in.set(options.subtitle_burn_in)
        self._extract_sub_format.set(options.extract_subtitle_format)
        self._normalize.set(options.normalize_audio)
        self._gif_mode.set(options.gif_mode)
        self._meta_title.set(options.metadata_title or "")
        self._meta_author.set(options.metadata_author or "")
        self._metadata_date.set(options.metadata_date or "")
        self._strip_meta.set(options.strip_metadata)
        self._verify.set(options.verify_output)
        self._merge_files.clear()
        self._merge_listbox.delete(0, tk.END)
        for merge_path in options.merge_inputs:
            self._merge_files.append(merge_path)
            self._merge_listbox.insert(tk.END, str(merge_path))
        self._crop.set(options.crop or "")
        self._rotation.set(str(options.rotation) if options.rotation else "0")
        self._fps.set(options.fps or "")
        self._watermark_path.set(str(options.watermark_path) if options.watermark_path else "")
        self._watermark_position.set(options.watermark_position)
        self._two_pass.set(options.two_pass)
        self._cover_art_path.set(str(options.cover_art_path) if options.cover_art_path else "")
        self._preserve_chapters.set(options.preserve_chapters)
        self._deinterlace.set(options.deinterlace)
        self._denoise.set(options.denoise)
        self._extra_audio_tracks.set(",".join(str(x) for x in options.extra_audio_tracks))
        self._replace_audio.set(options.replace_audio)
        self._audio_delay_ms.set(options.audio_delay_ms)
        if options.input_path.is_file():
            try:
                self._populate_streams(options.input_path)
            except Exception:
                pass
            self._set_stream_by_index(self._video_stream_idx, self._video_stream_cb, options.video_stream)
            self._set_stream_by_index(self._audio_stream_idx, self._audio_stream_cb, options.audio_stream)
            self._set_stream_by_index(self._subtitle_stream_idx, self._subtitle_stream_cb, options.subtitle_stream)

    def _history_load(self) -> None:
        entry = self._history_get_selected_entry()
        if not entry or "options" not in entry:
            messagebox.showwarning(self._t("error"), self._t("history_load"))
            return
        try:
            options = options_from_dict(entry["options"])
            self._apply_options_to_gui(options)
            self._status.set(self._t("history_load"))
        except Exception as exc:
            messagebox.showerror(self._t("error"), str(exc))

    def _history_rerun(self) -> None:
        entry = self._history_get_selected_entry()
        if not entry or "options" not in entry:
            messagebox.showwarning(self._t("error"), self._t("history_rerun"))
            return
        try:
            options = options_from_dict(entry["options"])
            self._apply_options_to_gui(options)
            self._start_convert()
        except Exception as exc:
            messagebox.showerror(self._t("error"), str(exc))

    def _history_double_click(self, _event=None) -> None:
        self._history_load()

    def _watch_start(self) -> None:
        folder = self._watch_folder.get().strip()
        if not folder:
            messagebox.showwarning(self._t("error"), self._t("watch_folder"))
            return
        path = Path(folder)
        if not path.is_dir():
            messagebox.showerror(self._t("error"), self._t("watch_folder"))
            return
        self._watch_stop()
        self._folder_watcher = FolderWatcher(
            path,
            interval_sec=int(self._watch_interval.get()),
            recursive=self._recursive_batch.get(),
            on_new_file=lambda p: self.after(0, lambda fp=p: self._auto_convert_path(fp)),
        )
        self._folder_watcher.start()
        self._watch_enabled.set(True)
        self._save_settings()
        self._status.set(self._t("tab_watch"))

    def _watch_stop(self) -> None:
        if self._folder_watcher is not None:
            self._folder_watcher.stop()
            self._folder_watcher = None

    def _auto_convert_path(self, path: Path) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._input_path.set(str(path))
        self._suggest_output_path(path)
        self._start_convert()

    def _open_output_folder(self) -> None:
        text = self._output_path.get().strip()
        if not text:
            return
        folder = Path(text).parent
        if folder.exists():
            open_path(folder)

    def _open_log_folder(self) -> None:
        open_path(log_path().parent)

    def _check_ffmpeg(self) -> None:
        try:
            from .ffmpeg_utils import ensure_ffmpeg

            ensure_ffmpeg()
        except FFmpegNotFoundError as exc:
            messagebox.showwarning(self._t("error"), str(exc))

    def _check_updates(self) -> None:
        def worker() -> None:
            try:
                available, latest, url = check_for_updates()
                if available:
                    self.after(0, lambda: self._prompt_update(latest, url))
                else:
                    msg = self._t("update_latest").format(version=__version__)
                    self.after(0, lambda: messagebox.showinfo(self._t("check_updates"), msg))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror(self._t("error"), str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _startup_update_check(self) -> None:
        if not self._check_updates_on_startup.get() or self._update_in_progress:
            return

        def worker() -> None:
            try:
                available, latest, url = check_for_updates()
                if available:
                    self.after(0, lambda: self._prompt_update(latest, url))
            except Exception:
                return

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_update(self, latest: str, url: str) -> None:
        if self._update_in_progress:
            return
        if not messagebox.askyesno(
            self._t("check_updates"),
            self._t("update_available").format(latest=latest) + f"\n\n{url}",
        ):
            return
        self._install_update()

    def _install_update(self) -> None:
        if self._update_in_progress:
            return
        if self._worker and self._worker.is_alive():
            messagebox.showwarning(self._t("error"), self._t("update_busy"))
            return
        if not can_auto_update():
            if messagebox.askyesno(self._t("install_update"), self._t("update_dev_mode")):
                try:
                    open_latest_release_download()
                except Exception as exc:
                    messagebox.showerror(self._t("error"), str(exc))
            return

        self._update_in_progress = True
        self._convert_btn.configure(state="disabled")
        self._progress.set(0)

        def worker() -> None:
            try:
                def on_progress(done: int, total: int) -> None:
                    pct = int(done * 100 / total) if total else 0
                    self.after(
                        0,
                        lambda p=pct: (
                            self._progress.set(p / 100.0),
                            self._status.set(self._t("update_downloading").format(pct=p)),
                        ),
                    )

                self.after(0, lambda: self._status.set(self._t("update_downloading").format(pct=0)))
                install_latest_update(progress=on_progress)
                self.after(0, self._finish_update_install)
            except Exception as exc:
                self.after(0, lambda: self._fail_update_install(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_update_install(self) -> None:
        self._status.set(self._t("update_installing"))
        self._progress.set(1.0)
        self.update_idletasks()
        self.after(300, self.destroy)

    def _fail_update_install(self, message: str) -> None:
        self._update_in_progress = False
        self._convert_btn.configure(state="normal")
        self._progress.set(0)
        self._status.set(self._t("ready"))
        messagebox.showerror(self._t("error"), message)

    def _download_update(self) -> None:
        try:
            open_latest_release_download()
        except Exception as exc:
            messagebox.showerror(self._t("error"), str(exc))

    def _on_close(self) -> None:
        if self._worker and self._worker.is_alive():
            if self._batch_running and self._batch_items and self._batch_base is not None:
                if messagebox.askyesno(self._t("app_title"), self._t("exit_background")):
                    spawn_background_batch(self._batch_items, self._batch_base)
                    self._watch_stop()
                    self._preview_stop()
                    self._save_settings()
                    self.destroy()
                else:
                    self._cancel_requested = True
                return
            if not messagebox.askyesno(self._t("app_title"), self._t("exit_confirm")):
                return
            self._cancel_requested = True
        self._watch_stop()
        self._preview_stop()
        self._save_settings()
        self.destroy()


try:
    from tkinterdnd2 import TkinterDnD

    class VideoConverterApp(_VideoConverterMixin, ctk.CTk, TkinterDnD.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.TkdndVersion = TkinterDnD._require(self)
            self._init_app()
except ImportError:

    class VideoConverterApp(_VideoConverterMixin, ctk.CTk):
        def __init__(self) -> None:
            super().__init__()
            self._init_app()


def main() -> int:
    try:
        app = VideoConverterApp()
    except tk.TclError as exc:
        print(f"GUI error: {exc}", file=__import__("sys").stderr)
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
