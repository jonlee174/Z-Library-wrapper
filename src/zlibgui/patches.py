"""Runtime patches for bugs in the bundled zlibrary that would otherwise crash
on some platforms. Split into two groups:

1. apply_pre_import_patches() - MUST run before `import zlibrary`.
   zlibrary/booklists.py annotates a parameter as `OrderOptions | str`. The
   `EnumMeta | type` operation only works on Python 3.10+; on 3.9 (the macOS
   system Python) it raises `TypeError: unsupported operand type(s) for |:
   EnumMeta and type` at import time, crashing the whole app before any window
   appears. We add __or__/__ror__ to EnumMeta so the annotation evaluates
   harmlessly. (Booklists isn't used by this app.)

2. apply_patches() - run once at startup after zlibrary is importable.
   zlibrary's SearchPaginator.parse_page has a leftover debug line that writes
   the results HTML using the platform default encoding. On Windows (cp1252)
   that raises UnicodeEncodeError for non-Latin-1 book titles, killing the
   search. We shim `open` in the library module to always use UTF-8.
"""

from __future__ import annotations

import builtins

_applied = False
_pre_applied = False


def apply_pre_import_patches() -> None:
    """Make `EnumMeta | type` work on Python 3.9. No-op on 3.10+.
    Call this BEFORE importing zlibrary."""
    global _pre_applied
    if _pre_applied:
        return
    _pre_applied = True

    import sys
    if sys.version_info >= (3, 10):
        return  # native support; nothing to do

    from enum import EnumMeta
    try:
        import typing

        if not hasattr(EnumMeta, "__or__"):
            EnumMeta.__or__ = lambda self, other: typing.Union[self, other]
        if not hasattr(EnumMeta, "__ror__"):
            EnumMeta.__ror__ = lambda self, other: typing.Union[other, self]
    except Exception:  # noqa: BLE001 - never block startup on a patch
        pass


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
