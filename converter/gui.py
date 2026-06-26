from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

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
from .watch_folder import FolderWatcher
from .updater import (
    can_auto_update,
    check_for_updates,
    install_latest_update,
    open_latest_release_download,
)

try:
    from tkinterdnd2 import TkinterDnD

    _AppBase = TkinterDnD.Tk
except ImportError:
    _AppBase = tk.Tk

VIDEO_EXTS = {".mov", ".mp4", ".mkv", ".avi", ".webm", ".wmv", ".flv", ".m4v", ".mpeg", ".mpg", ".ts", ".ogv"}


class VideoConverterApp(_AppBase):
    def __init__(self) -> None:
        super().__init__()
        settings = load_settings()
        self.i18n = I18n(settings.lang)
        self.title(f"{self.i18n.t('app_title')} v{__version__}")
        self.geometry("980x860")
        self.minsize(900, 740)

        self._i18n_widgets: list[tuple[object, str, str]] = []
        self._notebook_tabs: list[tuple[ttk.Frame, str]] = []
        self._help_menu: tk.Menu | None = None
        self._menu: tk.Menu | None = None

        self._dark = tk.BooleanVar(value=settings.dark)
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
        self._preview_image: tk.PhotoImage | None = None
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
        self._apply_theme()
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
        for i, (frame, key) in enumerate(self._notebook_tabs):
            self._notebook.tab(i, text=self._t(key))
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

    def _build_ui(self) -> None:
        self._build_menu()
        pad = {"padx": 10, "pady": 4}
        top = ttk.Frame(self)
        top.pack(fill=tk.X, **pad)
        self._add_i18n(
            ttk.Checkbutton(top, text="", variable=self._dark, command=self._on_dark_toggle),
            "dark_theme",
        ).pack(side=tk.LEFT)
        self._add_i18n(ttk.Label(top, text=""), "language").pack(side=tk.LEFT, padx=(16, 4))
        lang_cb = ttk.Combobox(top, textvariable=self._lang, values=["uk", "en"], width=5, state="readonly")
        lang_cb.pack(side=tk.LEFT)
        lang_cb.bind("<<ComboboxSelected>>", lambda _e: self._change_language())
        self._add_i18n(
            ttk.Checkbutton(top, text="", variable=self._check_updates_on_startup, command=self._save_settings),
            "update_on_startup",
        ).pack(side=tk.LEFT, padx=(16, 0))
        self._add_i18n(
            ttk.Checkbutton(top, text="", variable=self._notify_on_complete, command=self._save_settings),
            "notify_on_complete",
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._add_i18n(
            ttk.Button(top, text="", command=self._save_custom_preset),
            "save_preset",
        ).pack(side=tk.RIGHT)

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self._tab_convert = ttk.Frame(self._notebook)
        self._tab_audio = ttk.Frame(self._notebook)
        self._tab_trim = ttk.Frame(self._notebook)
        self._tab_advanced = ttk.Frame(self._notebook)
        self._tab_batch = ttk.Frame(self._notebook)
        self._tab_watch = ttk.Frame(self._notebook)
        self._tab_history = ttk.Frame(self._notebook)
        for tab, name in [
            (self._tab_convert, "tab_convert"),
            (self._tab_audio, "tab_audio"),
            (self._tab_trim, "tab_trim"),
            (self._tab_advanced, "tab_advanced"),
            (self._tab_batch, "tab_batch"),
            (self._tab_watch, "tab_watch"),
            (self._tab_history, "tab_history"),
        ]:
            self._notebook.add(tab, text=self._t(name))
            self._notebook_tabs.append((tab, name))

        self._build_convert_tab()
        self._build_audio_tab()
        self._build_trim_tab()
        self._build_advanced_tab()
        self._build_batch_tab()
        self._build_watch_tab()
        self._build_history_tab()

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=4)
        self._progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self._progress.pack(fill=tk.X)
        ttk.Label(bottom, textvariable=self._status).pack(anchor=tk.W, pady=(4, 0))
        self._cmd_label = ttk.Label(bottom, textvariable=self._cmd_text, wraplength=940, font=("Consolas", 9))
        self._cmd_label.pack(anchor=tk.W)
        self._cmp_label = ttk.Label(bottom, textvariable=self._comparison, wraplength=940)
        self._cmp_label.pack(anchor=tk.W)

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._convert_btn = self._add_i18n(
            ttk.Button(btns, text="", command=self._start_convert),
            "convert",
        )
        self._convert_btn.pack(side=tk.LEFT)
        self._add_i18n(
            ttk.Button(btns, text="", command=self._dry_run),
            "dry_run",
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._cancel_btn = self._add_i18n(
            ttk.Button(btns, text="", command=self._cancel_convert, state=tk.DISABLED),
            "cancel",
        )
        self._cancel_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._add_i18n(
            ttk.Button(btns, text="", command=self._open_output_folder),
            "open_folder",
        ).pack(side=tk.RIGHT)

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
        p = self._tab_convert
        inp = ttk.LabelFrame(p, text=self._t("input_file"))
        inp.pack(fill=tk.X, padx=8, pady=6)
        self._add_i18n(inp, "input_file", "label")
        row = ttk.Frame(inp)
        row.pack(fill=tk.X, padx=8, pady=6)
        ttk.Entry(row, textvariable=self._input_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self._add_i18n(ttk.Button(row, text="", command=self._browse_input), "browse").pack(side=tk.LEFT)
        self._add_i18n(ttk.Button(row, text="", command=self._analyze), "analyze").pack(side=tk.LEFT, padx=(8, 0))
        drop_lbl = ttk.Label(inp, text=self._t("drop_hint"), foreground="gray")
        drop_lbl.pack(anchor=tk.W, padx=8, pady=(0, 6))
        self._add_i18n(drop_lbl, "drop_hint")

        body = ttk.Frame(p)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        prev_frame = ttk.LabelFrame(body, text=self._t("preview"))
        prev_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self._add_i18n(prev_frame, "preview", "label")
        self._preview_label = ttk.Label(prev_frame, text="—", width=28)
        self._preview_label.pack(padx=8, pady=(8, 4))
        preview_ctrl = ttk.Frame(prev_frame)
        preview_ctrl.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._add_i18n(ttk.Label(preview_ctrl, text=""), "preview_position").pack(anchor=tk.W)
        ttk.Scale(
            preview_ctrl,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self._preview_pct,
            command=self._on_preview_seek,
        ).pack(fill=tk.X)
        preview_btns = ttk.Frame(preview_ctrl)
        preview_btns.pack(fill=tk.X, pady=(4, 0))
        self._add_i18n(ttk.Button(preview_btns, text="", command=self._preview_play), "preview_play").pack(
            side=tk.LEFT, padx=(0, 4)
        )
        self._add_i18n(ttk.Button(preview_btns, text="", command=self._preview_stop), "preview_stop").pack(side=tk.LEFT)

        info_frame = ttk.LabelFrame(body, text=self._t("file_info"))
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._add_i18n(info_frame, "file_info", "label")
        self._info_text = tk.Text(info_frame, wrap=tk.WORD, height=14, font=("Consolas", 9))
        scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self._info_text.yview)
        self._info_text.configure(yscrollcommand=scroll.set)
        self._info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)
        self._info_text.configure(state=tk.DISABLED)

        settings = ttk.LabelFrame(p, text=self._t("settings"))
        settings.pack(fill=tk.X, padx=8, pady=6)
        self._add_i18n(settings, "settings", "label")
        g = ttk.Frame(settings)
        g.pack(fill=tk.X, padx=8, pady=8)
        self._add_i18n(ttk.Label(g, text=""), "format").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Combobox(g, textvariable=self._format, values=list_supported_formats(), state="readonly", width=8).grid(
            row=0, column=1, sticky=tk.W
        )
        self._add_i18n(ttk.Label(g, text=""), "quality_preset").grid(row=0, column=2, sticky=tk.W, padx=(16, 8))
        self._quality_preset_cb = ttk.Combobox(
            g, textvariable=self._quality_preset, values=list_quality_presets(), state="readonly", width=14
        )
        self._quality_preset_cb.grid(row=0, column=3, sticky=tk.W)
        self._add_i18n(ttk.Label(g, text=""), "resolution").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Combobox(g, textvariable=self._resolution, values=list(RESOLUTIONS.keys()), state="readonly", width=10).grid(
            row=1, column=1, sticky=tk.W, pady=4
        )
        self._add_i18n(ttk.Label(g, text=""), "crf").grid(row=1, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Scale(g, from_=0, to=51, orient=tk.HORIZONTAL, variable=self._crf).grid(row=1, column=3, sticky=tk.EW, pady=4)
        self._add_i18n(ttk.Label(g, text=""), "video_stream").grid(row=2, column=0, sticky=tk.W, pady=4)
        self._video_stream_cb = ttk.Combobox(g, textvariable=self._video_stream_idx, state="readonly", width=24)
        self._video_stream_cb.grid(row=2, column=1, columnspan=3, sticky=tk.EW, pady=4)
        self._add_i18n(ttk.Label(g, text=""), "audio_stream").grid(row=3, column=0, sticky=tk.W, pady=4)
        self._audio_stream_cb = ttk.Combobox(g, textvariable=self._audio_stream_idx, state="readonly", width=24)
        self._audio_stream_cb.grid(row=3, column=1, columnspan=3, sticky=tk.EW, pady=4)
        self._add_i18n(ttk.Label(g, text=""), "video_codec").grid(row=4, column=0, sticky=tk.W, pady=4)
        ttk.Entry(g, textvariable=self._video_codec, width=12).grid(row=4, column=1, sticky=tk.W, pady=4)
        self._add_i18n(ttk.Label(g, text=""), "audio_codec").grid(row=4, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Entry(g, textvariable=self._audio_codec, width=12).grid(row=4, column=3, sticky=tk.W, pady=4)
        self._add_i18n(ttk.Label(g, text=""), "video_bitrate").grid(row=5, column=0, sticky=tk.W, pady=4)
        ttk.Entry(g, textvariable=self._video_bitrate, width=12).grid(row=5, column=1, sticky=tk.W, pady=4)
        self._add_i18n(
            ttk.Checkbutton(g, text="", variable=self._copy_streams),
            "copy_streams",
        ).grid(row=6, column=0, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ttk.Checkbutton(g, text="", variable=self._overwrite),
            "overwrite",
        ).grid(row=6, column=2, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ttk.Checkbutton(g, text="", variable=self._hw_encode),
            "hw_encode",
        ).grid(row=7, column=0, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ttk.Checkbutton(g, text="", variable=self._prefer_hevc),
            "prefer_hevc",
        ).grid(row=7, column=2, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ttk.Checkbutton(g, text="", variable=self._verify),
            "verify",
        ).grid(row=8, column=0, columnspan=2, sticky=tk.W)
        self._add_i18n(
            ttk.Checkbutton(g, text="", variable=self._show_cmd),
            "show_cmd",
        ).grid(row=8, column=2, columnspan=2, sticky=tk.W)
        g.columnconfigure(3, weight=1)

        out_row = ttk.Frame(settings)
        out_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._add_i18n(ttk.Label(out_row, text=""), "output").pack(side=tk.LEFT)
        ttk.Entry(out_row, textvariable=self._output_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(out_row, text="...", width=4, command=self._browse_output).pack(side=tk.LEFT)

    def _build_audio_tab(self) -> None:
        p = self._tab_audio
        f = ttk.LabelFrame(p, text=self._t("tab_audio"))
        f.pack(fill=tk.X, padx=8, pady=8)
        self._add_i18n(f, "tab_audio", "label")
        self._add_i18n(
            ttk.Checkbutton(f, text="", variable=self._extract_audio),
            "extract_audio",
        ).pack(anchor=tk.W, padx=8, pady=4)
        row = ttk.Frame(f)
        row.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row, text=""), "audio_format").pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=self._audio_format, values=list_audio_formats(), state="readonly", width=8).pack(
            side=tk.LEFT, padx=8
        )
        self._add_i18n(
            ttk.Checkbutton(f, text="", variable=self._normalize),
            "normalize",
        ).pack(anchor=tk.W, padx=8, pady=4)
        row2 = ttk.Frame(f)
        row2.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row2, text=""), "add_audio").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self._external_audio).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row2, text="...", width=4, command=self._browse_external_audio).pack(side=tk.LEFT)
        row3 = ttk.Frame(f)
        row3.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row3, text=""), "embed_sub").pack(side=tk.LEFT)
        ttk.Entry(row3, textvariable=self._subtitle_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row3, text="...", width=4, command=self._browse_subtitle).pack(side=tk.LEFT)
        self._add_i18n(
            ttk.Checkbutton(f, text="", variable=self._extract_sub),
            "extract_sub",
        ).pack(anchor=tk.W, padx=8, pady=4)
        row4 = ttk.Frame(f)
        row4.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row4, text=""), "subtitle_stream").pack(side=tk.LEFT)
        self._subtitle_stream_cb = ttk.Combobox(row4, textvariable=self._subtitle_stream_idx, state="readonly", width=28)
        self._subtitle_stream_cb.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        self._add_i18n(
            ttk.Checkbutton(f, text="", variable=self._subtitle_burn_in),
            "subtitle_burn_in",
        ).pack(anchor=tk.W, padx=8, pady=4)
        row5 = ttk.Frame(f)
        row5.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row5, text=""), "extract_sub_format").pack(side=tk.LEFT)
        ttk.Combobox(
            row5,
            textvariable=self._extract_sub_format,
            values=["srt", "ass", "vtt"],
            state="readonly",
            width=8,
        ).pack(side=tk.LEFT, padx=8)
        self._add_i18n(
            ttk.Checkbutton(f, text="", variable=self._replace_audio),
            "replace_audio",
        ).pack(anchor=tk.W, padx=8, pady=4)
        row6 = ttk.Frame(f)
        row6.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row6, text=""), "audio_delay").pack(side=tk.LEFT)
        ttk.Entry(row6, textvariable=self._audio_delay_ms, width=10).pack(side=tk.LEFT, padx=8)
        row7 = ttk.Frame(f)
        row7.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row7, text=""), "extra_audio_tracks").pack(side=tk.LEFT)
        ttk.Entry(row7, textvariable=self._extra_audio_tracks).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

    def _build_trim_tab(self) -> None:
        p = self._tab_trim
        f = ttk.LabelFrame(p, text=self._t("tab_trim"))
        f.pack(fill=tk.X, padx=8, pady=8)
        self._add_i18n(f, "tab_trim", "label")
        r1 = ttk.Frame(f)
        r1.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(r1, text="", width=18), "trim_start").pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self._trim_start, width=12).pack(side=tk.LEFT, padx=8)
        self._add_i18n(ttk.Label(r1, text=""), "trim_end").pack(side=tk.LEFT, padx=(16, 0))
        ttk.Entry(r1, textvariable=self._trim_end, width=12).pack(side=tk.LEFT, padx=8)
        self._add_i18n(ttk.Label(f, text=""), "preset_speed").pack(anchor=tk.W, padx=8, pady=(8, 0))
        ttk.Combobox(
            f,
            textvariable=self._preset,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
            state="readonly",
            width=16,
        ).pack(anchor=tk.W, padx=8, pady=4)
        self._add_i18n(
            ttk.Checkbutton(f, text="", variable=self._gif_mode),
            "gif_mode",
        ).pack(anchor=tk.W, padx=8, pady=4)
        meta = ttk.LabelFrame(p, text=self._t("metadata"))
        meta.pack(fill=tk.X, padx=8, pady=8)
        self._add_i18n(meta, "metadata", "label")
        r2 = ttk.Frame(meta)
        r2.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(r2, text="", width=12), "metadata_title").pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self._meta_title).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        r3 = ttk.Frame(meta)
        r3.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(r3, text="", width=12), "metadata_author").pack(side=tk.LEFT)
        ttk.Entry(r3, textvariable=self._meta_author).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        r4 = ttk.Frame(meta)
        r4.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(r4, text="", width=12), "metadata_date").pack(side=tk.LEFT)
        ttk.Entry(r4, textvariable=self._metadata_date).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self._add_i18n(
            ttk.Checkbutton(meta, text="", variable=self._strip_meta),
            "strip_meta",
        ).pack(anchor=tk.W, padx=8, pady=4)
        r5 = ttk.Frame(meta)
        r5.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(r5, text=""), "cover_art").pack(side=tk.LEFT)
        ttk.Entry(r5, textvariable=self._cover_art_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self._add_i18n(ttk.Button(r5, text="", command=self._browse_cover_art), "browse").pack(side=tk.LEFT)
        filt = ttk.LabelFrame(p, text=self._t("tab_advanced"))
        filt.pack(fill=tk.X, padx=8, pady=8)
        self._add_i18n(
            ttk.Checkbutton(filt, text="", variable=self._preserve_chapters, command=self._save_settings),
            "preserve_chapters",
        ).pack(anchor=tk.W, padx=8, pady=4)
        self._add_i18n(
            ttk.Checkbutton(filt, text="", variable=self._deinterlace),
            "deinterlace",
        ).pack(anchor=tk.W, padx=8, pady=4)
        self._add_i18n(
            ttk.Checkbutton(filt, text="", variable=self._denoise),
            "denoise",
        ).pack(anchor=tk.W, padx=8, pady=4)

    def _build_advanced_tab(self) -> None:
        p = self._tab_advanced
        merge_frame = ttk.LabelFrame(p, text=self._t("merge_files"))
        merge_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._add_i18n(merge_frame, "merge_files", "label")
        merge_body = ttk.Frame(merge_frame)
        merge_body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._merge_listbox = tk.Listbox(merge_body, height=8)
        self._merge_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        merge_sb = ttk.Scrollbar(merge_body, orient=tk.VERTICAL, command=self._merge_listbox.yview)
        self._merge_listbox.configure(yscrollcommand=merge_sb.set)
        merge_sb.pack(side=tk.LEFT, fill=tk.Y)
        merge_btns = ttk.Frame(merge_body)
        merge_btns.pack(side=tk.LEFT, padx=8)
        self._add_i18n(ttk.Button(merge_btns, text="", command=self._merge_add_files), "add_files").pack(
            fill=tk.X, pady=2
        )
        self._add_i18n(ttk.Button(merge_btns, text="", command=self._merge_clear), "clear_queue").pack(
            fill=tk.X, pady=2
        )

        opts = ttk.LabelFrame(p, text=self._t("tab_advanced"))
        opts.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._add_i18n(opts, "tab_advanced", "label")
        og = ttk.Frame(opts)
        og.pack(fill=tk.X, padx=8, pady=8)
        self._add_i18n(ttk.Label(og, text=""), "crop").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(og, textvariable=self._crop, width=28).grid(row=0, column=1, sticky=tk.W, pady=2)
        self._add_i18n(ttk.Label(og, text=""), "rotation").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=2)
        ttk.Combobox(og, textvariable=self._rotation, values=["0", "90", "180", "270"], state="readonly", width=8).grid(
            row=1, column=1, sticky=tk.W, pady=2
        )
        self._add_i18n(ttk.Label(og, text=""), "fps").grid(row=2, column=0, sticky=tk.W, padx=(0, 8), pady=2)
        ttk.Entry(og, textvariable=self._fps, width=12).grid(row=2, column=1, sticky=tk.W, pady=2)
        wm_row = ttk.Frame(opts)
        wm_row.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(wm_row, text=""), "watermark").pack(side=tk.LEFT)
        ttk.Entry(wm_row, textvariable=self._watermark_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self._add_i18n(ttk.Button(wm_row, text="", command=self._browse_watermark), "browse").pack(side=tk.LEFT)
        wm_pos_row = ttk.Frame(opts)
        wm_pos_row.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(wm_pos_row, text=""), "watermark_position").pack(side=tk.LEFT)
        ttk.Entry(wm_pos_row, textvariable=self._watermark_position, width=12).pack(side=tk.LEFT, padx=8)
        self._add_i18n(
            ttk.Checkbutton(opts, text="", variable=self._two_pass),
            "two_pass",
        ).pack(anchor=tk.W, padx=8, pady=(0, 8))

    def _build_batch_tab(self) -> None:
        p = self._tab_batch
        f = ttk.LabelFrame(p, text=self._t("batch_queue"))
        f.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._add_i18n(f, "batch_queue", "label")
        self._batch_list = tk.Listbox(f, height=12)
        self._batch_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self._batch_list.yview)
        self._batch_list.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.LEFT, fill=tk.Y, pady=8)
        btns = ttk.Frame(f)
        btns.pack(side=tk.LEFT, padx=8, pady=8)
        self._add_i18n(ttk.Button(btns, text="", command=self._batch_add_files), "add_files").pack(fill=tk.X, pady=2)
        self._add_i18n(ttk.Button(btns, text="", command=self._batch_add_folder), "browse_folder").pack(
            fill=tk.X, pady=2
        )
        self._add_i18n(ttk.Button(btns, text="", command=self._batch_clear), "clear_queue").pack(fill=tk.X, pady=2)
        self._add_i18n(ttk.Button(btns, text="", command=self._start_batch), "convert").pack(fill=tk.X, pady=(12, 2))
        self._add_i18n(ttk.Button(btns, text="", command=self._pause_batch), "pause_batch").pack(fill=tk.X, pady=2)
        self._add_i18n(ttk.Button(btns, text="", command=self._resume_batch), "resume_batch").pack(fill=tk.X, pady=2)
        opts_row = ttk.Frame(p)
        opts_row.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(
            ttk.Checkbutton(opts_row, text="", variable=self._recursive_batch, command=self._save_settings),
            "recursive_batch",
        ).pack(side=tk.LEFT)
        self._add_i18n(ttk.Label(opts_row, text=""), "parallel_batch").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Spinbox(
            opts_row,
            from_=1,
            to=4,
            textvariable=self._parallel_batch,
            width=4,
            command=self._save_settings,
        ).pack(side=tk.LEFT)
        row = ttk.Frame(p)
        row.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row, text=""), "output_dir").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self._batch_output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row, text="...", width=4, command=self._browse_batch_dir).pack(side=tk.LEFT)

    def _build_watch_tab(self) -> None:
        p = self._tab_watch
        f = ttk.LabelFrame(p, text=self._t("tab_watch"))
        f.pack(fill=tk.X, padx=8, pady=8)
        self._add_i18n(f, "tab_watch", "label")
        row = ttk.Frame(f)
        row.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(ttk.Label(row, text=""), "watch_folder").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self._watch_folder).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self._add_i18n(ttk.Button(row, text="", command=self._browse_watch_folder), "browse_folder").pack(side=tk.LEFT)
        row2 = ttk.Frame(f)
        row2.pack(fill=tk.X, padx=8, pady=4)
        self._add_i18n(
            ttk.Checkbutton(row2, text="", variable=self._watch_enabled, command=self._save_settings),
            "watch_enable",
        ).pack(side=tk.LEFT)
        self._add_i18n(ttk.Label(row2, text=""), "watch_interval").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Spinbox(row2, from_=2, to=120, textvariable=self._watch_interval, width=5).pack(side=tk.LEFT)
        row3 = ttk.Frame(f)
        row3.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(row3, text="Start", command=self._watch_start).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row3, text="Stop", command=self._watch_stop).pack(side=tk.LEFT)

    def _build_history_tab(self) -> None:
        p = self._tab_history
        cols = ("time", "input", "output")
        self._history_tree = ttk.Treeview(p, columns=cols, show="headings", height=16)
        self._history_tree.heading("time", text=self._t("history_col_time"))
        self._history_tree.heading("input", text=self._t("history_col_in"))
        self._history_tree.heading("output", text=self._t("history_col_out"))
        self._history_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._history_tree.bind("<Double-1>", self._history_double_click)
        hist_btns = ttk.Frame(p)
        hist_btns.pack(pady=4)
        self._add_i18n(ttk.Button(hist_btns, text="", command=self._history_load), "history_load").pack(
            side=tk.LEFT, padx=4
        )
        self._add_i18n(ttk.Button(hist_btns, text="", command=self._history_rerun), "history_rerun").pack(
            side=tk.LEFT, padx=4
        )
        self._add_i18n(ttk.Button(hist_btns, text="", command=self._refresh_history), "refresh").pack(side=tk.LEFT, padx=4)
        self._refresh_history()

    def _apply_theme(self) -> None:
        style = ttk.Style(self)
        if self._dark.get():
            bg, fg = "#1e1e1e", "#e0e0e0"
            self.configure(bg=bg)
            style.theme_use("clam")
            style.configure(".", background=bg, foreground=fg, fieldbackground="#2d2d2d")
            style.configure("TLabel", background=bg, foreground=fg)
            style.configure("TFrame", background=bg)
            style.configure("TLabelframe", background=bg, foreground=fg)
            style.configure("TLabelframe.Label", background=bg, foreground=fg)
            style.configure("Treeview", background="#2d2d2d", foreground=fg, fieldbackground="#2d2d2d")
            style.configure("Treeview.Heading", background=bg, foreground=fg)
            style.map("Treeview", background=[("selected", "#404040")])
            self._info_text.configure(bg="#2d2d2d", fg=fg, insertbackground=fg)
            self._batch_list.configure(bg="#2d2d2d", fg=fg)
            self._merge_listbox.configure(bg="#2d2d2d", fg=fg)
        else:
            style.theme_use("vista" if "vista" in style.theme_names() else "default")
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
            style.configure("Treeview.Heading", background="SystemButtonFace", foreground="black")
            self._info_text.configure(bg="white", fg="black", insertbackground="black")
            self._batch_list.configure(bg="white", fg="black")
            self._merge_listbox.configure(bg="white", fg="black")

    def _on_dark_toggle(self) -> None:
        self._apply_theme()
        self._save_settings()

    def _save_settings(self) -> None:
        save_settings(
            AppSettings(
                lang=self._lang.get(),
                dark=self._dark.get(),
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

    def _set_stream_by_index(self, var: tk.StringVar, cb: ttk.Combobox, index: int | None) -> None:
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
        self._info_text.configure(state=tk.NORMAL)
        self._info_text.delete("1.0", tk.END)
        self._info_text.insert(tk.END, text)
        self._info_text.configure(state=tk.DISABLED)

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
            self._preview_image = tk.PhotoImage(file=str(preview))
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
        self._convert_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self._cancel_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)

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
        self._progress["value"] = 0
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
        self._progress["value"] = percent
        self._status.set(message)

    def _on_convert_done(self, output_path: Path, cmd: list[str], cmp_text: str, options: ConvertOptions) -> None:
        self._progress["value"] = 100
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
        self._progress["value"] = 100
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
        self._convert_btn.configure(state=tk.DISABLED)
        self._progress["value"] = 0

        def worker() -> None:
            try:
                def on_progress(done: int, total: int) -> None:
                    pct = int(done * 100 / total) if total else 0
                    self.after(
                        0,
                        lambda p=pct: (
                            self._progress.configure(value=p),
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
        self._progress["value"] = 100
        self.update_idletasks()
        self.after(300, self.destroy)

    def _fail_update_install(self, message: str) -> None:
        self._update_in_progress = False
        self._convert_btn.configure(state=tk.NORMAL)
        self._progress["value"] = 0
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
