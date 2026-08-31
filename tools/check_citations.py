#!/usr/bin/env python3
"""Lint file:line citation freshness in docs/.

Scans docs/**/*.md for backtick-wrapped file:line and file:line-line
citations (cited-file extensions: cpp, h, c, cc, hpp, md, txt), resolves
the cited file against src/, and verifies the cited line(s) are within
the file's current bounds.

On top of the bounds check, an opt-in content-expectations ledger
(tools/citation-expectations.txt) adds two failure classes: an
expectation mismatch (a cited line no longer contains the expected
snippet after normalization) and an orphaned expectation (a ledger
key's doc line no longer carries a citation).

Usage:
    python3 tools/check_citations.py [OPTIONS] [PATH...]
    # default PATH: docs/

Options:
    --budget N          Fail if new drift exceeds N (default: 0).
    --allowlist PATH    Allowlist file (default: tools/citation-allowlist.txt).
    --expectations PATH Content expectations ledger
                        (default: tools/citation-expectations.txt).
    --advisory          Exit 0 always; print stale count for trend tracking.
    --help              Show this help.

Exit codes:
    0 — all citations fresh (or within budget, or advisory mode).
    1 — new drift exceeds budget.
    2 — infrastructure error (missing scan target, malformed or
        unreadable expectations ledger, etc.).
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # LegacyClonk/
DEFAULT_ALLOWLIST = REPO_ROOT / "tools" / "citation-allowlist.txt"
DEFAULT_EXPECTATIONS = REPO_ROOT / "tools" / "citation-expectations.txt"

# Backtick-wrapped citation: `file.ext:NNN` or `file.ext:NNN-MMM`
# (ext one of: cpp, h, c, cc, hpp, md, txt)
CITE_RE = re.compile(
    r"`"
    r"([^`]+\.(?:cpp|h|c|cc|hpp|md|txt))"
    r":(\d+)"
    r"(?:-(\d+))?"
    r"`"
)

_line_cache: dict[Path, int] = {}

# Smart quotes/dashes -> ASCII canonical forms, for content matching.
_SMART_MAP = str.maketrans({
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote / apostrophe
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
})

_content_cache: dict[Path, list[str]] = {}


def normalize_snippet(s: str) -> str:
    """NFC -> smart-quote/dash canonicalization -> casefold -> collapse."""
    s = unicodedata.normalize("NFC", s)
    s = s.translate(_SMART_MAP)
    s = s.casefold()
    return re.sub(r"\s+", " ", s).strip()


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


def file_lines(path: Path) -> list[str]:
    """Cached line list (utf-8, errors='replace'); [] when unreadable."""
    if path not in _content_cache:
        try:
            _content_cache[path] = path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            _content_cache[path] = []
    return _content_cache[path]


def locate_snippet(path: Path, snippet: str) -> list[int]:
    """1-based line numbers in `path` whose normalized content contains
    the normalized snippet. Runs only on mismatch; reads via file_lines."""
    norm = normalize_snippet(snippet)
    return [
        i
        for i, line in enumerate(file_lines(path), start=1)
        if norm in normalize_snippet(line)
    ]


def check_snippet(cites: list[tuple[str, int, int | None]], snippet: str) -> tuple[bool, str]:
    """True iff the normalized snippet is contained in the normalized
    cited lines (any line of a range) of at least one citation in `cites`
    (all pre-verified in bounds). On failure returns the mismatch message
    with located candidates, distinguishing line drift (found at line(s))
    from content drift (not found anywhere)."""
    if not cites:
        return (False, "expectation mismatch: no bounds-passing citations to check")
    norm = normalize_snippet(snippet)
    for (src_raw, start, end) in cites:
        resolved = resolve_src_file(src_raw)
        if resolved is None:
            continue
        lines = file_lines(resolved)
        hi = start if end is None or end < start else end
        for i in range(start, min(hi, len(lines)) + 1):
            if norm in normalize_snippet(lines[i - 1]):
                return (True, "")
    src_raw, start, _end = cites[0]
    head = (
        f"expectation mismatch: `{src_raw}:{start}` no longer contains "
        f"\"{snippet}\" (after normalization)"
    )
    resolved = resolve_src_file(src_raw)
    found = locate_snippet(resolved, snippet) if resolved is not None else []
    if found:
        locs = ", ".join(str(n) for n in found[:5])
        if len(found) > 5:
            locs += ", …"
        return (False, f"{head}; found at line(s): {locs}")
    return (False, (
        f"{head}; snippet not found anywhere in {src_raw} — content "
        "drifted, update tools/citation-expectations.txt"
    ))


def scan_file(doc_path: Path, allowlist: set[str],
              expectations: dict[str, list[str]],
              exercised: set[str]) -> tuple[list[dict], int]:
    """Scan a single doc file.

    Returns (failures, citations_checked). Each failure dict has keys:
    doc_rel, doc_lineno, src_raw, start, end, message, allowlisted, kind
    (kind is "bounds" | "content").
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
        citations = extract_citations(line)
        key = f"{rel}:{lineno}"
        if citations and key in expectations:
            exercised.add(key)
        passing: list[tuple[str, int, int | None]] = []
        for (src_raw, start, end) in citations:
            total += 1
            status, msg = check_citation(src_raw, start, end)
            if status == "fail":
                failures.append({
                    "doc_rel": rel,
                    "doc_lineno": lineno,
                    "src_raw": src_raw,
                    "start": start,
                    "end": end,
                    "message": msg,
                    "allowlisted": key in allowlist,
                    "kind": "bounds",
                })
            else:
                passing.append((src_raw, start, end))
        if key in expectations and passing:
            for snippet in expectations[key]:
                ok, msg = check_snippet(passing, snippet)
                if not ok:
                    failures.append({
                        "doc_rel": rel,
                        "doc_lineno": lineno,
                        "src_raw": passing[0][0],
                        "start": passing[0][1],
                        "end": passing[0][2],
                        "message": msg,
                        "allowlisted": key in allowlist,
                        "kind": "content",
                    })
    return failures, total


