"""Application entry point: load config, start the backend, launch the UI."""

from __future__ import annotations

import os
import sys

# Ensure text file writes default to UTF-8 regardless of the OS locale. The
# bundled zlibrary has a debug write that otherwise crashes on Windows (cp1252)
# for non-Latin book titles; patches.py also guards this, this is a safety net.
os.environ.setdefault("PYTHONUTF8", "1")

import tkinter as tk
from tkinter import messagebox

from .backend import Backend
from .config import ConfigError, load_config
from .ui.app import App


def _selftest() -> int:
    """Headless import + login + search check, used to validate the frozen
    build. Writes the outcome to selftest_result.txt next to the executable so
    it's observable even though the app is windowed. Invoke with --selftest."""
    import queue
    import time
    from pathlib import Path

    out = Path(sys.executable).parent / "selftest_result.txt"
    lines = []
    try:
        from .backend import Backend
        from .models import Filters

        config = load_config()
        be = Backend(config)
        be.start()
        be.login()
        books = 0
        deadline = time.time() + 90
        result = "TIMEOUT"
        while time.time() < deadline:
            try:
                msg = be.queue.get(timeout=1)
            except queue.Empty:
                continue
            if msg.kind == "login_ok":
                lines.append("login_ok")
                be.search(Filters(title="python", count=3))
            elif msg.kind == "result":
                books += 1
            elif msg.kind == "search_done":
                result = f"OK: {books} results"
                break
            elif msg.kind in ("login_err", "search_err"):
                result = f"{msg.kind}: {msg.payload}"
                break
        lines.append(result)
        be.shutdown()
    except Exception as exc:  # noqa: BLE001
        lines.append(f"EXCEPTION: {exc!r}")
    out.write_text("\n".join(lines), encoding="utf-8")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    try:
        config = load_config()
    except ConfigError as exc:
        # No usable config: tell the user exactly what to do, then exit.
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("Z-Library — setup needed", str(exc))
        root.destroy()
        return 1

    backend = Backend(config)
    backend.start()
    backend.login()

    app = App(backend, config)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
