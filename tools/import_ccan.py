#!/usr/bin/env python3
"""Curated CCAN importer for LegacyClonk's content-community archive.

Driven by a TOML manifest (``ccan_curated.toml``). Each manifest entry
references one CCAN entry. The importer materializes curated packs into
``content-community/<destination>/`` with per-pack ``COPYING``,
``ATTRIBUTION.txt``, and ``ChangesLE.txt``.

Pipeline per entry: fetch -> unpack -> normalize -> validate. Idempotent
via ``ATTRIBUTION.txt``. Rolls back on validation failure.

Usage::

    python3 tools/import_ccan.py list
    python3 tools/import_ccan.py import 6421
    python3 tools/import_ccan.py import 6421 --force
    python3 tools/import_ccan.py verify-manifest

The ``c4group`` binary is resolved via the ``$C4GROUP`` env var (matches
``tools/make_*.sh``), falling back to ``LegacyClonk/build/c4group``
relative to this script's parent's parent.
"""
from __future__ import annotations

import argparse
import html.parser
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
LEGACYCLONK_DIR = SCRIPT_DIR.parent
DEFAULT_MANIFEST = SCRIPT_DIR / "ccan_curated.toml"
DEFAULT_C4GROUP = LEGACYCLONK_DIR / "build" / "c4group"
DEFAULT_CONTENT_COMMUNITY = LEGACYCLONK_DIR.parent / "content-community"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "ccan-import"
USER_AGENT = "LegacyClonk-preservation/0.1 (https://legacyclonk.github.io)"
DEFAULT_RATE_LIMIT = 2.0  # seconds between requests
CCAN_BASE = "https://ccan.de/cgi-bin/ccan"
CCAN_VIEW_URL = f"{CCAN_BASE}/ccan-view.pl?a=view&i={{id}}"
CCAN_DOWNLOAD_URL = f"{CCAN_BASE}/ccan-dl-auth.pl/{{id}}/{{filename}}"

# License text baked into per-pack COPYING when license = "CC-BY-NC-4.0".
CC_BY_NC_40_TEXT = (
    "This work is licensed under the Creative Commons Attribution-NonCommercial\n"
    "4.0 International License (CC BY-NC 4.0).\n"
    "\n"
    "You are free to share and adapt the material for non-commercial purposes,\n"
    "provided you give appropriate credit. See:\n"
    "    https://creativecommons.org/licenses/by-nc/4.0/\n"
)

REQUIRED_FIELDS = (
    "title",
    "ccan_id",
    "author_nick",
    "author_uid",
    "uploaded",
    "engine",
    "license",
    "license_rationale",
    "filename",
    "destination",
    "notes",
)

PACK_EXTENSIONS = (".c4d", ".c4f", ".c4s")

# ===========================================================================
# Data classes
# ===========================================================================

@dataclass
class ManifestEntry:
    ccan_id: int
    title: str
    author_nick: str
    author_uid: int
    uploaded: str
    engine: str  # "CR" | "LC" | "both"
    license: str
    license_rationale: str
    filename: str
    destination: str
    notes: str

    @property
    def view_url(self) -> str:
        return CCAN_VIEW_URL.format(id=self.ccan_id)

    @property
    def download_url(self) -> str:
        return CCAN_DOWNLOAD_URL.format(id=self.ccan_id, filename=self.filename)

@dataclass
class CcanMetadata:
    ccan_id: int
    title: str
    author_nick: str
    author_uid: int
    uploaded: str
    engine: str
    filename: str
    description_de: str
    description_us: str

# ===========================================================================
# c4group resolution
# ===========================================================================

def resolve_c4group() -> Path:
    """Resolve the c4group binary path or exit with a clear message."""
    env = os.environ.get("C4GROUP")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    if DEFAULT_C4GROUP.is_file():
        return DEFAULT_C4GROUP
    sys.exit(
        "c4group not found. Set $C4GROUP or build it via `cmake --build build`."
    )

# ===========================================================================
# Idempotency + rollback
# ===========================================================================

