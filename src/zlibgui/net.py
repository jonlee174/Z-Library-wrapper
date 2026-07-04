"""Network setup applied once, before any aiohttp session is created.

On some Windows machines the async DNS resolver (aiodns/pycares) can't reach the
system DNS servers and every request fails with "Could not contact DNS servers",
even though the standard library resolver works fine. aiohttp prefers aiodns
whenever it's installed (it's pulled in as a transitive dependency of zlibrary).

We force aiohttp's default resolver back to the threaded stdlib resolver so both
the zlibrary sessions and our own downloader resolve hostnames reliably. This is
a no-op on platforms where aiodns works.
"""

from __future__ import annotations

_applied = False


def use_threaded_resolver() -> None:
    global _applied
    if _applied:
        return
    _applied = True
    try:
        import aiohttp.connector as connector
        import aiohttp.resolver as resolver

        resolver.DefaultResolver = resolver.ThreadedResolver
        # The connector module binds DefaultResolver at import time.
        connector.DefaultResolver = resolver.ThreadedResolver
    except Exception:  # noqa: BLE001 - never block startup on this
        pass
