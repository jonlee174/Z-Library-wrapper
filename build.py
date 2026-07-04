"""One command to build the app for the current OS.

    python build.py            # build for whatever OS you're on
    python build.py --install  # Windows: also install + create desktop shortcut

- Windows -> dist/ZLibraryWrapper/ZLibraryWrapper.exe  (+ optional installer)
- macOS   -> dist/ZLibraryWrapper.dmg                  (drag-to-Applications)

PyInstaller can't cross-compile, so run this on each OS you want to ship for.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str] | str, shell: bool = False) -> None:
    printable = cmd if isinstance(cmd, str) else " ".join(cmd)
    print(f"\n$ {printable}\n")
    subprocess.run(cmd, cwd=ROOT, shell=shell, check=True)


def rmtree_robust(path: Path, attempts: int = 5) -> None:
    """Remove a directory tree, retrying through the transient file locks that
    OneDrive / antivirus put on freshly-written build output on Windows."""
    for i in range(attempts):
        if not path.exists():
            return
        try:
            shutil.rmtree(path)
            return
        except (PermissionError, OSError):
            # Clear read-only flags and back off before retrying.
            for p in path.rglob("*"):
                try:
                    os.chmod(p, 0o777)
                except OSError:
                    pass
            time.sleep(1.5 * (i + 1))
    # Last resort: leave it to PyInstaller/OS; warn but don't crash.
    if path.exists():
        print(f"Warning: could not fully remove {path} (locked). Continuing.")


def clean() -> None:
    for d in (DIST, BUILD):
        if d.exists():
            print(f"Removing {d} ...")
            rmtree_robust(d)


def ensure_icons() -> None:
    """Generate icons if missing (needs Pillow)."""
    if (ROOT / "assets" / "icon.ico").exists():
        return
    try:
        run([sys.executable, str(PACKAGING / "make_icon.py")])
    except Exception as exc:  # noqa: BLE001
        print(f"(icon generation skipped: {exc})")


def fix_zlibrary() -> None:
    """Patch the installed zlibrary for Python 3.9 before PyInstaller analyses
    it (PyInstaller imports the package at build time; on 3.9 the un-patched
    source crashes the build). Idempotent; no-op if already compatible."""
    try:
        run([sys.executable, str(PACKAGING / "fix_zlibrary.py")])
    except Exception as exc:  # noqa: BLE001
        print(f"(zlibrary fix skipped: {exc})")


def build_pyinstaller() -> None:
    """Build via PyInstaller.

    On Windows we build into a temp directory OUTSIDE OneDrive, then move the
    result into dist/. OneDrive's sync grabs handles on files the moment they
    appear inside a synced folder, which makes PyInstaller's own cleanup fail
    with 'Access is denied'. Building outside and moving in sidesteps that.
    """
    if sys.platform == "win32":
        tmp = Path(tempfile.mkdtemp(prefix="zlib_build_"))
        tdist, twork = tmp / "dist", tmp / "work"
        try:
            run([sys.executable, "-m", "PyInstaller", str(PACKAGING / "app.spec"),
                 "--noconfirm", "--distpath", str(tdist), "--workpath", str(twork)])
            rmtree_robust(DIST)
            DIST.mkdir(parents=True, exist_ok=True)
            for item in tdist.iterdir():
                shutil.move(str(item), str(DIST / item.name))
        finally:
            rmtree_robust(tmp)
    else:
        run([sys.executable, "-m", "PyInstaller", str(PACKAGING / "app.spec"),
             "--noconfirm", "--distpath", str(DIST), "--workpath", str(BUILD)])


def build_windows(install: bool) -> None:
    build_pyinstaller()
    exe = DIST / "ZLibraryWrapper" / "ZLibraryWrapper.exe"
    if not exe.exists():
        sys.exit(f"Build failed: {exe} not found")
    print(f"\nBuilt: {exe}")
    if install:
        run(["powershell", "-ExecutionPolicy", "Bypass", "-File",
             str(PACKAGING / "install.ps1")])
    else:
        print("Run  python build.py --install  to install + add a Desktop shortcut.")


def build_macos() -> None:
    # build_dmg.sh builds the .app (with native .icns) then the DMG.
    run(["bash", str(PACKAGING / "build_dmg.sh")])
    dmg = DIST / "ZLibraryWrapper.dmg"
    if dmg.exists():
        print(f"\nBuilt: {dmg}\nOpen it and drag Z-Library into Applications.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Z-Library app.")
    parser.add_argument("--install", action="store_true",
                        help="Windows only: install and create a desktop shortcut.")
    parser.add_argument("--clean", action="store_true",
                        help="Remove dist/ and build/ before building.")
    args = parser.parse_args()

    if args.clean:
        clean()
    fix_zlibrary()   # make the installed zlibrary import cleanly on Python 3.9
    ensure_icons()

    if sys.platform == "win32":
        build_windows(args.install)
    elif sys.platform == "darwin":
        build_macos()
    else:
        print("Unsupported OS for packaging; building a plain PyInstaller bundle.")
        build_pyinstaller()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
