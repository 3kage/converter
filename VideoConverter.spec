# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

ctk_datas = collect_data_files("customtkinter")
theme_datas = [("converter/assets/premium-theme.json", "converter/assets")]

a = Analysis(
    ['video_converter_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=ctk_datas + theme_datas,    hiddenimports=['converter', 'converter.cli', 'converter.convert', 'converter.ffmpeg_utils', 'converter.platform_utils', 'converter.paths', 'converter.probe', 'converter.presets', 'converter.batch', 'converter.i18n', 'converter.history', 'converter.hardware', 'converter.preview', 'converter.compare', 'converter.updater', 'converter.dnd', 'converter.filters', 'converter.streams', 'converter.settings', 'converter.options_io', 'converter.notifications', 'converter.file_scan', 'converter.watch_folder', 'converter.background', 'converter.system_theme', 'converter.ui_premium', 'converter.recovery', 'converter.security', 'customtkinter', 'windnd', 'tkinterdnd2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VideoConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoConverter',
)