def _parse_attribution_id_and_uploaded(attr_text: str) -> tuple[Optional[int], Optional[str]]:
    """Extract ccan_id (from the Source URL) and uploaded date from ATTRIBUTION.txt."""
    import re
    id_match = re.search(r"i=(\d+)", attr_text)
    ccan_id = int(id_match.group(1)) if id_match else None
    up_match = re.search(r"^Uploaded:\s*(.+)$", attr_text, re.MULTILINE)
    uploaded = up_match.group(1).strip() if up_match else None
    return ccan_id, uploaded

def is_already_imported(
    entry: ManifestEntry,
    content_community: Path,
) -> bool:
    """True if content-community/<destination>/ATTRIBUTION.txt exists and
    its ccan_id + uploaded match the manifest entry."""
    attr = content_community / entry.destination / "ATTRIBUTION.txt"
    if not attr.is_file():
        return False
    existing_id, existing_uploaded = _parse_attribution_id_and_uploaded(
        attr.read_text(encoding="utf-8", errors="replace")
    )
    return (
        existing_id == entry.ccan_id
        and existing_uploaded == entry.uploaded
    )

def rollback_import(dest_dir: Path) -> None:
    """Delete a partial destination directory on failure."""
    if dest_dir.is_dir():
        shutil.rmtree(dest_dir)

# ===========================================================================
# Validate step (c4group <pack> -l integrity probe)
# ===========================================================================

def validate(pack_dir: Path, c4group: Path) -> tuple[bool, str]:
    """Run ``c4group <pack_dir> -l``. Returns (ok, combined_output)."""
    proc = subprocess.run(
        [str(c4group), str(pack_dir), "-l"],
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    return proc.returncode == 0, output

# ===========================================================================
# Normalize step (COPYING / ATTRIBUTION.txt / ChangesLE.txt)
# ===========================================================================

def _license_copying_text(entry: ManifestEntry) -> str:
    if entry.license == "CC-BY-NC-4.0":
        return CC_BY_NC_40_TEXT
    return (
        f"License: {entry.license}\n"
        f"\n"
        f"Rationale: {entry.license_rationale}\n"
        f"\n"
        f"The curator is responsible for ensuring the full license text is\n"
        f"reproduced here for any license other than CC-BY-NC-4.0.\n"
    )

def render_attribution(entry: ManifestEntry, metadata: CcanMetadata) -> str:
    """Render the per-pack ATTRIBUTION.txt content (spec section 'How attribution')."""
    return (
        f"Title:    {metadata.title or entry.title}\n"
        f"Author:   {metadata.author_nick or entry.author_nick} "
        f"(CCAN user ID {metadata.author_uid or entry.author_uid})\n"
        f"Uploaded: {entry.uploaded}\n"
        f"Source:   {entry.view_url}\n"
        f"License:  {entry.license} (see COPYING)\n"
        f"\n"
        f"Description (DE):\n"
        f"{metadata.description_de or '(not captured)'}\n"
        f"\n"
        f"Description (US):\n"
        f"{metadata.description_us or '(not captured)'}\n"
        f"\n"
        f"License rationale:\n"
        f"{entry.license_rationale}\n"
        f"\n"
        f"Imported by LegacyClonk import_ccan.py on "
        f"{time.strftime('%Y-%m-%d', time.gmtime())}.\n"
    )

def normalize(
    entry: ManifestEntry,
    metadata: CcanMetadata,
    pack_dir: Path,
) -> None:
    """Write COPYING, ATTRIBUTION.txt, and ChangesLE.txt into ``pack_dir``."""
    (pack_dir / "COPYING").write_text(_license_copying_text(entry), encoding="utf-8")
    (pack_dir / "ATTRIBUTION.txt").write_text(
        render_attribution(entry, metadata), encoding="utf-8"
    )
    (pack_dir / "ChangesLE.txt").write_text("", encoding="utf-8")

# ===========================================================================
# Unpack step (extension dispatch)
# ===========================================================================

def unpack(blob_path: Path, dest_dir: Path, c4group: Path) -> Path:
    """Unpack a downloaded blob into ``dest_dir``.

    Dispatches on the blob extension:
      - ``.c4d`` / ``.c4f`` / ``.c4s`` -> ``c4group <blob> -u`` (in-place
        unpack), then the resulting directory is moved into ``dest_dir``.
      - ``.zip`` -> ``zipfile.extractall(dest_dir)``.
      - ``.txt`` -> reject (text-only compilation entry).
      - anything else -> error.

    Returns the path to the unpacked pack directory inside ``dest_dir``.
    """
    suffix = blob_path.suffix.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)

    if suffix in PACK_EXTENSIONS:
        # c4group -u unpacks in place next to the blob.
        proc = subprocess.run(
            [str(c4group), str(blob_path), "-u"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"c4group unpack failed (exit {proc.returncode}):\n{proc.stderr}"
            )
        # The unpacked directory has the blob's stem (e.g. Hazard3D.c4s -> Hazard3D.c4s/).
        unpacked = blob_path.parent / blob_path.name
        if not unpacked.is_dir():
            raise RuntimeError(
                f"c4group unpack produced no directory at {unpacked}"
            )
        target = dest_dir / blob_path.name
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(unpacked), str(target))
        return target

    if suffix == ".zip":
        with zipfile.ZipFile(blob_path) as zf:
            zf.extractall(dest_dir)
        return dest_dir

    if suffix == ".txt":
        raise ValueError(
            "Text-only compilation entries are not packs; skip."
        )

    raise ValueError(f"Unsupported download extension: {suffix}")

