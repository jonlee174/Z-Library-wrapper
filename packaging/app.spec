# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Z-Library desktop wrapper.

Build (run on the target OS — PyInstaller is not a cross-compiler):

    pyinstaller packaging/app.spec

Output:
    Windows -> dist/ZLibraryWrapper/ZLibraryWrapper.exe
    macOS   -> dist/ZLibraryWrapper.app
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "ZLibraryWrapper"
ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"

is_windows = sys.platform == "win32"
is_macos = sys.platform == "darwin"

icon_ico = ASSETS / "icon.ico"
icon_icns = ASSETS / "icon.icns"
icon = None
if is_windows and icon_ico.exists():
    icon = str(icon_ico)
elif is_macos and icon_icns.exists():
    icon = str(icon_icns)

# zlibrary pulls in a few dynamically-referenced deps; collect them explicitly.
hidden = (
    ["zlibrary"]
    + collect_submodules("zlibrary")
    + collect_submodules("aiohttp")
    + ["aiohttp_socks", "python_socks", "aiodns", "bs4", "lxml", "ujson", "certifi"]
)

a = Analysis(
    [str(SRC / "run.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["numpy", "pandas", "matplotlib", "PIL", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,          # windowed app, no terminal
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if is_macos:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier="com.zlibgui.wrapper",
        info_plist={
            "CFBundleName": "Z-Library",
            "CFBundleDisplayName": "Z-Library",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.13",
        },
    )
