"""Solve Z-Library's "Checking your browser" proof-of-work challenge.

Z-Library gates its search/detail/limits pages behind a JavaScript interstitial
that a scraping client can't execute. The page is NOT a real CAPTCHA — it's a
proof-of-work: it embeds a 40-hex token, then brute-forces an integer `i` such
that SHA1(token + i) has two specific bytes at a token-derived offset, and sets
a `c_token` cookie to `token + i` (plus a `c_time` cookie). We replicate that in
Python and inject the resulting cookies into the logged-in session so every
subsequent library request passes the gate.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Optional

import aiohttp

from .net import use_threaded_resolver

CHALLENGE_MARKER = "Checking your browser"

# The obfuscated JS stores the token as the first 40-hex string in this array.
_ARRAY_RE = re.compile(r"a0_0x2a54\s*=\s*\[([^\]]+)\]")
_STRING_RE = re.compile(r"'([^']*)'")
_HEX40_RE = re.compile(r"[0-9A-Fa-f]{40}")


def is_challenge(html: str) -> bool:
    return CHALLENGE_MARKER in html


def _extract_token(html: str) -> Optional[str]:
    m = _ARRAY_RE.search(html)
    if not m:
        # Fall back to any standalone 40-hex literal in the page.
        found = _HEX40_RE.search(html)
        return found.group(0) if found else None
    for candidate in _STRING_RE.findall(m.group(1)):
        if _HEX40_RE.fullmatch(candidate):
            return candidate
    return None


def solve_token(html: str, max_iter: int = 20_000_000) -> Optional[str]:
    """Return the c_token value (`token + i`) for the challenge, or None."""
    token = _extract_token(html)
    if not token:
        return None
    offset = int(token[0], 16)  # byte index the JS checks (n1)
    i = 0
    while i < max_iter:
        digest = hashlib.sha1(f"{token}{i}".encode()).digest()
        if digest[offset] == 0xB0 and digest[offset + 1] == 0x0B:
            return f"{token}{i}"
        i += 1
    return None


async def solve_cookies(mirror: str, cookies: Dict[str, str]) -> Dict[str, str]:
    """Hit a protected page, solve any challenge, and return every cookie the
    session ended up with that isn't already in `cookies` — i.e. `c_token` plus
    whatever the server sets in response to accepting it (`c_time`, `bsrv`,
    `siteLanguage`, ...). Empty dict if no challenge appears.

    `cookies` are the logged-in session cookies; merge the return value into
    that same dict so later library requests carry the solved tokens.
    """
    use_threaded_resolver()
    base = mirror.rstrip("/")
    url = base + "/s/test"
    timeout = aiohttp.ClientTimeout(total=60)
    # Use the same User-Agent the library sends, so the solved cookies are valid
    # for the library's own requests (the challenge can be UA-bound).
    try:
        from zlibrary.util import HEAD as _HEAD
        headers = dict(_HEAD)
    except Exception:  # noqa: BLE001
        headers = {}
    async with aiohttp.ClientSession(
        cookies=dict(cookies), timeout=timeout, headers=headers
    ) as sess:
        async with sess.get(url) as resp:
            html = await resp.text()
        if not is_challenge(html):
            return {}
        token = solve_token(html)
        if not token:
            return {}
        # Present the solved token; the server accepts it and sets more cookies.
        sess.cookie_jar.update_cookies({"c_token": token, "c_time": "1.5"})
        async with sess.get(url) as resp2:
            await resp2.text()

        # Collect the full post-solve cookie set (last write wins per key),
        # then return only what's new/changed versus the input cookies.
        final: Dict[str, str] = {}
        for c in sess.cookie_jar:
            final[c.key] = c.value
        final["c_token"] = token  # ensure our solved token is the one kept
        return {k: v for k, v in final.items() if cookies.get(k) != v}
