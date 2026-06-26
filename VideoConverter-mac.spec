# -*- mode: python ; coding: utf-8 -*-
# macOS build spec (creates VideoConverter.app)

block_cipher = None

a = Analysis(
    ['video_converter_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'converter',
        'converter.cli',
        'converter.convert',
        'converter.ffmpeg_utils',
        'converter.platform_utils',
        'converter.probe',
    ],
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

app = BUNDLE(
    coll,
    name='VideoConverter.app',
    icon=None,
    bundle_identifier='ua.converter.videoconverter',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleName': 'Video Converter',
        'CFBundleDisplayName': 'Video Converter',
    },
)
