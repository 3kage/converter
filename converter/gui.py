from __future__ import annotations

import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .batch import build_batch_items, run_batch
from .compare import compare_conversion
from .convert import ConvertOptions, build_ffmpeg_args, convert_video, list_audio_formats, list_supported_formats
from .dnd import bind_file_drop
from .ffmpeg_utils import FFmpegNotFoundError
from .history import append_history, load_history, log_error, log_path
from .i18n import I18n
from .platform_utils import open_path
from .presets import RESOLUTIONS, list_quality_presets
from .preview import generate_preview
from .probe import analyze_file, render_media_info
from .updater import check_for_updates

VIDEO_EXTS = {".mov", ".mp4", ".mkv", ".avi", ".webm", ".wmv", ".flv", ".m4v", ".mpeg", ".mpg", ".ts", ".ogv"}


class VideoConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.i18n = I18n("uk")
        self.title(f"{self.i18n.t('app_title')} v{__version__}")
        self.geometry("980x820")
        self.minsize(900, 720)

        self._dark = tk.BooleanVar(value=False)
        self._lang = tk.StringVar(value="uk")
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
        self._verify = tk.BooleanVar(value=True)
        self._show_cmd = tk.BooleanVar(value=False)
        self._extract_audio = tk.BooleanVar(value=False)
        self._extract_sub = tk.BooleanVar(value=False)
        self._normalize = tk.BooleanVar(value=False)
        self._gif_mode = tk.BooleanVar(value=False)
        self._strip_meta = tk.BooleanVar(value=False)
        self._audio_format = tk.StringVar(value="mp3")
        self._external_audio = tk.StringVar()
        self._subtitle_path = tk.StringVar()
        self._trim_start = tk.StringVar()
        self._trim_end = tk.StringVar()
        self._meta_title = tk.StringVar()
        self._meta_author = tk.StringVar()
        self._batch_output_dir = tk.StringVar()
        self._status = tk.StringVar(value=self.i18n.t("ready"))
        self._cmd_text = tk.StringVar(value="")
        self._comparison = tk.StringVar(value="")

        self._cancel_requested = False
        self._worker: threading.Thread | None = None
        self._progress_start = 0.0
        self._preview_image: tk.PhotoImage | None = None
        self._batch_files: list[Path] = []
        self._labels: dict[str, ttk.Label | ttk.Button | ttk.Checkbutton | ttk.LabelFrame] = {}

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._check_ffmpeg)
        bind_file_drop(self, self._on_drop)

    def _t(self, key: str) -> str:
        return self.i18n.t(key)

    def _build_ui(self) -> None:
        self._build_menu()
        pad = {"padx": 10, "pady": 4}
        top = ttk.Frame(self)
        top.pack(fill=tk.X, **pad)
        ttk.Checkbutton(top, text=self._t("dark_theme"), variable=self._dark, command=self._apply_theme).pack(side=tk.LEFT)
        ttk.Label(top, text=self._t("language")).pack(side=tk.LEFT, padx=(16, 4))
        lang_cb = ttk.Combobox(top, textvariable=self._lang, values=["uk", "en"], width=5, state="readonly")
        lang_cb.pack(side=tk.LEFT)
        lang_cb.bind("<<ComboboxSelected>>", lambda _e: self._change_language())

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self._tab_convert = ttk.Frame(self._notebook)
        self._tab_audio = ttk.Frame(self._notebook)
        self._tab_trim = ttk.Frame(self._notebook)
        self._tab_batch = ttk.Frame(self._notebook)
        self._tab_history = ttk.Frame(self._notebook)
        for tab, name in [
            (self._tab_convert, "tab_convert"),
            (self._tab_audio, "tab_audio"),
            (self._tab_trim, "tab_trim"),
            (self._tab_batch, "tab_batch"),
            (self._tab_history, "tab_history"),
        ]:
            self._notebook.add(tab, text=self._t(name))

        self._build_convert_tab()
        self._build_audio_tab()
        self._build_trim_tab()
        self._build_batch_tab()
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
        self._convert_btn = ttk.Button(btns, text=self._t("convert"), command=self._start_convert)
        self._convert_btn.pack(side=tk.LEFT)
        self._cancel_btn = ttk.Button(btns, text=self._t("cancel"), command=self._cancel_convert, state=tk.DISABLED)
        self._cancel_btn.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text=self._t("open_folder"), command=self._open_output_folder).pack(side=tk.RIGHT)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label=self._t("check_updates"), command=self._check_updates)
        help_menu.add_command(label=f"Log: {log_path()}", command=lambda: open_path(log_path().parent))
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

    def _build_convert_tab(self) -> None:
        p = self._tab_convert
        inp = ttk.LabelFrame(p, text=self._t("input_file"))
        inp.pack(fill=tk.X, padx=8, pady=6)
        row = ttk.Frame(inp)
        row.pack(fill=tk.X, padx=8, pady=6)
        ttk.Entry(row, textvariable=self._input_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(row, text=self._t("browse"), command=self._browse_input).pack(side=tk.LEFT)
        ttk.Button(row, text=self._t("analyze"), command=self._analyze).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(inp, text=self._t("drop_hint"), foreground="gray").pack(anchor=tk.W, padx=8, pady=(0, 6))

        body = ttk.Frame(p)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        prev_frame = ttk.LabelFrame(body, text=self._t("preview"))
        prev_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self._preview_label = ttk.Label(prev_frame, text="—", width=28)
        self._preview_label.pack(padx=8, pady=8)

        info_frame = ttk.LabelFrame(body, text=self._t("file_info"))
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._info_text = tk.Text(info_frame, wrap=tk.WORD, height=14, font=("Consolas", 9))
        scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self._info_text.yview)
        self._info_text.configure(yscrollcommand=scroll.set)
        self._info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)
        self._info_text.configure(state=tk.DISABLED)

        settings = ttk.LabelFrame(p, text=self._t("settings"))
        settings.pack(fill=tk.X, padx=8, pady=6)
        g = ttk.Frame(settings)
        g.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(g, text=self._t("format")).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Combobox(g, textvariable=self._format, values=list_supported_formats(), state="readonly", width=8).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(g, text=self._t("quality_preset")).grid(row=0, column=2, sticky=tk.W, padx=(16, 8))
        ttk.Combobox(g, textvariable=self._quality_preset, values=list_quality_presets(), state="readonly", width=14).grid(row=0, column=3, sticky=tk.W)
        ttk.Label(g, text=self._t("resolution")).grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Combobox(g, textvariable=self._resolution, values=list(RESOLUTIONS.keys()), state="readonly", width=10).grid(row=1, column=1, sticky=tk.W, pady=4)
        ttk.Label(g, text=self._t("crf")).grid(row=1, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Scale(g, from_=0, to=51, orient=tk.HORIZONTAL, variable=self._crf).grid(row=1, column=3, sticky=tk.EW, pady=4)
        ttk.Checkbutton(g, text=self._t("copy_streams"), variable=self._copy_streams).grid(row=2, column=0, columnspan=2, sticky=tk.W)
        ttk.Checkbutton(g, text=self._t("hw_encode"), variable=self._hw_encode).grid(row=2, column=2, columnspan=2, sticky=tk.W)
        ttk.Checkbutton(g, text=self._t("verify"), variable=self._verify).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        ttk.Checkbutton(g, text=self._t("show_cmd"), variable=self._show_cmd).grid(row=3, column=2, columnspan=2, sticky=tk.W)
        g.columnconfigure(3, weight=1)

        out_row = ttk.Frame(settings)
        out_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(out_row, text=self._t("output")).pack(side=tk.LEFT)
        ttk.Entry(out_row, textvariable=self._output_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(out_row, text="...", width=4, command=self._browse_output).pack(side=tk.LEFT)

    def _build_audio_tab(self) -> None:
        p = self._tab_audio
        f = ttk.LabelFrame(p, text=self._t("tab_audio"))
        f.pack(fill=tk.X, padx=8, pady=8)
        ttk.Checkbutton(f, text=self._t("extract_audio"), variable=self._extract_audio).pack(anchor=tk.W, padx=8, pady=4)
        row = ttk.Frame(f)
        row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(row, text=self._t("audio_format")).pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=self._audio_format, values=list_audio_formats(), state="readonly", width=8).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(f, text=self._t("normalize"), variable=self._normalize).pack(anchor=tk.W, padx=8, pady=4)
        row2 = ttk.Frame(f)
        row2.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(row2, text=self._t("add_audio")).pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self._external_audio).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row2, text="...", width=4, command=self._browse_external_audio).pack(side=tk.LEFT)
        row3 = ttk.Frame(f)
        row3.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(row3, text=self._t("embed_sub")).pack(side=tk.LEFT)
        ttk.Entry(row3, textvariable=self._subtitle_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row3, text="...", width=4, command=self._browse_subtitle).pack(side=tk.LEFT)
        ttk.Checkbutton(f, text=self._t("extract_sub"), variable=self._extract_sub).pack(anchor=tk.W, padx=8, pady=4)

    def _build_trim_tab(self) -> None:
        p = self._tab_trim
        f = ttk.LabelFrame(p, text=self._t("tab_trim"))
        f.pack(fill=tk.X, padx=8, pady=8)
        r1 = ttk.Frame(f)
        r1.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(r1, text=self._t("trim_start"), width=18).pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self._trim_start, width=12).pack(side=tk.LEFT, padx=8)
        ttk.Label(r1, text=self._t("trim_end")).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Entry(r1, textvariable=self._trim_end, width=12).pack(side=tk.LEFT, padx=8)
        ttk.Label(f, text=self._t("preset_speed")).pack(anchor=tk.W, padx=8, pady=(8, 0))
        ttk.Combobox(
            f,
            textvariable=self._preset,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
            state="readonly",
            width=16,
        ).pack(anchor=tk.W, padx=8, pady=4)
        ttk.Checkbutton(f, text=self._t("gif_mode"), variable=self._gif_mode).pack(anchor=tk.W, padx=8, pady=4)
        meta = ttk.LabelFrame(p, text="Metadata")
        meta.pack(fill=tk.X, padx=8, pady=8)
        r2 = ttk.Frame(meta)
        r2.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(r2, text=self._t("metadata_title"), width=12).pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self._meta_title).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        r3 = ttk.Frame(meta)
        r3.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(r3, text=self._t("metadata_author"), width=12).pack(side=tk.LEFT)
        ttk.Entry(r3, textvariable=self._meta_author).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Checkbutton(meta, text=self._t("strip_meta"), variable=self._strip_meta).pack(anchor=tk.W, padx=8, pady=4)

    def _build_batch_tab(self) -> None:
        p = self._tab_batch
        f = ttk.LabelFrame(p, text=self._t("batch_queue"))
        f.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._batch_list = tk.Listbox(f, height=12)
        self._batch_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self._batch_list.yview)
        self._batch_list.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.LEFT, fill=tk.Y, pady=8)
        btns = ttk.Frame(f)
        btns.pack(side=tk.LEFT, padx=8, pady=8)
        ttk.Button(btns, text=self._t("add_files"), command=self._batch_add_files).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text=self._t("browse_folder"), command=self._batch_add_folder).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text=self._t("clear_queue"), command=self._batch_clear).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text=self._t("convert"), command=self._start_batch).pack(fill=tk.X, pady=(12, 2))
        row = ttk.Frame(p)
        row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(row, text="Output dir (optional):").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self._batch_output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row, text="...", width=4, command=self._browse_batch_dir).pack(side=tk.LEFT)

    def _build_history_tab(self) -> None:
        p = self._tab_history
        cols = ("time", "input", "output")
        self._history_tree = ttk.Treeview(p, columns=cols, show="headings", height=16)
        self._history_tree.heading("time", text=self._t("history_col_time"))
        self._history_tree.heading("input", text=self._t("history_col_in"))
        self._history_tree.heading("output", text=self._t("history_col_out"))
        self._history_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Button(p, text="Refresh", command=self._refresh_history).pack(pady=4)
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
            self._info_text.configure(bg="#2d2d2d", fg=fg, insertbackground=fg)
            self._batch_list.configure(bg="#2d2d2d", fg=fg)
        else:
            style.theme_use("vista" if "vista" in style.theme_names() else "default")
            self._info_text.configure(bg="white", fg="black", insertbackground="black")
            self._batch_list.configure(bg="white", fg="black")

    def _change_language(self, _event=None) -> None:
        self.i18n.set_lang(self._lang.get())
        self.title(f"{self.i18n.t('app_title')} v{__version__}")
        for i, key in enumerate(["tab_convert", "tab_audio", "tab_trim", "tab_batch", "tab_history"]):
            self._notebook.tab(i, text=self.i18n.t(key))
        self._convert_btn.configure(text=self.i18n.t("convert"))
        self._cancel_btn.configure(text=self.i18n.t("cancel"))

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

    def _browse_batch_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self._batch_output_dir.set(path)

    def _suggest_output_path(self, input_path: Path) -> None:
        fmt = self._audio_format.get() if self._extract_audio.get() else self._format.get().lstrip(".")
        if self._gif_mode.get():
            fmt = "gif"
        self._output_path.set(str(input_path.with_name(f"{input_path.stem}_converted.{fmt}")))

    def _analyze(self) -> None:
        text = self._input_path.get().strip()
        if not text:
            return
        path = Path(text)
        try:
            info = analyze_file(path)
            self._set_info_text(render_media_info(info))
            self._status.set(f"{path.name}")
            preview = generate_preview(path)
            if preview and preview.is_file():
                self._preview_image = tk.PhotoImage(file=str(preview))
                self._preview_label.configure(image=self._preview_image, text="")
            if not self._output_path.get().strip():
                self._suggest_output_path(path)
        except Exception as exc:
            messagebox.showerror(self._t("error"), str(exc))

    def _build_options(self, input_path: Path, output_path: Path | None = None) -> ConvertOptions:
        scale = RESOLUTIONS.get(self._resolution.get())
        fmt = self._audio_format.get() if self._extract_audio.get() else self._format.get()
        if self._gif_mode.get():
            fmt = "gif"
        out = Path(output_path) if output_path else (Path(self._output_path.get()) if self._output_path.get().strip() else None)
        ext_audio = self._external_audio.get().strip()
        sub = self._subtitle_path.get().strip()
        return ConvertOptions(
            input_path=input_path,
            output_path=out,
            output_format=fmt,
            crf=None if self._copy_streams.get() else int(self._crf.get()),
            preset=self._preset.get(),
            copy_streams=self._copy_streams.get(),
            overwrite=self._overwrite.get(),
            quality_preset_id=self._quality_preset.get(),
            scale=scale,
            start_time=self._trim_start.get().strip() or None,
            end_time=self._trim_end.get().strip() or None,
            hardware_encode=self._hw_encode.get(),
            extract_audio=self._extract_audio.get(),
            extract_subtitles=self._extract_sub.get(),
            external_audio_path=Path(ext_audio) if ext_audio else None,
            subtitle_path=Path(sub) if sub else None,
            normalize_audio=self._normalize.get(),
            gif_mode=self._gif_mode.get(),
            metadata_title=self._meta_title.get().strip() or None,
            metadata_author=self._meta_author.get().strip() or None,
            strip_metadata=self._strip_meta.get(),
            verify_output=self._verify.get(),
        )

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
                cmd = build_ffmpeg_args(options)
                from .ffmpeg_utils import ensure_ffmpeg

                ffmpeg, _ = ensure_ffmpeg()
                self._cmd_text.set(f"{ffmpeg} {' '.join(cmd)}")
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
            from .ffmpeg_utils import ensure_ffmpeg

            ffmpeg, _ = ensure_ffmpeg()
            self._cmd_text.set(f"{ffmpeg} {' '.join(cmd)}")
        append_history({"input": str(options.input_path), "output": str(output_path), "mode": "single"})
        self._refresh_history()
        self._set_busy(False)
        messagebox.showinfo(self._t("done"), str(output_path))

    def _on_convert_failed(self, error: str) -> None:
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
        root = Path(folder)
        for ext in ("mov", "mp4", "mkv", "avi", "webm", "wmv", "flv", "m4v", "mpeg", "mpg", "ts", "ogv"):
            for path in root.glob(f"*.{ext}"):
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
        self._cancel_requested = False
        self._progress_start = time.time()
        self._set_busy(True)
        self._worker = threading.Thread(target=self._batch_worker, args=(items, base), daemon=True)
        self._worker.start()

    def _batch_worker(self, items, base: ConvertOptions) -> None:
        try:
            results = run_batch(items, base, on_progress=self._on_progress, cancel_check=lambda: self._cancel_requested)
            self.after(0, lambda: self._on_batch_done(results))
        except Exception as exc:
            log_error(str(exc))
            self.after(0, lambda: self._on_convert_failed(str(exc)))

    def _on_batch_done(self, results) -> None:
        self._progress["value"] = 100
        self._status.set(f"{self._t('done')}: {len(results)} files")
        for output_path, _ in results:
            append_history({"input": "batch", "output": str(output_path), "mode": "batch"})
        self._refresh_history()
        self._set_busy(False)
        messagebox.showinfo(self._t("done"), f"{len(results)} files")

    def _refresh_history(self) -> None:
        for item in self._history_tree.get_children():
            self._history_tree.delete(item)
        for row in reversed(load_history()):
            self._history_tree.insert("", tk.END, values=(row.get("time", ""), row.get("input", ""), row.get("output", "")))

    def _open_output_folder(self) -> None:
        text = self._output_path.get().strip()
        if not text:
            return
        folder = Path(text).parent
        if folder.exists():
            open_path(folder)

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
                msg = f"Latest: {latest}\n{url}" if available else f"You have the latest ({__version__})."
                self.after(0, lambda: messagebox.showinfo(self._t("check_updates"), msg))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror(self._t("error"), str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self) -> None:
        if self._worker and self._worker.is_alive():
            if not messagebox.askyesno("Exit", "Conversion in progress. Exit?"):
                return
            self._cancel_requested = True
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
