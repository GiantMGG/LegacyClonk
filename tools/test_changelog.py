"""Pytest suite for tools/build_release_notes.py.

Exercises the pure functions by importing the module and calling its helpers with
tmp-path fixtures. No network, no git.

Run locally:

    cd LegacyClonk
    pytest tools/test_changelog.py -v
"""
import sys
from pathlib import Path

import pytest

# Make tools/ importable.
sys.path.insert(0, str(Path(__file__).parent))
import build_release_notes as brn

# ---------------------------------------------------------------------------
# Highlights validation
# ---------------------------------------------------------------------------

def test_highlights_missing_stable_fails(tmp_path: Path) -> None:
    """Stable tag + missing highlights file -> SystemExit with error message."""
    with pytest.raises(SystemExit) as exc:
        brn.load_highlights("366", "v366", tmp_path)
    assert exc.value.code != 0
    assert "highlights fragment missing" in str(exc.value)

def test_highlights_missing_prerelease_warns(tmp_path: Path) -> None:
    """Pre-release tag + missing highlights -> placeholder string, no exit."""
    result = brn.load_highlights("366-rc1", "v366-rc1", tmp_path)
    assert "pre-release" in result.lower()

def test_highlights_present_stable_ok(tmp_path: Path) -> None:
    """Stable tag + highlights file with 3 bullets -> returns file content."""
    hl = tmp_path / "v366.highlights.md"
    hl.write_text(
        "- bullet one\n- bullet two\n- bullet three\n", encoding="utf-8"
    )
    result = brn.load_highlights("366", "v366", tmp_path)
    assert "bullet one" in result
    assert "bullet three" in result

# ---------------------------------------------------------------------------
# Release notes assembly
# ---------------------------------------------------------------------------

def test_release_notes_structure(tmp_path: Path) -> None:
    """release-notes.md has exactly two ## headings (Highlights, Full changelog)
    in that order, and the digest block is appended verbatim."""
    highlights = "- bullet one\n- bullet two\n- bullet three"
    digest = (
        "## [366] - 2026-08-29\n\n"
        "### Added\n"
        "- **network**: test (abcdef0)\n"
    )
    notes = brn.assemble_release_notes(highlights, digest)
    assert notes.startswith("## Highlights\n")
    assert "## Full changelog" in notes
    headings = [line for line in notes.splitlines() if line.startswith("## ")]
    # Highlights and Full changelog must be the first two ## headings, in order.
    # The digest may contribute its own ## [version] heading after them.
    assert headings[:2] == ["## Highlights", "## Full changelog"]
    assert "abcdef0" in notes

# ---------------------------------------------------------------------------
# CHANGELOG.md splice
# ---------------------------------------------------------------------------

_SEED_CHANGELOG = """\
# Changelog

All notable changes to LegacyClonk are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

<!-- git-cliff prepends new release sections above this line. -->
"""

def test_changelog_prepend_splice(tmp_path: Path) -> None:
    """Splicing inserts the new section above the marker and below the header,
    and leaves the rest of the file intact."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_SEED_CHANGELOG, encoding="utf-8")
    digest = (
        "## [366] - 2026-08-29\n\n"
        "### Added\n"
        "- **network**: test (abcdef0)\n"
    )
    brn.splice_changelog(changelog, digest, "366")
    result = changelog.read_text(encoding="utf-8")
    assert "## [366] - 2026-08-29" in result
    assert result.index("## [366]") < result.index("<!-- git-cliff")
    assert "All notable changes" in result  # header preserved

def test_changelog_duplicate_section_refused(tmp_path: Path) -> None:
    """If CHANGELOG.md already contains ## [366], the splice step exits and does
    not modify the file."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_SEED_CHANGELOG, encoding="utf-8")
    digest = (
        "## [366] - 2026-08-29\n\n"
        "### Added\n"
        "- **network**: test (abcdef0)\n"
    )
    brn.splice_changelog(changelog, digest, "366")
    original = changelog.read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        brn.splice_changelog(changelog, digest, "366")
    assert exc.value.code != 0
    assert "already contains section" in str(exc.value)
    assert changelog.read_text(encoding="utf-8") == original

