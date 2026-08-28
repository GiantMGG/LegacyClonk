#!/usr/bin/env python3
"""Harvest C4Script callbacks, functions, constants, and DefCore.txt fields
from engine source and emit Markdown reference pages under docs/reference/.

Read-only: never modifies engine source. Pure function of the engine tree.

Usage:
    python tools/harvest_callbacks.py [--src-dir src] [--out-dir docs/reference]

The script writes:
  docs/reference/callbacks/<group>.md        (one per callback group)
  docs/reference/functions/<Name>.md         (one per registered function)
  docs/reference/functions/index.md          (alphabetic table)
  docs/reference/constants.md                (grouped constant table)
  docs/reference/defcore.md                  (DefCore.txt field table)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


# ===========================================================================
# Hand-maintained mapping tables (trivially auditable, live at top of file)
# ===========================================================================

# C++ type -> C4Script type. Unknown types fall through to "any" and emit a
# build warning so the table can be extended (one-line edit).
TYPE_MAP: dict[str, str] = {
    "C4ValueInt": "int",
    "int32_t": "int",
    "int": "int",
    "C4Object *": "object",
    "C4Object*": "object",
    "C4String *": "string",
    "C4String*": "string",
    "C4ID": "id",
    "C4Value": "any",
    "C4Value &": "any",
    "C4PropList *": "proplist",
    "C4PropList*": "proplist",
    "bool": "bool",
    "C4ValueArray *": "array",
    "C4ValueArray*": "array",
    "C4ValueArray &": "array",
    "C4Real": "int",
    "float": "int",
    "double": "int",
    "C4Facet *": "proplist",
    "C4Facet &": "proplist",
    "C4Value *": "any",
    "id": "id",
    "C4V_Type": "any",
    "std::optional<C4ValueInt>": "int",
}

# C4V_* -> C4Script type (used for the constants table).
C4V_MAP: dict[str, str] = {
    "C4V_Int": "int",
    "C4V_Bool": "bool",
    "C4V_String": "string",
    "C4V_Object": "object",
    "C4V_Array": "array",
    "C4V_PropList": "proplist",
    "C4V_Any": "any",
}

# Hungarian-prefix -> C4Script type (used for bare callback `//` param hints).
HUNGARIAN_MAP: dict[str, str] = {
    "i": "int",
    "p": "object",
    "sz": "string",
    "id": "id",
    "f": "bool",
    "v": "any",
    "b": "bool",
}

# Callback group routing: ordered list of (regex, group_file, group_title).
# First match wins; fallback is misc.md.
CALLBACK_GROUPS: list[tuple[str, str, str]] = [
    (r"^PSF_Hit", "combat.md", "Combat callbacks"),
    (r"^PSF_(Initialize(Def|Player|ScriptPlayer|PlayerSection)?|PreInitializePlayer|"
     r"Construction|Destruction|Completion|Script\{\}|LineBreak|BuildNeedsMaterial)$",
     "object-lifecycle.md", "Object lifecycle callbacks"),
    (r"^PSF_Fx", "effects.md", "Effect callbacks"),
    (r"^PSF_(InitializePlayer|InitializeScriptPlayer|PreInitializePlayer|RemovePlayer|"
     r"InitializePlayerSection|OnJoinCrew)$", "player.md", "Player callbacks"),
    (r"^PSF_(Control|ContainedControl|ControlUpdate|ContainedControlUpdate|"
     r"ControlCommand|ControlCommandConstruction|ControlCommandAcquire|ControlTransfer)$",
     "control.md", "Control callbacks"),
    (r"^PSF_(Menu|MenuQueryCancel|MenuSelection|GetContextMenuItems|OnMenuSelection)",
     "menu.md", "Menu callbacks"),
    (r"^PSF_(.*Transfer.*|Grab|Grabbed|RejectGrabbed|GrabLost|Contact|LiftTop|"
     r"UpdateTransferZone|DeepBreath|Stuck)$", "movement.md", "Movement callbacks"),
    (r"^PSF_(Action|OnActionJump)$", "actions.md", "Action callbacks"),
]


# ===========================================================================
# Data classes
# ===========================================================================

@dataclass
class Param:
    name: str
    c4type: str


@dataclass
class Callback:
    name: str           # e.g. "Hit" (stripped of ~ and {})
    symbol: str         # e.g. "PSF_Hit"
    raw_string: str     # e.g. "~Hit" or "Fx{}Start"
    param_hint: str     # trailing // comment, e.g. "iChange, iCausedBy" (may be "")
    source_line: int


@dataclass
class Function:
    name: str           # C4Script function name (AddFunc second arg)
    symbol: str         # C++ symbol, e.g. "FnExplode"
    return_type: str    # C++ return type, e.g. "bool"
    params: list[Param]
    protected: bool     # True if callable from protected context (no fourth arg or fourth arg true)
    docstring: str      # preceding /** */ block, "" if absent
    addfunc_line: int
    signature_found: bool
    signature_source: str  # file:line where the static Fn<Name>(...) was found


@dataclass
class Constant:
    name: str
    c4v_type: str       # raw C4V_* token
    c4type: str         # mapped C4Script type
    source_line: int
    value_token: str    # raw symbolic value token from the const map (e.g. "C4D_StaticBack")


@dataclass
class DefCoreField:
    key: str            # DefCore.txt key (quoted second arg)
    field: str          # C++ field identifier (first arg)
    default: str        # default value literal (third arg, "" if absent)
    source_line: int


# ===========================================================================
# Parse helpers
# ===========================================================================

_WARN_UNKNOWN_TYPES: set[str] = set()


def _map_cpp_type(cpp_type: str) -> str:
    cpp_type = cpp_type.strip()
    # Try exact match, then match with normalized spacing.
    if cpp_type in TYPE_MAP:
        return TYPE_MAP[cpp_type]
    # Normalize pointer spacing: "C4Object *" already covered; try stripping trailing space.
    normalized = re.sub(r"\s*\*\s*", "*", cpp_type)
    if normalized in TYPE_MAP:
        return TYPE_MAP[normalized]
    _WARN_UNKNOWN_TYPES.add(cpp_type)
    return "any"


def _map_hungarian(name: str) -> str:
    for prefix, c4type in sorted(HUNGARIAN_MAP.items(), key=lambda kv: -len(kv[0])):
        if name.startswith(prefix):
            return c4type
    return "any"


def _map_c4v(c4v_token: str) -> str:
    return C4V_MAP.get(c4v_token.strip(), "any")


def _split_top_level_commas(s: str) -> list[str]:
    """Split on commas that are not nested inside (), [], or {}."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in s:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


