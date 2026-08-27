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
# Subcommand stubs (implemented in later tasks)
# ===========================================================================


def cmd_list(args: argparse.Namespace) -> int:
    # Implemented in Task 10.
    raise NotImplementedError


def cmd_import(args: argparse.Namespace) -> int:
    # Implemented in Task 9.
    raise NotImplementedError


def cmd_verify_manifest(args: argparse.Namespace) -> int:
    # Implemented in Task 10.
    raise NotImplementedError


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
