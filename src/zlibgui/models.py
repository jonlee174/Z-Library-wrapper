"""Plain data structures passed between the UI and the async backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Filters:
    """Search-bar input, straight from the UI fields."""

    title: str = ""
    author: str = ""
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    publisher: str = ""
    edition: str = ""
    fmt: str = ""          # "", "PDF", "EPUB", ...
    count: int = 25

    def query(self) -> str:
        """Fold title + author into a single Z-Library query string."""
        return " ".join(p for p in (self.title.strip(), self.author.strip()) if p)

    def needs_detail_fetch(self) -> bool:
        """Publisher/edition only exist on fetched books, so those filters
        force us to fetch each result's detail page before filtering."""
        return bool(self.publisher.strip() or self.edition.strip())


@dataclass
class Book:
    """A search result, optionally enriched with detail-page metadata.

    Wraps the library's result dict (a zlibrary BookItem, itself a dict) so the
    UI never touches the library types directly.
    """

    raw: dict = field(default_factory=dict)      # the original stub (has .fetch())
    detail: Optional[dict] = None                # populated after fetch()

    def _pick(self, key: str, default: str = "") -> str:
        if self.detail and self.detail.get(key):
            return str(self.detail[key])
        val = self.raw.get(key)
        return str(val) if val else default

    @property
    def name(self) -> str:
        return self._pick("name", "(untitled)")

    @property
    def year(self) -> str:
        return self._pick("year")

    @property
    def extension(self) -> str:
        return self._pick("extension").upper()

    @property
    def size(self) -> str:
        return self._pick("size")

    @property
    def publisher(self) -> str:
        return self._pick("publisher")

    @property
    def edition(self) -> str:
        return self._pick("edition")

    @property
    def language(self) -> str:
        return self._pick("language")

    @property
    def description(self) -> str:
        return self._pick("description")

    @property
    def cover(self) -> str:
        return self._pick("cover")

    @property
    def download_url(self) -> str:
        return self.detail.get("download_url", "") if self.detail else ""

    @property
    def authors(self) -> str:
        src = self.detail or self.raw
        authors = src.get("authors")
        if isinstance(authors, list):
            names = []
            for a in authors:
                if isinstance(a, dict):
                    names.append(a.get("author") or a.get("name") or "")
                else:
                    names.append(str(a))
            return ", ".join(n for n in names if n)
        if authors:
            return str(authors)
        return src.get("author", "") or ""


@dataclass
class Message:
    """Envelope pushed from the async thread onto the UI queue."""

    kind: str          # login_ok | login_err | limits | result | search_done | ...
    payload: Any = None