# ---------------------------------------------------------------------------
# Callbacks: parse C4Script.h #define PSF_* lines
# ---------------------------------------------------------------------------

_PSF_RE = re.compile(
    r"""^\s*\#\s*define\s+
        (PSF[A-Za-z0-9_]*)        # group 1: macro name (symbol)
        \s+
        "([^"]*)"                 # group 2: quoted string value
        (?:\s*//\s*(.*))?         # group 3: optional trailing // comment
        \s*$""",
    re.VERBOSE,
)


def parse_callbacks(header_path: Path) -> list[Callback]:
    callbacks: list[Callback] = []
    for lineno, line in enumerate(header_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        m = _PSF_RE.match(line)
        if not m:
            continue
        symbol, raw_string, hint = m.group(1), m.group(2), (m.group(3) or "")
        # Strip "~" prefix and "{}" template marker to get the callback name.
        name = raw_string.lstrip("~").replace("{}", "")
        callbacks.append(Callback(
            name=name,
            symbol=symbol,
            raw_string=raw_string,
            param_hint=hint.strip(),
            source_line=lineno,
        ))
    return callbacks


def count_psf_macros(header_path: Path) -> int:
    """Independent count of `#define PSF_*` macro lines.

    Uses a deliberately simple line-prefix check that does NOT share the
    parser's `_PSF_RE` regex, so the integration test can catch regex misses.
    """
    count = 0
    for line in header_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"\s*\#\s*define\s+PSF", line):
            count += 1
    return count


