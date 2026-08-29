#!/usr/bin/env python3
"""Lint file:line citation freshness in docs/.

Scans docs/**/*.md for backtick-wrapped file:line and file:line-line
citations, resolves the cited file against src/, and verifies the cited
line(s) are within the file's current bounds.

Usage:
    python3 tools/check_citations.py [OPTIONS] [PATH...]
    # default PATH: docs/

Options:
    --budget N          Fail if new drift exceeds N (default: 0).
    --allowlist PATH    Allowlist file (default: tools/citation-allowlist.txt).
    --advisory          Exit 0 always; print stale count for trend tracking.
    --help              Show this help.

Exit codes:
    0 — all citations fresh (or within budget, or advisory mode).
    1 — new drift exceeds budget.
    2 — infrastructure error (missing scan target, etc.).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # LegacyClonk/
DEFAULT_ALLOWLIST = REPO_ROOT / "tools" / "citation-allowlist.txt"

# Backtick-wrapped citation: `file.ext:NNN` or `file.ext:NNN-MMM`
CITE_RE = re.compile(
    r"`"
    r"([^`]+\.(?:cpp|h|c|cc|hpp))"
    r":(\d+)"
    r"(?:-(\d+))?"
    r"`"
)

_line_cache: dict[Path, int] = {}


def extract_citations(text: str) -> list[tuple[str, int, int | None]]:
    """Return all backtick-wrapped citations found in `text`.

    Each element is (src_raw, start_line, end_line_or_None).
    """
    out: list[tuple[str, int, int | None]] = []
    for m in CITE_RE.finditer(text):
        raw = m.group(1)
        start = int(m.group(2))
        end_s = m.group(3)
        end = int(end_s) if end_s is not None else None
        out.append((raw, start, end))
    return out


def resolve_src_file(raw_path: str) -> Path | None:
    """Resolve a cited file path to an absolute Path, or None if not found.

    Resolution order:
      1. Absolute path — used as-is.
      2. REPO_ROOT/src/<raw_path> — covers bare filenames and src/-prefixed paths.
      3. REPO_ROOT/<raw_path> — covers other relative paths.
    """
    p = Path(raw_path)
    if p.is_absolute():
        return p if p.exists() else None
    candidate = REPO_ROOT / "src" / raw_path
    if candidate.exists():
        return candidate
    candidate = REPO_ROOT / raw_path
    if candidate.exists():
        return candidate
    return None


def line_count(path: Path) -> int:
    """Return the number of lines in `path`, or -1 if unreadable."""
    if path not in _line_cache:
        try:
            _line_cache[path] = len(
                path.read_text(encoding="utf-8", errors="replace").splitlines()
            )
        except OSError:
            _line_cache[path] = -1
    return _line_cache[path]


def check_citation(src_raw: str, start: int, end: int | None) -> tuple[str, str]:
    """Check a single citation. Returns (status, message).

    status is "pass" or "fail". message is empty on pass, a human-readable
    diagnostic on fail.
    """
    resolved = resolve_src_file(src_raw)
    if resolved is None:
        return ("fail", f"cited file not found: {src_raw}")
    n = line_count(resolved)
    if n < 0:
        return ("fail", f"cannot read cited file: {src_raw}")
    if start > n:
        return ("fail", f"citation {src_raw}:{start} is out of bounds (file has {n} lines)")
    # Range check: only flag the end if end >= start (malformed ranges like
    # X:400-300 are treated as single-line citations at `start`).
    if end is not None and end >= start and end > n:
        return ("fail", f"citation {src_raw}:{start}-{end} range end out of bounds (file has {n} lines)")
    return ("pass", "")


def scan_file(doc_path: Path, allowlist: set[str]) -> tuple[list[dict], int]:
    """Scan a single doc file.

    Returns (failures, citations_checked). Each failure dict has keys:
    doc_rel, doc_lineno, src_raw, start, end, message, allowlisted.
    """
    try:
        rel = doc_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(doc_path)
    try:
        text = doc_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], 0
    failures: list[dict] = []
    total = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        for (src_raw, start, end) in extract_citations(line):
            total += 1
            status, msg = check_citation(src_raw, start, end)
            if status == "fail":
                key = f"{rel}:{lineno}"
                failures.append({
                    "doc_rel": rel,
                    "doc_lineno": lineno,
                    "src_raw": src_raw,
                    "start": start,
                    "end": end,
                    "message": msg,
                    "allowlisted": key in allowlist,
                })
    return failures, total


def scan_docs(doc_files: list[Path], allowlist: set[str]) -> tuple[list[dict], int]:
    """Scan all doc files. Returns (failures, total_citations_checked)."""
    all_failures: list[dict] = []
    total_checked = 0
    for doc_path in doc_files:
        failures, checked = scan_file(doc_path, allowlist)
        all_failures.extend(failures)
        total_checked += checked
    return all_failures, total_checked


def collect_doc_files(scan_targets: list[Path]) -> list[Path]:
    """Expand scan targets into a sorted, de-duplicated list of .md files."""
    files: list[Path] = []
    for target in scan_targets:
        if target.is_file() and target.suffix == ".md":
            files.append(target)
        elif target.is_dir():
            files.extend(target.rglob("*.md"))
    return sorted(set(files))


def load_allowlist(path: Path) -> set[str]:
    """Load allowlist entries (doc_rel:doc_lineno) from `path`.

    Blank lines and `#`-prefixed comments are skipped. Returns an empty set
    if the file does not exist.
    """
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def run(scan_targets: list[Path], allowlist: set[str], budget: int, advisory: bool) -> int:
    """Run the linter. Returns exit code (0, 1, or 2)."""
    doc_files = collect_doc_files(scan_targets)
    if not doc_files:
        print("error: no .md files found in scan targets", file=sys.stderr)
        return 2

    all_failures, total_checked = scan_docs(doc_files, allowlist)

    for f in all_failures:
        print(f"{f['doc_rel']}:{f['doc_lineno']}: {f['message']}", file=sys.stderr)

    failed = len(all_failures)
    allowlisted_count = sum(1 for f in all_failures if f["allowlisted"])
    new_drift = failed - allowlisted_count

    print(
        f"{total_checked} citations checked, {failed} failed, "
        f"{allowlisted_count} allowlisted, {new_drift} new drift (budget {budget})",
        file=sys.stderr,
    )

    if advisory:
        return 0
    if new_drift > budget:
        print(f"ERROR: new drift ({new_drift}) exceeds budget ({budget})", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint file:line citation freshness in docs/.",
    )
    parser.add_argument("paths", nargs="*", default=["docs"],
                        help="doc files/dirs to scan (default: docs)")
    parser.add_argument("--budget", type=int, default=0,
                        help="fail if new drift exceeds N (default: 0)")
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST,
                        help="allowlist file (default: tools/citation-allowlist.txt)")
    parser.add_argument("--advisory", action="store_true",
                        help="exit 0 always; print stale count for trend tracking")
    args = parser.parse_args()

    targets: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if not path.is_absolute():
            path = REPO_ROOT / p
        if not path.exists():
            print(f"error: scan target does not exist: {path}", file=sys.stderr)
            return 2
        targets.append(path)

    allowlist = load_allowlist(args.allowlist)
    return run(targets, allowlist, args.budget, args.advisory)


if __name__ == "__main__":
    sys.exit(main())
