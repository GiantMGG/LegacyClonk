#!/usr/bin/env python3
"""Lint TODO/FIXME markers in src/.

Enforces the convention that every new marker includes an upstream issue link:
    // TODO(legacyclonk/LegacyClonk#NNN): <summary>
    // FIXME(legacyclonk/LegacyClonk#NNN): <summary>

Accepted prefixes: TODO, FIXME, HACK, XXX, BUG (upper-case only).
Grandfathered markers are exempt via tools/todo-legacy-allowlist.txt (format: `path:line`).

The lint scans comment lines only — a line is flagged if it contains a `//` or
`/*` token followed by a marker. String-literal "FIXME"s (e.g. fputs("FIXME: ..."))
are NOT flagged because the marker is not inside a comment.

Usage:
    python3 tools/check_todos.py [path]    # default path: src/
Exit 0 if all markers conform or are allowlisted; exit 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Comment-line marker: a `//` or `/*` token followed (eventually) by a marker keyword.
COMMENT_MARKER_RE = re.compile(r"(?://|/\*).*?\b(TODO|FIXME|HACK|XXX|BUG)\b")
# Conforming marker: keyword immediately followed by (legacyclonk/LegacyClonk#<digits>)
ISSUE_LINK_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\(legacyclonk/LegacyClonk#\d+\)")
# Broad marker regex (for stale-allowlist check — matches markers anywhere, including
# string literals like fputs("FIXME: ...")).
BROAD_MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\b")
ALLOWLIST_PATH = REPO_ROOT / "tools" / "todo-legacy-allowlist.txt"

def load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.exists():
        return set()
    return {
        line.strip()
        for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

def scan_file(path: Path, allowlist: set[str]) -> list[str]:
    rel = path.relative_to(REPO_ROOT).as_posix()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    errors: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not COMMENT_MARKER_RE.search(line):
            continue
        if ISSUE_LINK_RE.search(line):
            continue
        key = f"{rel}:{lineno}"
        if key in allowlist:
            continue
        errors.append(
            f"{rel}:{lineno}: marker does not match required format "
            f"'TODO(legacyclonk/LegacyClonk#NNN): <summary>'\n"
            f"  {line.strip()}"
        )
    return errors

def scan_tree(target: Path, allowlist: set[str]) -> list[str]:
    errors: list[str] = []
    for ext in ("*.cpp", "*.h"):
        for path in sorted(target.rglob(ext)):
            errors.extend(scan_file(path, allowlist))
    return errors

def check_stale_allowlist(allowlist: set[str]) -> list[str]:
    warnings: list[str] = []
    for entry in sorted(allowlist):
        rel, _, line_str = entry.rpartition(":")
        if not rel or not line_str.isdigit():
            warnings.append(f"malformed allowlist entry: {entry}")
            continue
        fpath = REPO_ROOT / rel
        if not fpath.exists():
            warnings.append(f"stale allowlist entry (file missing): {entry}")
            continue
        try:
            lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            warnings.append(f"cannot read file for allowlist entry: {entry}")
            continue
        line_no = int(line_str)
        if line_no < 1 or line_no > len(lines):
            warnings.append(f"stale allowlist entry (line out of range): {entry}")
            continue
        if not BROAD_MARKER_RE.search(lines[line_no - 1]):
            warnings.append(f"stale allowlist entry (no marker at line): {entry}")
    return warnings

def main() -> int:
    args = sys.argv[1:]
    target = Path(args[0]) if args else Path("src")
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.exists():
        print(f"error: scan target does not exist: {target}", file=sys.stderr)
        return 2

    allowlist = load_allowlist()

    if target.is_file():
        errors = scan_file(target, allowlist)
    else:
        errors = scan_tree(target, allowlist)

    for e in errors:
        print(e, file=sys.stderr)

    for w in check_stale_allowlist(allowlist):
        print(f"warning: {w}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} marker(s) do not match the required format.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
