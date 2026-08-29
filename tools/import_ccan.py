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
import hashlib
import html.parser
import json
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
from dataclasses import dataclass, field
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

# Smoke scenario template (C4Script — tabs for indentation per .editorconfig).
# Literal braces are doubled ({{ }}) so str.format() leaves them intact; only
# {pack_name} is a real substitution placeholder.
SMOKE_SCRIPT_TEMPLATE = (
    "#strict 2\n"
    "\n"
    "static g_iStep;\n"
    "\n"
    "protected func Initialize()\n"
    "{{\n"
    "\tg_iStep = 0;\n"
    "\tAddEffect(\"RunTest\", this, 1, 35, this);\n"
    "\treturn true;\n"
    "}}\n"
    "\n"
    "func FxRunTestStart(target, effect) {{ return 1; }}\n"
    "\n"
    "func FxRunTestTimer(object target, int effect, int timer)\n"
    "{{\n"
    "\tif (g_iStep == 0)\n"
    "\t{{\n"
    "\t\tLog(\"{pack_name} PASS\");\n"
    "\t\tGameOver();\n"
    "\t}}\n"
    "\t++g_iStep;\n"
    "\treturn 1;\n"
    "}}\n"
)

# ===========================================================================
# Data classes
# ===========================================================================

@dataclass
class SmokeConfig:
    """Per-entry smoke gate configuration (the [entry.<id>.smoke] sub-table)."""
    ticks: int = 350
    skip: bool = False
    curator_script: bool = False


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
    requires: list[str] = field(default_factory=list)
    smoke: SmokeConfig = field(default_factory=SmokeConfig)

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


@dataclass
class ImportResult:
    """Outcome of importing one manifest entry."""
    status: str  # "imported" | "skipped"
    metadata: Optional[CcanMetadata] = None
    blob_path: Optional[Path] = None


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file (streaming)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

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
            # Parse requires (optional, default []).
            requires_raw = block.get("requires", [])
            if not isinstance(requires_raw, list):
                sys.exit(
                    f"Manifest entry `{block_key}`: `requires` must be a list of strings."
                )
            requires = [str(r) for r in requires_raw]

            # Parse smoke sub-table (optional, defaults via SmokeConfig).
            smoke_block = block.get("smoke", {})
            if not isinstance(smoke_block, dict):
                sys.exit(
                    f"Manifest entry `{block_key}`: `[entry.<id>.smoke]` must be a table."
                )
            smoke = SmokeConfig(
                ticks=int(smoke_block.get("ticks", 350)),
                skip=bool(smoke_block.get("skip", False)),
                curator_script=bool(smoke_block.get("curator_script", False)),
            )

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
                requires=requires,
                smoke=smoke,
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
# Dependency resolution (requires closure + cycle detection)
# ===========================================================================

def resolve_requires(
    entry: ManifestEntry,
    entries: list[ManifestEntry],
    content_community: Path,
) -> list[str]:
    """Resolve the transitive `requires` closure for ``entry``.

    Returns an ordered list of dependency directory names (each a
    ``content-community/<dep>/`` directory). Fails fast (SystemExit) if a
    declared dependency's directory does not exist on disk. Detects
    dependency cycles via a path-tracking visited set.
    """
    by_dest = {e.destination: e for e in entries}
    visited: set[str] = set()
    order: list[str] = []

    def visit(dep: str, path: tuple[str, ...]) -> None:
        if dep in path:
            cycle = " -> ".join(path + (dep,))
            sys.exit(f"Dependency cycle detected: {cycle}")
        if dep in visited:
            return
        dep_dir = content_community / dep
        if not dep_dir.is_dir():
            sys.exit(
                f"Manifest entry {entry.ccan_id} requires '{dep}' but "
                f"content-community/{dep}/ does not exist. "
                f"Import the dependency first."
            )
        visited.add(dep)
        order.append(dep)
        dep_entry = by_dest.get(dep)
        if dep_entry:
            for transitive in dep_entry.requires:
                visit(transitive, path + (dep,))

    for r in entry.requires:
        visit(r, (entry.destination,))
    return order

# ===========================================================================
# Smoke artefact emission (tier-A marker + tier-B smoke scenario)
# ===========================================================================

