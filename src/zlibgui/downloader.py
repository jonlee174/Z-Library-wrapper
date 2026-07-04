"""Authenticated streaming download of a book file.

The library only fetches HTML (its GET_request returns text), so we do the
binary download ourselves with aiohttp, reusing the login session cookies.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Dict, Optional

import aiohttp

from .util import sanitize_filename, unique_path

CHUNK = 64 * 1024


def _headers() -> dict:
    """Match the exact User-Agent the zlibrary session uses, so the download
    request is accepted by the same anti-bot gate that the session passed."""
    try:
        from zlibrary.util import HEAD

        return dict(HEAD)
    except Exception:  # noqa: BLE001
        return {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            )
        }


async def download_book(
    download_url: str,
    filename: str,
    dest_dir: Path,
    cookies: Dict[str, str],
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """Stream `download_url` to `dest_dir/filename`.

    Writes to a temp file first and renames atomically on success so a failed
    or cancelled download never leaves a partial file under the final name.
    `on_progress(downloaded_bytes, total_bytes)` is called as bytes arrive
    (total is 0 when the server omits Content-Length).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_path = unique_path(dest_dir, filename)
    tmp_path = final_path.with_suffix(final_path.suffix + ".part")

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=120)
    try:
        async with aiohttp.ClientSession(
            cookies=cookies, headers=_headers(), timeout=timeout
        ) as session:
            async with session.get(download_url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0) or 0)
                downloaded = 0
                with open(tmp_path, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(CHUNK):
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(downloaded, total)
        os.replace(tmp_path, final_path)
        return final_path
    except BaseException:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


def build_filename(name: str, extension: str) -> str:
    return sanitize_filename(name, extension)