def scan_docs(doc_files: list[Path], allowlist: set[str],
              expectations: dict[str, list[str]],
              exercised: set[str]) -> tuple[list[dict], int]:
    """Scan all doc files. Returns (failures, total_citations_checked)."""
    all_failures: list[dict] = []
    total_checked = 0
    for doc_path in doc_files:
        failures, checked = scan_file(doc_path, allowlist, expectations, exercised)
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


def load_expectations(path: Path) -> dict[str, list[str]]:
    """Parse the content-expectations ledger at `path`.

    Grammar (per line): blank | `#` comment | `key " -> " snippet`.
    Keys match `(.+):(\\d+)` (doc_rel:lineno). Same-key entries append.
    The snippet is taken literally (no unquoting; embedded `->` safe).

    Raises ValueError (naming the 1-based line number) on a malformed
    entry. A missing file yields {} (gate-identical default behavior).
    """
    if not path.exists():
        return {}
    out: dict[str, list[str]] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, snippet = stripped.partition(" -> ")
        if not sep:
            raise ValueError(
                f"{path.name}:{lineno}: malformed entry "
                f"(no ' -> ' separator): {stripped!r}"
            )
        snippet = snippet.strip()
        if not snippet:
            raise ValueError(f"{path.name}:{lineno}: empty snippet")
        if not re.fullmatch(r"(.+):(\d+)", key):
            raise ValueError(
                f"{path.name}:{lineno}: malformed key "
                f"(expected doc_rel:lineno): {key!r}"
            )
        out.setdefault(key, []).append(snippet)
    return out


def orphan_failures(expectations: dict[str, list[str]], exercised: set[str],
                    allowlist: set[str]) -> list[dict]:
    """Orphan pass: ledger keys whose doc line was never exercised (the
    line no longer carries a citation, or the doc is outside the scan).
    """
    failures: list[dict] = []
    for key in expectations:
        if key not in exercised:
            doc_rel, _, lineno_s = key.rpartition(":")
            failures.append({
                "doc_rel": doc_rel,
                "doc_lineno": int(lineno_s),
                "src_raw": "",
                "start": 0,
                "end": None,
                "message": (
                    "orphaned expectation: no citation on this line — "
                    "delete or re-key the entry in "
                    "tools/citation-expectations.txt"
                ),
                "allowlisted": key in allowlist,
                "kind": "orphan",
            })
    return failures


def run(scan_targets: list[Path], allowlist: set[str], budget: int, advisory: bool,
        expectations: dict[str, list[str]] | None = None) -> int:
    """Run the linter. Returns exit code (0, 1, or 2)."""
    doc_files = collect_doc_files(scan_targets)
    if not doc_files:
        print("error: no .md files found in scan targets", file=sys.stderr)
        return 2

    exp = expectations if expectations is not None else {}
    exercised: set[str] = set()
    all_failures, total_checked = scan_docs(doc_files, allowlist, exp, exercised)

    all_failures.extend(orphan_failures(exp, exercised, allowlist))

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
    mismatches = sum(1 for f in all_failures if f["kind"] == "content")
    orphans = sum(1 for f in all_failures if f["kind"] == "orphan")
    print(
        f"{len(exp)} expectations checked, {mismatches} content mismatches, "
        f"{orphans} orphaned",
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
        description=(
            "Lint file:line citation freshness in docs/. "
            "Cited-file extensions: cpp, h, c, cc, hpp, md, txt."
        ),
    )
    parser.add_argument("paths", nargs="*", default=["docs"],
                        help="doc files/dirs to scan (default: docs)")
    parser.add_argument("--budget", type=int, default=0,
                        help="fail if new drift exceeds N (default: 0)")
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST,
                        help="allowlist file (default: tools/citation-allowlist.txt)")
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS,
                        help="content expectations ledger "
                             "(default: tools/citation-expectations.txt)")
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

    try:
        expectations = load_expectations(args.expectations)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    allowlist = load_allowlist(args.allowlist)
    return run(targets, allowlist, args.budget, args.advisory, expectations)


if __name__ == "__main__":
    sys.exit(main())