def _minimal_bmp() -> bytes:
    """Return a minimal 1x1 24-bit BMP file (58 bytes)."""
    width, height = 1, 1
    row = b"\x00\x00\x00"  # 1 pixel, BGR
    padded_row = row + b"\x00"  # pad to 4-byte boundary
    pixel_data = padded_row * height
    file_size = 54 + len(pixel_data)
    return (
        b"BM"
        + file_size.to_bytes(4, "little")
        + b"\x00\x00\x00\x00"
        + (54).to_bytes(4, "little")
        + (40).to_bytes(4, "little")
        + width.to_bytes(4, "little", signed=True)
        + height.to_bytes(4, "little", signed=True)
        + (1).to_bytes(2, "little")
        + (24).to_bytes(2, "little")
        + (0).to_bytes(4, "little")
        + len(pixel_data).to_bytes(4, "little")
        + (2835).to_bytes(4, "little")
        + (2835).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + pixel_data
    )


def _collect_pack_definitions(directory: Path) -> list[str]:
    """Return bare filenames of .c4d/.c4f/.c4s packs directly inside directory.

    Skips ``Tests.c4f`` (the test folder, not a loadable definition).
    """
    defs = []
    for entry in sorted(directory.iterdir()):
        if entry.name == "Tests.c4f":
            continue
        if entry.suffix.lower() in PACK_EXTENSIONS:
            defs.append(entry.name)
    return defs


def _build_smoke_definitions(
    unpack_path: Path,
    requires_closure: list[str],
    content_community: Path,
) -> list[str]:
    """Build the list of definition pack filenames for the smoke scenario's
    [Definitions] block.

    - For a .c4d/.c4f pack: the pack itself.
    - For a .c4s pack: the .c4d/.c4f sub-defs inside it.
    - Plus each required dep's top-level packs.
    """
    defs: list[str] = []
    suffix = unpack_path.suffix.lower()
    if suffix in (".c4d", ".c4f"):
        defs.append(unpack_path.name)
    elif suffix == ".c4s":
        defs.extend(_collect_pack_definitions(unpack_path))
    for dep in requires_closure:
        dep_dir = content_community / dep
        defs.extend(_collect_pack_definitions(dep_dir))
    return defs


def emit_smoke_artefacts(
    entry: ManifestEntry,
    dest_dir: Path,
    unpack_path: Path,
    requires_closure: list[str],
    content_community: Path,
) -> None:
    """Emit tier-A struct marker + tier-B smoke scenario into Tests.c4f/.

    No-ops when ``entry.smoke.skip`` is True. Preserves an existing
    Script.c when ``entry.smoke.curator_script`` is True.
    """
    if entry.smoke.skip:
        return

    tests_dir = dest_dir / "Tests.c4f"
    tests_dir.mkdir(parents=True, exist_ok=True)

    pack_name = entry.destination  # e.g. "Hazard3D"

    # Tier A: struct marker (absolute pack path).
    marker = tests_dir / f"{pack_name}Struct.txt"
    marker.write_text(
        str(unpack_path.resolve()) + "\n", encoding="utf-8"
    )

    # Tier B: smoke scenario directory.
    smoke_dir = tests_dir / f"{pack_name}Smoke.c4s"
    smoke_dir.mkdir(parents=True, exist_ok=True)

    # [Definitions] block.
    defs = _build_smoke_definitions(
        unpack_path, requires_closure, content_community
    )
    defs_block = "".join(
        f"Definition{i + 1}={d}\n" for i, d in enumerate(defs)
    )

    # Scenario.txt.
    scenario_txt = (
        f"[Head]\n"
        f"Title={pack_name} Smoke\n"
        f"Icon=43\n"
        f"\n"
        f"[Definitions]\n"
        f"{defs_block}"
        f"\n"
        f"[Game]\n"
        f"Timeout={entry.smoke.ticks}\n"
    )
    (smoke_dir / "Scenario.txt").write_text(
        scenario_txt, encoding="utf-8"
    )

    # Title.txt.
    (smoke_dir / "Title.txt").write_text(
        f"{pack_name} Smoke\n", encoding="utf-8"
    )

    # Map.bmp — minimal 1x1 BMP.
    (smoke_dir / "Map.bmp").write_bytes(_minimal_bmp())

    # Script.c — generic template, or curator-preserved.
    script_path = smoke_dir / "Script.c"
    if entry.smoke.curator_script and script_path.exists():
        return  # preserve curator's Script.c
    script_path.write_text(
        SMOKE_SCRIPT_TEMPLATE.format(pack_name=pack_name),
        encoding="utf-8",
    )

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

