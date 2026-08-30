#!/usr/bin/env python3
"""Assemble release notes from a curated highlights fragment + a git-cliff digest.

Invoked by the ``changelog`` job in .github/workflows/release.yml. Stdlib only so
it runs in the default runner image without ``pip install``.

Flow:
  1. Validate the highlights fragment for the current buildversion.
     - Stable tag + missing file  -> sys.exit(1).
     - Pre-release + missing file -> substitute a placeholder.
  2. Write release-notes.md = "## Highlights\\n\\n{highlights}\\n\\n## Full changelog\\n\\n{digest}".
  3. Splice the digest into CHANGELOG.md above the marker comment.
     - Refuse if CHANGELOG.md already has a ``## [{buildversion}]`` line.
  4. Mirror CHANGELOG.md -> docs/changelog.md.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

PRERELEASE_RE = re.compile(r"-(rc|beta|alpha)\d*$", re.IGNORECASE)
MARKER = "<!-- git-cliff prepends new release sections above this line. -->"

def is_prerelease(tag: str) -> bool:
    """Return True if the tag matches a pre-release suffix (``-rc*``, ``-beta*``, ``-alpha*``)."""
    return bool(PRERELEASE_RE.search(tag))

def load_highlights(buildversion: str, tag: str, highlights_dir: Path) -> str:
    """Load the highlights fragment for ``buildversion``.

    Stable tag + missing file -> sys.exit(1) with a clear error.
    Pre-release + missing file -> placeholder string.
    """
    path = highlights_dir / f"v{buildversion}.highlights.md"
    if path.is_file():
        return path.read_text(encoding="utf-8").rstrip()
    if is_prerelease(tag):
        return "*(pre-release \u2014 no highlights)*"
    sys.exit(
        f"FatalError: highlights fragment missing: {path}\n"
        f"Create it with 3-8 player-facing bullets before tagging."
    )

def assemble_release_notes(highlights: str, digest: str) -> str:
    """Build the release-notes.md body: highlights + full changelog digest."""
    return (
        "## Highlights\n\n"
        f"{highlights}\n\n"
        "## Full changelog\n\n"
        f"{digest.rstrip()}\n"
    )

def splice_changelog(changelog: Path, digest: str, buildversion: str) -> None:
    """Splice the git-cliff digest into CHANGELOG.md above the marker comment.

    Refuses (sys.exit(1)) if CHANGELOG.md already contains a section for
    ``buildversion``, guarding against double-prepending on re-runs.
    """
    text = changelog.read_text(encoding="utf-8")
    if re.search(rf"^## \[{re.escape(buildversion)}\]", text, re.MULTILINE):
        sys.exit(
            f"FatalError: CHANGELOG.md already contains section [{buildversion}]; "
            f"remove it before re-running."
        )
    if MARKER in text:
        text = text.replace(MARKER, f"{digest.rstrip()}\n\n{MARKER}")
    else:
        text = text.rstrip() + "\n\n" + digest.rstrip() + "\n"
    changelog.write_text(text, encoding="utf-8")

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--buildversion", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--digest", required=True, type=Path)
    p.add_argument("--highlights-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--changelog", required=True, type=Path)
    p.add_argument("--docs-mirror", required=True, type=Path)
    args = p.parse_args()

    highlights = load_highlights(args.buildversion, args.tag, args.highlights_dir)
    digest = args.digest.read_text(encoding="utf-8")
    release_notes = assemble_release_notes(highlights, digest)
    args.out.write_text(release_notes, encoding="utf-8")

    splice_changelog(args.changelog, digest, args.buildversion)
    shutil.copyfile(args.changelog, args.docs_mirror)
    return 0

if __name__ == "__main__":
    sys.exit(main())
