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
    """One row in CCAN's paginated listing.

    The Phase-0 enriched-listing fields are appended AFTER the legacy fields
    (with defaults) so the positional construction at mirror_ccan.py:268-271
    keeps compiling exactly as written.
    """
    ccan_id: int
    title: str
    author_nick: str
    uploaded: str
    engine: str
    filename: str
    file_type: str          # lower-cased extension without dot, e.g. "c4s"
    size_label: str         # human-readable, e.g. "16.7 MB"
    entry_type: str = ""    # Szenario/Objekt/Dokument/News/Programm
    category: str = ""
    niveau_label: Optional[str] = None
    niveau_numeric: Optional[float] = None
    votes: Optional[int] = None
    downloads: Optional[int] = None
    author_uid: int = 0

    @property
    def is_pack(self) -> bool:
        return self.file_type in ("c4d", "c4f", "c4s", "zip")

@dataclass
class ListingPage:
    entries: list[ListingEntry]
    page_number: int
    total_pages: int
    total_entries: int      # the "von N" count; 0 if undetectable
    parse_failures: int = 0  # cells/rows the evidence classifier skipped

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

# Cell-text shapes used by the row/column evidence classifier.
_NIVEAU_RE = re.compile(r"^(.+?) \((-?\d+[.,]\d+)\)(?: \((\d+) Votes?\))?$")
_SIZE_RE = re.compile(r"^(\d+[.,]?\d*)\s*(KB|MB|GB|Bytes?)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TYPE_RE = re.compile(r"^(?:Szenario|Objekt|Dokument|News|Programm)$")
_INT_RE = re.compile(r"^-?\d+$")
# Footer entry range: "Einträge 1-30 von 3697" / "… 1 bis 30 von N" /
# "entries 1-30 of N" (English). Anchored on a dash/bis before the "von N"
# total so the "davon M unter Niveau" clause can never shadow the real total.
# The whitespace after the separator is optional ("1-30" and "1 bis 30" and
# "1 - 30" all occur); \s* right before the closing total is deliberate so
# the separator never consumes the low end of the range.
_ENTRY_RANGE_RE = re.compile(r"\d+\s*(?:-|bis|–)\s*\d+\s+(?:von|of)\s+(\d+)")

# Positional fallback column orders for layout families without a caller
# column order. Used only for cells that carry no href/text-shape evidence.
_LEGACY_FAMILY = ["title", "author", "uploaded", "engine",
                  "filename", "file_type", "size"]
_MODERN_FAMILY = ["entry_type", "title", "dl", "author", "uploaded"]

def _to_int(text: str) -> Optional[int]:
    try:
        return int(text)
    except ValueError:
        return None

class _ListingParser(html.parser.HTMLParser):
    """Scrape the CCAN listing table.

    Columns are identified by per-cell **evidence** (href signatures +
    cell-text shapes + an optional caller-supplied ``column_order``), never
    by position or column count:

    - ``ccan-view.pl?a=view&i=<id>``           -> title (+ entry id)
    - ``ccan-user.pl?a=info&i=<uid>``          -> author (+ author uid)
    - ``ccan-dl-auth.pl``                      -> download-link column
    - ``f1=ca`` / ``f1=ev``                    -> category / engine
    - Niveau text ``label (x,x) (n Votes)``    -> Niveau label/numeric/votes
    - plain integer                            -> votes/downloads
    - ``16.7 MB`` etc.                         -> size
    - ``2026-08-27``                           -> uploaded
    - ``Szenario|Objekt|Dokument|News|Programm`` -> entry_type

    Cells matching no evidence and no remaining layout slot are skipped and
    counted in ``parse_failures``; a row without any ``a=view&i=`` link is
    skipped and counted the same way. The legacy synthetic 7-column fixture
    and the live 5/11-column layouts all parse through this same path.
    """

    def __init__(self, column_order: Optional[list[str]] = None) -> None:
        super().__init__()
        self.column_order = list(column_order) if column_order else None
        self.entries: list[ListingEntry] = []
        self.page_number = 0
        self.total_pages = 0
        self.total_entries = 0
        self.parse_failures = 0
        self._in_tr = False
        self._in_td = False
        self._in_a = False
        self._cell_parts: list[str] = []
        self._cell_hrefs: list[str] = []
        self._row_cells: list[tuple[str, list[str]]] = []
        self._full_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._in_tr = True
            self._row_cells = []
        elif tag == "td" and self._in_tr:
            self._in_td = True
            self._cell_parts = []
            self._cell_hrefs = []
        elif tag == "a" and self._in_td:
            self._in_a = True
            href = a.get("href", "")
            if href:
                self._cell_hrefs.append(href)

    def handle_endtag(self, tag):
        if tag == "td" and self._in_td:
            self._row_cells.append(
                ("".join(self._cell_parts).strip(), list(self._cell_hrefs)))
            self._in_td = False
        elif tag == "a":
            self._in_a = False
        elif tag == "tr" and self._in_tr:
            self._finalize_row()
            self._in_tr = False

    def handle_data(self, data):
        # Every data chunk feeds the page-text accumulator (used for the
        # footer/pagination regexes) — the live listing renders the footer
        # line INSIDE a <td> (COLSPAN=12) with IMG/A tags between its tokens,
        # so only accumulating out-of-td text would leave total_entries 0 on
        # every live page. The cell buffer stays separate for the rows.
        self._full_text.append(data)
        if self._in_td:
            self._cell_parts.append(data)

    @staticmethod
    def _query_params(href: str) -> dict[str, str]:
        """Split a (possibly absolute) link href into its query params."""
        query = href.split("?", 1)[-1]
        params: dict[str, str] = {}
        for kv in query.split("&"):
            if "=" in kv:
                key, _, value = kv.partition("=")
                params[key] = value
        return params

    def _cell_column(self, text: str, hrefs: list[str]) -> Optional[str]:
        """Classify one cell's href/text evidence into a column name."""
        for h in hrefs:
            if self._query_params(h).get("a") == "view":
                return "title"
        for h in hrefs:
            if "ccan-user.pl" in h:
                return "author"
        for h in hrefs:
            if "ccan-dl-auth.pl" in h:
                return "dl"
        for h in hrefs:
            if "f1=ca" in h:
                return "category"
            if "f1=ev" in h:
                return "engine"
        if text == "":
            return None
        if _NIVEAU_RE.match(text):
            return "niveau"
        if _INT_RE.match(text):
            return "votes_or_downloads"
        if _SIZE_RE.match(text):
            return "size"
        if _DATE_RE.match(text):
            return "uploaded"
        if _TYPE_RE.match(text):
            return "entry_type"
        return None

    @staticmethod
    def _apply_column(entry: ListingEntry, column: str,
                      text: str, hrefs: list[str]) -> None:
        """Store one classified column's cell text into the entry."""
        if column == "title":
            entry.title = text
        elif column == "author":
            entry.author_nick = text
            for h in hrefs:
                if "ccan-user.pl" in h:
                    uid = _to_int(_ListingParser._query_params(h).get("i", ""))
                    if uid is not None:
                        entry.author_uid = uid
        elif column == "engine":
            entry.engine = text
        elif column == "category":
            entry.category = text
        elif column == "entry_type":
            entry.entry_type = text
        elif column == "filename":
            entry.filename = text
        elif column == "file_type":
            entry.file_type = text.lower().lstrip(".")
        elif column == "size":
            entry.size_label = text
        elif column == "uploaded":
            entry.uploaded = text
        elif column == "niveau":
            m = _NIVEAU_RE.match(text)
            if m:
                entry.niveau_label = m.group(1)
                entry.niveau_numeric = float(m.group(2).replace(",", "."))
                if m.group(3) is not None:
                    entry.votes = int(m.group(3))
        elif column == "votes":
            value = _to_int(text)
            if value is not None:
                entry.votes = value
        elif column == "downloads":
            value = _to_int(text)
            if value is not None:
                entry.downloads = value
        # "dl": recognized download-link column, no entry field.

    def _finalize_row(self) -> None:
        cells = self._row_cells
        if not cells:
            return

        # Layout family for the positional fallback (no caller column order).
        modern = False
        for _text, hrefs in cells:
            if any("ccan-dl-auth.pl" in h or "f1=" in h for h in hrefs):
                modern = True
                break
        if self.column_order is not None:
            candidates = self.column_order
        elif modern:
            candidates = _MODERN_FAMILY
        else:
            candidates = _LEGACY_FAMILY

        # --- Evidence classification per cell ---
        named: dict[int, str] = {}
        embedded_votes: Optional[int] = None
        plain_ints: list[tuple[int, str]] = []
        for idx, (text, hrefs) in enumerate(cells):
            column = self._cell_column(text, hrefs)
            if column == "votes_or_downloads":
                plain_ints.append((idx, text))
            elif column == "niveau":
                m = _NIVEAU_RE.match(text)
                if m and m.group(3) is not None:
                    embedded_votes = int(m.group(3))
                named[idx] = "niveau"
            elif column:
                named[idx] = column

        # Disambiguate plain integers into Votes / Downloads: anything
        # matching the Niveau cell's embedded "(n Votes)" is Votes; with a
        # caller column order the order position decides; otherwise the first
        # plain integer is Votes and the rest Downloads.
        if embedded_votes is not None:
            for idx, text in plain_ints:
                value = _to_int(text)
                named[idx] = "votes" if value == embedded_votes else "downloads"
        elif self.column_order is not None:
            for idx, _text in plain_ints:
                if idx < len(candidates) and candidates[idx] in ("votes", "downloads"):
                    named[idx] = candidates[idx]
        else:
            for pos, (idx, _text) in enumerate(plain_ints):
                named[idx] = "votes" if pos == 0 else "downloads"

        # --- Positional fill for cells without any evidence ---
        if self.column_order is not None:
            for idx, (_text, _hrefs) in enumerate(cells):
                if idx in named:
                    continue
                if idx >= len(candidates):
                    break
                name_at = candidates[idx]
                if name_at in named.values():
                    continue
                named[idx] = name_at
        else:
            unused = [name for name in candidates if name not in named.values()]
            for idx, (_text, _hrefs) in enumerate(cells):
                if idx in named:
                    continue
                if not unused:
                    break
                named[idx] = unused.pop(0)

        # Any still-unmapped cell was unidentifiable: skip it, count it.
        # Live enriched rows end with an empty spacer cell (<TD>&nbsp;</TD>;
        # no text, no hrefs) that carries no column evidence — it is layout,
        # not an unidentifiable column, so it must not inflate the failure
        # counter (Task-3 live-shape adaptation; L6's non-empty '???' cell
        # and view-less-row semantics are unchanged).
        for idx, (text, hrefs) in enumerate(cells):
            if idx not in named:
                if text == "" and not hrefs:
                    continue
                self.parse_failures += 1

        # --- Entry id must come from a view link, never another href ---
        ccan_id: Optional[int] = None
        for _text, hrefs in cells:
            for h in hrefs:
                params = self._query_params(h)
                if params.get("a") == "view":
                    ccan_id = _to_int(params.get("i", ""))
                    if ccan_id is not None:
                        break
            if ccan_id is not None:
                break
        if ccan_id is None:
            self.parse_failures += 1
            return

        entry = ListingEntry(
            ccan_id=ccan_id, title="", author_nick="", uploaded="",
            engine="", filename="", file_type="", size_label="",
        )
        for idx, (text, hrefs) in enumerate(cells):
            column = named.get(idx)
            if column is not None:
                self._apply_column(entry, column, text, hrefs)
        self.entries.append(entry)

def parse_listing(html_text: str,
                  column_order: Optional[list[str]] = None) -> ListingPage:
    """Parse one CCAN listing page. Returns a ListingPage.

    ``column_order`` optionally names the page's column sequence (the Phase-0
    enriched listing's known order); when omitted the layout family is
    detected from the row evidence (modern vs legacy synthetic).
    """
    parser = _ListingParser(column_order)
    parser.feed(html_text)
    full = " ".join(parser._full_text)
    # Pagination footer: "Seite x von y" / "Page x of y"
    m = re.search(r"(?:Seite|Page)\s+(\d+)\s+(?:von|of)\s+(\d+)", full)
    if m:
        parser.page_number = int(m.group(1))
        parser.total_pages = int(m.group(2))
    # Total entries from the entry range "… 1-30 von N": the "davon M unter
    # Niveau" clause must not shadow the real total.
    m = _ENTRY_RANGE_RE.search(full)
    if m:
        parser.total_entries = int(m.group(1))
    return ListingPage(
        entries=parser.entries,
        page_number=parser.page_number,
        total_pages=parser.total_pages,
        total_entries=parser.total_entries,
        parse_failures=parser.parse_failures,
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