def _fetch_metadata(
    entry: ManifestEntry,
    rate_limit: float,
    snapshot_dir: Optional[Path] = None,
) -> str:
    """Fetch metadata HTML, preferring a snapshot's raw.html if available."""
    if snapshot_dir is not None:
        raw_path = snapshot_dir / "entries" / str(entry.ccan_id) / "raw.html"
        if raw_path.is_file():
            return raw_path.read_text(encoding="utf-8", errors="replace")
    return fetch_metadata_html(entry, rate_limit=rate_limit)


def _fetch_blob(
    entry: ManifestEntry,
    cache_dir: Path,
    rate_limit: float,
    snapshot_dir: Optional[Path] = None,
) -> Path:
    """Resolve the pack blob, preferring a snapshot blob if available."""
    if snapshot_dir is not None:
        blob_path = (
            snapshot_dir / "entries" / str(entry.ccan_id) / entry.filename)
        if blob_path.is_file():
            return blob_path
    return fetch_pack(entry, cache_dir, rate_limit=rate_limit)


def _import_one(
    entry: ManifestEntry,
    entries: list[ManifestEntry],
    content_community: Path,
    c4group: Path,
    force: bool,
    rate_limit: float,
    snapshot_dir: Optional[Path] = None,
) -> ImportResult:
    """Import a single manifest entry. Raises SystemExit on failure."""
    dest_dir = content_community / entry.destination

    if not force and is_already_imported(entry, content_community):
        print(f"[{entry.ccan_id}] already imported, skipping "
              f"(use --force to override).")
        return ImportResult(status="skipped")

    if force and dest_dir.is_dir():
        rollback_import(dest_dir)

    if dest_dir.exists():
        sys.exit(
            f"Destination {dest_dir} already exists and is not a recognized "
            f"import. Remove it manually or use --force."
        )

    # Fail fast on missing dependencies before any network fetch.
    requires_closure = resolve_requires(entry, entries, content_community)

    # 1. Fetch metadata + parse.
    print(f"[{entry.ccan_id}] fetching metadata...")
    metadata = parse_ccan_metadata(
        _fetch_metadata(entry, rate_limit, snapshot_dir),
        entry.ccan_id,
    )

    # 2. Fetch pack blob.
    print(f"[{entry.ccan_id}] downloading {entry.filename}...")
    blob_path = _fetch_blob(entry, CACHE_DIR, rate_limit, snapshot_dir)

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

    # 4. Emit tier-A struct marker + tier-B smoke scenario.
    emit_smoke_artefacts(
        entry=entry,
        dest_dir=dest_dir,
        unpack_path=unpack_path,
        requires_closure=requires_closure,
        content_community=content_community,
    )

    print(f"[{entry.ccan_id}] imported -> {dest_dir}")
    return ImportResult(
        status="imported", metadata=metadata, blob_path=blob_path)

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
            entries,
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

# ===========================================================================
# License triage (Phase 2 discover)
# ===========================================================================

TRIAGE_RULES_PATH = SCRIPT_DIR / "ccan_license_triage.toml"


def load_triage_rules(path: Path) -> list[dict]:
    """Load the [[rule]] list from ccan_license_triage.toml."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"Triage rules not found: {path}")
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Triage rules parse error: {e}")
    return list(data.get("rule", []))


def run_triage(meta: dict, rules: list[dict]) -> tuple[str, str]:
    """Return (verdict, matched_keyword). First matching rule wins.

    Searches the concatenated description_de + description_us + comments
    fields (case-insensitive substring match).
    """
    haystack = " ".join([
        str(meta.get("description_de", "")),
        str(meta.get("description_us", "")),
        str(meta.get("comments", "")),
    ]).lower()
    for rule in rules:
        kw = rule["keyword"].lower()
        if kw and kw in haystack:
            return rule["verdict"], rule["keyword"]
    return "ok", ""


def slugify(title: str) -> str:
    """Strip a title to an alphanumeric slug (no spaces, no punctuation)."""
    slug = re.sub(r"[^A-Za-z0-9]+", "", title or "")
    if not slug:
        slug = "ccan"
    return slug


def engine_supports(entry_engine: str, wanted: str) -> bool:
    """True if entry's engine field is compatible with the wanted engine."""
    e = (entry_engine or "").upper()
    w = (wanted or "").upper()
    if not e:
        return True
    if "BOTH" in e or w in e:
        return True
    return False


