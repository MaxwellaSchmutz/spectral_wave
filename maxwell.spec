# -*- mode: python ; coding: utf-8 -*-
#
# Pinned PyInstaller build config. Build with:
#
#     uv run pyinstaller --noconfirm maxwell.spec
#
# Do NOT build with `pyinstaller ... main.py` -- that regenerates this file
# from defaults and silently discards the settings below.

# MP4 export goes through imageio-ffmpeg's bundled encoder. PyInstaller's module
# graph cannot see it: nothing imports the .exe, it is located at call time by
# imageio_ffmpeg.get_ffmpeg_exe(). Without this the build succeeds and then
# silently exports GIF instead of MP4, which is exactly the failure mode this
# whole dependency exists to remove. Located dynamically so the version in the
# filename is not pinned here.
try:
    import imageio_ffmpeg
    _ffmpeg = [(imageio_ffmpeg.get_ffmpeg_exe(), 'imageio_ffmpeg/binaries')]
except Exception as _exc:                       # noqa: BLE001 - build-time only
    print(f"maxwell.spec WARNING: no bundled ffmpeg ({_exc}); "
          f"the build will fall back to GIF export.")
    _ffmpeg = []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_ffmpeg,
    datas=[],
    hiddenimports=['imageio_ffmpeg'],
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