def callback_group(symbol: str) -> str:
    for pattern, group_file, _title in CALLBACK_GROUPS:
        if re.search(pattern, symbol):
            return group_file
    return "misc.md"


def _parse_hint_params(hint: str) -> list[Param]:
    """Parse a trailing // comment into typed params.

    The comment may be bare names ('iChange, iCausedBy') or full C++ signatures
    ('C4Object *pTarget, int iEffectNumber'). For bare names, type is inferred
    from the Hungarian prefix.
    """
    if not hint:
        return []
    params: list[Param] = []
    # Split on top-level commas only (respect () and [] nesting).
    depth = 0
    current = []
    for ch in hint:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            params.append(_parse_one_param_token("".join(current)))
            current = []
        else:
            current.append(ch)
    if current:
        params.append(_parse_one_param_token("".join(current)))
    return [p for p in params if p is not None]


def _parse_one_param_token(token: str) -> Optional[Param]:
    token = token.strip()
    if not token:
        return None
    # Pattern: <type> <name> where type may contain *, &, ::, alphanumerics.
    # Heuristic: if the token contains whitespace, split last word as name.
    if " " in token:
        # Split into type and name on the last whitespace run.
        m = re.match(r"^(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)$", token)
        if m:
            cpp_type, name = m.group(1), m.group(2)
            # Strip leading "const " etc. — keep simple.
            cpp_type = cpp_type.replace("const ", "").strip()
            # If the type part contains a semicolon or slash it's prose, not a
            # parameter — skip it (some PSF_* hint comments are descriptive).
            if ";" in cpp_type or "/" in cpp_type:
                return None
            return Param(name=name, c4type=_map_cpp_type(cpp_type))
    # Bare name: infer type from Hungarian prefix.
    name = token
    # Strip a leading type char if it looks like Hungarian.
    return Param(name=name, c4type=_map_hungarian(name))


# ---------------------------------------------------------------------------
# Functions: parse AddFunc registration table + Fn<Name> signatures
# ---------------------------------------------------------------------------

_ADDFUNC_RE = re.compile(
    r"""^\s*AddFunc\s*\(\s*pEngine\s*,\s*
        (?:"([^"]+)"|(PSF_[A-Za-z0-9_]+))   # group 1: quoted name; group 2: PSF_ macro
        \s*,\s*
        (Fn[A-Za-z0-9_]+)                    # group 3: C++ symbol
        (?:\s*,\s*(true|false))?             # group 4: optional protected flag
        \s*\)\s*;?\s*$""",
    re.VERBOSE,
)

# static <ret> Fn<Name>(<params>)
# `\s*` (not `\s+`) between return type and symbol so pointer return types
# like `static C4Object *FnFindObject(...)` match (no space between `*` and
# `Fn`). Multi-line signatures are joined into a single logical line by
# `_scan_fn_definitions` before this regex is applied. The params capture is
# non-greedy and the `)` may be followed by a body (`{ ... }`) or a trailing
# `//` comment, so single-line definitions like
# `static C4ValueInt FnAnyContainer(C4AulContext *) { return ANY_CONTAINER; }`
# are matched.
_FN_DEF_RE = re.compile(
    r"""^(?:static\s+)?(?:inline\s+)?
        ([A-Za-z_][A-Za-z0-9_ *\&<>:]*?)\s*    # group 1: return type
        (Fn[A-Za-z0-9_]+)\s*                   # group 2: symbol
        \(([^;]*?)\)                           # group 3: params (non-greedy, no ';')
        .*$""",
    re.VERBOSE,
)