def _render_discovered_manifest(candidates: list[dict]) -> str:
    """Render a candidate manifest in the ccan_curated.toml schema."""
    lines = [
        "# Candidate manifest emitted by `import_ccan.py discover`.\n"
        "# Review in a PR: remove false positives, correct licenses, add "
        "requires + notes.\n"
        "# `license = \"unknown\"` is rejected at import time — set a "
        "concrete license before importing.\n\n",
    ]
    for c in candidates:
        lines.append(f"[entry.{c['ccan_id']}]\n")
        for field in (
            "title", "ccan_id", "author_nick", "author_uid", "uploaded",
            "engine", "license", "license_rationale", "filename",
            "destination", "notes",
        ):
            v = c.get(field, "")
            if isinstance(v, str):
                lines.append(f'{field} = "{v}"\n')
            else:
                lines.append(f"{field} = {v}\n")
        lines.append("\n")
    return "".join(lines)


def cmd_discover(args: argparse.Namespace) -> int:
    """Phase 2: triage a CCAN snapshot into a candidate import manifest."""
    snapshot_dir = Path(args.snapshot_dir).expanduser()
    index_path = snapshot_dir / "index.jsonl"
    if not index_path.is_file():
        sys.exit(
            f"Snapshot index not found: {index_path}\n"
            f"Run `mirror_ccan.py mirror --snapshot-dir {snapshot_dir}` first.")

    rules = load_triage_rules(TRIAGE_RULES_PATH)
    engine_filter = args.engine
    max_size_bytes = int(args.max_size * 1024 * 1024) if args.max_size else 0

    candidates: list[dict] = []
    skip_lines: list[str] = []
    seen_slugs: dict[str, int] = {}
    n_total = 0

    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            meta = json.loads(line)
        except json.JSONDecodeError:
            continue
        n_total += 1
        ccan_id = meta.get("ccan_id")
        title = meta.get("title", "")
        filename = meta.get("filename", "")
        engine = meta.get("engine", "")

        verdict, matched_kw = run_triage(meta, rules)

        # Filters.
        if engine_filter and not engine_supports(engine, engine_filter):
            skip_lines.append(
                f"{ccan_id}\tengine_filter\t{engine}\t{title}")
            continue
        if filename.lower().endswith(".txt"):
            skip_lines.append(
                f"{ccan_id}\ttext_only\t-\t{title}")
            continue
        if max_size_bytes and int(meta.get("blob_size", 0)) > max_size_bytes:
            skip_lines.append(
                f"{ccan_id}\tsize_filter\t{meta.get('blob_size')}\t{title}")
            continue
        if verdict == "skip":
            skip_lines.append(
                f"{ccan_id}\tskip\t{matched_kw}\t{title}")
            continue

        # Destination slug with collision suffix.
        slug = slugify(title)
        if slug in seen_slugs:
            slug = f"{slug}-{ccan_id}"
            skip_lines.append(
                f"{ccan_id}\tdestination_collision\t{slug}\t{title}")
        seen_slugs[slug] = ccan_id

        license_val = "CC-BY-NC-4.0" if verdict == "ok" else "unknown"
        rationale = (
            f"Triage verdict: {verdict}. "
            f"Matched keyword: '{matched_kw}'. "
            f"Description: '{(meta.get('description_de') or meta.get('description_us') or '')[:120]}'"
            if matched_kw
            else f"Triage verdict: ok. No skip/ambiguous keyword matched. "
                f"Default CC BY-NC 4.0 applies."
        )
        candidates.append({
            "title": title,
            "ccan_id": ccan_id,
            "author_nick": meta.get("author_nick", ""),
            "author_uid": meta.get("author_uid", 0),
            "uploaded": meta.get("uploaded", ""),
            "engine": engine,
            "license": license_val,
            "license_rationale": rationale,
            "filename": filename,
            "destination": slug,
            "notes": "",
        })

    out_manifest = Path(args.out_manifest)
    out_manifest.write_text(
        _render_discovered_manifest(candidates), encoding="utf-8")
    out_skip = Path(args.out_skip)
    out_skip.write_text(
        "\n".join(skip_lines) + ("\n" if skip_lines else ""), encoding="utf-8")

    print(f"{n_total} entries mirrored, {len(candidates)} candidates, "
          f"{len(skip_lines)} skipped.")
    return 0


# ===========================================================================
# Master ATTRIBUTION.toml index (Phase 3 bulk-import)
# ===========================================================================

MASTER_INDEX_FIELDS = (
    "ccan_id", "title", "author_nick", "author_uid", "uploaded",
    "source_url", "download_url", "filename", "license",
    "license_rationale", "sha256", "imported_at",
)