# ---------------------------------------------------------------------------
# Scope map coverage
# ---------------------------------------------------------------------------

_KNOWN_SCOPES = {
    "network", "savegame", "rollback", "replay", "weather", "preservation",
    "input", "ccan", "tutorial", "players", "contributors",
}

def test_scope_map_coverage() -> None:
    """Every scope listed in cliff.toml's Tera elif chain is present; unknown
    scopes fall through to verbatim rendering via the else branch."""
    cliff_path = Path(__file__).parent.parent / "cliff.toml"
    text = cliff_path.read_text(encoding="utf-8")
    found = set()
    for scope in _KNOWN_SCOPES:
        if f'commit.scope == "{scope}"' in text:
            found.add(scope)
    missing = _KNOWN_SCOPES - found
    assert not missing, f"Scopes missing from cliff.toml template: {missing}"
    # Verify the else fall-through exists.
    assert "{% else %}" in text
    # Verify the verbatim rendering uses commit.scope.
    assert "**{{ commit.scope }}**" in text

# ---------------------------------------------------------------------------
# Docs mirror (full main() flow)
# ---------------------------------------------------------------------------

def test_docs_mirror_copied(tmp_path: Path) -> None:
    """After a successful main() run, docs/changelog.md is byte-identical to
    CHANGELOG.md, and release-notes.md has the expected structure."""
    highlights_dir = tmp_path / "docs" / "changelog"
    highlights_dir.mkdir(parents=True)
    (highlights_dir / "v366.highlights.md").write_text(
        "- bullet one\n- bullet two\n- bullet three\n", encoding="utf-8"
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_SEED_CHANGELOG, encoding="utf-8")
    digest_file = tmp_path / "digest.md"
    digest_file.write_text(
        "## [366] - 2026-08-29\n\n"
        "### Added\n"
        "- **network**: test (abcdef0)\n",
        encoding="utf-8",
    )
    out = tmp_path / "release-notes.md"
    mirror = tmp_path / "docs" / "changelog.md"

    old_argv = sys.argv
    sys.argv = [
        "build_release_notes.py",
        "--buildversion", "366",
        "--tag", "v366",
        "--digest", str(digest_file),
        "--highlights-dir", str(highlights_dir),
        "--out", str(out),
        "--changelog", str(changelog),
        "--docs-mirror", str(mirror),
    ]
    try:
        rc = brn.main()
        assert rc == 0
    finally:
        sys.argv = old_argv

    assert mirror.read_text(encoding="utf-8") == changelog.read_text(encoding="utf-8")
    notes = out.read_text(encoding="utf-8")
    assert notes.startswith("## Highlights\n")
    assert "## Full changelog" in notes
    assert "## [366] - 2026-08-29" in notes

# ---------------------------------------------------------------------------
# --skip-splice (nightly dry-run path)
# ---------------------------------------------------------------------------

_DIGEST = (
    "## [366] - 2026-08-29\n\n"
    "### Added\n"
    "- **network**: test (abcdef0)\n"
)

_PRE_SPLICED_CHANGELOG = (
    _SEED_CHANGELOG
    + "\n## [366] - 2026-09-01\n\n### Added\n\n- **network**: test (abcdef0)\n"
)

def _invoke_main(argv: list[str]) -> int:
    """Run brn.main() with a synthetic argv (the workflow invocation shape)."""
    old_argv = sys.argv
    sys.argv = ["build_release_notes.py", *argv]
    try:
        return brn.main()
    finally:
        sys.argv = old_argv