def parse_functions(cpp_path: Path, src_dir: Path) -> list[Function]:
    """Parse AddFunc registrations and resolve Fn<Name> signatures across src_dir."""
    # Build a PSF_* macro -> raw_string map so AddFunc calls that reference a
    # PSF_* macro (e.g. `AddFunc(pEngine, PSF_OnOwnerRemoved, ...)`) can be
    # resolved to their C4Script callback name.
    psf_map: dict[str, str] = {}
    header = src_dir / "C4Script.h"
    if header.exists():
        for cb in parse_callbacks(header):
            psf_map[cb.symbol] = cb.raw_string

    # 1. Collect AddFunc registrations from cpp_path (the InitFunctionMap file).
    registrations: list[tuple[str, str, bool, int]] = []
    text = cpp_path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _ADDFUNC_RE.match(line)
        if not m:
            continue
        quoted, psf_macro, symbol, prot = m.group(1), m.group(2), m.group(3), m.group(4)
        if quoted is not None:
            name = quoted
        else:
            # Resolve PSF_* macro to the callback name (strip "~" and "{}").
            raw = psf_map.get(psf_macro or "", "")
            if raw:
                name = raw.lstrip("~").replace("{}", "")
            else:
                name = (psf_macro or "")[len("PSF_"):]
        protected = (prot != "false")  # no fourth arg => callable => protected True per spec convention
        registrations.append((name, symbol, protected, lineno))

    # 2. Scan all src/*.cpp for static <ret> Fn<Name>(...) definitions.
    fn_defs: dict[str, dict] = {}  # symbol -> {return_type, params, docstring, source}
    cpp_files = sorted(src_dir.glob("*.cpp"))
    for cf in cpp_files:
        _scan_fn_definitions(cf, fn_defs)

    # 3. Build Function list.
    functions: list[Function] = []
    for name, symbol, protected, addfunc_line in registrations:
        fdef = fn_defs.get(symbol)
        if fdef is not None:
            functions.append(Function(
                name=name, symbol=symbol,
                return_type=fdef["return_type"], params=fdef["params"],
                protected=protected, docstring=fdef["docstring"],
                addfunc_line=addfunc_line, signature_found=True,
                signature_source=fdef["source"],
            ))
        else:
            functions.append(Function(
                name=name, symbol=symbol,
                return_type="", params=[], protected=protected, docstring="",
                addfunc_line=addfunc_line, signature_found=False,
                signature_source="",
            ))
    return functions


def _scan_fn_definitions(cpp_path: Path, fn_defs: dict) -> None:
    raw_lines = cpp_path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Join multi-line function signatures into a single logical line so
    # `_FN_DEF_RE` (which expects the closing `)` on the same line) can match
    # them. We only join when a line opens a `Fn<Name>(` whose parentheses
    # are not yet balanced.
    logical: list[tuple[int, str]] = []
    i = 0
    n = len(raw_lines)
    while i < n:
        line = raw_lines[i]
        if (
            re.search(r"\bFn[A-Za-z0-9_]+\s*\(", line)
            and line.count("(") > line.count(")")
        ):
            buf = [line]
            start = i
            joined = buf[0]
            while i + 1 < n and joined.count("(") > joined.count(")"):
                i += 1
                buf.append(raw_lines[i])
                joined = " ".join(buf)
            logical.append((start + 1, joined))
        else:
            logical.append((i + 1, line))
        i += 1

    pending_docstring = ""
    for idx, (lineno, line) in enumerate(logical):
        # Capture /** ... */ docstring that may span lines.
        if "/**" in line:
            start = line.index("/**")
            if "*/" in line[start:]:
                pending_docstring = line[start:line.index("*/", start) + 2]
            else:
                buf = [line[start:]]
                j = idx + 1
                while j < len(logical) and "*/" not in logical[j][1]:
                    buf.append(logical[j][1])
                    j += 1
                if j < len(logical):
                    buf.append(logical[j][1][:logical[j][1].index("*/") + 2])
                pending_docstring = "\n".join(buf)
            continue
        m = _FN_DEF_RE.match(line)
        if not m:
            # Reset pending docstring if a non-definition line intervenes? Keep it
            # only if the very next non-blank line is a definition.
            if line.strip() == "" or line.strip().startswith("//") or line.strip().startswith("/*"):
                continue
            pending_docstring = ""
            continue
        ret_type, symbol, params_text = m.group(1), m.group(2), m.group(3)
        params = _parse_fn_params(params_text)
        fn_defs[symbol] = {
            "return_type": ret_type.strip(),
            "params": params,
            "docstring": _clean_docstring(pending_docstring),
            "source": f"{cpp_path.name}:{lineno}",
        }
        pending_docstring = ""