def load_master_index(path: Path) -> dict:
    """Load content-community/ATTRIBUTION.toml. Returns {} if absent."""
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Master index parse error: {e}")


def write_master_index(path: Path, packs: dict) -> None:
    """Write the master index, sorted by destination for diff stability."""
    header = (
        "# Master attribution index for bulk-imported packs.\n"
        "# Generated by `import_ccan.py bulk-import`. Per-pack "
        "ATTRIBUTION.txt + COPYING\n"
        "# convention is unchanged; this index is an additive, diffable, "
        "machine-readable\n"
        "# summary. Sorted by `destination` for diff stability.\n\n"
    )
    lines = [header]
    for dest in sorted(packs):
        block = packs[dest]
        lines.append(f"[pack.{dest}]\n")
        for f in MASTER_INDEX_FIELDS:
            if f not in block:
                continue
            v = block[f]
            if isinstance(v, str):
                lines.append(f'{f} = "{v}"\n')
            else:
                lines.append(f"{f} = {v}\n")
        lines.append("\n")
    path.write_text("".join(lines), encoding="utf-8")


def cmd_bulk_import(args: argparse.Namespace) -> int:
    """Phase 3: bulk-import from a curator-approved manifest + snapshot."""
    entries = load_manifest(args.manifest)
    c4group = resolve_c4group()
    content_community = args.content_community
    content_community.mkdir(parents=True, exist_ok=True)
    snapshot_dir = (
        Path(args.snapshot_dir).expanduser() if args.snapshot_dir else None)
    rate_limit = args.rate_limit

    master_path = content_community / "ATTRIBUTION.toml"
    # Advisory lock on a sibling of the master index.
    try:
        import fcntl
        lock_path = content_community / "ATTRIBUTION.toml.lock"
        lock_file = open(lock_path, "w")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock_file.close()
            sys.exit(
                f"content-community/ATTRIBUTION.toml is locked by another "
                f"bulk-import run.")
    except ImportError:
        lock_file = None

    master = load_master_index(master_path)
    packs: dict = dict(master.get("pack", {}))

    failures_path = Path(args.failures_log)
    # Pre-flight: ensure failures log is writable.
    try:
        failures_path.write_text("", encoding="utf-8")
    except OSError as e:
        sys.exit(f"Failures log not writable ({failures_path}): {e}")

    failures: list[dict] = []
    imported = 0
    for entry in entries:
        try:
            result = _import_one(
                entry=entry,
                entries=entries,
                content_community=content_community,
                c4group=c4group,
                force=False,
                rate_limit=rate_limit,
                snapshot_dir=snapshot_dir,
            )
        except SystemExit as e:
            failures.append({
                "ccan_id": entry.ccan_id,
                "destination": entry.destination,
                "error": str(e),
            })
            print(f"[{entry.ccan_id}] FAILED: {e}", file=sys.stderr)
            continue
        if result.status == "skipped":
            print(f"[{entry.ccan_id}] already imported, skipping.")
            continue
        # Success — update master index block.
        sha = sha256_file(result.blob_path) if result.blob_path else ""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        packs[entry.destination] = {
            "ccan_id": entry.ccan_id,
            "title": (result.metadata.title if result.metadata else entry.title),
            "author_nick": (result.metadata.author_nick
                            if result.metadata else entry.author_nick),
            "author_uid": (result.metadata.author_uid
                           if result.metadata else entry.author_uid),
            "uploaded": entry.uploaded,
            "source_url": entry.view_url,
            "download_url": entry.download_url,
            "filename": entry.filename,
            "license": entry.license,
            "license_rationale": entry.license_rationale,
            "sha256": sha,
            "imported_at": today,
        }
        write_master_index(master_path, packs)
        imported += 1
        print(f"[{entry.ccan_id}] imported -> "
              f"{content_community / entry.destination}")

    if failures:
        failures_path.write_text(
            "\n".join(json.dumps(f, ensure_ascii=False) for f in failures)
            + "\n", encoding="utf-8")

    if lock_file is not None:
        lock_file.close()

    print(f"\n{imported} entries imported, {len(failures)} failure(s)."
          + (f" See {failures_path}." if failures else ""))
    if failures:
        return 1
    return 0


# ===========================================================================
# verify-imports (Phase 4, stretch)
# ===========================================================================

