#!/usr/bin/env python3
"""Unit tests for tools/check_citations.py.

Run: pytest tools/test_check_citations.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# Import check_citations from the sibling file (no package needed).
_spec = importlib.util.spec_from_file_location(
    "check_citations", Path(__file__).resolve().parent / "check_citations.py"
)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

# The real repo root, captured at import time — before any test repoints
# cc.REPO_ROOT at a tmp tree.
_REAL_ROOT = cc.REPO_ROOT

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
         budget: int = 0, advisory: bool = False,
         expectations: dict[str, list[str]] | None = None):
    """Scan tmp/docs/ with REPO_ROOT pointed at tmp.

    Returns (failures, total_checked, exit_code).
    """
    cc.REPO_ROOT = tmp
    cc._line_cache.clear()
    cc._content_cache.clear()
    doc_files = cc.collect_doc_files([tmp / "docs"])
    al = allowlist or set()
    exp = expectations or {}
    exercised: set[str] = set()
    failures, total = cc.scan_docs(doc_files, al, exp, exercised)
    for key in exp:
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
                "allowlisted": key in al,
                "kind": "orphan",
            })
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

# --- Content expectations: normalization matrix ---

def test_normalize_smart_apostrophe():
    """U+2019 (won’t) normalizes to the ASCII apostrophe (won't)."""
    assert cc.normalize_snippet("won’t start") == "won't start"

def test_normalize_smart_quotes_and_dashes():
    assert cc.normalize_snippet(
        "\u2018x\u2019 \u201cy\u201d \u2013 \u2014") == "'x' \"y\" - -"

def test_normalize_casefold():
    assert cc.normalize_snippet("System.c4g") == cc.normalize_snippet("system.c4g")
    assert cc.normalize_snippet("WON’T START") == "won't start"

def test_normalize_whitespace_collapse():
    assert cc.normalize_snippet("a\t b   c") == "a b c"
    assert cc.normalize_snippet("  padded  ") == "padded"
    assert cc.normalize_snippet("a\u00a0b") == "a b"

def test_normalize_nfc_combining():
    """NFD e+combining-acute composes to NFC precomposed é."""
    assert cc.normalize_snippet("e\u0301") == cc.normalize_snippet("\u00e9")

# --- Content expectations: parser matrix ---

def test_load_expectations_basic(tmp_path):
    led = tmp_path / "exp.txt"
    led.write_text(
        "docs/a.md:1 -> won't start\n"
        "docs/b.md:42 -> System.c4g\n",
        encoding="utf-8")
    result = cc.load_expectations(led)
    assert result == {
        "docs/a.md:1": ["won't start"],
        "docs/b.md:42": ["System.c4g"],
    }, result

def test_load_expectations_skips_comments_and_blanks(tmp_path):
    led = tmp_path / "exp.txt"
    led.write_text(
        "# header\n"
        "\n"
        "docs/a.md:1 -> snippet\n"
        "   \n"
        "# trailer\n",
        encoding="utf-8")
    result = cc.load_expectations(led)
    assert result == {"docs/a.md:1": ["snippet"]}, result

def test_load_expectations_multiple_snippets_append(tmp_path):
    led = tmp_path / "exp.txt"
    led.write_text(
        "docs/a.md:1 -> first\n"
        "docs/a.md:1 -> second\n",
        encoding="utf-8")
    result = cc.load_expectations(led)
    assert result == {"docs/a.md:1": ["first", "second"]}, result

def test_load_expectations_snippet_with_arrow_and_quotes(tmp_path):
    led = tmp_path / "exp.txt"
    led.write_text("docs/a.md:1 -> a -> b \"q\" 'q'\n", encoding="utf-8")
    result = cc.load_expectations(led)
    assert result == {"docs/a.md:1": ["a -> b \"q\" 'q'"]}, result

def test_load_expectations_missing_file_returns_empty(tmp_path):
    result = cc.load_expectations(tmp_path / "nonexistent.txt")
    assert result == {}, result

def test_load_expectations_malformed_line_raises(tmp_path):
    led = tmp_path / "exp.txt"
    led.write_text(
        "# header\n"
        "docs/a.md:1 no arrow here\n",
        encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        cc.load_expectations(led)
    assert ":2:" in str(excinfo.value), excinfo.value
    led.write_text("docs/a.md:1 ->  \n", encoding="utf-8")
    with pytest.raises(ValueError):
        cc.load_expectations(led)
    led.write_text("docs/a.md:x -> snippet\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cc.load_expectations(led)

# --- Content expectations: behavior matrix ---

def test_expectation_satisfied_passes(tmp_path, capsys):
    """The seed shape: cited line carries won’t (U+2019), the ledger
    snippet uses the ASCII apostrophe — normalization bridges the two."""
    cc.REPO_ROOT = tmp_path
    cc._line_cache.clear()
    cc._content_cache.clear()
    _make_tree(tmp_path,
        src_files={"README.md": "line one\nline two\nWithout them, the engine won’t start.\n"},
        doc_files={"a.md": "**Citation.** `README.md:3`.\n"})
    exp = {"docs/a.md:1": ["won't start"]}
    exit_code = cc.run([tmp_path / "docs"], set(), 0, False, exp)
    err = capsys.readouterr().err
    assert exit_code == 0, err
    assert "1 expectations checked, 0 content mismatches, 0 orphaned" in err

def test_cycle71_shape_in_bounds_drift_fails_expectation(tmp_path):
    """The would-have-caught-cycle-71 test (N4's complement).

    A one-line insert moves the target sentence off the cited line; the
    citation stays in bounds, but the content expectation now fails with
    the located-candidates diagnostic.
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
    exp = {"docs/a.md:1": ["the target sentence"]}
    failures, total, exit_code = _run(tmp_path, expectations=exp)
    assert total == 1, total
    assert failures == [], failures
    assert exit_code == 0
    inserted = ten_lines.replace(
        "line two\nTHE TARGET SENTENCE\n",
        "line two\nINSERTED LINE\nTHE TARGET SENTENCE\n",
    )
    (tmp_path / "src" / "README.md").write_text(inserted, encoding="utf-8")
    failures, total, exit_code = _run(tmp_path, expectations=exp)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert failures[0]["kind"] == "content"
    assert "expectation mismatch" in failures[0]["message"]
    assert "found at line(s): 4" in failures[0]["message"], failures[0]["message"]
    assert exit_code == 1

def test_expectation_mismatch_reports_located_candidates(tmp_path):
    src = "one\ntwo\nTHE SNIPPET LIVES HERE\nfour\nfive\n"
    _make_tree(tmp_path,
        src_files={"x.cpp": src},
        doc_files={"a.md": "See `src/x.cpp:3` for details.\n"})
    exp = {"docs/a.md:1": ["the snippet lives here"]}
    # Line drift: the snippet moved to line 5 → located candidates.
    (tmp_path / "src" / "x.cpp").write_text(
        "one\ntwo\nthree\nfour\nTHE SNIPPET LIVES HERE\n", encoding="utf-8")
    failures, _, exit_code = _run(tmp_path, expectations=exp)
    assert len(failures) == 1, failures
    assert failures[0]["kind"] == "content"
    assert "found at line(s): 5" in failures[0]["message"], failures[0]["message"]
    assert exit_code == 1
    # Content drift: the snippet is gone from the file entirely.
    (tmp_path / "src" / "x.cpp").write_text(
        "one\ntwo\nthree\nfour\nfive\n", encoding="utf-8")
    failures, _, exit_code = _run(tmp_path, expectations=exp)
    assert len(failures) == 1, failures
    assert "not found anywhere" in failures[0]["message"], failures[0]["message"]
    assert exit_code == 1

def test_expectation_range_containment(tmp_path):
    src = (
        "one\ntwo\nthree\nfour\nTHE SNIPPET LIVES HERE\n"
        "six\nseven\neight\nnine\nten\n"
    )
    _make_tree(tmp_path,
        src_files={"x.cpp": src},
        doc_files={"a.md": "See `src/x.cpp:3-7` for details.\n"})
    exp = {"docs/a.md:1": ["the snippet lives here"]}
    # Snippet on line 5, inside the cited range 3-7 → satisfied.
    failures, total, exit_code = _run(tmp_path, expectations=exp)
    assert total == 1, total
    assert failures == [], failures
    assert exit_code == 0
    # Snippet moved outside the range → content mismatch.
    moved = (
        "one\ntwo\nthree\nfour\nfive\nsix\nseven\neight\n"
        "THE SNIPPET LIVES HERE\nten\n"
    )
    (tmp_path / "src" / "x.cpp").write_text(moved, encoding="utf-8")
    failures, total, exit_code = _run(tmp_path, expectations=exp)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert failures[0]["kind"] == "content"
    assert "found at line(s): 9" in failures[0]["message"], failures[0]["message"]
    assert exit_code == 1

def test_multiple_citations_one_line_expectation(tmp_path):
    _make_tree(tmp_path,
        src_files={
            "a.cpp": "alpha\nbeta\ngamma\n",
            "b.cpp": "THE SNIPPET LIVES HERE\nother\n",
        },
        doc_files={"a.md": "See `src/a.cpp:2` and `src/b.cpp:1` for details.\n"})
    # Satisfied by the second citation on the same doc line.
    exp = {"docs/a.md:1": ["the snippet lives here"]}
    failures, total, exit_code = _run(tmp_path, expectations=exp)
    assert total == 2, total
    assert failures == [], failures
    assert exit_code == 0
    # Unsatisfiable snippet → exactly one mismatch failure.
    exp = {"docs/a.md:1": ["nowhere to be found"]}
    failures, total, exit_code = _run(tmp_path, expectations=exp)
    assert total == 2, total
    assert len(failures) == 1, failures
    assert failures[0]["kind"] == "content"
    assert exit_code == 1

def test_bounds_failure_on_expected_line_not_orphan(tmp_path):
    """The expected line's citation fails bounds: no content failure, no
    orphan — exactly the bounds failure."""
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "See `src/x.cpp:15` for details.\n"})
    exp = {"docs/a.md:1": ["some snippet"]}
    failures, total, exit_code = _run(tmp_path, expectations=exp)
    assert total == 1, total
    assert len(failures) == 1, failures
    assert failures[0]["kind"] == "bounds"
    assert "out of bounds" in failures[0]["message"]
    assert exit_code == 1

def test_orphaned_expectation_fails(tmp_path, capsys):
    """A ledger key whose doc line carries no citation fails as an
    orphan, via the full run() path."""
    cc.REPO_ROOT = tmp_path
    cc._line_cache.clear()
    cc._content_cache.clear()
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={
            "a.md": "See `src/x.cpp:1` for details.\n",
            "b.md": "No citations on this line.\n",
        })
    exp = {"docs/b.md:1": ["anything"]}
    exit_code = cc.run([tmp_path / "docs"], set(), 0, False, exp)
    err = capsys.readouterr().err
    assert exit_code == 1, err
    assert "orphaned expectation" in err
    assert "1 expectations checked, 0 content mismatches, 1 orphaned" in err

def test_orphan_allowlisted_and_mismatch_allowlisted(tmp_path):
    """Allowlist suppression is uniform across content and orphan
    failure classes."""
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={
            "a.md": "See `src/x.cpp:1` for details.\n",
            "b.md": "No citations on this line.\n",
        })
    # Content mismatch, allowlisted → suppressed, exit 0.
    exp = {"docs/a.md:1": ["not present in the cited line"]}
    failures, _, exit_code = _run(tmp_path, allowlist={"docs/a.md:1"},
                                  expectations=exp)
    assert len(failures) == 1, failures
    assert failures[0]["kind"] == "content"
    assert failures[0]["allowlisted"] is True
    assert exit_code == 0
    # Orphan, allowlisted → suppressed, exit 0.
    exp = {"docs/b.md:1": ["anything"]}
    failures, _, exit_code = _run(tmp_path, allowlist={"docs/b.md:1"},
                                  expectations=exp)
    assert len(failures) == 1, failures
    assert failures[0]["kind"] == "orphan"
    assert failures[0]["allowlisted"] is True
    assert exit_code == 0

# --- Content expectations: interaction matrix ---

def test_expectation_outside_scan_scope_orphans(tmp_path, capsys):
    """Strict-orphan pin: a key for a doc outside the scan targets is
    never exercised and fails as an orphan; an explicitly empty ledger
    (--expectations /dev/null) is the escape hatch."""
    cc.REPO_ROOT = tmp_path
    cc._line_cache.clear()
    cc._content_cache.clear()
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "See `src/x.cpp:1` for details.\n"})
    exp = {"docs/elsewhere.md:1": ["whatever"]}
    exit_code = cc.run([tmp_path / "docs"], set(), 0, False, exp)
    err = capsys.readouterr().err
    assert exit_code == 1, err
    assert "orphaned expectation" in err
    empty = cc.load_expectations(Path("/dev/null"))
    assert empty == {}, empty
    exit_code = cc.run([tmp_path / "docs"], set(), 0, False, empty)
    assert exit_code == 0

def test_budget_and_advisory_with_expectations(tmp_path, capsys):
    cc.REPO_ROOT = tmp_path
    cc._line_cache.clear()
    cc._content_cache.clear()
    _make_tree(tmp_path,
        src_files={"x.cpp": "a\nb\nc\n"},
        doc_files={"a.md": "See `src/x.cpp:1` for details.\n"})
    exp = {"docs/a.md:1": ["not in the cited line"]}
    # One content mismatch: budget 1 tolerates it, budget 0 does not.
    assert cc.run([tmp_path / "docs"], set(), 1, False, exp) == 0
    assert cc.run([tmp_path / "docs"], set(), 0, False, exp) == 1
    # Advisory: exit 0 with both summary lines.
    capsys.readouterr()
    assert cc.run([tmp_path / "docs"], set(), 0, True, exp) == 0
    err = capsys.readouterr().err
    assert "citations checked" in err
    assert "1 expectations checked, 1 content mismatches, 0 orphaned" in err

def test_seed_real_tree_unchanged_behavior(tmp_path):
    """End-to-end CLI on the real tree — the zero-visible-change default.

    An empty expectations ledger reproduces the pre-feature gate exactly
    (summary line 1 byte-identical, exit 0), and the default ledger —
    the seed, once tools/citation-expectations.txt exists — keeps the
    real-tree run green end-to-end.
    """
    script = _REAL_ROOT / "tools" / "check_citations.py"
    result = subprocess.run(
        [sys.executable, str(script), "--budget", "0", "docs/"],
        capture_output=True, text=True, cwd=_REAL_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert ("citations checked, 0 failed, 0 allowlisted, "
            "0 new drift (budget 0)") in result.stderr
    empty_ledger = tmp_path / "empty-expectations.txt"
    empty_ledger.write_text("# empty\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "--budget", "0",
         "--expectations", str(empty_ledger), "docs/"],
        capture_output=True, text=True, cwd=_REAL_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert ("0 expectations checked, 0 content mismatches, "
            "0 orphaned") in result.stderr
