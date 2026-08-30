#!/usr/bin/env python3
"""Unit tests for tools/check_citations.py.

Run: pytest tools/test_check_citations.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Import check_citations from the sibling file (no package needed).
_spec = importlib.util.spec_from_file_location(
    "check_citations", Path(__file__).resolve().parent / "check_citations.py"
)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

def _make_tree(tmp: Path, src_files: dict[str, str], doc_files: dict[str, str]) -> None:
    """Populate tmp/src/ and tmp/docs/ from {relpath: content} dicts."""
    for rel, content in src_files.items():
        p = tmp / "src" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    for rel, content in doc_files.items():
        p = tmp / "docs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

def _run(tmp: Path, allowlist: set[str] | None = None,
         budget: int = 0, advisory: bool = False):
    """Scan tmp/docs/ with REPO_ROOT pointed at tmp.

    Returns (failures, total_checked, exit_code).
    """
    cc.REPO_ROOT = tmp
    cc._line_cache.clear()
    doc_files = cc.collect_doc_files([tmp / "docs"])
    al = allowlist or set()
    failures, total = cc.scan_docs(doc_files, al)
    allowlisted = sum(1 for f in failures if f["allowlisted"])
    new_drift = len(failures) - allowlisted
    exit_code = 0 if advisory else (1 if new_drift > budget else 0)
    return failures, total, exit_code

# --- Regex extraction ---

def test_extract_citations_single():
    line = "See `C4Config.cpp:345` for the config."
    cites = cc.extract_citations(line)
    assert cites == [("C4Config.cpp", 345, None)], cites

def test_extract_citations_src_prefix_and_range():
    line = "`src/C4Game.cpp:986` and `C4Game.cpp:3069-3086` end."
    cites = cc.extract_citations(line)
    assert cites == [
        ("src/C4Game.cpp", 986, None),
        ("C4Game.cpp", 3069, 3086),
    ], cites

def test_extract_citations_multiple_on_one_line():
    line = "`a.cpp:1` `b.h:2` `c.cc:3-5`"
    cites = cc.extract_citations(line)
    assert len(cites) == 3, cites

@pytest.mark.parametrize("ext", ["cpp", "h", "c", "cc", "hpp", "md", "txt"])
def test_extract_citations_extension_matrix(ext):
    """N1: every accepted extension extracts as (raw, start, end=None)."""
    line = f"See `x.{ext}:5` for details."
    assert cc.extract_citations(line) == [("x." + ext, 5, None)]

@pytest.mark.parametrize(
    "line",
    [
        "`script.py:10`",
        "`notes.rst:5`",
        "bare prose C4Config.cpp:345 without backticks",
        "`CMake Error at CMakeLists.txt:14 (...)` is not citation-shaped",
        "`README.md` without a line number stays unmatched",
    ],
)
def test_extract_citations_rejection_matrix(line):
    """N2: non-citation shapes extract nothing.

    Replaces the pre-extension test that asserted `readme.txt:5` is not
    matched — .txt is matched by design now.
    """
    assert cc.extract_citations(line) == []

# --- In-bounds / out-of-bounds ---

def test_in_bounds_passes(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `src/x.cpp:5` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert failures == [], failures
    assert exit == 0

def test_out_of_bounds_fails(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `src/x.cpp:15` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert "out of bounds (file has 10 lines)" in failures[0]["message"]
    assert exit == 1

def test_range_end_out_of_bounds_fails(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `src/x.cpp:5-15` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert "range end out of bounds" in failures[0]["message"]
    assert exit == 1

def test_range_in_bounds_passes(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `src/x.cpp:3-7` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert failures == [], failures
    assert exit == 0

# --- File resolution ---

def test_cited_file_not_found_fails(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "See `src/missing.cpp:1` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert "cited file not found" in failures[0]["message"]
    assert exit == 1

def test_bare_filename_resolves_to_src(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `x.cpp:5` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert failures == [], failures
    assert exit == 0

# --- New citation class: .md / .txt (cycle 76) ---

def test_md_citation_in_bounds_passes(tmp_path):
    """N3: .md citation in bounds passes."""
    _make_tree(tmp_path,
        src_files={"README.md": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `README.md:5` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert failures == [], failures
    assert exit == 0

def test_md_citation_out_of_bounds_fails(tmp_path):
    """N3: .md citation past EOF fails."""
    _make_tree(tmp_path,
        src_files={"README.md": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `README.md:15` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert "out of bounds (file has 10 lines)" in failures[0]["message"]
    assert exit == 1

def test_md_cited_file_not_found_fails(tmp_path):
    """N3: .md citation to a missing file fails."""
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "See `missing.md:1` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert "cited file not found" in failures[0]["message"]
    assert exit == 1

def test_txt_range_end_out_of_bounds_fails(tmp_path):
    """N3: .txt range citation past EOF fails."""
    _make_tree(tmp_path,
        src_files={"notes.txt": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
        doc_files={"a.md": "See `notes.txt:5-15` for details.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert "range end out of bounds" in failures[0]["message"]
    assert exit == 1

def test_run_exit_codes_for_md_citations(tmp_path):
    """N3: end-to-end run() exit codes for the new .md citation class."""
    cc.REPO_ROOT = tmp_path
    cc._line_cache.clear()
    _make_tree(tmp_path,
        src_files={"real.md": "a\nb\nc\nd\ne\n"},
        doc_files={"fresh.md": "See `real.md:3` for details.\n"})
    assert cc.run([tmp_path / "docs"], set(), 0, False) == 0
    _make_tree(tmp_path,
        src_files={},
        doc_files={"drift.md": "See `missing.md:3` for details.\n"})
    assert cc.run([tmp_path / "docs"], set(), 0, False) == 1
    assert cc.run([tmp_path / "docs"], set(), 1, False) == 0
    assert cc.run([tmp_path / "docs"], set(), 0, True) == 0

def test_cycle71_regression_pin_in_bounds_semantic_drift_still_passes(tmp_path):
    """N4 — cycle-71 regression pin (documents the gate's limitation).

    Cycle 71 shipped `README.md:87` stale by one line: a README insert
    moved the target sentence to line 88 while the citation still said 87.
    The stale citation was IN BOUNDS the whole time — line 87 exists and
    contains the macOS binary-symlink line. A bounds-only gate therefore
    would NOT have caught the cycle-71 drift, and this test pins that
    limitation as a documented decision: a one-line insert moves the
    target sentence off the cited line, the citation stays in bounds,
    and the gate stays silent. Catching in-bounds semantic drift requires
    per-citation content assertions — filed as the follow-up
    `citation-content-assertions`.
    """
    ten_lines = (
        "line one\n"
        "line two\n"
        "THE TARGET SENTENCE\n"
        "line four\n"
        "line five\n"
        "line six\n"
        "line seven\n"
        "line eight\n"
        "line nine\n"
        "line ten\n"
    )
    _make_tree(tmp_path,
        src_files={"README.md": ten_lines},
        doc_files={"a.md": "See `README.md:3` for the target sentence.\n"})
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert failures == [], failures
    assert exit == 0
    # One-line insert: the sentence moves to line 4, the citation still
    # says line 3 — in bounds, so the bounds-only gate passes.
    inserted = ten_lines.replace(
        "line two\nTHE TARGET SENTENCE\n",
        "line two\nINSERTED LINE\nTHE TARGET SENTENCE\n",
    )
    (tmp_path / "src" / "README.md").write_text(inserted, encoding="utf-8")
    failures, total, exit = _run(tmp_path)
    assert total == 1, total
    assert failures == [], failures
    assert exit == 0

# --- Allowlist + budget ---

def test_allowlist_suppresses_failure(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "See `src/x.cpp:15` for details.\n"})
    # doc line 1 has the out-of-bounds citation; allowlist it
    failures, total, exit = _run(tmp_path, allowlist={"docs/a.md:1"}, budget=0)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert failures[0]["allowlisted"] is True
    assert exit == 0

def test_budget_tolerance_one_failure_budget_one(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "`src/x.cpp:15`\n"})
    _, _, exit_ok = _run(tmp_path, budget=1)
    assert exit_ok == 0, "budget 1 with 1 failure should pass"

def test_budget_tolerance_two_failures_budget_one(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "`src/x.cpp:15`\n`src/x.cpp:16`\n"})
    _, _, exit_fail = _run(tmp_path, budget=1)
    assert exit_fail == 1, "budget 1 with 2 failures should fail"

def test_advisory_always_exits_zero(tmp_path):
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "`src/x.cpp:15`\n`src/x.cpp:16`\n`src/x.cpp:17`\n`src/x.cpp:18`\n`src/x.cpp:19`\n"})
    _, _, exit_code = _run(tmp_path, budget=0, advisory=True)
    assert exit_code == 0, "advisory mode should always exit 0"

# --- Allowlist loading ---

def test_load_allowlist_skips_comments_and_blanks(tmp_path):
    al_file = tmp_path / "al.txt"
    al_file.write_text(
        "# header\n"
        "docs/a.md:1\n"
        "\n"
        "  docs/b.md:2  \n"
        "# trailer\n",
        encoding="utf-8")
    result = cc.load_allowlist(al_file)
    assert result == {"docs/a.md:1", "docs/b.md:2"}, result

def test_load_allowlist_missing_file_returns_empty():
    result = cc.load_allowlist(Path("/nonexistent/allowlist.txt"))
    assert result == set(), result
