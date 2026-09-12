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
# Live listing Datum cell: "23.06.00 18:22" / "09.09.26 23:46". The time part
# is optional and either '[T ]' separated (the live pages use a space).
_NATIVE_DATE_RE = re.compile(
    r"^(\d{1,2})\.(\d{1,2})\.(\d{2})(?:[ T]\d{1,2}:\d{2})?$")
_TYPE_RE = re.compile(r"^(?:Szenario|Objekt|Dokument|News|Programm)$")
_INT_RE = re.compile(r"^-?\d+$")
# Type evidence carried by the live Typ column's IMG (the type is rendered as
# an image, never as cell text): the TITLE "Alles vom Typ Szenario anzeigen"
# or the src "/img/type-scenario.gif". The src stem is English, the TITLE
# German — both map onto the schema's canonical five labels.
_TYPE_TITLE_RE = re.compile(r"\bvom\s+Typ\s+(\w+)\s+anzeigen", re.IGNORECASE)
_TYPE_SRC_RE = re.compile(r"type-(\w+)\.gif")
_TYPE_LABELS = {
    "scenario": "Szenario", "szenario": "Szenario",
    "object": "Objekt", "objekt": "Objekt",
    "document": "Dokument", "dokument": "Dokument",
    "news": "News",
    "program": "Programm", "programm": "Programm",
}
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

def normalize_uploaded(raw: Optional[str]) -> Optional[str]:
    """Normalize a listing Datum cell to ISO ``YYYY-MM-DD``.

    The live listing renders ``DD.MM.YY HH:MM`` (e.g. ``09.09.26 23:46``);
    ISO input passes through unchanged. The 2-digit-year pivot is the
    standard POSIX/Excel convention: ``00``-``69`` -> ``20XX``, ``70``-``99``
    -> ``19XX``. The CCAN era never exercises the ``19XX`` branch: the whole
    Phase-0 dataset spans 2000-2026 (observed 2-digit years ``00``..``26``,
    nothing pre-2000) — the pivot only exists to stay honest outside this
    archive. Unparseable input -> None (the dataset stores null per the
    spec's "null if unparseable" pin).
    """
    if raw is None:
        return None
    raw = raw.strip()
    if _DATE_RE.match(raw):
        return raw
    m = _NATIVE_DATE_RE.match(raw)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    century = "20" if year <= 69 else "19"
    return f"{century}{year:02d}-{month:02d}-{day:02d}"