def cmd_verify_imports(args: argparse.Namespace) -> int:
    """Phase 4: re-fetch CCAN blobs and diff sha256 vs the master index."""
    content_community = args.content_community
    master_path = content_community / "ATTRIBUTION.toml"
    if not master_path.is_file():
        sys.exit("Run `bulk-import` first to generate the master index.")
    master = load_master_index(master_path)
    packs = master.get("pack", {})
    snapshot_dir = (
        Path(args.snapshot_dir).expanduser() if args.snapshot_dir else None)
    rate_limit = args.rate_limit

    changed, missing, local_missing, unchanged, unknown = (
        [], [], [], [], [])

    for dest in sorted(packs):
        block = packs[dest]
        ccan_id = block.get("ccan_id")
        local_dir = content_community / dest
        if not local_dir.is_dir():
            local_missing.append((dest, block))
            continue
        # Resolve blob: snapshot first, else HTTP.
        blob_bytes = None
        err = None
        if snapshot_dir is not None:
            blob_path = (snapshot_dir / "entries" / str(ccan_id)
                         / block.get("filename", ""))
            if blob_path.is_file():
                blob_bytes = blob_path.read_bytes()
        if blob_bytes is None:
            try:
                blob_bytes = fetch_url(
                    block.get("download_url", ""), rate_limit=rate_limit)
            except SystemExit as e:
                err = str(e)
            except (ConnectionError, OSError) as e:
                err = str(e)
        if blob_bytes is None:
            if err and "404" in err:
                missing.append((dest, block))
            else:
                unknown.append((dest, block, err))
            continue
        new_sha = hashlib.sha256(blob_bytes).hexdigest()
        if new_sha == block.get("sha256"):
            unchanged.append(dest)
        else:
            changed.append((dest, block.get("sha256"), new_sha))

    # Emit markdown report.
    report_path = Path("ccan_verify_imports_report.md")
    r = []
    r.append("# CCAN verify-imports report\n\n")
    r.append(f"- unchanged: {len(unchanged)}\n")
    r.append(f"- changed: {len(changed)}\n")
    r.append(f"- missing (CCAN deleted): {len(missing)}\n")
    r.append(f"- local_missing (master index out of sync): "
             f"{len(local_missing)}\n")
    r.append(f"- unknown (could not verify): {len(unknown)}\n\n")
    if changed:
        r.append("## Changed (sha256 mismatch)\n\n")
        for dest, old, new in changed:
            r.append(f"- `{dest}`: `{old}` -> `{new}`\n")
        r.append("\n")
    if missing:
        r.append("## Missing (CCAN deleted)\n\n")
        for dest, block in missing:
            r.append(f"- `{dest}` (ccan_id={block.get('ccan_id')})\n")
        r.append("\n")
    if local_missing:
        r.append("## Local missing (master index out of sync)\n\n")
        for dest, block in local_missing:
            r.append(f"- `{dest}` (ccan_id={block.get('ccan_id')})\n")
        r.append("\n")
    if unknown:
        r.append("## Unknown (could not verify)\n\n")
        for dest, block, err in unknown:
            r.append(f"- `{dest}`: {err}\n")
        r.append("\n")
    report_path.write_text("".join(r), encoding="utf-8")

    print(f"verify-imports: {len(unchanged)} unchanged, {len(changed)} "
          f"changed, {len(missing)} missing, {len(local_missing)} "
          f"local_missing, {len(unknown)} unknown. "
          f"Report: {report_path}")
    if changed or missing or local_missing:
        return 1
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

    p_disc = sub.add_parser(
        "discover",
        help="Triage a CCAN snapshot into a candidate import manifest.",
    )
    p_disc.add_argument(
        "--snapshot-dir",
        required=True,
        help="Path to the ccan-snapshot/ directory (mirror_ccan.py output).",
    )
    p_disc.add_argument(
        "--engine",
        default="LC",
        help="Drop entries not compatible with this engine (default: LC).",
    )
    p_disc.add_argument(
        "--rate-limit",
        type=float,
        default=DEFAULT_RATE_LIMIT,
        help=f"Seconds between requests (default: {DEFAULT_RATE_LIMIT}).",
    )
    p_disc.add_argument(
        "--max-size",
        type=float,
        default=0.0,
        help="Drop entries larger than N MB (0 = no limit).",
    )
    p_disc.add_argument(
        "--out-manifest",
        default="ccan_discovered.toml",
        help="Candidate manifest output path (default: ccan_discovered.toml).",
    )
    p_disc.add_argument(
        "--out-skip",
        default="ccan_triage_skip.txt",
        help="Skip/audit log output path (default: ccan_triage_skip.txt).",
    )
    p_disc.set_defaults(func=cmd_discover)

    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
