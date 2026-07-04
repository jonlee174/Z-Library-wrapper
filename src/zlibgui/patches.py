"""Runtime patches for bugs in the bundled zlibrary that would otherwise crash
searches on Windows. Applied once at startup, before any search runs.

zlibrary's SearchPaginator.parse_page has a leftover debug line that writes the
results HTML to 'test.html' using the platform default encoding. On Windows
(cp1252) that raises UnicodeEncodeError as soon as a book title contains
non-Latin-1 characters, killing the whole search. We shim the `open` name in the
library's module so that debug write always uses UTF-8 (and never crashes).
"""

from __future__ import annotations

import builtins

_applied = False


def _utf8_open(file, mode="r", *args, **kwargs):
    # Force a UTF-8 text encoding for the library's debug write so it can't
    # crash on Unicode; leave binary modes untouched.
    if "b" not in mode and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
    try:
        return builtins.open(file, mode, *args, **kwargs)
    except OSError:
        # If even that fails (e.g. read-only app dir), swallow debug writes.
        import io

        return io.StringIO()


def apply_patches() -> None:
    global _applied
    if _applied:
        return
    _applied = True
    try:
        import zlibrary.abs as abs_mod

        abs_mod.open = _utf8_open  # shadow builtin open within the library module
    except Exception:  # noqa: BLE001 - never block startup on a patch
        pass
