from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .convert import ConvertOptions, convert_video, list_supported_formats
from .ffmpeg_utils import FFmpegNotFoundError
from .platform_utils import open_path
from .probe import analyze_file, render_media_info


class VideoConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Video Converter v{__version__}")
        self.geometry("860x720")
        self.minsize(760, 640)

        self._input_path = tk.StringVar()
        self._output_path = tk.StringVar()
        self._format = tk.StringVar(value="mp4")
        self._crf = tk.IntVar(value=23)
        self._preset = tk.StringVar(value="medium")
        self._copy_streams = tk.BooleanVar(value=False)
        self._overwrite = tk.BooleanVar(value=True)
        self._status = tk.StringVar(value="Оберіть відеофайл для аналізу та конвертації")
        self._cancel_requested = False
        self._worker: threading.Thread | None = None
        self._duration_sec: float | None = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._check_ffmpeg)

    def _check_ffmpeg(self) -> None:
        try:
            from .ffmpeg_utils import ensure_ffmpeg

            ensure_ffmpeg()
        except FFmpegNotFoundError as exc:
            messagebox.showwarning(
                "FFmpeg не знайдено",
                f"{exc}\n\nНа macOS встановіть: brew install ffmpeg",
            )

    def _build_ui(self) -> None:
        padding = {"padx": 12, "pady": 6}
        root = ttk.Frame(self)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            root,
            text="Конвертер відео",
            font=("Segoe UI", 16, "bold"),
        )
        header.pack(anchor=tk.W, **padding)

        input_frame = ttk.LabelFrame(root, text="Вхідний файл")
        input_frame.pack(fill=tk.X, **padding)

        input_row = ttk.Frame(input_frame)
        input_row.pack(fill=tk.X, padx=8, pady=8)
        ttk.Entry(input_row, textvariable=self._input_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(input_row, text="Обрати...", command=self._browse_input).pack(side=tk.LEFT)
        ttk.Button(input_row, text="Аналіз", command=self._analyze).pack(side=tk.LEFT, padx=(8, 0))

        info_frame = ttk.LabelFrame(root, text="Інформація про файл")
        info_frame.pack(fill=tk.BOTH, expand=True, **padding)
        self._info_text = tk.Text(info_frame, wrap=tk.WORD, height=16, font=("Consolas", 10))
        info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self._info_text.yview)
        self._info_text.configure(yscrollcommand=info_scroll.set)
        self._info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)
        self._info_text.configure(state=tk.DISABLED)

        settings = ttk.LabelFrame(root, text="Налаштування конвертації")
        settings.pack(fill=tk.X, **padding)

        grid = ttk.Frame(settings)
        grid.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(grid, text="Формат:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Combobox(
            grid,
            textvariable=self._format,
            values=list_supported_formats(),
            state="readonly",
            width=10,
        ).grid(row=0, column=1, sticky=tk.W, pady=4)

        ttk.Label(grid, text="Preset:").grid(row=0, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Combobox(
            grid,
            textvariable=self._preset,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
            state="readonly",
            width=12,
        ).grid(row=0, column=3, sticky=tk.W, pady=4)

        ttk.Label(grid, text="CRF (якість):").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        crf_scale = ttk.Scale(
            grid,
            from_=0,
            to=51,
            orient=tk.HORIZONTAL,
            variable=self._crf,
            command=self._update_crf_label,
        )
        crf_scale.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=4)
        self._crf_label = ttk.Label(grid, text="23")
        self._crf_label.grid(row=1, column=3, sticky=tk.W, pady=4)

        ttk.Checkbutton(grid, text="Копіювати потоки (без перекодування)", variable=self._copy_streams).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=4
        )
        ttk.Checkbutton(grid, text="Перезаписати існуючий файл", variable=self._overwrite).grid(
            row=2, column=2, columnspan=2, sticky=tk.W, pady=4
        )

        output_row = ttk.Frame(settings)
        output_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(output_row, text="Вихідний файл:").pack(side=tk.LEFT)
        ttk.Entry(output_row, textvariable=self._output_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(output_row, text="...", width=4, command=self._browse_output).pack(side=tk.LEFT)

        progress_frame = ttk.Frame(root)
        progress_frame.pack(fill=tk.X, **padding)
        self._progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self._progress.pack(fill=tk.X)
        ttk.Label(progress_frame, textvariable=self._status).pack(anchor=tk.W, pady=(6, 0))

        buttons = ttk.Frame(root)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._convert_btn = ttk.Button(buttons, text="Конвертувати", command=self._start_convert)
        self._convert_btn.pack(side=tk.LEFT)
        self._cancel_btn = ttk.Button(buttons, text="Скасувати", command=self._cancel_convert, state=tk.DISABLED)
        self._cancel_btn.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="Відкрити папку результату", command=self._open_output_folder).pack(side=tk.RIGHT)

        grid.columnconfigure(1, weight=1)

    def _update_crf_label(self, _value: str) -> None:
        self._crf_label.configure(text=str(int(float(self._crf.get()))))

    def _set_info_text(self, text: str) -> None:
        self._info_text.configure(state=tk.NORMAL)
        self._info_text.delete("1.0", tk.END)
        self._info_text.insert(tk.END, text)
        self._info_text.configure(state=tk.DISABLED)

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Оберіть відеофайл",
            filetypes=[
                ("Відео", "*.mov *.mp4 *.mkv *.avi *.webm *.wmv *.flv *.m4v *.mpeg *.mpg *.ts *.ogv"),
                ("Усі файли", "*.*"),
            ],
        )
        if path:
            self._input_path.set(path)
            self._suggest_output_path(Path(path))
            self._analyze()

    def _browse_output(self) -> None:
        initial = self._output_path.get() or self._input_path.get()
        path = filedialog.asksaveasfilename(
            title="Зберегти як",
            defaultextension=f".{self._format.get()}",
            initialfile=Path(initial).name if initial else "output.mp4",
            filetypes=[("Відео", "*.*")],
        )
        if path:
            self._output_path.set(path)

    def _suggest_output_path(self, input_path: Path) -> None:
        fmt = self._format.get().lstrip(".")
        output = input_path.with_name(f"{input_path.stem}_converted.{fmt}")
        self._output_path.set(str(output))

    def _analyze(self) -> None:
        path_text = self._input_path.get().strip()
        if not path_text:
            messagebox.showwarning("Увага", "Спочатку оберіть вхідний файл.")
            return

        input_path = Path(path_text)
        try:
            info = analyze_file(input_path)
            self._duration_sec = info.duration_sec
            self._set_info_text(render_media_info(info))
            self._status.set(f"Файл проаналізовано: {input_path.name}")
            if not self._output_path.get().strip():
                self._suggest_output_path(input_path)
        except (FFmpegNotFoundError, FileNotFoundError, RuntimeError) as exc:
            messagebox.showerror("Помилка", str(exc))

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self._convert_btn.configure(state=state)
        self._cancel_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _start_convert(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        input_text = self._input_path.get().strip()
        output_text = self._output_path.get().strip()
        if not input_text:
            messagebox.showwarning("Увага", "Оберіть вхідний файл.")
            return
        if not output_text:
            messagebox.showwarning("Увага", "Вкажіть шлях до вихідного файлу.")
            return

        self._cancel_requested = False
        self._progress["value"] = 0
        self._set_busy(True)
        self._status.set("Конвертація...")

        options = ConvertOptions(
            input_path=Path(input_text),
            output_path=Path(output_text),
            output_format=self._format.get(),
            crf=None if self._copy_streams.get() else int(self._crf.get()),
            preset=self._preset.get(),
            copy_streams=self._copy_streams.get(),
            overwrite=self._overwrite.get(),
        )

        self._worker = threading.Thread(target=self._convert_worker, args=(options,), daemon=True)
        self._worker.start()

    def _convert_worker(self, options: ConvertOptions) -> None:
        try:
            output_path, _ = convert_video(
                options,
                on_progress=self._on_progress,
                cancel_check=lambda: self._cancel_requested,
            )
        except Exception as exc:
            self.after(0, lambda: self._on_convert_failed(str(exc)))
            return
        self.after(0, lambda: self._on_convert_done(output_path))

    def _on_progress(self, percent: float, message: str) -> None:
        self.after(0, lambda: self._apply_progress(percent, message))

    def _apply_progress(self, percent: float, message: str) -> None:
        self._progress["value"] = percent
        self._status.set(message[:120])

    def _on_convert_done(self, output_path: Path) -> None:
        self._progress["value"] = 100
        self._status.set(f"Готово: {output_path}")
        self._set_busy(False)
        messagebox.showinfo("Готово", f"Файл збережено:\n{output_path}")

    def _on_convert_failed(self, error: str) -> None:
        self._status.set("Помилка конвертації")
        self._set_busy(False)
        if "скасовано" not in error.lower():
            messagebox.showerror("Помилка", error)
        else:
            self._status.set("Конвертацію скасовано")

    def _cancel_convert(self) -> None:
        self._cancel_requested = True
        self._status.set("Скасування...")

    def _open_output_folder(self) -> None:
        output_text = self._output_path.get().strip()
        if not output_text:
            messagebox.showwarning("Увага", "Шлях до вихідного файлу не вказано.")
            return
        folder = Path(output_text).parent
        if not folder.exists():
            messagebox.showwarning("Увага", "Папка ще не існує.")
            return
        try:
            open_path(folder)
        except (OSError, subprocess.CalledProcessError) as exc:
            messagebox.showerror("Помилка", f"Не вдалося відкрити папку:\n{exc}")

    def _on_close(self) -> None:
        if self._worker and self._worker.is_alive():
            if not messagebox.askyesno("Вихід", "Конвертація ще триває. Закрити програму?"):
                return
            self._cancel_requested = True
        self.destroy()


def main() -> int:
    try:
        app = VideoConverterApp()
    except tk.TclError as exc:
        print(f"Помилка запуску GUI: {exc}", file=__import__("sys").stderr)
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
