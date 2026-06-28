# Video Converter

Крос-платформний конвертер відео на базі **FFmpeg** з GUI (CustomTkinter), CLI та автооновленням.

Репозиторій: https://github.com/3kage/converter

## Залежності

| Режим | Python-пакети | Зовнішні утиліти |
|-------|---------------|------------------|
| **Готовий .exe / .app** (Releases) | Не потрібні | FFmpeg (вбудований у збірку) |
| **CLI** з вихідного коду | Не потрібні (лише stdlib) | FFmpeg у PATH |
| **GUI** з вихідного коду | `customtkinter`, `Pillow`, `tkinterdnd2`, … | FFmpeg + **tkinter** (системний) |
| **Збірка** | `pyinstaller` + GUI-залежності | FFmpeg |

```bash
# Лише CLI
pip install -e .

# GUI з вихідного коду
pip install -e ".[gui]"
# або
pip install -r requirements.txt && pip install -e .

# Розробка / збірка
pip install -e ".[dev]"
```

## Можливості

- Конвертація MOV, MP4, MKV, AVI, WebM та інших форматів
- Пресети: YouTube, Telegram, iPhone, TV, WebM short, власні пресети
- Пакетна обробка (рекурсивні папки, пауза, паралельні потоки, фоновий режим)
- Watch folder — автоконвертація нових файлів
- GPU-кодування (NVENC, QSV, VideoToolbox), HEVC
- Аудіо/субтитри: витяг, embed, burn-in, кілька доріжок
- Обрізка, GIF, merge, crop, watermark, 2-pass, deinterlace, denoise
- Історія з повтором налаштувань
- UA/EN, темна тема, збереження налаштувань
- Автооновлення з GitHub Releases (Windows / macOS / Linux)

## Швидкий старт

```bash
pip install -e ".[gui]"
python video_converter_gui.py
```

CLI (без додаткових pip-пакетів):

```bash
python -m converter info video.mov
python -m converter convert video.mov -f mp4
python -m converter batch --input-dir ./videos --recursive -f mp4 --parallel 2
```

## Збірка

| Платформа | Команда | Результат |
|-----------|---------|-----------|
| Windows | `powershell -File build.ps1` | `dist/VideoConverter/VideoConverter.exe` |
| macOS | `./build.sh` | `dist/VideoConverter.app` |
| Linux | `./build-linux.sh` | `dist/VideoConverter/VideoConverter` |

Артефакти CI та Releases: https://github.com/3kage/converter/actions

## macOS (без підпису Apple)

```bash
xattr -cr VideoConverter.app
open VideoConverter.app
```

Підпис і нотаризація потребують Apple Developer Program (~$99/рік).

## Intel Mac

CI збирає Apple Silicon; на Intel Mac програма зазвичай працює через Rosetta.

## Ліцензія

Використовуйте на власний розсуд. FFmpeg — відповідна ліцензія FFmpeg/LGPL.
