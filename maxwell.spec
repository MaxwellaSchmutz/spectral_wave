# -*- mode: python ; coding: utf-8 -*-
#
# Pinned PyInstaller build config. Build with:
#
#     uv run pyinstaller --noconfirm maxwell.spec
#
# Do NOT build with `pyinstaller ... main.py` -- that regenerates this file
# from defaults and silently discards the settings below.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='maxwell',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is known to corrupt Qt/Python DLLs on Windows, producing a binary
    # that fails at startup with no console to report it (console=False below).
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