def _parse_fn_params(params_text: str) -> list[Param]:
    """Parse a C++ parameter list, dropping C4AulContext *cthr."""
    params_text = params_text.strip()
    if not params_text:
        return []
    # Split on top-level commas.
    depth = 0
    tokens: list[str] = []
    current: list[str] = []
    for ch in params_text:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            tokens.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))

    params: list[Param] = []
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        # Strip embedded /* ... */ block comments inside a parameter.
        tok = re.sub(r"/\*.*?\*/", "", tok).strip()
        if not tok:
            continue
        # Drop the hidden calling-context param.
        if "C4AulContext" in tok:
            continue
        # Split type and name: last identifier is the name.
        m = re.match(r"^(.+?)\s*([A-Za-z_][A-Za-z0-9_]*)$", tok)
        if m:
            cpp_type, name = m.group(1).strip(), m.group(2)
            cpp_type = cpp_type.replace("const ", "").strip()
            params.append(Param(name=name, c4type=_map_cpp_type(cpp_type)))
        else:
            # Type only, no name.
            params.append(Param(name="", c4type=_map_cpp_type(tok)))
    return params


def _clean_docstring(raw: str) -> str:
    if not raw:
        return ""
    # Strip /** and */ and leading * on each line.
    raw = raw.strip()
    if raw.startswith("/**"):
        raw = raw[3:]
    if raw.endswith("*/"):
        raw = raw[:-2]
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("*"):
            line = line[1:].lstrip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def count_addfuncs(cpp_path: Path) -> int:
    """Independent count of `AddFunc(pEngine, ...)` registration lines.

    Uses a plain substring check (not `_ADDFUNC_RE`) so the integration test
    can catch regex misses — e.g. a `PSF_*` macro argument the regex doesn't
    yet accept would show up as `count > len(parse_functions(...))`.
    """
    count = 0
    for line in cpp_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "AddFunc" in line and "pEngine" in line:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Constants: parse C4ScriptConstMap[] rows
# ---------------------------------------------------------------------------

_CONSTROW_RE = re.compile(
    r"""^\s*\{\s*
        "([A-Za-z0-9_]+)"        # group 1: constant name
        \s*,\s*
        (C4V_[A-Za-z]+)          # group 2: C4V_* type
        \s*,\s*
        ([^}]+?)                 # group 3: value (unused but captured)
        \s*\}\s*,?\s*
        (?: //[^\n]*)?           # optional trailing // comment
        \s*$""",
    re.VERBOSE,
)


