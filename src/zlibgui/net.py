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
_ssl_applied = False


def use_certifi_ca() -> None:
    """Point SSL verification at certifi's CA bundle.

    A frozen (.app / .exe) build ships its own OpenSSL, which on macOS has no
    default CA path — so every HTTPS request fails with
    SSLCertVerificationError even against a valid host like z-library.sk.
    certifi provides a known-good CA bundle; we set SSL_CERT_FILE (read by
    OpenSSL / aiohttp / ssl) and make the stdlib default SSL context load it, so
    both the zlibrary sessions and our downloader verify correctly.
    """
    global _ssl_applied
    if _ssl_applied:
        return
    _ssl_applied = True
    try:
        import os
        import ssl

        import certifi

        ca = certifi.where()
        if ca and os.path.exists(ca):
            os.environ.setdefault("SSL_CERT_FILE", ca)
            os.environ.setdefault("SSL_CERT_DIR", os.path.dirname(ca))
            os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)

            # Make the stdlib default context load certifi's bundle too, so
            # aiohttp's default ssl context (built from create_default_context)
            # trusts the same CAs even if the env vars are ignored.
            _orig = ssl.create_default_context

            def _ctx(*args, **kwargs):
                context = _orig(*args, **kwargs)
                try:
                    context.load_verify_locations(cafile=ca)
                except Exception:  # noqa: BLE001
                    pass
                return context

            ssl.create_default_context = _ctx
    except Exception:  # noqa: BLE001 - never block startup on this
        pass


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
