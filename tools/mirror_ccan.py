#!/usr/bin/env python3
"""Bulk CCAN mirror — preserves every CCAN entry content-addressed.

Phase 1 of the ccan-bulk-mirror roadmap item. Crawls CCAN's paginated
listing, scrapes each per-entry metadata page, downloads the blob, and
writes everything content-addressed into a snapshot directory outside the
workspace (default ``~/clonk/ccan-snapshot``).

Resumable via ``--resume``: entries whose on-disk blob sha256 matches the
recorded ``meta.json`` are skipped. Rate-limited, with per-entry failure
isolation (``failures.jsonl``) and an advisory ``fcntl.flock`` lock.

Usage::

    python3 tools/mirror_ccan.py mirror \\
        --snapshot-dir ~/clonk/ccan-snapshot \\
        --rate-limit 2.0 \\
        --resume
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Make tools/ importable for ccan_index + import_ccan.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ccan_index as CI
from import_ccan import (
    CCAN_BASE,
    DEFAULT_RATE_LIMIT,
    USER_AGENT,
)

DEFAULT_SNAPSHOT_DIR = Path(os.environ.get(
    "CCAN_SNAPSHOT_DIR", str(Path.home() / "clonk" / "ccan-snapshot")))
LISTING_URL = f"{CCAN_BASE}/ccan-view.pl?pg={{pg}}&nr={{nr}}"


# ===========================================================================
# Resilient HTTP fetch (per-entry failure isolation)
# ===========================================================================

_LAST_REQUEST_TIME: float = 0.0


def _rate_limit_sleep(rate_limit: float) -> None:
    global _LAST_REQUEST_TIME
    now = time.monotonic()
    wait = rate_limit - (now - _LAST_REQUEST_TIME)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_TIME = time.monotonic()


def mirror_fetch(
    url: str,
    rate_limit: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
) -> tuple[Optional[bytes], Optional[str]]:
    """Fetch a URL, returning (body, None) or (None, error). Never raises."""
    attempt = 0
    backoff = 1.0
    while True:
        _rate_limit_sleep(rate_limit)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(), None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                attempt += 1
                continue
            return None, f"HTTP {e.code}: {e.reason}"
        except (urllib.error.URLError, OSError) as e:
            if attempt < max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                attempt += 1
                continue
            return None, str(e)


# ===========================================================================
# Advisory lock
# ===========================================================================

def acquire_lock(snapshot_dir: Path) -> Optional[object]:
    """Acquire an advisory lock on <snapshot>/.lock. Exits if held."""
    try:
        import fcntl
    except ImportError:
        return None
    lock_path = snapshot_dir / ".lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        sys.exit(f"Snapshot {snapshot_dir} is locked by another mirror run.")
    lock_file.write(str(os.getpid()) + "\n")
    lock_file.flush()
    return lock_file


# ===========================================================================
# Listing crawl
# ===========================================================================

def crawl_listing(
    rate_limit: float,
    max_retries: int,
    page_size: int = 30,
) -> tuple[list[CI.ListingEntry], int]:
    """Crawl the paginated CCAN listing. Returns (entries, total_entries)."""
    all_entries: list[CI.ListingEntry] = []
    total_entries = 0
    pg = 0
    seen_ids: set[int] = set()
    while True:
        url = LISTING_URL.format(pg=pg, nr=page_size)
        body, err = mirror_fetch(url, rate_limit, max_retries)
        if err is not None:
            print(f"[listing pg={pg}] fetch failed: {err}", file=sys.stderr)
            break
        html_text = body.decode("utf-8", errors="replace")
        page = CI.parse_listing(html_text)
        if not page.entries:
            break
        for e in page.entries:
            if e.ccan_id in seen_ids:
                continue
            seen_ids.add(e.ccan_id)
            all_entries.append(e)
        if page.total_entries:
            total_entries = page.total_entries
        if page.total_pages and pg >= page.total_pages - 1:
            break
        pg += 1
    return all_entries, total_entries


# ===========================================================================
# Per-entry mirror
# ===========================================================================

def _entry_dir(snapshot_dir: Path, ccan_id: int) -> Path:
    return snapshot_dir / "entries" / str(ccan_id)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_resolved(snapshot_dir: Path, ccan_id: int) -> bool:
    """True if meta.json + blob exist and sha256 matches."""
    ed = _entry_dir(snapshot_dir, ccan_id)
    meta_path = ed / "meta.json"
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    blob_path = ed / meta.get("filename", "")
    if not blob_path.is_file():
        return False
    return _sha256_file(blob_path) == meta.get("sha256")


def mirror_entry(
    entry: CI.ListingEntry,
    snapshot_dir: Path,
    rate_limit: float,
    max_retries: int,
) -> tuple[bool, Optional[str]]:
    """Mirror one entry. Returns (ok, error)."""
    ed = _entry_dir(snapshot_dir, entry.ccan_id)
    ed.mkdir(parents=True, exist_ok=True)

    # 1. Fetch per-entry page.
    view_url = CI.CCAN_VIEW_URL.format(id=entry.ccan_id)
    body, err = mirror_fetch(view_url, rate_limit, max_retries)
    if err is not None:
        return False, f"view fetch failed: {err}"
    raw_html = body
    (ed / "raw.html").write_bytes(raw_html)
    html_text = raw_html.decode("utf-8", errors="replace")
    try:
        per = CI.parse_per_entry(html_text, entry.ccan_id)
    except Exception as e:
        return False, f"per-entry parse failed: {e}"

    # 2. Download blob.
    dl_url = CI.CCAN_DOWNLOAD_URL.format(id=entry.ccan_id, filename=per.filename)
    blob, err = mirror_fetch(dl_url, rate_limit, max_retries)
    if err is not None:
        return False, f"blob fetch failed: {err}"
    sha = hashlib.sha256(blob).hexdigest()
    blob_path = ed / per.filename
    blob_path.write_bytes(blob)

    # 3. Write meta.json.
    meta = {
        "ccan_id": per.ccan_id,
        "title": per.title,
        "author_nick": per.author_nick,
        "author_uid": per.author_uid,
        "uploaded": per.uploaded,
        "engine": per.engine,
        "filename": per.filename,
        "description_de": per.description_de,
        "description_us": per.description_us,
        "comments": per.comments,
        "sha256": sha,
        "blob_size": len(blob),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "view_url": per.view_url,
        "download_url": per.download_url,
        "is_pack": entry.is_pack,
    }
    (ed / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, None


# ===========================================================================
# Snapshot index writers
# ===========================================================================

def write_index(snapshot_dir: Path, mirrored_ids: list[int]) -> None:
    index_path = snapshot_dir / "index.jsonl"
    manifest_path = snapshot_dir / "manifest.txt"
    index_lines: list[str] = []
    manifest_lines: list[str] = []
    for ccan_id in sorted(mirrored_ids):
        meta_path = _entry_dir(snapshot_dir, ccan_id) / "meta.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        index_lines.append(json.dumps(meta, ensure_ascii=False))
        manifest_lines.append(
            f"{meta['ccan_id']}\t{meta['title']}\t{meta['sha256']}")
    index_path.write_text(
        "\n".join(index_lines) + ("\n" if index_lines else ""), encoding="utf-8")
    manifest_path.write_text(
        "\n".join(manifest_lines) + ("\n" if manifest_lines else ""),
        encoding="utf-8")


# ===========================================================================
# Subcommand: mirror
# ===========================================================================

def cmd_mirror(args: argparse.Namespace) -> int:
    snapshot_dir = Path(args.snapshot_dir).expanduser()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    lock_file = acquire_lock(snapshot_dir)

    rate_limit = args.rate_limit
    max_retries = args.retry

    if args.entry_id:
        entries = [CI.ListingEntry(
            ccan_id=i, title="", author_nick="", uploaded="",
            engine="", filename="", file_type="", size_label="",
        ) for i in args.entry_id]
    else:
        print(f"Crawling CCAN listing (rate limit {rate_limit}s)...")
        entries, total = crawl_listing(rate_limit, max_retries)
        print(f"Listing: {len(entries)} entries "
              f"(CCAN reports {total} total).")
        if args.limit:
            entries = entries[:args.limit]
            print(f"--limit {args.limit} applied.")

    mirrored_ids: list[int] = []
    failures: list[dict] = []
    for idx, entry in enumerate(entries, 1):
        ccan_id = entry.ccan_id
        if args.resume and _is_resolved(snapshot_dir, ccan_id):
            print(f"[{idx}/{len(entries)}] #{ccan_id} already mirrored, "
                  f"skipping.")
            mirrored_ids.append(ccan_id)
            continue
        print(f"[{idx}/{len(entries)}] mirroring #{ccan_id} "
              f"({entry.title or 'unknown'})...")
        ok, err = mirror_entry(entry, snapshot_dir, rate_limit, max_retries)
        if ok:
            mirrored_ids.append(ccan_id)
        else:
            failures.append({
                "ccan_id": ccan_id,
                "error": err,
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
            })
            print(f"[{idx}/{len(entries)}] #{ccan_id} FAILED: {err}",
                  file=sys.stderr)

    write_index(snapshot_dir, mirrored_ids)

    if failures:
        (snapshot_dir / "failures.jsonl").write_text(
            "\n".join(json.dumps(f, ensure_ascii=False) for f in failures)
            + "\n", encoding="utf-8")

    if lock_file is not None:
        lock_file.close()

    print(f"\nMirrored {len(mirrored_ids)} entries, "
          f"{len(failures)} failure(s).")
    if failures:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mirror_ccan.py",
        description="Bulk CCAN mirror — preserves every CCAN entry "
                    "content-addressed.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mirror = sub.add_parser("mirror", help="Mirror CCAN into a "
                              "content-addressed snapshot.")
    p_mirror.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR),
                          help=f"Snapshot directory (default: "
                          f"{DEFAULT_SNAPSHOT_DIR}).")
    p_mirror.add_argument("--rate-limit", type=float,
                          default=DEFAULT_RATE_LIMIT,
                          help=f"Seconds between requests (default: "
                          f"{DEFAULT_RATE_LIMIT}).")
    p_mirror.add_argument("--retry", type=int, default=3,
                          help="Max retries on transient failure (default: 3).")
    p_mirror.add_argument("--resume", action="store_true",
                          help="Skip entries already mirrored with matching "
                          "sha256.")
    p_mirror.add_argument("--limit", type=int, default=0,
                          help="Mirror only the first N entries "
                          "(0 = no limit).")
    p_mirror.add_argument("--entry-id", type=int, nargs="*", default=[],
                          help="Mirror only these CCAN entry IDs (skips "
                          "listing crawl).")
    p_mirror.set_defaults(func=cmd_mirror)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