class _ListingParser(html.parser.HTMLParser):
    """Scrape the CCAN listing table.

    Columns are identified by per-cell **evidence** (href signatures +
    cell-text shapes + an optional caller-supplied ``column_order``), never
    by position or column count:

    - ``ccan-view.pl?a=view&i=<id>``           -> title (+ entry id)
    - Typ-column IMG (``type-<x>.gif`` / ``TITLE`` "Alles vom Typ X anzeigen")
      inside an ``f1=ca`` filter link          -> entry_type
    - ``ccan-user.pl?a=info&i=<uid>``          -> author (+ author uid)
    - ``ccan-dl-auth.pl``                      -> download-link column
    - ``f1=ca`` (with ``a=`` param)            -> category
    - ``f1=ev``                                -> engine
    - Niveau text ``label (x,x) (n Votes)``    -> Niveau label/numeric/votes
    - plain integer                            -> votes/downloads
    - ``16.7 MB`` etc.                         -> size
    - ``2026-08-27`` / ``09.09.26 23:46``      -> uploaded

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
        self._cell_imgs: list[tuple[str, str, str]] = []
        # (cell_text, hrefs, [(src, title, alt)]) per cell; the image
        # evidence lets the classifier recover the Typ column's type from
        # the live image-only rendering.
        self._row_cells = []  # type: list[tuple[str, list[str], list[tuple[str, str, str]]]]
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
            self._cell_imgs = []
        elif tag == "a" and self._in_td:
            self._in_a = True
            href = a.get("href", "")
            if href:
                self._cell_hrefs.append(href)
        elif tag == "img" and self._in_td:
            self._cell_imgs.append(
                (a.get("src", ""), a.get("title", ""), a.get("alt", "")))

    def handle_endtag(self, tag):
        if tag == "td" and self._in_td:
            self._row_cells.append(
                ("".join(self._cell_parts).strip(),
                 list(self._cell_hrefs), list(self._cell_imgs)))
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

    @staticmethod
    def _canonical_type(name: str) -> str:
        return _TYPE_LABELS.get(name.lower(), name)

    @staticmethod
    def _type_from_imgs(imgs: list[tuple[str, str, str]]) -> Optional[str]:
        """Recover the Typ-column type from a cell's IMG evidence.

        The live listing renders the type as an image inside an ``f1=ca``
        filter link; the type rides in the IMG's TITLE ("Alles vom Typ
        Szenario anzeigen") or src ("/img/type-scenario.gif"). Returns the
        canonical schema label or None when nothing looks like a type image.
        """
        for _src, title, _alt in imgs:
            m = _TYPE_TITLE_RE.search(title or "")
            if m:
                return _ListingParser._canonical_type(m.group(1))
            m = _TYPE_SRC_RE.search(_src or "")
            if m:
                return _ListingParser._canonical_type(m.group(1))
        return None

    def _cell_column(self, text: str, hrefs: list[str],
                     imgs: list[tuple[str, str, str]]) -> Optional[str]:
        """Classify one cell's href/text/image evidence into a column name."""
        for h in hrefs:
            if self._query_params(h).get("a") == "view":
                return "title"
        if self._type_from_imgs(imgs) is not None:
            # Live Typ column: an <A HREF="ccan-view.pl?f1=ca&m1=e&v1=N-0">
            # filter link wrapping the type image — the type is in the IMG
            # TITLE/src, never in cell text. The f1=ca href alone would
            # mis-classify this cell as a duplicate category filter link
            # (the real category cell carries an added "a=" param).
            return "entry_type"
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
        if _DATE_RE.match(text) or _NATIVE_DATE_RE.match(text):
            return "uploaded"
        if _TYPE_RE.match(text):
            return "entry_type"
        return None

    @staticmethod
    def _apply_column(entry: ListingEntry, column: str,
                      text: str, hrefs: list[str],
                      imgs: list[tuple[str, str, str]]) -> None:
        """Store one classified column's cell evidence into the entry."""
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
            # Live rows carry only the type image (TITLE/src evidence);
            # the synthetic fixtures carry the type as plain cell text.
            entry.entry_type = (
                _ListingParser._type_from_imgs(imgs)
                or (text if _TYPE_RE.match(text) else ""))
        elif column == "filename":
            entry.filename = text
        elif column == "file_type":
            entry.file_type = text.lower().lstrip(".")
        elif column == "size":
            entry.size_label = text
        elif column == "uploaded":
            # ISO YYYY-MM-DD per the dataset schema; the live German Datum
            # cells ("23.06.00 18:22") are normalized at parse time (see
            # normalize_uploaded); "" stays empty for the dataset's null.
            entry.uploaded = normalize_uploaded(text) or ""
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
        for _text, hrefs, _imgs in cells:
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
        for idx, (text, hrefs, imgs) in enumerate(cells):
            column = self._cell_column(text, hrefs, imgs)
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
            for idx, (_text, _hrefs, _imgs) in enumerate(cells):
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
            for idx, (_text, _hrefs, _imgs) in enumerate(cells):
                if idx in named:
                    continue
                if not unused:
                    break
                named[idx] = unused.pop(0)

        # Any still-unmapped cell was unidentifiable: skip it, count it.
        # Live enriched rows end with an empty spacer cell (<TD>&nbsp;</TD>;
        # no text, no hrefs, no images) that carries no column evidence — it
        # is layout, not an unidentifiable column, so it must not inflate the
        # failure counter (Task-3 live-shape adaptation; L6's non-empty '???'
        # cell and view-less-row semantics are unchanged).
        for idx, (text, hrefs, imgs) in enumerate(cells):
            if idx not in named:
                if text == "" and not hrefs and not imgs:
                    continue
                self.parse_failures += 1

        # --- Entry id must come from a view link, never another href ---
        ccan_id: Optional[int] = None
        for _text, hrefs, _imgs in cells:
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
        for idx, (text, hrefs, imgs) in enumerate(cells):
            column = named.get(idx)
            if column is not None:
                self._apply_column(entry, column, text, hrefs, imgs)
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
