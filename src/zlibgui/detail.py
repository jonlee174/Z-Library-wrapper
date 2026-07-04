"""Parse a Z-Library book detail page ourselves.

The bundled zlibrary's own BookItem.fetch() targets an older page layout and
breaks on the current markup, so we fetch the detail HTML through the library's
authenticated request method and parse the fields we need here. This keeps us
resilient to the library lagging behind Z-Library's frontend.
"""

from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# bookProperty class -> our key
_PROP_MAP = {
    "property_year": "year",
    "property_publisher": "publisher",
    "property_edition": "edition",
    "property_language": "language",
    "property_volume": "volume",
    "property_series": "series",
    "property_pages": "pages",
    "property_isbn": "isbn",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _authors(soup: BeautifulSoup) -> List[str]:
    names: List[str] = []
    for a in soup.select("a.color1"):
        name = _clean(a.get_text())
        # The author block sits near the title; drop obvious tag/user noise.
        if name and name.lower() not in {n.lower() for n in names}:
            names.append(name)
    # Heuristic: the first entries are the real authors; commenters/tags follow.
    # Keep at most the leading run that looks like proper names.
    return names[:6]


def parse_detail(html: str, base_url: str) -> Dict[str, object]:
    """Extract detail fields + download_url from a book page."""
    soup = BeautifulSoup(html, "lxml")
    parsed: Dict[str, object] = {}

    title = soup.find("h1", {"itemprop": "name"})
    if title:
        parsed["name"] = _clean(title.get_text())

    authors = _authors(soup)
    if authors:
        parsed["authors"] = authors

    for bp in soup.find_all("div", class_="bookProperty"):
        classes = bp.get("class", [])
        value_el = bp.find("div", class_="property_value")
        value = _clean(value_el.get_text()) if value_el else ""
        if not value:
            continue
        for cls in classes:
            if cls in _PROP_MAP:
                parsed[_PROP_MAP[cls]] = value
            if cls == "property__file":
                # e.g. "EPUB, 3.19 MB" -> extension + size
                parts = [p.strip() for p in value.split(",", 1)]
                if parts:
                    parsed["extension"] = parts[0].lower()
                if len(parts) > 1:
                    parsed["size"] = parts[1]

    desc = soup.find("div", {"id": "bookDescriptionBox"})
    if desc:
        parsed["description"] = _clean(desc.get_text())

    cover = soup.find("img", {"class": "cover"}) or soup.find("z-cover")
    if cover:
        src = cover.get("data-src") or cover.get("src")
        if src:
            parsed["cover"] = src

    parsed["download_url"] = _download_url(soup, base_url)
    parsed["url"] = base_url
    return parsed


def _download_url(soup: BeautifulSoup, base_url: str) -> str:
    """Find the primary 'Download' button's href, resolved to an absolute URL.

    Z-Library serves either a relative link (e.g. '/dl/XXXX', which then
    redirects to the signed file URL) or an already-signed absolute reader URL;
    both work when requested with the login cookies.
    """
    selectors = [
        "a.addDownloadedBook",
        "a.btn.btn-primary.dlButton",
        "a.dlButton",
        "a.book-details-button",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get("href"):
            href = el["href"].strip()
            if href and "unavailable" not in href.lower():
                return urljoin(base_url, href)
    # Fall back: any anchor whose text says Download.
    for a in soup.find_all("a"):
        if "download" in _clean(a.get_text()).lower() and a.get("href"):
            return urljoin(base_url, a["href"].strip())
    return ""