def _seed_tree(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Seed a workflow-shaped tree with a PRE-SPLICED changelog (master's
    current state). Returns (highlights_dir, digest, changelog, out, mirror)."""
    highlights_dir = tmp_path / "docs" / "changelog"
    highlights_dir.mkdir(parents=True)
    (highlights_dir / "v366.highlights.md").write_text(
        "- bullet one\n- bullet two\n- bullet three\n", encoding="utf-8"
    )
    digest = tmp_path / "digest.md"
    digest.write_text(_DIGEST, encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_PRE_SPLICED_CHANGELOG, encoding="utf-8")
    mirror = tmp_path / "docs" / "changelog.md"
    mirror.write_text("SENTINEL-MIRROR", encoding="utf-8")
    return highlights_dir, digest, changelog, tmp_path / "release-notes.md", mirror

def test_skip_splice_leaves_changelog_and_mirror_untouched(
    tmp_path: Path, capsys
) -> None:
    """(a) --skip-splice on the pre-spliced nightly state: rc 0, notes written,
    CHANGELOG.md + docs mirror byte-identical, stderr notice emitted."""
    highlights_dir, digest, changelog, out, mirror = _seed_tree(tmp_path)
    original = changelog.read_text(encoding="utf-8")
    sentinel = mirror.read_text(encoding="utf-8")

    rc = _invoke_main([
        "--buildversion", "366",
        "--tag", "v366",
        "--digest", str(digest),
        "--highlights-dir", str(highlights_dir),
        "--out", str(out),
        "--changelog", str(changelog),
        "--docs-mirror", str(mirror),
        "--skip-splice",
    ])

    assert rc == 0
    err = capsys.readouterr().err
    assert "--skip-splice" in err
    assert "untouched" in err
    notes = out.read_text(encoding="utf-8")
    assert notes.startswith("## Highlights\n")
    assert "## Full changelog" in notes
    assert "abcdef0" in notes
    assert changelog.read_text(encoding="utf-8") == original
    assert mirror.read_text(encoding="utf-8") == sentinel

def test_skip_splice_still_requires_highlights(tmp_path: Path) -> None:
    """(b) --skip-splice does NOT bypass the highlights guard: stable tag +
    missing fragment still exits 1 before writing anything."""
    highlights_dir = tmp_path / "docs" / "changelog"
    highlights_dir.mkdir(parents=True)
    digest = tmp_path / "digest.md"
    digest.write_text(_DIGEST, encoding="utf-8")
    out = tmp_path / "release-notes.md"

    with pytest.raises(SystemExit) as exc:
        _invoke_main([
            "--buildversion", "366",
            "--tag", "v366",
            "--digest", str(digest),
            "--highlights-dir", str(highlights_dir),
            "--out", str(out),
            "--changelog", str(tmp_path / "CHANGELOG.md"),
            "--docs-mirror", str(tmp_path / "docs" / "changelog.md"),
            "--skip-splice",
        ])
    assert exc.value.code != 0
    assert "highlights fragment missing" in str(exc.value)
    assert not out.exists()

def test_duplicate_guard_fires_through_main(tmp_path: Path) -> None:
    """(c) WITHOUT the flag, main() hits the duplicate-section guard on the
    pre-spliced changelog — the pre-fix nightly red, reproduced end-to-end."""
    highlights_dir, digest, changelog, out, mirror = _seed_tree(tmp_path)
    original = changelog.read_text(encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        _invoke_main([
            "--buildversion", "366",
            "--tag", "v366",
            "--digest", str(digest),
            "--highlights-dir", str(highlights_dir),
            "--out", str(out),
            "--changelog", str(changelog),
            "--docs-mirror", str(mirror),
        ])
    assert exc.value.code != 0
    assert "already contains section" in str(exc.value)
    assert changelog.read_text(encoding="utf-8") == original

def test_skip_splice_still_requires_changelog_args(tmp_path: Path) -> None:
    """(d) Arg contract unchanged: --changelog/--docs-mirror stay required even
    under --skip-splice (argparse usage error, exit 2)."""
    highlights_dir = tmp_path / "docs" / "changelog"
    highlights_dir.mkdir(parents=True)
    (highlights_dir / "v366.highlights.md").write_text(
        "- bullet one\n- bullet two\n- bullet three\n", encoding="utf-8"
    )
    digest = tmp_path / "digest.md"
    digest.write_text(_DIGEST, encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        _invoke_main([
            "--buildversion", "366",
            "--tag", "v366",
            "--digest", str(digest),
            "--highlights-dir", str(highlights_dir),
            "--out", str(tmp_path / "release-notes.md"),
            "--skip-splice",
        ])
    assert exc.value.code == 2
