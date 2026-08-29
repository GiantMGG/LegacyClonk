#!/usr/bin/env python3
"""Unit tests for tools/check_citations.py.

Run: python3 tools/test_check_citations.py
Exit 0 if all tests pass, 1 otherwise. No external test framework needed.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

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


def test_extract_citations_ignores_non_source_extensions():
    line = "`readme.txt:5` and `script.py:10` not matched."
    assert cc.extract_citations(line) == []


# --- In-bounds / out-of-bounds ---

def test_in_bounds_passes():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
            doc_files={"a.md": "See `src/x.cpp:5` for details.\n"})
        failures, total, exit = _run(tmp)
        assert total == 1, total
        assert failures == [], failures
        assert exit == 0


def test_out_of_bounds_fails():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
            doc_files={"a.md": "See `src/x.cpp:15` for details.\n"})
        failures, total, exit = _run(tmp)
        assert total == 1, total
        assert len(failures) == 1, failures
        assert "out of bounds (file has 10 lines)" in failures[0]["message"]
        assert exit == 1


def test_range_end_out_of_bounds_fails():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
            doc_files={"a.md": "See `src/x.cpp:5-15` for details.\n"})
        failures, total, exit = _run(tmp)
        assert total == 1, total
        assert len(failures) == 1, failures
        assert "range end out of bounds" in failures[0]["message"]
        assert exit == 1


def test_range_in_bounds_passes():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
            doc_files={"a.md": "See `src/x.cpp:3-7` for details.\n"})
        failures, total, exit = _run(tmp)
        assert total == 1, total
        assert failures == [], failures
        assert exit == 0


# --- File resolution ---

def test_cited_file_not_found_fails():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\n"},
            doc_files={"a.md": "See `src/missing.cpp:1` for details.\n"})
        failures, total, exit = _run(tmp)
        assert total == 1, total
        assert len(failures) == 1, failures
        assert "cited file not found" in failures[0]["message"]
        assert exit == 1


def test_bare_filename_resolves_to_src():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"},
            doc_files={"a.md": "See `x.cpp:5` for details.\n"})
        failures, total, exit = _run(tmp)
        assert total == 1, total
        assert failures == [], failures
        assert exit == 0


# --- Allowlist + budget ---

def test_allowlist_suppresses_failure():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\n"},
            doc_files={"a.md": "See `src/x.cpp:15` for details.\n"})
        # doc line 1 has the out-of-bounds citation; allowlist it
        failures, total, exit = _run(tmp, allowlist={"docs/a.md:1"}, budget=0)
        assert total == 1, total
        assert len(failures) == 1, failures
        assert failures[0]["allowlisted"] is True
        assert exit == 0


def test_budget_tolerance_one_failure_budget_one():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\n"},
            doc_files={"a.md": "`src/x.cpp:15`\n"})
        _, _, exit_ok = _run(tmp, budget=1)
        assert exit_ok == 0, "budget 1 with 1 failure should pass"


def test_budget_tolerance_two_failures_budget_one():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\n"},
            doc_files={"a.md": "`src/x.cpp:15`\n`src/x.cpp:16`\n"})
        _, _, exit_fail = _run(tmp, budget=1)
        assert exit_fail == 1, "budget 1 with 2 failures should fail"


def test_advisory_always_exits_zero():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _make_tree(tmp,
            src_files={"x.cpp": "a\nb\nc\n"},
            doc_files={"a.md": "`src/x.cpp:15`\n`src/x.cpp:16`\n`src/x.cpp:17`\n`src/x.cpp:18`\n`src/x.cpp:19`\n"})
        _, _, exit_code = _run(tmp, budget=0, advisory=True)
        assert exit_code == 0, "advisory mode should always exit 0"


# --- Allowlist loading ---

def test_load_allowlist_skips_comments_and_blanks():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        al_file = tmp / "al.txt"
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


# --- Runner ---

def main() -> int:
    tests = [
        test_extract_citations_single,
        test_extract_citations_src_prefix_and_range,
        test_extract_citations_multiple_on_one_line,
        test_extract_citations_ignores_non_source_extensions,
        test_in_bounds_passes,
        test_out_of_bounds_fails,
        test_range_end_out_of_bounds_fails,
        test_range_in_bounds_passes,
        test_cited_file_not_found_fails,
        test_bare_filename_resolves_to_src,
        test_allowlist_suppresses_failure,
        test_budget_tolerance_one_failure_budget_one,
        test_budget_tolerance_two_failures_budget_one,
        test_advisory_always_exits_zero,
        test_load_allowlist_skips_comments_and_blanks,
        test_load_allowlist_missing_file_returns_empty,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
