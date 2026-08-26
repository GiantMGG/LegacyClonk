#!/usr/bin/env python3
"""Generate a TODO/FIXME triage worksheet to stdout.

For each marker line in src/**/*.{cpp,h}, emit a Markdown table row:
    | # | blame-date | file:line | marker-text | category | disposition | status |

Usage:
    python3 tools/todo_audit.py > docs/TODO-FIXME-triage.md
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\b")


def scan_file(path: Path):
    rel = path.relative_to(REPO_ROOT).as_posix()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        if MARKER_RE.search(line):
            yield rel, lineno, line.strip()


def find_markers():
    markers = []
    for ext in ("*.cpp", "*.h"):
        for path in sorted(SRC_ROOT.rglob(ext)):
            for rel, line, text in scan_file(path):
                markers.append((rel, line, text))
    return markers


def blame_date(rel_path: str, line: int) -> str:
    try:
        out = subprocess.run(
            ["git", "blame", "-L", f"{line},{line}", "--format=%ai", "--", rel_path],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.strip().split(" ")[0]
    except FileNotFoundError:
        pass
    return "unknown"


def main() -> int:
    markers = find_markers()
    # Attach blame date
    dated = []
    for rel, line, text in markers:
        date = blame_date(rel, line)
        dated.append((date, rel, line, text))
    # Sort by (date, file, line) for stable oldest-first ordering
    dated.sort(key=lambda x: (x[0], x[1], x[2]))

    print("# TODO/FIXME triage worksheet")
    print()
    print("Frozen snapshot of every `TODO|FIXME|HACK|XXX|BUG` marker in `src/`.")
    print("Columns: `#`, `blame-date`, `file:line`, `marker-text`, `category`, `disposition`, `status`.")
    print()
    print("| # | blame-date | file:line | marker-text | category | disposition | status |")
    print("|---|---|---|---|---|---|---|")
    for idx, (date, rel, line, text) in enumerate(dated, start=1):
        snippet = text.replace("|", "\\|")
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        print(f"| {idx} | {date} | {rel}:{line} | `{snippet}` |   |   | open (grandfathered) |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
