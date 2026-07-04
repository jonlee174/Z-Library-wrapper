"""Small filesystem helpers: safe filenames, collision handling, downloads dir."""

from __future__ import annotations

import re
from pathlib import Path

_ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]')


def default_download_dir() -> Path:
    """The OS Downloads folder, falling back to the home directory."""
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def sanitize_filename(name: str, extension: str = "") -> str:
    """Turn a book title + extension into a safe filename for both OSes."""
    stem = _ILLEGAL.sub("_", name).strip().strip(".")
    stem = re.sub(r"\s+", " ", stem)
    if len(stem) > 180:
        stem = stem[:180].rstrip()
    if not stem:
        stem = "book"
    ext = extension.lower().lstrip(".")
    return f"{stem}.{ext}" if ext else stem


def unique_path(directory: Path, filename: str) -> Path:
    """A non-colliding path in `directory`, appending ' (1)', ' (2)', ... ."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    i = 1
    while True:
        candidate = directory / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1
