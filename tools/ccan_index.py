#!/usr/bin/env python3
"""HTML parsers for CCAN's listing and per-entry pages.

Shared between ``mirror_ccan.py`` (Phase 1 raw mirror) and ``import_ccan.py``
(per-entry metadata parsing). Pure stdlib.

- ``parse_listing`` scrapes the paginated ``ccan-view.pl`` table.
- ``parse_per_entry`` scrapes a per-entry page into a ``PerEntry`` record
  (the ``CcanMetadata`` fields plus the comments section + canonical URLs).

The per-entry metadata parser (``parse_ccan_metadata`` + ``CcanMetadata``)
is re-used from ``import_ccan.py`` to avoid duplication; this module wraps
it and adds listing + comments parsing.
"""
from __future__ import annotations

import html.parser
import re
from dataclasses import dataclass
from typing import Optional

# Re-use the per-entry metadata parser + URL constants from import_ccan.
# ccan_index is imported by mirror_ccan; import_ccan does NOT import
# ccan_index, so there is no cycle.
from import_ccan import (
    CCAN_BASE,
    CCAN_DOWNLOAD_URL,
    CCAN_VIEW_URL,
    CcanMetadata,
    parse_ccan_metadata,
)


# ===========================================================================
# Data classes
# ===========================================================================

@dataclass
class ListingEntry:
    """One row in CCAN's paginated listing."""
    ccan_id: int
    title: str
    author_nick: str
    uploaded: str
    engine: str
    filename: str
    file_type: str          # lower-cased extension without dot, e.g. "c4s"
    size_label: str         # human-readable, e.g. "16.7 MB"

    @property
    def is_pack(self) -> bool:
        return self.file_type in ("c4d", "c4f", "c4s", "zip")


@dataclass
class ListingPage:
    entries: list[ListingEntry]
    page_number: int
    total_pages: int
    total_entries: int      # the "von N" count; 0 if undetectable


@dataclass
class PerEntry:
    """Full per-entry record (mirror's meta.json payload minus sha256)."""
    ccan_id: int
    title: str
    author_nick: str
    author_uid: int
    uploaded: str
    engine: str
    filename: str
    description_de: str
    description_us: str
    comments: str
    view_url: str
    download_url: str


# ===========================================================================
# Listing parser
# ===========================================================================

class _ListingParser(html.parser.HTMLParser):
    """Scrape the CCAN listing table.

    The listing is a ``<table>`` with one ``<tr>`` per entry. Each row's
    first cell contains an ``<a href="ccan-view.pl?a=view&i=<id>">`` link.
    Columns (in order): Title, Author, Uploaded, Engine, Filename, Type, Size.
    """

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[ListingEntry] = []
        self.page_number = 0
        self.total_pages = 0
        self.total_entries = 0
        self._in_tr = False
        self._in_td = False
        self._in_a = False
        self._cell_parts: list[str] = []
        self._row_cells: list[str] = []
        self._row_href = ""
        self._full_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._in_tr = True
            self._row_cells = []
            self._row_href = ""
        elif tag == "td" and self._in_tr:
            self._in_td = True
            self._cell_parts = []
        elif tag == "a" and self._in_td:
            self._in_a = True
            href = a.get("href", "")
            if "i=" in href:
                self._row_href = href

    def handle_endtag(self, tag):
        if tag == "td" and self._in_td:
            self._row_cells.append("".join(self._cell_parts).strip())
            self._in_td = False
        elif tag == "a":
            self._in_a = False
        elif tag == "tr" and self._in_tr:
            self._finalize_row()
            self._in_tr = False

    def handle_data(self, data):
        if self._in_td:
            self._cell_parts.append(data)
        else:
            self._full_text.append(data)

    def _finalize_row(self) -> None:
        cells = self._row_cells
        if len(cells) < 7:
            return
        m = re.search(r"i=(\d+)", self._row_href or "")
        if not m:
            return
        ccan_id = int(m.group(1))
        self.entries.append(ListingEntry(
            ccan_id=ccan_id,
            title=cells[0],
            author_nick=cells[1],
            uploaded=cells[2],
            engine=cells[3],
            filename=cells[4],
            file_type=cells[5].lower().lstrip("."),
            size_label=cells[6],
        ))


def parse_listing(html_text: str) -> ListingPage:
    """Parse one CCAN listing page. Returns a ListingPage."""
    parser = _ListingParser()
    parser.feed(html_text)
    full = " ".join(parser._full_text)
    # Pagination footer: "Seite x von y" / "Page x of y"
    m = re.search(r"(?:Seite|Page)\s+(\d+)\s+(?:von|of)\s+(\d+)", full)
    if m:
        parser.page_number = int(m.group(1))
        parser.total_pages = int(m.group(2))
    # Total entries: the last "von N" / "of N" number in the footer.
    matches = re.findall(r"(?:von|of)\s+(\d+)", full)
    if matches:
        parser.total_entries = int(matches[-1])
    return ListingPage(
        entries=parser.entries,
        page_number=parser.page_number,
        total_pages=parser.total_pages,
        total_entries=parser.total_entries,
    )


# ===========================================================================
# Per-entry parser + comments extraction
# ===========================================================================

def extract_comments(html_text: str) -> str:
    """Extract the comments section from a raw CCAN entry page.

    Looks for ``<div id="comments">...</div>`` (case-insensitive) and
    returns the text content with tags stripped + whitespace collapsed.
    Returns "" if no comments block is present.
    """
    m = re.search(
        r"<div[^>]*id=[\"']comments[\"'][^>]*>(.*?)</div>",
        html_text, re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ""
    inner = m.group(1)
    text = re.sub(r"<[^>]+>", " ", inner)
    return re.sub(r"\s+", " ", text).strip()


def parse_per_entry(html_text: str, ccan_id: int) -> PerEntry:
    """Parse a per-entry CCAN page into a full PerEntry record."""
    meta = parse_ccan_metadata(html_text, ccan_id)
    comments = extract_comments(html_text)
    return PerEntry(
        ccan_id=meta.ccan_id,
        title=meta.title,
        author_nick=meta.author_nick,
        author_uid=meta.author_uid,
        uploaded=meta.uploaded,
        engine=meta.engine,
        filename=meta.filename,
        description_de=meta.description_de,
        description_us=meta.description_us,
        comments=comments,
        view_url=CCAN_VIEW_URL.format(id=ccan_id),
        download_url=CCAN_DOWNLOAD_URL.format(id=ccan_id, filename=meta.filename),
    )
