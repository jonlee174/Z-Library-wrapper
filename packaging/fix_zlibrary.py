"""Patch the installed `zlibrary` package to be Python 3.9-compatible.

zlibrary/booklists.py annotates a parameter as `OrderOptions | str`. That
`EnumMeta | type` syntax only works on Python 3.10+, so on Python 3.9 (macOS
system Python) it raises `TypeError: unsupported operand type(s) for |: EnumMeta
and type` — at IMPORT time, and therefore also when PyInstaller analyses the
module during a build. A runtime shim can't help the build-time analysis, so we
fix the source directly.

This edits the annotation to the equivalent, universally-valid
`Union[OrderOptions, str]`. It's idempotent (safe to run repeatedly) and does
nothing if the file is already fixed. Run automatically by build.py; can also be
run standalone:  python packaging/fix_zlibrary.py
"""

from __future__ import annotations

import sys


def _booklists_path():
    import zlibrary.booklists as bl  # noqa: import to locate the file
    return bl.__file__


def apply() -> bool:
    """Returns True if a change was made, False if already patched / n/a."""
    try:
        path = _booklists_path()
    except Exception as exc:  # noqa: BLE001
        print(f"fix_zlibrary: could not locate zlibrary ({exc}); skipping.")
        return False

    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()

    if "OrderOptions | str" not in src:
        return False  # already fixed (or a version without this annotation)

    new = src.replace("OrderOptions | str", "Union[OrderOptions, str]")

    # Ensure Union is importable. booklists.py has `from typing import ...`.
    if "Union" not in new:
        new = "from typing import Union\n" + new
    elif "import Union" not in new and "from typing import Callable, Optional" in new:
        new = new.replace(
            "from typing import Callable, Optional",
            "from typing import Callable, Optional, Union",
        )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    print(f"fix_zlibrary: patched {path} for Python 3.9 compatibility.")
    return True


if __name__ == "__main__":
    changed = apply()
    print("Changed." if changed else "Already compatible; nothing to do.")
    sys.exit(0)
