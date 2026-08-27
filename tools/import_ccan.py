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
import os
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
    # Implemented in Task 10.
    raise NotImplementedError


def cmd_import(args: argparse.Namespace) -> int:
    # Implemented in Task 9.
    raise NotImplementedError


def cmd_verify_manifest(args: argparse.Namespace) -> int:
    """Validate manifest syntax + required fields + duplicate destinations."""
    entries = load_manifest(args.manifest)
    print(f"Manifest OK: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}.")
    for e in entries:
        print(f"  [{e.ccan_id}] {e.title} -> content-community/{e.destination}/")
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
    p_imp.set_defaults(func=cmd_import)

    p_ver = sub.add_parser("verify-manifest", help="Validate manifest + detect duplicate destinations.")
    p_ver.set_defaults(func=cmd_verify_manifest)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