# ===========================================================================
# HTTP fetch (rate-limited, retrying)
# ===========================================================================

_LAST_REQUEST_TIME: float = 0.0

def _rate_limit_sleep(rate_limit: float) -> None:
    global _LAST_REQUEST_TIME
    now = time.monotonic()
    wait = rate_limit - (now - _LAST_REQUEST_TIME)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_TIME = time.monotonic()

def fetch_url(
    url: str,
    rate_limit: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
) -> bytes:
    """Fetch a URL with rate limiting + exponential backoff on HTTP 429."""
    attempt = 0
    backoff = 1.0
    while True:
        _rate_limit_sleep(rate_limit)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                attempt += 1
                continue
            if e.code == 404:
                sys.exit(f"CCAN entry not found (HTTP 404): {url}")
            sys.exit(f"CCAN HTTP error {e.code}: {e.reason} ({url})")
        except urllib.error.URLError as e:
            raise ConnectionError(f"CCAN unreachable: {e.reason}") from e

def fetch_pack(
    entry: ManifestEntry,
    cache_dir: Path,
    rate_limit: float = DEFAULT_RATE_LIMIT,
) -> Path:
    """Download the pack blob to the cache dir. Returns the cached blob path."""
    dest_dir = cache_dir / str(entry.ccan_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    blob_path = dest_dir / entry.filename
    blob_path.write_bytes(fetch_url(entry.download_url, rate_limit=rate_limit))
    return blob_path

def fetch_metadata_html(
    entry: ManifestEntry,
    rate_limit: float = DEFAULT_RATE_LIMIT,
) -> str:
    """Fetch the CCAN metadata page HTML for the entry."""
    raw = fetch_url(entry.view_url, rate_limit=rate_limit)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")

# ===========================================================================
# CCAN metadata HTML parser
# ===========================================================================

class CcanMetadataParser(html.parser.HTMLParser):
    """Best-effort scraper for a CCAN per-entry metadata page.

    The CCAN metadata page is a table where each row is either
    ``<th>Label</th><td>value</td>`` (synthetic fixture) or
    ``<td>Label:</td><td>value</td>`` (live CCAN page). We capture the
    text of each value ``<td>`` keyed by the preceding label, plus the
    ``<title>`` tag for the page title.
    """

    def __init__(self) -> None:
        super().__init__()
        self.fields: dict[str, str] = {}
        self._label: Optional[str] = None
        self._collecting_label: bool = False
        self._expecting_value: bool = False
        self._in_td: bool = False
        self._in_title: bool = False
        self._title_parts: list[str] = []
        self._td_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "th":
            self._label = ""
            self._collecting_label = True
        elif tag == "td":
            self._in_td = True
            self._td_parts = []
        elif tag == "br" and self._in_td:
            self._td_parts.append("\n")
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "th":
            self._collecting_label = False
            self._expecting_value = True
        elif tag == "td":
            td_text = "".join(self._td_parts)
            if self._expecting_value and self._label is not None:
                self.fields[self._label] = td_text
                self._label = None
                self._expecting_value = False
            elif td_text.strip().endswith(":"):
                self._label = td_text.strip().rstrip(":").strip()
                self._expecting_value = True
            self._in_td = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._collecting_label:
            self._label += data
        elif self._in_td:
            self._td_parts.append(data)

def _extract_descriptions(fields: dict[str, str]) -> tuple[str, str]:
    raw_de = (
        fields.get("Beschreibung")
        or fields.get("Description (DE)")
        or fields.get("Beschreibung (DE)")
        or ""
    )
    raw_us = (
        fields.get("Description (US)")
        or fields.get("Description")
        or fields.get("Beschreibung (US)")
        or ""
    )
    if "[US]" in raw_de or "[DE]" in raw_de:
        parts = {"DE": "", "US": ""}
        pattern = r"\[(DE|US)\](.*?)(?=\[(?:DE|US)\]|$)"
        for m in re.finditer(pattern, raw_de, re.DOTALL):
            parts[m.group(1)] = m.group(2).strip()
        return parts["DE"], parts["US"]
    return raw_de.strip(), raw_us.strip()

def parse_ccan_metadata(html_text: str, ccan_id: int) -> CcanMetadata:
    """Parse a CCAN metadata HTML page into a ``CcanMetadata`` struct."""
    parser = CcanMetadataParser()
    parser.feed(html_text)
    f = parser.fields

    def get(*keys: str) -> str:
        for k in keys:
            if k in f:
                return " ".join(f[k].split())
        return ""

    title = " ".join("".join(parser._title_parts).split())
    for prefix in ("CCAN : Info zu ", "CCAN - ", "CCAN : ", "Info zu "):
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
            break
    if not title:
        title = get("Titel", "Title")

    author_raw = get("Autor", "Author")
    author_nick = author_raw
    author_uid = 0
    m = re.search(r"i=(\d+)", author_raw)
    if m:
        author_uid = int(m.group(1))
        author_nick = re.sub(r"\s*\(?\s*UID:?\s*\d+\s*\)?", "", author_raw).strip()
    else:
        m = re.search(r"\(?\s*UID:?\s*(\d+)\s*\)?", author_raw)
        if m:
            author_uid = int(m.group(1))
            author_nick = re.sub(
                r"\s*\(?\s*UID:?\s*\d+\s*\)?", "", author_raw
            ).strip()
        else:
            author_nick = re.sub(r"\s*/\s*n/a\s*$", "", author_raw).strip()

    uploaded = get("Zeit", "Datum", "Date", "Uploaded")
    engine = get("Engine-Version", "Engine")
    filename = get("Download", "Dateiname", "Filename")

    desc_de, desc_us = _extract_descriptions(f)

    return CcanMetadata(
        ccan_id=ccan_id,
        title=title,
        author_nick=author_nick,
        author_uid=author_uid,
        uploaded=uploaded,
        engine=engine,
        filename=filename,
        description_de=desc_de,
        description_us=desc_us,
    )

# ===========================================================================
# Manifest loading + validation
# ===========================================================================

def load_manifest(path: Path) -> list[ManifestEntry]:
    """Load and validate the curated manifest.

    Exits non-zero with a clear message on any of:
      - TOML parse error
      - Missing required field in an ``[entry.<id>]`` block
      - ``license = "unknown"``
      - Duplicate ``destination`` across entries
      - Entry block whose table key does not match its ``ccan_id`` field
    """
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Manifest parse error: {e}. Check `{path}` syntax.")
    except FileNotFoundError:
        sys.exit(f"Manifest not found: {path}")

    raw_entries = data.get("entry", {})
    if not raw_entries:
        sys.exit(f"Manifest `{path}` has no [entry.<id>] blocks.")

    entries: list[ManifestEntry] = []
    for block_key, block in raw_entries.items():
        if not isinstance(block, dict):
            sys.exit(f"Manifest entry `{block_key}` is not a table.")
        missing = [f for f in REQUIRED_FIELDS if f not in block]
        if missing:
            sys.exit(
                f"Manifest entry `{block_key}` is missing required field(s): "
                f"{', '.join(missing)}"
            )
        license_val = block["license"]
        if license_val == "unknown":
            sys.exit(
                f"Manifest entry `{block_key}` has license = \"unknown\". "
                f"Set a concrete license before importing."
            )
        try:
            entry = ManifestEntry(
                ccan_id=int(block["ccan_id"]),
                title=str(block["title"]),
                author_nick=str(block["author_nick"]),
                author_uid=int(block["author_uid"]),
                uploaded=str(block["uploaded"]),
                engine=str(block["engine"]),
                license=str(block["license"]),
                license_rationale=str(block["license_rationale"]),
                filename=str(block["filename"]),
                destination=str(block["destination"]),
                notes=str(block["notes"]),
            )
        except (ValueError, TypeError) as e:
            sys.exit(f"Manifest entry `{block_key}` has a typed-field error: {e}")

        # Block key must match the ccan_id (curator-consistency check).
        if str(block_key) != str(entry.ccan_id):
            sys.exit(
                f"Manifest entry table key `{block_key}` does not match its "
                f"`ccan_id = {entry.ccan_id}`."
            )
        entries.append(entry)

    check_duplicate_destinations(entries)
    return entries

def check_duplicate_destinations(entries: list[ManifestEntry]) -> None:
    """Exit non-zero if any two entries share a `destination`."""
    seen: dict[str, int] = {}
    for e in entries:
        if e.destination in seen:
            sys.exit(
                f"Duplicate destination `{e.destination}` in manifest: "
                f"entries {seen[e.destination]} and {e.ccan_id} both target it."
            )
        seen[e.destination] = e.ccan_id

# ===========================================================================
# Subcommand stubs (implemented in later tasks)
# ===========================================================================

def cmd_list(args: argparse.Namespace) -> int:
    entries = load_manifest(args.manifest)
    print(f"{len(entries)} curated entr{'y' if len(entries) == 1 else 'ies'}:")
    for e in entries:
        print(f"  [{e.ccan_id}] {e.title}  ->  content-community/{e.destination}/")
        print(f"      engine={e.engine}  license={e.license}")
    return 0

def _import_one(
    entry: ManifestEntry,
    content_community: Path,
    c4group: Path,
    force: bool,
    rate_limit: float,
) -> None:
    """Import a single manifest entry. Raises on failure (caller exits)."""
    dest_dir = content_community / entry.destination

    if not force and is_already_imported(entry, content_community):
        print(f"[{entry.ccan_id}] already imported, skipping "
              f"(use --force to override).")
        return

    if force and dest_dir.is_dir():
        rollback_import(dest_dir)

    if dest_dir.exists():
        sys.exit(
            f"Destination {dest_dir} already exists and is not a recognized "
            f"import. Remove it manually or use --force."
        )

    # 1. Fetch metadata + parse.
    print(f"[{entry.ccan_id}] fetching metadata...")
    metadata = parse_ccan_metadata(
        fetch_metadata_html(entry, rate_limit=rate_limit),
        entry.ccan_id,
    )

    # 2. Fetch pack blob.
    print(f"[{entry.ccan_id}] downloading {entry.filename}...")
    blob_path = fetch_pack(entry, CACHE_DIR, rate_limit=rate_limit)

    # 3. Unpack into the destination.
    print(f"[{entry.ccan_id}] unpacking...")
    dest_dir.mkdir(parents=True, exist_ok=False)
    try:
        unpack_path = unpack(blob_path, dest_dir, c4group)
        normalize(entry, metadata, dest_dir)
        if unpack_path.suffix.lower() in PACK_EXTENSIONS:
            print(f"[{entry.ccan_id}] validating (c4group -l)...")
            ok, output = validate(unpack_path, c4group)
            if not ok:
                rollback_import(dest_dir)
                sys.exit(
                    f"[{entry.ccan_id}] validation failed (c4group -l):\n{output}"
                )
    except (OSError, RuntimeError, ValueError) as e:
        rollback_import(dest_dir)
        sys.exit(f"[{entry.ccan_id}] import failed: {e}")

    print(f"[{entry.ccan_id}] imported -> {dest_dir}")

def cmd_import(args: argparse.Namespace) -> int:
    entries = load_manifest(args.manifest)
    by_id = {e.ccan_id: e for e in entries}
    c4group = resolve_c4group()
    rate_limit = getattr(args, "rate_limit", DEFAULT_RATE_LIMIT)

    for requested_id in args.entry_ids:
        if requested_id not in by_id:
            sys.exit(f"Entry ID {requested_id} not in manifest.")
        _import_one(
            by_id[requested_id],
            args.content_community,
            c4group,
            args.force,
            rate_limit,
        )
    return 0

def _compare_entry_to_metadata(
    entry: ManifestEntry,
    metadata: CcanMetadata,
) -> list[str]:
    diffs: list[str] = []
    if metadata.title and metadata.title != entry.title:
        diffs.append(
            f"title: manifest='{entry.title}' vs live='{metadata.title}'"
        )
    if metadata.author_nick and metadata.author_nick != entry.author_nick:
        diffs.append(
            f"author_nick: manifest='{entry.author_nick}' vs live='{metadata.author_nick}'"
        )
    if metadata.author_uid and metadata.author_uid != entry.author_uid:
        diffs.append(
            f"author_uid: manifest={entry.author_uid} vs live={metadata.author_uid}"
        )
    if metadata.uploaded and metadata.uploaded != entry.uploaded:
        diffs.append(
            f"uploaded: manifest='{entry.uploaded}' vs live='{metadata.uploaded}'"
        )
    if metadata.engine and metadata.engine != entry.engine:
        diffs.append(
            f"engine: manifest='{entry.engine}' vs live='{metadata.engine}'"
        )
    if metadata.filename and metadata.filename != entry.filename:
        diffs.append(
            f"filename: manifest='{entry.filename}' vs live='{metadata.filename}'"
        )
    return diffs

def cmd_verify_manifest(args: argparse.Namespace) -> int:
    """Validate manifest syntax + re-fetch live CCAN metadata to detect upstream changes."""
    entries = load_manifest(args.manifest)
    print(f"Manifest OK: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}.")
    rate_limit = getattr(args, "rate_limit", DEFAULT_RATE_LIMIT)
    discrepancies = 0
    for e in entries:
        print(f"[{e.ccan_id}] {e.title} -> content-community/{e.destination}/")
        try:
            html = fetch_metadata_html(e, rate_limit=rate_limit)
            m = parse_ccan_metadata(html, e.ccan_id)
            diffs = _compare_entry_to_metadata(e, m)
            if diffs:
                discrepancies += len(diffs)
                for d in diffs:
                    print(f"  WARNING: {d}")
            else:
                print("  OK (matches live CCAN metadata)")
        except (ConnectionError, OSError) as ex:
            print(f"  WARNING: could not fetch live metadata: {ex}")
            discrepancies += 1
    if discrepancies:
        print(f"\n{discrepancies} discrepancy/discrepancies found.")
        return 1
    print(f"\nAll {len(entries)} entries match live CCAN metadata.")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_ccan.py",
        description="Curated CCAN importer for LegacyClonk's content-community archive.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Path to the curated manifest (default: {DEFAULT_MANIFEST}).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List curated manifest entries.")
    p_list.set_defaults(func=cmd_list)

    p_imp = sub.add_parser("import", help="Import one or more manifest entries.")
    p_imp.add_argument("entry_ids", nargs="+", type=int, help="CCAN entry IDs to import.")
    p_imp.add_argument("--force", action="store_true", help="Re-import even if already imported.")
    p_imp.add_argument(
        "--content-community",
        type=Path,
        default=DEFAULT_CONTENT_COMMUNITY,
        help="Destination repo root (default: ../content-community).",
    )
    p_imp.add_argument(
        "--rate-limit",
        type=float,
        default=DEFAULT_RATE_LIMIT,
        help=f"Seconds between CCAN requests (default: {DEFAULT_RATE_LIMIT}).",
    )
    p_imp.set_defaults(func=cmd_import)

    p_ver = sub.add_parser(
        "verify-manifest",
        help="Validate manifest + re-fetch live CCAN metadata to detect upstream changes.",
    )
    p_ver.add_argument(
        "--rate-limit",
        type=float,
        default=DEFAULT_RATE_LIMIT,
        help=f"Seconds between CCAN requests (default: {DEFAULT_RATE_LIMIT}).",
    )
    p_ver.set_defaults(func=cmd_verify_manifest)

    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
