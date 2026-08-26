"""Pytest suite for tools/harvest_callbacks.py.

Two layers:
1. Synthetic-fixture unit tests (fast, deterministic).
2. Real-engine integration tests (assert every PSF_*, AddFunc, ConstMap row,
   and DefCore field produces exactly one entry).
"""
import sys
from pathlib import Path

import pytest

# Make tools/ importable.
sys.path.insert(0, str(Path(__file__).parent))
import harvest_callbacks as H

HERE = Path(__file__).parent
FIX = HERE / "fixtures"
SRC = HERE.parent / "src"


# ---------------------------------------------------------------------------
# Synthetic-fixture unit tests
# ---------------------------------------------------------------------------

def test_parse_callbacks_from_synthetic_fixture():
    callbacks = H.parse_callbacks(FIX / "C4Script.h")
    names = {c.name for c in callbacks}
    assert names == {"Initialize", "Hit", "Damage", "FxStart"}


def test_parse_functions_from_synthetic_fixture():
    funcs = H.parse_functions(FIX / "C4Script.cpp", src_dir=FIX)
    names = {f.name for f in funcs}
    assert names == {"Explode", "Message", "Call"}


def test_parse_constants_from_synthetic_fixture():
    consts = H.parse_constants(FIX / "C4Script.cpp")
    names = {c.name for c in consts}
    assert names == {"C4D_All", "OCF_Construct", "COMD_None"}


def test_parse_defcore_fields_from_synthetic_fixture():
    fields = H.parse_defcore_fields(FIX / "C4Def.cpp")
    keys = {f.key for f in fields}
    assert keys == {"Timer", "TimerCall", "Mass"}


def test_callback_group_routing():
    callbacks = H.parse_callbacks(FIX / "C4Script.h")
    by_group = {}
    for c in callbacks:
        by_group.setdefault(H.callback_group(c.symbol), []).append(c.name)
    assert "Hit" in by_group.get("combat.md", [])
    assert "Initialize" in by_group.get("object-lifecycle.md", [])
    assert "FxStart" in by_group.get("effects.md", [])


def test_function_signature_extraction():
    funcs = H.parse_functions(FIX / "C4Script.cpp", src_dir=FIX)
    explode = next(f for f in funcs if f.name == "Explode")
    assert explode.return_type == "bool"
    # C4AulContext *cthr is dropped.
    param_names = [p.name for p in explode.params]
    assert param_names == ["iLevel", "pObj", "idEffect", "szEffect"]
    param_types = [p.c4type for p in explode.params]
    assert param_types == ["int", "object", "id", "string"]


def test_function_protected_flag():
    funcs = H.parse_functions(FIX / "C4Script.cpp", src_dir=FIX)
    call = next(f for f in funcs if f.name == "Call")
    assert call.protected is False  # fourth arg `false` => not callable from protected
    explode = next(f for f in funcs if f.name == "Explode")
    assert explode.protected is True  # no fourth arg => callable


def test_constant_type_mapping():
    consts = H.parse_constants(FIX / "C4Script.cpp")
    all_const = next(c for c in consts if c.name == "C4D_All")
    assert all_const.c4type == "int"


# ---------------------------------------------------------------------------
# Real-engine integration tests
# ---------------------------------------------------------------------------

def test_every_psf_macro_yields_a_callback():
    callbacks = H.parse_callbacks(SRC / "C4Script.h")
    # Every PSF_* macro in the real header must produce exactly one entry.
    macro_count = H.count_psf_macros(SRC / "C4Script.h")
    assert len(callbacks) == macro_count


def test_every_addfunc_yields_a_function():
    funcs = H.parse_functions(SRC / "C4Script.cpp", src_dir=SRC)
    addfunc_count = H.count_addfuncs(SRC / "C4Script.cpp")
    assert len(funcs) == addfunc_count


def test_every_constmap_row_yields_a_constant():
    consts = H.parse_constants(SRC / "C4Script.cpp")
    row_count = H.count_constmap_rows(SRC / "C4Script.cpp")
    assert len(consts) == row_count


def test_every_defcore_field_yields_a_row():
    fields = H.parse_defcore_fields(SRC / "C4Def.cpp")
    field_count = H.count_defcore_fields(SRC / "C4Def.cpp")
    assert len(fields) == field_count


def test_render_callbacks_group_page_is_nonempty():
    callbacks = H.parse_callbacks(SRC / "C4Script.h")
    md = H.render_callback_group("combat.md", "Combat callbacks",
                                 [c for c in callbacks if H.callback_group(c.symbol) == "combat.md"],
                                 curated={})
    assert "## " in md  # at least one callback heading
