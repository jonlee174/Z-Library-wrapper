"""Translate UI Filters into zlibrary.search() kwargs and apply the
client-side filters (publisher / edition / author) that the API can't do."""

from __future__ import annotations

from typing import Optional

import zlibrary

from .models import Book, Filters


def _extension(fmt: str) -> Optional["zlibrary.Extension"]:
    if not fmt:
        return None
    try:
        return zlibrary.Extension[fmt.strip().upper()]
    except KeyError:
        return None


def build_search_kwargs(filters: Filters) -> dict:
    """Native search parameters: q, from_year, to_year, extensions, count."""
    kwargs: dict = {"q": filters.query(), "count": max(1, min(filters.count, 100))}
    if filters.year_from:
        kwargs["from_year"] = filters.year_from
    if filters.year_to:
        kwargs["to_year"] = filters.year_to
    ext = _extension(filters.fmt)
    if ext is not None:
        kwargs["extensions"] = [ext]
    return kwargs


def passes_client_filters(book: Book, filters: Filters) -> bool:
    """Case-insensitive substring match for the filters the API lacks.
    Assumes the book has been fetched when publisher/edition are set."""
    pub = filters.publisher.strip().lower()
    if pub and pub not in book.publisher.lower():
        return False

    ed = filters.edition.strip().lower()
    if ed and ed not in book.edition.lower():
        return False

    # If an author was given, also tighten against the parsed author list
    # (the query already biases results, this drops obvious mismatches).
    author = filters.author.strip().lower()
    if author and book.authors and author not in book.authors.lower():
        return False

    return True
