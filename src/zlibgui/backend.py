"""The async engine: a background thread owning one asyncio event loop.

Login happens once at startup and the AsyncZlib session lives for the whole
app lifetime, so we never re-login. The UI calls the plain methods here
(search / download / etc.); each schedules a coroutine on the loop and pushes
Message envelopes onto `self.queue`, which the Tk thread drains.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from pathlib import Path
from typing import Optional

import zlibrary

from .net import use_certifi_ca, use_threaded_resolver
from .patches import apply_patches
from .challenge import solve_cookies
from .detail import parse_detail
from .config import AppConfig
from .downloader import build_filename, download_book
from .models import Book, Filters, Message
from .search import build_search_kwargs, passes_client_filters

# Cap concurrent detail fetches so we don't hammer the server / trip limits.
FETCH_CONCURRENCY = 5


class Backend:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.queue: "queue.Queue[Message]" = queue.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lib: Optional[zlibrary.AsyncZlib] = None
        self._search_seq = 0  # lets us ignore results from superseded searches
        self._ready = threading.Event()  # set once the loop is running

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # Block briefly until the event loop is up so early submit() calls
        # (login right after start) don't get dropped.
        self._ready.wait(timeout=5)

    def _run_loop(self) -> None:
        use_certifi_ca()         # trust certifi's CAs (fixes frozen-app SSL)
        use_threaded_resolver()  # must run before any aiohttp session is created
        apply_patches()          # fix library bugs before any search runs
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.call_soon(self._ready.set)
        self._loop.run_forever()

    def _submit(self, coro) -> None:
        if self._loop is None:
            self._ready.wait(timeout=5)
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _emit(self, kind: str, payload=None) -> None:
        self.queue.put(Message(kind, payload))

    def shutdown(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # --------------------------------------------------------------------- login
    def login(self) -> None:
        self._submit(self._login_coro())

    async def _login_coro(self) -> None:
        try:
            self._lib = zlibrary.AsyncZlib()
            await self._lib.login(self.config.email, self.config.password)
            await self._solve_challenge()
            self._emit("login_ok")
            await self._refresh_limits_coro()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self._emit("login_err", str(exc))

    async def _solve_challenge(self) -> None:
        """Pass Z-Library's proof-of-work interstitial once, then keep the
        resulting cookies on the session so every library request gets through.
        Best-effort: if the site isn't gating, this is a harmless no-op."""
        if not self._lib:
            return
        try:
            extra = await solve_cookies(self._lib.mirror, self._lib.cookies)
            if extra:
                self._lib.cookies.update(extra)
        except Exception:  # noqa: BLE001 - don't block login on this
            pass

    async def _resolve_and_retry(self) -> bool:
        """Re-solve the browser challenge (its cookies can expire mid-session).
        Returns True if new cookies were obtained."""
        if not self._lib:
            return False
        try:
            extra = await solve_cookies(self._lib.mirror, self._lib.cookies)
            if extra:
                self._lib.cookies.update(extra)
                return True
        except Exception:  # noqa: BLE001
            pass
        return False

    # -------------------------------------------------------------------- limits
    def refresh_limits(self) -> None:
        self._submit(self._refresh_limits_coro())

    async def _refresh_limits_coro(self) -> None:
        if not self._lib:
            return
        try:
            limits = await self._lib.profile.get_limits()
            self._emit("limits", limits)
        except Exception as exc:  # noqa: BLE001
            self._emit("status", f"Could not read download limits: {exc}")

    # -------------------------------------------------------------------- search
    def search(self, filters: Filters) -> None:
        self._search_seq += 1
        self._submit(self._search_coro(filters, self._search_seq))

    async def _search_coro(self, filters: Filters, seq: int) -> None:
        if not self._lib:
            self._emit("search_err", "Not logged in yet.")
            return
        kwargs = build_search_kwargs(filters)
        try:
            paginator = await self._lib.search(**kwargs)
            stubs = await paginator.next()
        except Exception as exc:  # noqa: BLE001
            # The browser challenge may have expired mid-session; re-solve once
            # and retry before giving up.
            if await self._resolve_and_retry():
                try:
                    paginator = await self._lib.search(**kwargs)
                    stubs = await paginator.next()
                except Exception as exc2:  # noqa: BLE001
                    self._emit("search_err", str(exc2))
                    return
            else:
                self._emit("search_err", str(exc))
                return

        if seq != self._search_seq:
            return  # a newer search superseded this one

        self._emit("search_started", len(stubs))

        if filters.needs_detail_fetch():
            await self._fetch_and_filter(stubs, filters, seq)
        else:
            # Fast path: emit stubs immediately, fetch details lazily on select.
            # Keep the original stub object so it retains its .fetch() coroutine.
            for stub in stubs:
                if seq != self._search_seq:
                    return
                self._emit("result", Book(raw=stub))

        if seq == self._search_seq:
            self._emit("search_done")

    async def _fetch_and_filter(self, stubs, filters: Filters, seq: int) -> None:
        sem = asyncio.Semaphore(FETCH_CONCURRENCY)

        async def worker(stub):
            async with sem:
                if seq != self._search_seq:
                    return
                try:
                    detail = await _fetch_stub(self._lib, stub)
                except Exception:  # noqa: BLE001 - skip un-fetchable results
                    return
                book = Book(raw=stub, detail=dict(detail))
                if seq == self._search_seq and passes_client_filters(book, filters):
                    self._emit("result", book)

        await asyncio.gather(*(worker(s) for s in stubs))

    # --------------------------------------------------- fetch a single book's detail
    def fetch_detail(self, book: Book, token: object) -> None:
        """Fetch a stub's detail page (for the detail pane / download_url)."""
        self._submit(self._fetch_detail_coro(book, token))

    async def _fetch_detail_coro(self, book: Book, token: object) -> None:
        if book.detail is not None:
            self._emit("detail", (token, book))
            return
        try:
            stub = book.raw
            # Rebuild a fetchable stub if we only kept a plain dict copy.
            detail = await _fetch_stub(self._lib, stub)
            book.detail = dict(detail)
            self._emit("detail", (token, book))
        except Exception as exc:  # noqa: BLE001
            self._emit("detail_err", (token, str(exc)))

    # ------------------------------------------------------------------ download
    def download(self, book: Book, dest_dir: Path, token: object) -> None:
        self._submit(self._download_coro(book, dest_dir, token))

    async def _download_coro(self, book: Book, dest_dir: Path, token: object) -> None:
        if not self._lib:
            self._emit("download_err", (token, "Not logged in."))
            return
        try:
            if book.detail is None:
                book.detail = dict(await _fetch_stub(self._lib, book.raw))

            url = book.download_url
            if not url or "unavailable" in url.lower():
                self._emit("download_err", (token, "This book has no available download."))
                return

            filename = build_filename(book.name, book.extension or "bin")

            def on_progress(done: int, total: int) -> None:
                self._emit("download_progress", (token, done, total))

            path = await download_book(
                url, filename, dest_dir, self._lib.cookies, on_progress
            )
            self._emit("download_done", (token, str(path)))
            await self._refresh_limits_coro()
        except Exception as exc:  # noqa: BLE001
            self._emit("download_err", (token, str(exc)))


async def _fetch_stub(lib, stub) -> dict:
    """Fetch and parse a result's detail page ourselves.

    We request the page through the library's authenticated `_r()` (so it
    carries the login + challenge cookies) and parse it with our own resilient
    parser rather than the library's outdated BookItem.fetch(). Stub-level
    fields (e.g. authors from the search row) are used as a fallback.
    """
    if lib is None:
        raise RuntimeError("Not logged in.")
    url = stub.get("url")
    if not url:
        raise RuntimeError("Result has no detail URL.")
    html = await lib._r(url)
    detail = parse_detail(html, url)
    # Fall back to stub fields the detail page might omit.
    for key in ("authors", "name", "year", "extension", "size", "cover"):
        if not detail.get(key) and stub.get(key):
            detail[key] = stub[key]
    return detail
