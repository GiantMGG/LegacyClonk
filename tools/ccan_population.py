#!/usr/bin/env python3
"""CCAN Phase-0 population crawl + offline statistics tool.

Crawls CCAN's enriched listing CGI (``ac=ty-ti-ni-tm-rp-vo-dc-ca-ev-si``,
``reveal=1``) — the complete population with rating/votes/downloads/category/
engine per entry — caches every raw page durably, and derives the per-tier
quality thresholds Phase 2 (``ccan-phase2-quality-gated-curation``) consumes.

Two subcommands:

``crawl``
    Fetches the enriched listing page by page via ``mirror_ccan.mirror_fetch``
    (house rate limiter, identified User-Agent, 429/backoff — no plumbing
    duplication), writes every page body to
    ``<population-dir>/raw-listings/pg-<NNNN>.html`` (durable, never /tmp;
    cache hit => reparse, never refetch), reconciles the unique-id count
    against the listing footer total (exit 1 on mismatch), and writes the
    schema-versioned dataset ``ccan_population.v1.jsonl`` (+ CSV mirror),
    sorted by ``ccan_id``. ``--validate-sample N`` (default 20) additionally
    cross-checks a deterministic stratified per-entry sample against the
    per-entry pages; every mismatch is a report finding, never an abort.

``stats``
    Pure-offline analysis of the dataset (never touches the network):
    ``statistics.quantiles`` distributions per engine tier and tier x
    category, the Bayesian-shrunk rating (m=5, per-tier prior from votes>=1
    rows), a Wilson lower-bound cross-check (z=1.96), a >=3-vote
    stratification with an n<10 small-stratum guard, and threshold derivation
    -> ``population-report.md`` + the generated, committed
    ``LegacyClonk/tools/ccan_thresholds.toml``.

Output location: ``<population-dir>/`` — default ``~/clonk/ccan-population/``,
``CCAN_POPULATION_DIR`` environment override; out-of-repo and durable.

Usage::

    python3 tools/ccan_population.py crawl --validate-sample 20
    python3 tools/ccan_population.py stats
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Make tools/ importable for ccan_index + import_ccan + mirror_ccan.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ccan_index as CI
from import_ccan import (
    CCAN_BASE,
    DEFAULT_RATE_LIMIT,
    USER_AGENT,
    CcanMetadataParser,
    parse_ccan_metadata,
)
# mirror_fetch carries the house politeness policy (2s rate limit, identified
# contact-bearing USER_AGENT, 429/backoff) — never re-implemented here.
from mirror_ccan import mirror_fetch

# ===========================================================================
# Constants
# ===========================================================================

ENRICHED_LISTING = (CCAN_BASE + "/ccan-view.pl?a=&ac=ty-ti-ni-tm-rp-vo-dc-ca-ev-si"
                    "&reveal=1&nr=30&pg={pg}")
DEFAULT_LISTING = CCAN_BASE + "/ccan-view.pl?pg=0&nr=30"  # mirror's verified shape
COLUMN_ORDER = ["entry_type", "title", "dl", "category", "author",
                "engine", "niveau", "votes", "downloads", "size", "uploaded"]
DATASET_SCHEMA = 1
# Schema field order is fixed (Phase 1 extends the nullable tails only).
DATASET_COLUMNS = [
    "schema", "ccan_id", "entry_type", "title", "category", "engine",
    "uploaded", "size_label", "niveau_label", "niveau_numeric", "votes",
    "downloads", "author_nick", "author_uid", "version", "players",
    "fetched_at",
]
# Deterministic validation-sample randomness (canonical seed — never time).
VALIDATION_SEED = 20260912

# Stats methodology constants (named, recorded in the TOML — spec §Stats).
BAYES_M = 5.0        # pretend votes for the prior
WILSON_Z = 1.96      # 95% Wilson bound
MIN_VOTES = 3        # >=3-vote stratification floor
MIN_STRATUM_N = 10   # small-stratum guard: below this, no thresholds
QUANTILE = 0.75      # the "top-quartile" cutoff
SANITY_FLOOR = 3000  # archive was 3,697 on 2026-09-12 and growing

_METRICS = ("niveau_numeric", "bayes_rating", "votes", "downloads")

DEFAULT_POPULATION_DIR = Path(os.environ.get(
    "CCAN_POPULATION_DIR", str(Path.home() / "clonk" / "ccan-population")))

# ===========================================================================
# Small helpers
# ===========================================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _to_float(text: str) -> Optional[float]:
    try:
        return float(str(text).replace(",", "."))
    except (ValueError, TypeError):
        return None

# ===========================================================================
# Durable raw-page cache
# ===========================================================================

def cache_or_fetch(cache_path: Path, url: str, rate_limit: float,
                   max_retries: int,
                   fetch_fn=None) -> tuple[bytes, bool]:
    """Return ``(body_bytes, fetched)``.

    A cache hit (existing non-empty file) never re-fetches — the raw page
    cache is itself preservation and makes re-crawls (and re-validation)
    cheap and idempotent. Raises RuntimeError after the fetch partner's
    retries are exhausted (mid-crawl failure -> clean abort).

    ``fetch_fn`` is resolved at call time so tests can
    ``monkeypatch.setattr(ccan_population, "mirror_fetch", fake)`` on the
    tool's own imported reference.
    """
    if cache_path.is_file() and cache_path.stat().st_size > 0:
        return cache_path.read_bytes(), False
    if fetch_fn is None:
        fetch_fn = mirror_fetch  # default only binding the name, not the fn
    body, err = fetch_fn(url, rate_limit, max_retries)
    if err is not None:
        raise RuntimeError(f"fetch failed for {url}: {err}")
    cache_path.write_bytes(body)
    return body, True

# ===========================================================================
# Dataset row conversion + persistence
# ===========================================================================

def listing_to_row(entry: CI.ListingEntry, fetched_at: str) -> dict:
    """Convert one listing row into the schema-v1 dataset record."""
    return {
        "schema": DATASET_SCHEMA,
        "ccan_id": entry.ccan_id,
        "entry_type": entry.entry_type,
        "title": entry.title,
        "category": entry.category,
        "engine": entry.engine,
        "uploaded": entry.uploaded,
        "size_label": entry.size_label,
        "niveau_label": entry.niveau_label,
        "niveau_numeric": entry.niveau_numeric,
        "votes": entry.votes,
        "downloads": entry.downloads,
        "author_nick": entry.author_nick,
        "author_uid": entry.author_uid,
        "version": None,   # per-entry-page fields, filled by Phase 1
        "players": None,   #   (uniformly null this cycle — spec edge #9)
        "fetched_at": fetched_at,
    }

def _decode_html(body: bytes) -> str:
    """Decode a fetched page — UTF-8 first, then the cp1252/latin-1
    fallback the house uses (``import_ccan.fetch_metadata_html``); the live
    German pages carry raw 0xe4/0xf6/0xfc bytes."""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp1252", errors="replace")

def write_dataset(population_dir: Path, rows: list[dict]) -> None:
    """Write the JSONL dataset + CSV mirror (sorted by ccan_id = by caller)."""
    jsonl_path = population_dir / f"ccan_population.v{DATASET_SCHEMA}.jsonl"
    csv_path = population_dir / f"ccan_population.v{DATASET_SCHEMA}.csv"
    jsonl_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(DATASET_COLUMNS)
        for row in rows:
            writer.writerow([row.get(col, "") for col in DATASET_COLUMNS])

def load_dataset(jsonl_path: Path) -> Optional[list[dict]]:
    """Read the dataset back. Returns None on read/parse error."""
    try:
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        print(f"Dataset read error: {e}", file=sys.stderr)
        return None
    rows = []
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"Dataset JSON error (line {lineno}): {e}", file=sys.stderr)
            return None
    return rows

# ===========================================================================
# crawl: the enriched-listing crawl + validation sample
# ===========================================================================

def normalize_tier(engine: str) -> str:
    """Map a raw engine string to a stratification tier.

    Raw values stay verbatim in the dataset; only stratification uses this.
    LC -> CR -> legacy -> other, per the cycle spec. The legacy matcher is
    derived from the live dataset's engine-string distribution (the one
    place the tool adapts to observed data): the live archive's non-LC/CR
    engines are the Clonk-4.x-era family ``CE`` (Clonk Extreme), ``GWE``/
    ``GWX`` (Gold Weber Edition), ``CP``/``C4*`` (Clonk Planet/Deluxe),
    ``NET2`` and plain version numbers, so those classify as ``legacy``.
    """
    e = (engine or "").lower()
    tokens = re.split(r"[^a-z0-9.]+", e)
    tokens = [t for t in tokens if t]
    if not tokens:
        return "other"
    if any("lc" in t for t in tokens):
        return "LC"
    if any(t in ("cr", "rage") or "rage" in t for t in tokens):
        return "CR"
    if any(re.match(r"^(ce|gw|cp|c[1-4]|net1|net2)", t) for t in tokens):
        return "legacy"
    if any(re.match(r"^\d+\.\d+$", t) for t in tokens):
        return "legacy"
    if any(t in ("gold", "clonk4", "4") for t in tokens):
        return "legacy"
    return "other"

def _rating_tercile(rating: Optional[float], bounds: list[float]) -> str:
    if rating is None:
        return "null"
    for i, b in enumerate(bounds):
        if rating <= b:
            return str(i)
    return str(len(bounds))

def select_validation_sample(entries: list[CI.ListingEntry],
                             count: int) -> list[CI.ListingEntry]:
    """Deterministic stratified sample: engine tier x rating tercile.

    The Random instance is seeded canonically (never time) and the group
    order / pool order are deterministic, so the sample is reproducible.
    """
    count = min(count, len(entries))
    ratings = sorted(e.niveau_numeric for e in entries
                     if e.niveau_numeric is not None)
    bounds: list[float] = []
    if len(ratings) >= 2:
        bounds = statistics.quantiles(ratings, n=3, method="inclusive")

    groups: dict[tuple[str, str], list[CI.ListingEntry]] = {}
    for e in entries:
        key = (normalize_tier(e.engine), _rating_tercile(e.niveau_numeric,
                                                          bounds))
        groups.setdefault(key, []).append(e)

    rng = random.Random(VALIDATION_SEED)
    selected_ids: set[int] = set()
    selected: list[CI.ListingEntry] = []
    total = len(entries)
    for key in sorted(groups):
        pool = sorted(groups[key], key=lambda e: e.ccan_id)
        quota = count * len(pool) // total
        if quota:
            for e in rng.sample(pool, quota):
                selected.append(e)
                selected_ids.add(e.ccan_id)
    # Top up any shortfall from the remaining entries (deterministic order).
    if len(selected) < count:
        rest = [e for e in sorted(entries, key=lambda e: e.ccan_id)
                if e.ccan_id not in selected_ids]
        for e in rng.sample(rest, count - len(selected)):
            selected.append(e)
    return selected[:count]

# Best-effort per-entry-page enrichment regexes. Task 3 adapts these to the
# live page shape if the ground truth differs; they are tolerant by design —
# a field that cannot be extracted is recorded as "unparsed", not a mismatch.
_PAGE_NIVEAU_RE = re.compile(
    r"(?i)\b(absolut genial|sehr gut|gut|befriedigend|ausreichend|"
    r"mangelhaft|ungenügend|mies|katastrophal|desaströs)\b\s*"
    r"\(?\s*(-?\d+[.,]\d+)")
_PAGE_VOTES_RE = re.compile(r"(?i)\b(?:Stimmen|Votes?|Stimmabgaben)\b")
_PAGE_DOWNLOADS_RE = re.compile(
    r"(?i)\b(?:Downloads?|Heruntergeladen)\b")

_PARITY_FIELDS = ("category", "engine", "niveau_label", "niveau_numeric",
                  "votes", "downloads")

def _page_count(html_text: str, label_re: re.Pattern,
                window: int = 40) -> Optional[int]:
    """Grab the integer count next to a label, accepting the number on
    either side (``2 Stimmen`` and ``Stimmen: 2`` both parse)."""
    m = label_re.search(html_text)
    if not m:
        return None
    before = html_text[max(0, m.start() - window):m.start()]
    nums = re.findall(r"\d+", before)
    if nums:
        return int(nums[-1])  # German "N Subst." construction
    after = re.search(r"(\d+)", html_text[m.end():m.end() + window])
    if after:
        return int(after.group(1))
    return None

def parse_page_fields(html_text: str, ccan_id: int = 0) -> dict:
    """Extract the fields the parity check compares from a per-entry page.

    Uses the house ``CcanMetadataParser``/``parse_ccan_metadata`` (fields the
    label-value table carries: engine, category) plus targeted regex
    fallbacks for Niveau/votes/downloads. Task-3 adaptation to the live
    page shape: CCAN's per-entry table labels the count ``Downloadzahl``
    (the old ``Downloads?`` regex hit the ``Download`` link row instead and
    grabbed the entry ID) and wraps the Niveau numeric in ``<span>``s
    (``gut <span>(0.7)</span> (3 Votes)``), so the regex fallbacks alone
    mis-parse both. The metadata-table cells are the primary source when
    present; the regexes stay as the synthetic-fixture fallback. Absent
    fields are ``None``.
    """
    meta = parse_ccan_metadata(html_text, ccan_id)
    parser = CcanMetadataParser()
    parser.feed(html_text)
    fields = parser.fields

    niveau_label: Optional[str] = None
    niveau_numeric: Optional[float] = None
    votes: Optional[int] = _page_count(html_text, _PAGE_VOTES_RE)
    downloads: Optional[int] = _page_count(html_text, _PAGE_DOWNLOADS_RE)

    # Live Niveau cell: "gut (0.7) (3 Votes) [Vote: ...]" — the vote-count
    # row's label/value are in the same cell, so parse all three in one go.
    niveau_cell = fields.get("Niveau")
    if niveau_cell:
        m = re.match(r"^\s*(.+?)\s*\((-?\d+[.,]\d+)\)"
                     r"\s*\((\d+)\s*Votes?\)", niveau_cell)
        if m:
            niveau_label = m.group(1).strip()
            niveau_numeric = _to_float(m.group(2))
            votes = int(m.group(3))
    if niveau_numeric is None:
        m = _PAGE_NIVEAU_RE.search(html_text)
        if m:
            niveau_label = m.group(1)
            niveau_numeric = _to_float(m.group(2))

    # Live count cell: "Downloadzahl:  <td>293</td>" — the number follows the
    # label in the next cell, which _page_count's look-back misses on the
    # "Download" (link) row; prefer the table field.
    for dl_key in ("Downloadzahl", "Downloads", "Heruntergeladen"):
        dl_cell = fields.get(dl_key)
        if dl_cell:
            try:
                downloads = int(dl_cell.strip())
            except ValueError:
                pass
            break
    return {
        "engine": meta.engine,
        "category": (fields.get("Kategorie") or fields.get("Category") or ""),
        "niveau_label": niveau_label,
        "niveau_numeric": niveau_numeric,
        "votes": votes,
        "downloads": downloads,
    }

def compare_entry_parity(entry: CI.ListingEntry, page_fields: dict) -> dict:
    """Field-by-field parity row for one sampled entry.

    A missing page field is ``unparsed`` (never a mismatch); both-missing is
    ``n/a``; any present-but-different value is a ``mismatch`` finding.
    """
    listing = {
        "category": entry.category,
        "engine": entry.engine,
        "niveau_label": entry.niveau_label,
        "niveau_numeric": entry.niveau_numeric,
        "votes": entry.votes,
        "downloads": entry.downloads,
    }
    fields: dict[str, dict] = {}
    for name in _PARITY_FIELDS:
        lv = listing[name]
        pv = page_fields.get(name)
        if isinstance(pv, str):
            pv = pv.strip() or None
        if lv is None and pv is None:
            verdict = "n/a"
        elif pv is None:
            verdict = "unparsed"
        elif isinstance(lv, float) and isinstance(pv, float):
            verdict = ("match" if math.isclose(lv, pv, rel_tol=1e-6,
                                               abs_tol=1e-6) else "mismatch")
        else:
            verdict = "match" if str(lv) == str(pv) else "mismatch"
        fields[name] = {"listing": lv, "page": pv, "verdict": verdict}
    return {"ccan_id": entry.ccan_id, "title": entry.title, "fields": fields}

def run_validation(entries: list[CI.ListingEntry], population_dir: Path,
                   rate_limit: float, max_retries: int,
                   count: int) -> tuple[list[dict], list[dict], int]:
    """Fetch + parse the sample, cache per-entry pages, build the parity list.

    Returns ``(parity_rows, findings, fetched_count)``. Mismatches are
    findings in the parity output — they must never abort the crawl.
    """
    raw_dir = population_dir / "raw-listings"
    raw_dir.mkdir(parents=True, exist_ok=True)
    selected = select_validation_sample(entries, count)
    parity_rows: list[dict] = []
    fetched_count = 0
    for entry in selected:
        cache_path = raw_dir / f"entry-{entry.ccan_id}.html"
        body, fetched = cache_or_fetch(
            cache_path,
            CI.CCAN_VIEW_URL.format(id=entry.ccan_id),
            rate_limit, max_retries)
        if fetched:
            fetched_count += 1
        page_fields = parse_page_fields(
            _decode_html(body), entry.ccan_id)
        parity_rows.append(compare_entry_parity(entry, page_fields))
    findings: list[dict] = []
    for row in parity_rows:
        bad = [name for name, fld in row["fields"].items()
               if fld["verdict"] == "mismatch"]
        if bad:
            findings.append({"ccan_id": row["ccan_id"], "fields": bad})
    (population_dir / "validation-parity.json").write_text(
        json.dumps(parity_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return parity_rows, findings, fetched_count

def cmd_crawl(args: argparse.Namespace) -> int:
    population_dir = Path(args.population_dir).expanduser()
    population_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = population_dir / "raw-listings"
    raw_dir.mkdir(parents=True, exist_ok=True)

    started_at = utc_now()
    request_count = 0
    parse_failures = 0

    # 1. Default-layout page once (live L1 regression, 1 extra request).
    try:
        default_cache = raw_dir / "pg-default.html"
        body, fetched = cache_or_fetch(default_cache, DEFAULT_LISTING,
                                       args.rate_limit, args.retry)
        request_count += int(fetched)
        default_page = CI.parse_listing(
            _decode_html(body))
    except RuntimeError as e:
        print(f"[default-layout] {e} — aborting (cached pages make the "
              f"re-run resume cheap).", file=sys.stderr)
        return 1
    parse_failures += default_page.parse_failures
    print(f"Default-layout regression page parsed: "
          f"{len(default_page.entries)} entries")
    print(f"Identified fetch identity (politeness): {USER_AGENT}; "
          f"{args.rate_limit:g}s rate limit, {args.retry} retries")

    # 2. Enriched listing pages (pg=0.. until no new ids / total_pages-1).
    seen: dict[int, CI.ListingEntry] = {}
    footer_total = 0
    pg = 0
    try:
        while True:
            cache_path = raw_dir / f"pg-{pg:04d}.html"
            body, fetched = cache_or_fetch(
                cache_path, ENRICHED_LISTING.format(pg=pg),
                args.rate_limit, args.retry)
            request_count += int(fetched)
            page = CI.parse_listing(
                _decode_html(body),
                column_order=COLUMN_ORDER)
            parse_failures += page.parse_failures
            if page.total_entries:
                footer_total = page.total_entries
            new = [e for e in page.entries if e.ccan_id not in seen]
            if not new:
                break
            for e in new:
                seen[e.ccan_id] = e
            print(f"  pg={pg:04d}: {len(page.entries)} rows, "
                  f"{len(seen)} unique so far")
            if page.total_pages and pg >= page.total_pages - 1:
                break
            pg += 1
    except RuntimeError as e:
        print(f"[crawl] {e} — aborting mid-crawl (cached pages make the "
              f"re-run resume cheap).", file=sys.stderr)
        return 1

    # 3. Count reconciliation vs the last page's footer total.
    unique = len(seen)
    if footer_total and unique != footer_total:
        print(f"RECONCILIATION MISMATCH: crawled {unique} unique ids, "
              f"footer reports {footer_total} entries.", file=sys.stderr)
        print(f"unique={unique} footer_total={footer_total}", file=sys.stderr)
        return 1
    if not footer_total:
        reconciliation = "unverified"
        print("WARNING: footer total undetectable; count reconciliation "
              "skipped.")
    else:
        reconciliation = "pass"
        print(f"RECONCILIATION PASS: unique {unique} == footer {footer_total}, "
              f"incl. the below-Niveau rows")

    # 4. Dataset + CSV mirror, sorted by ccan_id.
    fetched_at = utc_now()
    rows = [listing_to_row(seen[i], fetched_at) for i in sorted(seen)]
    write_dataset(population_dir, rows)
    print(f"Dataset written: "
          f"{population_dir / ('ccan_population.v%d.jsonl' % DATASET_SCHEMA)} "
          f"({len(rows)} rows, schema v{DATASET_SCHEMA}, sorted by id)")

    # 5. Validation sample (off via --validate-count 0).
    validate_count = (
        args.validate_count
        if args.validate_count is not None
        else (args.validate_sample if args.validate_sample is not None else 20))
    validate_count = max(0, validate_count)
    parity_rows: list[dict] = []
    findings: list[dict] = []
    if validate_count > 0:
        parity_rows, findings, val_fetched = run_validation(
            list(seen.values()), population_dir,
            args.rate_limit, args.retry, validate_count)
        request_count += val_fetched
        print(f"Validation sample: {len(parity_rows)} entries, "
              f"{len(findings)} finding(s) "
              f"({[f['ccan_id'] for f in findings] or '-'}).")

    # 6. Crawl metadata for the offline stats lineage.
    meta = {
        "schema": DATASET_SCHEMA,
        "listing_url_template": ENRICHED_LISTING,
        "default_listing_url": DEFAULT_LISTING,
        "crawl_started_at": started_at,
        "crawl_finished_at": utc_now(),
        "request_count": request_count,
        "footer_total": footer_total,
        "crawled_unique": unique,
        "reconciliation": reconciliation,
        "dataset_rows": len(rows),
        "parse_failures": parse_failures,
        "validate_sample_count": len(parity_rows),
        "validation_findings": len(findings),
    }
    (population_dir / "population-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return 0

# ===========================================================================
# stats: pure-offline scoring, distributions, thresholds, report, TOML
# ===========================================================================

def bayes_rating(prior: float, votes: Optional[int], rating: float,
                 m: float = BAYES_M) -> float:
    """(m * C + v * R) / (m + v); zero-vote rows collapse to the prior."""
    v = float(votes or 0)
    return (m * prior + v * float(rating)) / (m + v)

def wilson_lower(rating: float, votes: Optional[int],
                 z: float = WILSON_Z) -> Optional[float]:
    """Wilson-proportion lower bound on the rating, as a believability
    cross-check. Skipped (None) for votes < 1."""
    if votes is None or votes < 1:
        return None
    n = float(votes)
    p_hat = min(max((rating + 3.0) / 6.0, 0.01), 0.99)
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = p_hat + z2 / (2.0 * n)
    margin = z * math.sqrt((p_hat * (1.0 - p_hat) + z2 / (4.0 * n)) / n)
    return (centre - margin) / denom

def compute_priors(rows: list[dict]) -> dict:
    """Per-tier + archive-wide prior means over votes>=1 rated rows only,
    so author-history priors never contaminate the shrinkage prior."""
    voted = [r for r in rows
             if (r.get("votes") or 0) >= 1
             and r.get("niveau_numeric") is not None]
    c_archive = (statistics.mean([r["niveau_numeric"] for r in voted])
                 if voted else 0.0)
    tiers = sorted({normalize_tier(r.get("engine", "")) for r in rows})
    c_tier: dict[str, float] = {}
    tier_voted: dict[str, int] = {}
    for tier in tiers:
        tv = [r for r in voted if normalize_tier(r.get("engine", "")) == tier]
        tier_voted[tier] = len(tv)
        c_tier[tier] = (statistics.mean([r["niveau_numeric"] for r in tv])
                        if tv else c_archive)
    return {
        "C_archive": c_archive,
        "C_tier": c_tier,
        "archive_voted": len(voted),
        "tier_voted": tier_voted,
    }

def score_rows(rows: list[dict], priors: dict) -> list[dict]:
    """Annotate each row with its stratification tier, bayes_rating and
    wilson_lower (both None when the row carries no numeric Niveau)."""
    scored: list[dict] = []
    for r in rows:
        tier = normalize_tier(r.get("engine", ""))
        prior = priors["C_tier"].get(tier, priors["C_archive"])
        rating = r.get("niveau_numeric")
        votes = r.get("votes")
        row = dict(r)
        row["tier"] = tier
        if rating is None:
            row["bayes_rating"] = None
            row["wilson_lower"] = None
        else:
            row["bayes_rating"] = bayes_rating(prior, votes, rating)
            row["wilson_lower"] = wilson_lower(rating, votes)
        scored.append(row)
    return scored

def _summary(values: list[float]) -> dict:
    """mean/median/quartiles/deciles for one metric, inclusive quantiles.

    Never raises on small input: quantiles need >=2 values and are only
    computed then; n < MIN_STRATUM_N is flagged (low-n strata are excluded
    from threshold derivation downstream)."""
    out: dict = {"n": len(values), "mean": None, "median": None,
                 "q1": None, "q2": None, "q3": None}
    for i in range(1, 10):
        out[f"d{i}"] = None
    out["low_n"] = len(values) < MIN_STRATUM_N
    if not values:
        return out
    out["mean"] = statistics.mean(values)
    out["median"] = statistics.median(values)
    if len(values) >= 2:
        q = statistics.quantiles(values, n=4, method="inclusive")
        out["q1"], out["q2"], out["q3"] = q
        for i, v in enumerate(statistics.quantiles(
                values, n=10, method="inclusive"), 1):
            out[f"d{i}"] = v
    return out

def compute_distributions(scored: list[dict]) -> dict:
    """Distribution summaries: archive, per tier, per (tier x category).

    ``statistics.quantiles(..., method="inclusive")`` with n=4/10; empty
    strata are skipped (spec edge #10).
    """
    dist: dict = {}

    def block(key, rows):
        dist[key] = {
            m: _summary([r[m] for r in rows if r.get(m) is not None])
            for m in _METRICS
        }

    block("archive", scored)
    tiers = sorted({r["tier"] for r in scored})
    for tier in tiers:
        block(("tier", tier), [r for r in scored if r["tier"] == tier])
    for tier in tiers:
        cats = sorted({r.get("category") or "(none)"
                       for r in scored if r["tier"] == tier})
        for cat in cats:
            rows = [r for r in scored
                    if r["tier"] == tier
                    and (r.get("category") or "(none)") == cat]
            if rows:
                block(("tier_category", tier, cat), rows)
    return dist

def derive_thresholds(scored: list[dict],
                      tiers: list[str]) -> dict[str, dict]:
    """Per-tier candidate-quality cutoffs.

    Candidate iff votes >= 3 AND bayes_rating >= p75(bayes | votes>=3 rows of
    the tier) AND downloads >= p75(downloads | all rows of the tier). The
    votes>=3 stratum must clear MIN_STRATUM_N (>=10), else the tier is
    flagged low_n and derives nothing.
    """
    thresholds: dict[str, dict] = {}
    for tier in tiers:
        tier_rows = [r for r in scored if r["tier"] == tier]
        votes3 = [r for r in tier_rows
                  if r.get("votes") is not None and r["votes"] >= MIN_VOTES]
        dl_vals = [r["downloads"] for r in tier_rows
                   if r.get("downloads") is not None]
        info: dict = {
            "count": len(tier_rows),
            "voted1": sum(1 for r in tier_rows if (r.get("votes") or 0) >= 1),
            "voted3": len(votes3),
            "low_n": len(votes3) < MIN_STRATUM_N,
            "pass": 0,
        }
        if not info["low_n"] and len(dl_vals) >= 2:
            bayes_vals = [r["bayes_rating"] for r in votes3
                          if r.get("bayes_rating") is not None]
            raw_vals = [r["niveau_numeric"] for r in votes3
                        if r.get("niveau_numeric") is not None]
            if len(bayes_vals) >= 2 and len(raw_vals) >= 2:
                info["p75_bayes_rating"] = statistics.quantiles(
                    bayes_vals, n=4, method="inclusive")[2]
                info["p75_downloads"] = statistics.quantiles(
                    dl_vals, n=4, method="inclusive")[2]
                info["p75_raw_niveau"] = statistics.quantiles(
                    raw_vals, n=4, method="inclusive")[2]
                info["pass"] = sum(
                    1 for r in votes3
                    if r.get("downloads") is not None
                    and r["downloads"] >= info["p75_downloads"]
                    and r.get("bayes_rating") is not None
                    and r["bayes_rating"] >= info["p75_bayes_rating"])
        thresholds[tier] = info
    return thresholds

def analyze(rows: list[dict]) -> dict:
    """The full offline analysis bundle shared by the report and the TOML."""
    priors = compute_priors(rows)
    scored = score_rows(rows, priors)
    tiers_sorted = sorted({r["tier"] for r in scored})
    return {
        "rows": rows,
        "scored": scored,
        "priors": priors,
        "tiers_sorted": tiers_sorted,
        "distributions": compute_distributions(scored),
        "thresholds": derive_thresholds(scored, tiers_sorted),
    }

# ===========================================================================
# Report + TOML rendering (deterministically ordered)
# ===========================================================================

def _num(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, str):
        return v or "-"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    return f"{v:.6f}".rstrip("0").rstrip(".")

def _lineage_md(meta: dict) -> str:
    if not meta:
        return ("_No crawl metadata recorded — this dataset was imported "
                "without a `crawl` run._")
    rows = [
        f"- crawl window: `{meta.get('crawl_started_at', '-')}` → "
        f"`{meta.get('crawl_finished_at', '-')}` (UTC)",
        f"- request count: {meta.get('request_count', '-')}",
        f"- listing URL: `{meta.get('listing_url_template', '-')}`",
        f"- footer total: {meta.get('footer_total', '-')}",
        f"- crawled unique ids: {meta.get('crawled_unique', '-')}",
        f"- reconciliation: `{meta.get('reconciliation', '-')}`",
        f"- listing parse failures: {meta.get('parse_failures', '-')}",
        f"- dataset rows: {meta.get('dataset_rows', '-')}",
    ]
    return "\n".join(rows)

def _dist_md(dist: dict, group_label: str) -> str:
    summary = dist[group_label]
    header = ("| metric | n | mean | median | Q1 | Q3 | d1 | d2 | d3 | d4 | "
              "d5 | d6 | d7 | d8 | d9 | low-n |")
    sep = "|---" * 17 + "|"
    lines = [header, sep]
    for metric in _METRICS:
        s = summary[metric]
        cells = [metric, str(s["n"]), _num(s["mean"]), _num(s["median"]),
                 _num(s["q1"]), _num(s["q3"])]
        cells += [_num(s[f"d{i}"]) for i in range(1, 10)]
        cells.append("yes" if s["low_n"] else "")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

def render_parity_table(parity: list[dict]) -> str:
    """Markdown section for the validation-sample parity results."""
    if not parity:
        return "_No validation sample recorded for this dataset._"
    header = ("| ccan_id | field | listing | per-entry page | verdict |")
    sep = "|---|---|---|---|---|"
    lines = [header, sep]
    for row in parity:
        for name in _PARITY_FIELDS:
            fld = row["fields"][name]
            lines.append(
                f"| {row['ccan_id']} | {name} | {_num(fld['listing'])} | "
                f"{_num(fld['page'])} | {fld['verdict']} |")
    return "\n".join(lines)

def render_report(analysis: dict, meta: dict, parity: list[dict]) -> str:
    rows = analysis["rows"]
    scored = analysis["scored"]
    priors = analysis["priors"]
    thresholds = analysis["thresholds"]
    dist = analysis["distributions"]
    tiers = analysis["tiers_sorted"]

    lines = ["# CCAN population report", ""]
    lines.append(f"Dataset: `ccan_population.v{DATASET_SCHEMA}.jsonl` "
                 f"(schema v{DATASET_SCHEMA}) — {len(rows)} rows.")
    lines.append("")
    lines.append("## Dataset lineage")
    lines.append(_lineage_md(meta))
    lines.append("")

    # Per-tier and per-category counts.
    lines.append("## Population overview")
    lines.append("")
    lines.append("### Per engine tier")
    lines.append("| tier | entries | votes≥1 | votes≥3 |")
    lines.append("|---|---|---|---|")
    for tier in tiers:
        t = thresholds[tier]
        lines.append(f"| {tier} | {t['count']} | {t['voted1']} | "
                     f"{t['voted3']} |")
    lines.append("")
    lines.append("### Per category")
    lines.append("| category | entries |")
    lines.append("|---|---|")
    cats = sorted({(r.get("category") or "(none)") for r in scored})
    for cat in cats:
        n = sum(1 for r in scored if (r.get("category") or "(none)") == cat)
        lines.append(f"| {cat} | {n} |")
    lines.append("")

    # Null-field counts.
    lines.append("### Null/unset fields")
    null_fields = ("uploaded", "size_label", "niveau_label", "niveau_numeric",
                   "votes", "downloads", "author_uid", "version", "players")
    lines.append("| column | null / empty count |")
    lines.append("|---|---|")
    for col in null_fields:
        n = sum(1 for r in rows
                if r.get(col) in (None, "") or
                (col == "author_uid" and not r.get(col)))
        lines.append(f"| {col} | {n} |")
    lines.append("")

    # Priors.
    lines.append("## Priors (Bayesian shrinkage, m=5)")
    lines.append("")
    lines.append(f"- archive-wide prior `C`: **{_num(priors['C_archive'])}** "
                 f"from {priors['archive_voted']} voted rows (votes≥1, "
                 f"zero-vote author-priors excluded)")
    for tier in tiers:
        lines.append(f"- tier `{tier}` prior: **{_num(priors['C_tier'][tier])}**"
                     f" from {priors['tier_voted'][tier]} voted rows")
    lines.append("")
    lines.append("Zero-vote entries keep their *displayed* numeric (the "
                 "CCAN author-history prior, per the FAQ) and are excluded "
                 "from the priors above so author priors never contaminate "
                 "the shrinkage prior.")
    lines.append("")

    # Distributions.
    lines.append("## Distributions "
                 "(`statistics.quantiles`, inclusive, n=4 / n=10)")
    lines.append("")
    lines.append("### Archive-wide")
    lines.append(_dist_md(dist, "archive"))
    lines.append("")
    for tier in tiers:
        lines.append(f"### Tier `{tier}`")
        lines.append(_dist_md(dist, ("tier", tier)))
        lines.append("")
    for tier in tiers:
        cats = sorted({key for key in dist
                       if isinstance(key, tuple) and key[0] == "tier_category"
                       and key[1] == tier})
        for key in cats:
            lines.append(f"### Tier `{key[1]}` × category `{key[2]}`")
            lines.append(_dist_md(dist, key))
            lines.append("")

    # Thresholds.
    lines.append("## Derived threshold rules (per engine tier)")
    lines.append("")
    lines.append(f"Candidate-quality iff `votes ≥ {MIN_VOTES}` AND "
                 f"`bayes_rating ≥ p75(bayes_rating | votes≥3 rows of tier)` "
                 f"AND `downloads ≥ p75(downloads | all rows of tier)`. "
                 f"Strata with fewer than {MIN_STRATUM_N} ≥3-vote rows are "
                 f"flagged `low-n` and derive nothing.")
    lines.append("")
    lines.append("| tier | ≥3-vote n | p75 bayes_rating | p75 downloads | "
                 "p75 raw niveau | pass | low-n |")
    lines.append("|---|---|---|---|---|---|---|")
    for tier in tiers:
        t = thresholds[tier]
        lines.append(
            f"| {tier} | {t['voted3']} | {_num(t.get('p75_bayes_rating'))} | "
            f"{_num(t.get('p75_downloads'))} | {_num(t.get('p75_raw_niveau'))} "
            f"| {t['pass']} | {'yes' if t['low_n'] else ''} |")
    lines.append("")

    # Low-vote noise list.
    noise = sorted(
        (r for r in scored
         if r.get("votes") is not None and r["votes"] < MIN_VOTES),
        key=lambda r: r["ccan_id"])
    zero_votes = sum(1 for r in rows if r.get("votes") == 0)
    lines.append("## Low-vote noise list (votes < %d)" % MIN_VOTES)
    lines.append("")
    lines.append("Every entry below the ≥3-vote gate, with both its "
                 "Bayesian score and its Wilson lower bound. Entries here are "
                 "**excluded from the threshold derivation by construction** — "
                 "a single-vote `absolut genial (3.0)` (Hazard-3D class) can "
                 "never silently pass.")
    lines.append("")
    lines.append("| ccan_id | title | tier | category | rating | votes | "
                 "downloads | bayes_rating | wilson_lower |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    if noise:
        for r in noise:
            lines.append(
                f"| {r['ccan_id']} | {r['title']} | {r['tier']} | "
                f"{r.get('category') or '-'} | {_num(r.get('niveau_numeric'))} "
                f"| {r.get('votes')} | {_num(r.get('downloads'))} | "
                f"{_num(r.get('bayes_rating'))} | "
                f"{_num(r.get('wilson_lower'))} |")
    else:
        lines.append("| — | — | — | — | — | — | — | — | — |")
    lines.append("")
    lines.append(f"Zero-vote entries: **{zero_votes}** — their displayed "
                 "numeric is the author-history prior (CCAN FAQ), not "
                 "community signal; they are stored as-is, flagged here, and "
                 "excluded from the shrinkage priors.")
    lines.append("")

    # Validation parity.
    lines.append("## Validation-sample parity")
    lines.append("")
    lines.append(render_parity_table(parity))
    lines.append("")
    findings = [f for f in parity if any(
        fld["verdict"] == "mismatch" for fld in f["fields"].values())]
    if findings:
        lines.append("**Findings** (listing vs per-entry page diverge; "
                     "these are flagged, never an abort): "
                     + ", ".join(f"#{f['ccan_id']}" for f in findings))
    lines.append("")

    lines.append("## Methodology constants")
    lines.append("")
    lines.append(f"- Bayesian shrinkage: `m = {BAYES_M:g}` pretend votes, "
                 f"per-tier prior from votes≥1 rows, archive-wide fallback")
    lines.append(f"- Wilson lower-bound: `z = {WILSON_Z}` (95% one-sided), "
                 f"p̂ = clamp((R+3)/6, 0.01, 0.99)")
    lines.append(f"- Stratification floor: `votes ≥ {MIN_VOTES}`; "
                 f"small-stratum guard `n ≥ {MIN_STRATUM_N}`")
    lines.append(f"- Cutoff quantile: `p{int(QUANTILE * 100)}` (inclusive)")
    lines.append("")
    return "\n".join(lines)

def render_thresholds_toml(analysis: dict, meta: dict) -> str:
    rows_count = len(analysis["rows"])
    thresholds = analysis["thresholds"]
    tiers = analysis["tiers_sorted"]
    out = [
        "# ccan_thresholds.toml — Phase-0 population quality thresholds.",
        "# Generated by LegacyClonk/tools/ccan_population.py stats (pure-offline,",
        "# re-runnable at zero network cost). Consumption artifact for Phase 2",
        "# (ccan-phase2-quality-gated-curation). The accompanying",
        "# population-report.md carries the distributions, the low-vote noise",
        "# list and the validation parity table.",
        f"schema = {DATASET_SCHEMA}",
        "",
        "[method]",
        f"m = {BAYES_M:g}",
        f"z = {WILSON_Z}",
        f"min_votes = {MIN_VOTES}",
        f"min_stratum_n = {MIN_STRATUM_N}",
        f"quantile = {QUANTILE}",
        "",
        "[lineage]",
        f'generated_at = "{utc_now()}"',
        f'generated_from = "ccan_population.v{DATASET_SCHEMA}.jsonl"',
        f"dataset_rows = {rows_count}",
    ]
    for key in ("crawl_started_at", "crawl_finished_at", "request_count",
                "footer_total", "crawled_unique", "reconciliation",
                "parse_failures", "validate_sample_count",
                "validation_findings"):
        value = meta.get(key)
        if isinstance(value, str):
            out.append(f'{key} = "{value}"')
        elif value is None:
            out.append(f"# {key} = \"not recorded\"")
        else:
            out.append(f"{key} = {value}")
    out.append("")
    for tier in tiers:
        section = "".join(c for c in tier if c.isalnum() or c in "-_")
        info = thresholds[tier]
        out.append(f"[tier.{section}]")
        out.append(f"count = {info['count']}")
        out.append(f"voted1 = {info['voted1']}")
        out.append(f"voted3 = {info['voted3']}")
        out.append(f"pass = {info['pass']}")
        out.append(f"low_n = {str(info['low_n']).lower()}")
        for key in ("p75_bayes_rating", "p75_downloads", "p75_raw_niveau"):
            if info.get(key) is not None:
                out.append(f"cutoff_{key[4:]} = {info[key]!r}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"

def cmd_stats(args: argparse.Namespace) -> int:
    population_dir = Path(args.population_dir).expanduser()
    jsonl_path = population_dir / f"ccan_population.v{DATASET_SCHEMA}.jsonl"
    if not jsonl_path.is_file():
        print(f"Dataset not found: {jsonl_path}\n"
              f"Run `ccan_population.py crawl` first.", file=sys.stderr)
        return 1
    rows = load_dataset(jsonl_path)
    if rows is None:
        return 1
    if len(rows) < SANITY_FLOOR:
        print(f"Dataset below the sanity floor: {len(rows)} rows "
              f"(< {SANITY_FLOOR}) — refusing to derive thresholds from a "
              f"partial archive. Run a full `crawl` first.", file=sys.stderr)
        return 1

    analysis = analyze(rows)
    meta_path = population_dir / "population-meta.json"
    meta: dict = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    parity: list[dict] = []
    parity_path = population_dir / "validation-parity.json"
    if parity_path.is_file():
        try:
            parity = json.loads(parity_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parity = []

    report = render_report(analysis, meta, parity)
    report_path = population_dir / "population-report.md"
    report_path.write_text(report, encoding="utf-8")

    toml = render_thresholds_toml(analysis, meta)
    toml_path = Path(__file__).resolve().parent / "ccan_thresholds.toml"
    toml_path.write_text(toml, encoding="utf-8")

    print(f"Stats: {len(rows)} rows analyzed")
    print(f"Report: {report_path}")
    print(f"Thresholds: {toml_path}")
    return 0

# ===========================================================================
# CLI
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ccan_population.py",
        description="CCAN Phase-0 population crawl + offline statistics.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--population-dir", default=str(DEFAULT_POPULATION_DIR),
        help=f"Dataset/runtime directory (default: {DEFAULT_POPULATION_DIR}; "
             f"CCAN_POPULATION_DIR env var overrides).")
    parent.add_argument(
        "--rate-limit", type=float, default=DEFAULT_RATE_LIMIT,
        help=f"Seconds between requests (default: {DEFAULT_RATE_LIMIT}).")
    parent.add_argument(
        "--retry", type=int, default=3,
        help="Max retries on transient failure (default: 3).")

    p_crawl = sub.add_parser(
        "crawl", parents=[parent],
        help="Crawl the enriched listing into the population dataset.")
    p_crawl.add_argument(
        "--validate-sample", type=int, default=None, metavar="N",
        help="Per-entry validation sample size (default: 20).")
    p_crawl.add_argument(
        "--validate-count", type=int, default=None, metavar="N",
        help="Alias that can explicitly disable the validation sample "
             "(--validate-count 0).")
    p_crawl.set_defaults(func=cmd_crawl)

    p_stats = sub.add_parser(
        "stats", parents=[parent],
        help="Pure-offline statistics from the crawled dataset.")
    p_stats.set_defaults(func=cmd_stats)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