def parse_constants(cpp_path: Path) -> list[Constant]:
    consts: list[Constant] = []
    in_map = False
    for lineno, line in enumerate(cpp_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if "C4ScriptConstMap" in line and "[" in line:
            in_map = True
            continue
        if in_map and line.strip().startswith("};"):
            in_map = False
            continue
        if not in_map:
            continue
        m = _CONSTROW_RE.match(line)
        if not m:
            continue
        name, c4v, value_token = m.group(1), m.group(2), m.group(3).strip()
        consts.append(Constant(
            name=name, c4v_type=c4v, c4type=_map_c4v(c4v), source_line=lineno,
            value_token=value_token,
        ))
    return consts


def count_constmap_rows(cpp_path: Path) -> int:
    """Independent count of `C4ScriptConstMap[]` data rows.

    Counts lines starting with `{ "` (a quoted constant name) inside the
    const map block. Does NOT share the parser's `_CONSTROW_RE` regex, so the
    integration test can catch regex misses (e.g. trailing comments).
    """
    text = cpp_path.read_text(encoding="utf-8", errors="replace")
    in_map = False
    count = 0
    for line in text.splitlines():
        if "C4ScriptConstMap" in line and "[" in line:
            in_map = True
            continue
        if in_map and line.strip().startswith("};"):
            in_map = False
            continue
        if in_map and line.lstrip().startswith('{ "'):
            count += 1
    return count


# ---------------------------------------------------------------------------
# DefCore.txt fields: parse C4DefCore::CompileFunc mkNamingAdapt(...) calls
# ---------------------------------------------------------------------------

def _extract_paren_calls(text: str, name: str) -> list[tuple[int, str]]:
    """Return (char_offset, args_string) for every `<name>(...)` call in
    `text`, respecting nested parentheses. The char_offset is the index of
    the call's opening parenthesis."""
    results = []
    needle = name + "("
    pos = 0
    while True:
        idx = text.find(needle, pos)
        if idx == -1:
            break
        start = idx + len(needle)
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        if depth == 0:
            results.append((idx, text[start:i - 1]))
        pos = i
    return results


def _innermost_identifier(arg: str) -> str:
    """Given a field arg like `mkBitfieldAdapt(Category, ...)` or
    `toC4CStr(STimerCall)`, return the innermost C++ field identifier."""
    s = arg.strip()
    while "(" in s and s.endswith(")"):
        inner = s[s.index("(") + 1:s.rindex(")")]
        # If the inner has top-level commas, the field is the first part.
        commas = _split_top_level_commas(inner)
        s = commas[0].strip() if commas else inner.strip()
    return s


def parse_defcore_fields(def_path: Path) -> list[DefCoreField]:
    text = def_path.read_text(encoding="utf-8", errors="replace")
    # Locate the CompileFunc body.
    func_match = re.search(r"C4DefCore::CompileFunc\s*\([^)]*\)\s*\{", text)
    if not func_match:
        return []
    body_start = func_match.end()
    depth = 1
    i = body_start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    body = text[body_start:i - 1]

    fields: list[DefCoreField] = []
    for offset, args in _extract_paren_calls(body, "mkNamingAdapt"):
        parts = _split_top_level_commas(args)
        if len(parts) < 2:
            continue
        field_arg = parts[0].strip()
        key_match = re.match(r'\s*"([^"]+)"', parts[1])
        if not key_match:
            continue
        key = key_match.group(1)
        default = parts[2].strip() if len(parts) >= 3 else ""
        field_name = _innermost_identifier(field_arg)
        # Source line is the body offset + body_start, converted to a line number.
        line_no = text[:body_start + offset].count("\n") + 1
        fields.append(DefCoreField(
            key=key, field=field_name, default=default, source_line=line_no,
        ))
    return fields


def count_defcore_fields(def_path: Path) -> int:
    """Independent count of `mkNamingAdapt(...)` calls in `C4Def::CompileFunc`.

    Locates the `CompileFunc` body with simple brace matching (does NOT use
    the parser's `_extract_paren_calls` logic), then counts `mkNamingAdapt`
    occurrences. This way the integration test can catch parser extraction
    misses.
    """
    text = def_path.read_text(encoding="utf-8", errors="replace")
    func_match = re.search(r"C4DefCore::CompileFunc\s*\([^)]*\)\s*\{", text)
    if not func_match:
        return 0
    body_start = func_match.end()
    depth = 1
    i = body_start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    body = text[body_start:i - 1]
    return body.count("mkNamingAdapt")


# ===========================================================================
# Rendering
# ===========================================================================

def _load_curated(path: Path) -> dict:
    if path.exists() and yaml is not None:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def render_callback_group(group_file: str, group_title: str,
                          callbacks: list[Callback], curated: dict) -> str:
    lines = [f"# {group_title}", ""]
    for cb in sorted(callbacks, key=lambda c: c.name):
        entry = curated.get(cb.name, {})
        params = _parse_hint_params(cb.param_hint)
        sig = ", ".join(f"{p.c4type} {p.name}" for p in params) if params else ""
        lines.append(f"## `{cb.name}`")
        lines.append("")
        lines.append(f"**Engine symbol:** `{cb.symbol}`  ")
        lines.append(f"**Source:** `src/C4Script.h:{cb.source_line}`  ")
        if sig:
            lines.append(f"**Signature:** `{cb.name}({sig})`")
        else:
            lines.append(f"**Signature:** `{cb.name}()`")
        lines.append("")
        if entry.get("when"):
            lines.append(f"**When this fires:** {entry['when']}")
            lines.append("")
        if entry.get("returns"):
            lines.append(f"**Return value:** {entry['returns']}")
            lines.append("")
        if entry.get("description"):
            lines.append(entry["description"])
            lines.append("")
        if not entry:
            lines.append(f"> This callback is not yet documented. "
                         f"See `src/C4Script.h:{cb.source_line}`.")
            lines.append("")
    return "\n".join(lines) + "\n"


def render_function_page(fn: Function, curated: dict) -> str:
    entry = curated.get(fn.name, {})
    lines = [f"# `{fn.name}`", ""]
    sig_params = ", ".join(f"{p.c4type} {p.name}" for p in fn.params)
    lines.append(f"**C4Script signature:** `{fn.return_type} {fn.name}({sig_params})`  ")
    lines.append(f"**C++ symbol:** `{fn.symbol}`  ")
    lines.append(f"**Registration:** `src/C4Script.cpp:{fn.addfunc_line}` (in `InitFunctionMap`)  ")
    if fn.signature_found:
        lines.append(f"**Definition:** `{fn.signature_source}`")
    else:
        lines.append("**Definition:** signature not found in any `src/*.cpp`")
    lines.append("")
    if fn.protected is False:
        lines.append("> !!! warning \"Not callable from protected context\"")
        lines.append(">     This function is registered with the `false` protected flag.")
        lines.append("")
    if entry.get("summary"):
        lines.append(entry["summary"])
        lines.append("")
    elif fn.docstring:
        lines.append(fn.docstring)
        lines.append("")
    else:
        lines.append("> This function is not yet documented. See the C++ source line above.")
        lines.append("")
    if entry.get("params"):
        lines.append("**Parameters:**")
        lines.append("")
        for pname, pdesc in entry["params"].items():
            lines.append(f"- `{pname}`: {pdesc}")
        lines.append("")
    if entry.get("returns"):
        lines.append(f"**Returns:** {entry['returns']}")
        lines.append("")
    if entry.get("example"):
        lines.append("## Example")
        lines.append("")
        lines.append("```c")
        lines.append(entry["example"].strip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_function_index(functions: list[Function], curated: dict) -> str:
    lines = ["# Built-in functions", ""]
    lines.append("Alphabetic table of every built-in C4Script function, harvested from "
                 "`InitFunctionMap` in `src/C4Script.cpp`.")
    lines.append("")
    lines.append("| Name | C++ symbol | Status |")
    lines.append("|---|---|---|")
    for fn in sorted(functions, key=lambda f: f.name.lower()):
        status = "documented" if (curated.get(fn.name) or fn.docstring) else "stub"
        lines.append(f"| [`{fn.name}`]({fn.name}.md) | `{fn.symbol}` | {status} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_constants(consts: list[Constant], curated: dict, values: dict) -> str:
    lines = ["# Global constants", ""]
    lines.append("Every global C4Script constant, harvested from `C4ScriptConstMap[]` "
                 "in `src/C4Script.cpp`.")
    lines.append("")
    # Group by prefix.
    groups: dict[str, list[Constant]] = {}
    for c in consts:
        prefix = c.name.split("_")[0]
        groups.setdefault(prefix, []).append(c)
    for prefix in sorted(groups.keys()):
        lines.append(f"## `{prefix}_*`")
        lines.append("")
        lines.append("| Name | Value | Type | Description |")
        lines.append("|---|---|---|---|")
        for c in sorted(groups[prefix], key=lambda x: x.name):
            desc = curated.get(c.name, "")
            value = values.get(c.name, "")
            lines.append(f"| `{c.name}` | {value} | `{c.c4type}` | {desc} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_defcore(fields: list[DefCoreField], curated: dict) -> str:
    lines = ["# DefCore.txt fields", ""]
    lines.append("Every `DefCore.txt` field, harvested from `C4DefCore::CompileFunc` "
                 "in `src/C4Def.cpp`.")
    lines.append("")
    lines.append("| Key | C++ field | Default | Description |")
    lines.append("|---|---|---|---|")
    for f in sorted(fields, key=lambda x: x.key):
        desc = curated.get(f.key, "")
        lines.append(f"| `{f.key}` | `{f.field}` | `{f.default}` | {desc} |")
    lines.append("")
    return "\n".join(lines) + "\n"


# ===========================================================================
# Main: orchestrate parse + render + write
# ===========================================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harvest C4Script reference from engine source.")
    parser.add_argument("--src-dir", default="src", type=Path)
    parser.add_argument("--out-dir", default="docs/reference", type=Path)
    args = parser.parse_args(argv)

    src_dir: Path = args.src_dir
    out_dir: Path = args.out_dir

    header = src_dir / "C4Script.h"
    cpp = src_dir / "C4Script.cpp"
    def_cpp = src_dir / "C4Def.cpp"

    callbacks = parse_callbacks(header)
    functions = parse_functions(cpp, src_dir=src_dir)
    consts = parse_constants(cpp)
    defcore_fields = parse_defcore_fields(def_cpp)

    # Load curated sidecars.
    cb_curated = _load_curated(out_dir / "callbacks" / "_curated.yaml")
    fn_curated = _load_curated(out_dir / "functions" / "_curated.yaml")
    const_curated = _load_curated(out_dir / "_curated_constants.yaml")
    const_values = _load_curated(out_dir / "_curated_constant_values.yaml")
    defcore_curated = _load_curated(out_dir / "_curated_defcore.yaml")

    # Render callbacks: group by group file.
    cb_out = out_dir / "callbacks"
    cb_out.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[Callback]] = {}
    for cb in callbacks:
        groups.setdefault(callback_group(cb.symbol), []).append(cb)
    group_titles = {g: t for (_, g, t) in CALLBACK_GROUPS}
    for group_file, cbs in groups.items():
        title = group_titles.get(group_file, "Misc callbacks")
        md = render_callback_group(group_file, title, cbs, cb_curated)
        (cb_out / group_file).write_text(md, encoding="utf-8")

    # Render functions.
    fn_out = out_dir / "functions"
    fn_out.mkdir(parents=True, exist_ok=True)
    for fn in functions:
        md = render_function_page(fn, fn_curated)
        (fn_out / f"{fn.name}.md").write_text(md, encoding="utf-8")
    (fn_out / "index.md").write_text(render_function_index(functions, fn_curated), encoding="utf-8")

    # Render constants + defcore.
    (out_dir / "constants.md").write_text(render_constants(consts, const_curated, const_values), encoding="utf-8")
    (out_dir / "defcore.md").write_text(render_defcore(defcore_fields, defcore_curated), encoding="utf-8")

    # Warn about unknown types.
    if _WARN_UNKNOWN_TYPES:
        print("WARNING: unknown C++ types mapped to 'any':", file=sys.stderr)
        for t in sorted(_WARN_UNKNOWN_TYPES):
            print(f"  {t}", file=sys.stderr)

    print(f"Harvested {len(callbacks)} callbacks, {len(functions)} functions, "
          f"{len(consts)} constants, {len(defcore_fields)} DefCore.txt fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
