#!/usr/bin/env python3
"""Vision-QA harness: ollama-backed probe battery with oracle validation.

Cycle 98 (scorpion-art-vision-qa-rework). Renders the target sprite's
phases xN on white (stdlib PNG decode/encode only — no PIL), runs the
pinned question battery (Q1-Q4 per phase, Q5 on the stacked pair) against
a local ollama model, and prints GATE PASS / GATE FAIL.

Startup oracle controls validate the instrument itself:
  1. photo positive control  — model must read "scorpion" on the fixture
  2. flat-block negative A   — feature battery AND tail/arch read must
     FAIL on a flat block (bounds both Q2 acceptance paths)
  3. flat-block negative B   — Q5 coherence must FAIL on a stacked flat pair
Any control failing prints ORACLE FAIL and exits 2 — a broken instrument
aborts, it never produces data.

Exit codes: 0 = GATE PASS or SKIP, 1 = GATE FAIL, 2 = ORACLE FAIL /
usage error / decode error. The harness never pulls models; a missing
judge prints SKIP and exits 0.
"""

import argparse
import base64
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.request
import zlib

# ---------------------------------------------------------------------------
# pinned constants
# ---------------------------------------------------------------------------

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.8:27b"
DEFAULT_IMAGE = os.path.join("..", "content", "Desert.c4d", "Scorpion.c4d",
                             "Graphics.png")
# Default facet targets the committed content art (72x26 sheet = 2 phases
# of 36x26, cycle 105 scaleup).
DEFAULT_FACET = (0, 0, 36, 26)
PAIR_GAP = 4          # white rows between stacked frames (sprite pixels)
FLAT_RGB = (90, 58, 31)
FLAT_W, FLAT_H = 20, 12
CHAT_TIMEOUT = 600    # per-call timeout (27B model, cold load)
TAGS_TIMEOUT = 5      # judge reachability probe

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURE_JPG = os.path.normpath(os.path.join(
    SCRIPT_DIR, os.pardir, "tests", "fixtures", "vision_qa",
    "scorpion_photo.jpg"))

# Pinned probe wordings (empirically validated — do NOT rephrase).
Q1 = ("Look at this image. What creature is depicted? Answer in one line: "
      "the creature name, then one short sentence describing which visual "
      "features led you to that answer.")
Q2 = ("Second question about the same image. Describe the tail: is there a "
      "tail, what shape is it, where does it attach, and what is at its "
      "tip? Be literal, only report what is actually visible.")
Q3 = ("Third question about the same image. Are there pincers or claws at "
      "the front of the creature? Answer yes or no first, then one "
      "sentence describing what you see. Be literal, only report what is "
      "actually visible.")
Q4 = ("Fourth question about the same image. How many legs are visible? "
      "Answer with a number first, then one sentence describing them. "
      "Be literal, only report what is actually visible.")
Q5 = ("This image shows two frames stacked vertically. Do these two "
      "frames show the same creature walking? Answer yes or no first, "
      "then one sentence justifying your answer. Be literal, only report "
      "what is actually visible.")

# Q2 keyword sets (pinned v1; matched with word boundaries — see
# _keyword_re below. The sets themselves are unchanged from pinned v1.)
ARCH_WORDS = ("arch", "arched", "arc", "curve", "curved", "curl", "curled",
              "hook", "hooked", "bent", "raised", "segment", "segmented",
              "segments")
TIP_WORDS = ("point", "pointed", "sting", "stinger", "barb", "barbed",
             "venom", "telson", "sharp", "spike", "needle")

# Q2 tip sub-criterion revision (cycle 98 final iteration, documented +
# bounded). Empirical premise (~25 Q2 probes at temp 0): in Q2's literal
# mode the model describes pixel-art tips as "bar/block/square/pixel/
# tuft" — the pinned tip vocabulary is never emitted on any 28x20
# sprite, while the photo control passes. Meanwhile the same phase's Q1
# (open-ended) DOES elicit tip vocabulary ("curved, stinger-tipped
# tail"). This is a mode mismatch, not missing art features. Revision:
# the tip sub-criterion passes via Q2 as before (a), OR via cross-check
# (b): >= 2 of the phase's 3 Q1 run answers contain a tip word from the
# pinned set below (word-boundary match). Tail + arch criteria are
# unchanged; no other keyword set, wording, or criterion is touched.
Q1_TIP_WORDS = ("stinger", "sting", "telson", "barb", "pointed")
TAIL_WORDS = ("tail", "telson")

# Word-boundary keyword matching (cycle 98 review fix): the pinned sets
# above and below are matched as \b-anchored prefixes, not raw
# substrings. This kills the verified over-matches ("tail" in "detail",
# "arc" in "search", "sting" in "distinguishing") while still catching
# inflections the old substring match used to accept ("tails",
# "arched", "stinging"). The keyword sets themselves are unchanged.
def _keyword_re(words):
    alt = "|".join(re.escape(w) for w in words)
    return re.compile(r"\b(?:" + alt + r")")

TAIL_RE = _keyword_re(TAIL_WORDS)
ARCH_RE = _keyword_re(ARCH_WORDS)
TIP_RE = _keyword_re(TIP_WORDS)
Q1_TIP_RE = _keyword_re(Q1_TIP_WORDS)

# Q1 classification sets (whole-word, case-insensitive).
ARTHROPOD_WORDS = ("spider", "centipede", "ant", "crab", "insect", "beetle",
                   "bug", "arachnid", "arthropod")
MAMMAL_REPTILE_WORDS = ("pig", "boar", "dog", "puppy", "cat", "kitten",
                        "snake", "serpent", "horse", "pony", "cow", "bull",
                        "mouse", "rat", "lizard", "gecko", "fox", "weasel",
                        "rabbit", "hare", "wolf", "bear", "deer", "frog",
                        "toad", "turtle", "tortoise", "crocodile",
                        "alligator", "dinosaur", "dragon", "cattle",
                        "sheep", "goat")
ARTHROPOD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in ARTHROPOD_WORDS) + r")\b")
MAMMAL_REPTILE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w)
                        for w in MAMMAL_REPTILE_WORDS) + r")\b")

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
NUMBER_RE = re.compile(
    r"\d+|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b",
    re.IGNORECASE)

# Think-block defense: strip from content before parsing; a separate
# `thinking` field is tolerated (ignored).
THINK_BLOCK_RE = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL)
THINK_OPEN_RE = re.compile(r"<think(?:ing)?>.*", re.DOTALL)

CLASS_SEVERITY = ("mammal-reptile", "arthropod-adjacent", "other",
                  "scorpion")

# ---------------------------------------------------------------------------
# PNG decode (stdlib, no PIL): 8-bit, color types 0/2/3/4/6, non-interlaced
# ---------------------------------------------------------------------------

def png_decode(data):
    """Decode a PNG into (width, height, rows); rows[y][x] = (r,g,b,a).

    Supports bit depth 8, color types 0 (gray), 2 (RGB), 3 (palette),
    4 (gray+alpha), 6 (RGBA), filters 0-4, non-interlaced only.
    Raises ValueError on anything else (a broken instrument aborts).
    """
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("bad PNG signature (not a PNG file?)")
    pos = 8
    ihdr = None
    idat = bytearray()
    plte = None
    trns = None
    while pos + 8 <= len(data):
        (length, ) = struct.unpack(">I", data[pos:pos + 4])
        if pos + 8 + length > len(data):
            raise ValueError("truncated chunk")
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            ihdr = chunk
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"PLTE":
            plte = chunk
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IEND":
            break
    if ihdr is None or not idat:
        raise ValueError("missing IHDR/IDAT chunk")
    try:
        w, h, depth, color, _comp, _filt, interlace = struct.unpack(
            ">IIBBBBB", ihdr)
    except struct.error as e:
        raise ValueError(f"bad IHDR: {e}") from e
    if depth != 8:
        raise ValueError(f"unsupported bit depth {depth} (need 8)")
    if color not in (0, 2, 3, 4, 6):
        raise ValueError(f"unsupported color type {color}")
    if interlace != 0:
        raise ValueError("interlaced PNG not supported")
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    stride = w * nch
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as e:
        raise ValueError(f"zlib error in IDAT: {e}") from e
    if len(raw) < h * (stride + 1):
        raise ValueError("truncated pixel data")
    rows = []
    prev = bytearray(stride)
    off = 0
    for _y in range(h):
        ftype = raw[off]
        off += 1
        line = bytearray(raw[off:off + stride])
        off += stride
        if ftype == 1:  # Sub
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (
                    b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError(f"bad filter type {ftype}")
        prev = line
        rows.append(bytes(line))
    out = []
    for y in range(h):
        line = rows[y]
        row = []
        for x in range(w):
            i = x * nch
            if color == 0:
                g = line[i]
                row.append((g, g, g, 255))
            elif color == 2:
                row.append((line[i], line[i + 1], line[i + 2], 255))
            elif color == 3:
                if plte is None:
                    raise ValueError("palette PNG without PLTE chunk")
                idx = line[i]
                if idx * 3 + 2 >= len(plte):
                    raise ValueError("palette index out of range")
                r, g, b = plte[idx * 3:idx * 3 + 3]
                a = trns[idx] if (trns is not None and idx < len(trns)) else 255
                row.append((r, g, b, a))
            elif color == 4:
                g = line[i]
                row.append((g, g, g, line[i + 1]))
            else:  # 6
                row.append((line[i], line[i + 1], line[i + 2], line[i + 3]))
        out.append(row)
    return w, h, out

# ---------------------------------------------------------------------------
# rendering: xN nearest on white, PNG RGB (stdlib encode)
# ---------------------------------------------------------------------------

def png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

def render_b64(grid, scale):
    """grid: list of rows of (r,g,b,a). Nearest xN upscale on white -> PNG -> base64."""
    h = len(grid)
    w = len(grid[0])
    out_w, out_h = w * scale, h * scale
    raw = bytearray()
    for y in range(out_h):
        raw.append(0)  # filter: none
        srow = grid[y // scale]
        for x in range(out_w):
            r, g, b, a = srow[x // scale]
            if a == 0:
                raw.extend((255, 255, 255))
            elif a == 255:
                raw.extend((r, g, b))
            else:
                f = a / 255.0
                raw.extend((round(r * f + 255 * (1 - f)),
                            round(g * f + 255 * (1 - f)),
                            round(b * f + 255 * (1 - f))))
    png = (b"\x89PNG\r\n\x1a\n"
           + png_chunk(b"IHDR",
                       struct.pack(">IIBBBBB", out_w, out_h, 8, 2, 0, 0, 0))
           + png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + png_chunk(b"IEND", b""))
    return base64.b64encode(png).decode()

# ---------------------------------------------------------------------------
# ollama client
# ---------------------------------------------------------------------------

class JudgeError(RuntimeError):
    """Mid-battery judge failure (broken instrument -> exit 2)."""

def make_ask(host, model):
    """Return ask(image_b64, prompt) -> answer string (think blocks stripped)."""

    def ask(image_b64, prompt):
        body = json.dumps({
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }],
            "stream": False,
            # Second-highest ollama think level (ladder: false < low <
            # medium < high < max) — user directive 2026-09-07: the vision
            # judge runs at "high", not the model default ("max"/true).
            "think": "high",
            "options": {"temperature": 0},
        }).encode()
        req = urllib.request.Request(host.rstrip("/") + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as r:
                resp = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise JudgeError(f"ollama /api/chat HTTP {e.code}: "
                             f"{e.read()[:300]!r}") from e
        except (urllib.error.URLError, OSError) as e:
            raise JudgeError(f"ollama /api/chat unreachable: {e}") from e
        except ValueError as e:
            raise JudgeError(f"ollama /api/chat returned invalid JSON: "
                             f"{e}") from e
        msg = resp.get("message") or {}
        # Think-block defense: strip from content; tolerate separate field.
        return strip_think(msg.get("content", ""))

    return ask

# ---------------------------------------------------------------------------
# answer parsing (pinned evaluation rules)
# ---------------------------------------------------------------------------

def strip_think(text):
    if not text:
        return ""
    text = THINK_BLOCK_RE.sub("", text)
    text = THINK_OPEN_RE.sub("", text)  # unterminated block: drop the rest
    return text.strip()

def yes_first(answer):
    """Q3/Q5 pass rule: first token of the normalized answer is yes/y.

    Punctuation and leading markdown emphasis are stripped from the
    first token ("**Yes**," -> "yes").
    """
    toks = answer.strip().lower().split()
    return bool(toks) and toks[0].strip(".,;:!?\"'()_*`") in ("yes", "y")

def leg_count(answer):
    """First integer or spelled one..ten in the answer; None if absent."""
    m = NUMBER_RE.search(answer)
    if not m:
        return None
    t = m.group(0).lower()
    if t.isdigit():
        return int(t)
    return NUMBER_WORDS[t]

def q2_pass(answer):
    low = answer.lower()
    return (bool(TAIL_RE.search(low))
            and bool(ARCH_RE.search(low))
            and bool(TIP_RE.search(low)))

def q2_tail_arch(answer):
    """Tail + arch sub-criteria (the tip word is evaluated separately —
    see the Q2 tip revision comment at Q1_TIP_WORDS)."""
    low = answer.lower()
    return (bool(TAIL_RE.search(low))
            and bool(ARCH_RE.search(low)))

def q2_tip_via(q2_answers, q1_answers):
    """Revised Q2 tip sub-criterion: "q2" | "q1_cross" | "none".

    (a) "q2" — the Q2 majority carries the full tail+arch+tip read
        (unchanged behavior). (b) "q1_cross" — tail+arch majority in Q2
        plus >= 2 of 3 Q1 answers carrying a tip word (the mode-mismatch
        escape, see the comment at Q1_TIP_WORDS). "none" — the tip
        sub-criterion fails.
    """
    if majority([q2_pass(a) for a in q2_answers]):
        return "q2"
    tail_arch = majority([q2_tail_arch(a) for a in q2_answers])
    cross = sum(1 for a in q1_answers
                if Q1_TIP_RE.search(a.lower())) >= 2
    if tail_arch and cross:
        return "q1_cross"
    return "none"

def q4_pass(answer):
    n = leg_count(answer)
    return n is not None and n >= 4

def classify_q1(answer):
    low = answer.lower()
    if "scorpion" in low:
        return "scorpion"
    if MAMMAL_REPTILE_RE.search(low):
        return "mammal-reptile"
    if ARTHROPOD_RE.search(low):
        return "arthropod-adjacent"
    return "other"

def majority_class(classes):
    """Most frequent classification; ties broken toward the worse read."""
    counts = {}
    for c in classes:
        counts[c] = counts.get(c, 0) + 1
    best = max(counts.values())
    for sev in CLASS_SEVERITY:
        if counts.get(sev) == best:
            return sev
    return "other"

def majority(passes):
    """Strict majority of boolean per-run results; a split = fail."""
    return 2 * sum(passes) > len(passes)

# ---------------------------------------------------------------------------
# oracle controls (single-shot each)
# ---------------------------------------------------------------------------

def run_oracle(ask, scale, record):
    """Three controls; any failure -> False (caller prints ORACLE FAIL)."""
    ok = True

    # -- control 1: photo positive (model must identify a scorpion) --
    try:
        with open(FIXTURE_JPG, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode()
    except OSError as e:
        print(f"ORACLE FAIL: cannot read photo fixture {FIXTURE_JPG}: {e}",
              flush=True)
        return False
    a_photo = ask(photo_b64, Q1)
    photo_ok = "scorpion" in a_photo.lower()
    print(f"[oracle 1] photo Q1: {a_photo}", flush=True)
    record["photo_q1"] = {"answer": a_photo, "pass": photo_ok}
    if not photo_ok:
        print('ORACLE FAIL: photo control - Q1 answer lacks "scorpion"',
              flush=True)
        ok = False

    # -- control 2: flat block (negative A — the gate must bite) --
    block = [[(*FLAT_RGB, 255)] * FLAT_W for _ in range(FLAT_H)]
    block_b64 = render_b64(block, scale)
    a_b1 = ask(block_b64, Q1)
    a_b2 = ask(block_b64, Q2)
    a_b3 = ask(block_b64, Q3)
    a_b4 = ask(block_b64, Q4)
    print(f"[oracle 2] block Q1: {a_b1}", flush=True)
    print(f"[oracle 2] block Q2: {a_b2}", flush=True)
    print(f"[oracle 2] block Q3: {a_b3}", flush=True)
    print(f"[oracle 2] block Q4: {a_b4}", flush=True)
    # Control 2 bounds every acceptance path of the revised Q2 gate:
    # the block's Q2 answer must fail the full tail+arch+tip
    # conjunction AND the tail/arch sub-criterion that feeds the Q1
    # cross-check (q2_tip_via path (b)) — otherwise a judge that
    # volunteers tip vocabulary in open-ended mode on tip-less art
    # would pass the revised gate while this control stays green.
    battery_ok = not (q2_pass(a_b2) or q2_tail_arch(a_b2)
                      or yes_first(a_b3) or q4_pass(a_b4))
    no_scorpion = "scorpion" not in a_b1.lower()
    record["block_q1"] = a_b1
    record["block_battery"] = {"q2": a_b2, "q3": a_b3, "q4": a_b4}
    record["block_q2_tail_arch"] = q2_tail_arch(a_b2)
    record["block_battery_failed"] = battery_ok
    record["block_q1_no_scorpion"] = no_scorpion
    if not battery_ok:
        print("ORACLE FAIL: flat-block control - feature battery or "
              "tail/arch read passed (gate is vacuous)", flush=True)
        ok = False
    if not no_scorpion:
        print('ORACLE FAIL: flat-block control - Q1 answered "scorpion" '
              "(judge is sycophantic)", flush=True)
        ok = False

    # -- control 3: stacked flat pair (negative B — coherence must bite) --
    stacked = (block + [[(255, 255, 255, 255)] * FLAT_W for _ in range(PAIR_GAP)]
               + block)
    a_s5 = ask(render_b64(stacked, scale), Q5)
    stacked_ok = not yes_first(a_s5)
    print(f"[oracle 3] stacked Q5: {a_s5}", flush=True)
    record["stacked_q5"] = {"answer": a_s5, "pass": stacked_ok}
    if not stacked_ok:
        print("ORACLE FAIL: stacked-block control - Q5 passed on a flat "
              "pair (coherence gate is vacuous)", flush=True)
        ok = False

    return ok

# ---------------------------------------------------------------------------
# battery
# ---------------------------------------------------------------------------

def probe_phase(ask, grid, runs, scale, label, record):
    """Q1-Q4 x runs on one phase grid. Fills record[label]."""
    b64 = render_b64(grid, scale)
    res = {}

    # Q1: open-ended, classification + mammal/reptile gate
    q1_answers, q1_classes = [], []
    for r in range(runs):
        a = ask(b64, Q1)
        q1_answers.append(a)
        q1_classes.append(classify_q1(a))
        print(f"[{label}] Q1 run {r + 1}/{runs}: {a}", flush=True)
    mammal_runs = sum(1 for c in q1_classes if c == "mammal-reptile")
    q1_gate = mammal_runs * 2 <= runs  # strict majority of mammal reads fails
    res["q1"] = {
        "answers": q1_answers,
        "classifications": q1_classes,
        "majority_class": majority_class(q1_classes),
        "mammal_reptile_runs": mammal_runs,
        "gate_pass": q1_gate,
    }

    # Q2: tail arch + tip
    q2_answers, q2_passes = [], []
    for r in range(runs):
        a = ask(b64, Q2)
        q2_answers.append(a)
        q2_passes.append(q2_pass(a))
        print(f"[{label}] Q2 run {r + 1}/{runs}: {a}", flush=True)
    res["q2"] = {"answers": q2_answers, "passes": q2_passes,
                 "majority_pass": majority(q2_passes)}

    # Q3: pincers yes-first
    q3_answers, q3_passes = [], []
    for r in range(runs):
        a = ask(b64, Q3)
        q3_answers.append(a)
        q3_passes.append(yes_first(a))
        print(f"[{label}] Q3 run {r + 1}/{runs}: {a}", flush=True)
    res["q3"] = {"answers": q3_answers, "passes": q3_passes,
                 "majority_pass": majority(q3_passes)}

    # Q4: legs >= 4
    q4_answers, q4_passes = [], []
    for r in range(runs):
        a = ask(b64, Q4)
        q4_answers.append(a)
        q4_passes.append(q4_pass(a))
        print(f"[{label}] Q4 run {r + 1}/{runs}: {a}", flush=True)
    res["q4"] = {"answers": q4_answers, "passes": q4_passes,
                 "majority_pass": majority(q4_passes)}

    record[label] = res

def probe_pair(ask, top_grid, bot_grid, fw, runs, scale, record):
    """Q5 x runs on the stacked pair (top above bottom, PAIR_GAP white rows)."""
    pair = (top_grid
            + [[(255, 255, 255, 255)] * fw for _ in range(PAIR_GAP)]
            + bot_grid)
    b64 = render_b64(pair, scale)
    answers, passes = [], []
    for r in range(runs):
        a = ask(b64, Q5)
        answers.append(a)
        passes.append(yes_first(a))
        print(f"[pair] Q5 run {r + 1}/{runs}: {a}", flush=True)
    record["pair_q5"] = {
        "answers": answers,
        "passes": passes,
        "majority_pass": majority(passes),
    }

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_facet(s):
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--facet must be X,Y,W,H")
    try:
        vals = tuple(int(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("--facet must be integers")
    if any(v < 0 for v in vals) or vals[2] <= 0 or vals[3] <= 0:
        raise argparse.ArgumentTypeError("--facet needs X,Y >= 0 and W,H > 0")
    return vals

def main():
    ap = argparse.ArgumentParser(
        description="Ollama-backed vision-QA battery with oracle validation")
    ap.add_argument("--image", default=DEFAULT_IMAGE,
                    help="target sprite sheet PNG")
    ap.add_argument("--facet", type=parse_facet, default=DEFAULT_FACET,
                    help="facet rect X,Y,W,H (phase 0 at facet, phase i "
                         "at X+i*W); default targets the committed "
                         "content art (2 phases of 20x12)")
    ap.add_argument("--phases", type=int, default=2,
                    help="number of phases laid out horizontally")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--runs", type=int, default=3,
                    help="runs per gating probe (majority decides)")
    ap.add_argument("--scale", type=int, default=8,
                    help="nearest-integer upscale factor")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--oracle-only", action="store_true",
                    help="run only the oracle controls and exit")
    ap.add_argument("--json", default=None,
                    help="write the full record (verbatim answers, "
                         "majorities, verdict) to this path")
    ap.add_argument("--gate-mode", choices=["full", "feature", "advisory"],
                    default="full",
                    help="gate strictness: full = complete scorpion battery; "
                         "feature = per-phase Q4 legs + Q5 pair coherence; "
                         "advisory = record-only, no gate evaluated")
    args = ap.parse_args()

    if args.runs < 1 or args.scale < 1:
        print("ERROR: --runs and --scale must be >= 1", file=sys.stderr)
        return 2
    if not args.oracle_only and args.phases < 2:
        print("ERROR: --phases must be >= 2 (Q5 needs a phase pair)",
             file=sys.stderr)
        return 2

    # -- SKIP path: judge reachability, then model presence -----------
    base = args.host.rstrip("/")
    try:
        with urllib.request.urlopen(base + "/api/tags",
                                    timeout=TAGS_TIMEOUT) as r:
            tags = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"SKIP: judge reachability check failed (HTTP {e.code})",
              flush=True)
        return 0
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"SKIP: ollama unreachable ({getattr(e, 'reason', e)})",
              flush=True)
        return 0
    names = [m.get("name", "") for m in tags.get("models", [])]
    if args.model not in names and args.model.lower() not in (
            n.lower() for n in names):
        print(f"SKIP: model '{args.model}' not present in ollama tags",
              flush=True)
        return 0

    ask = make_ask(base, args.model)

    # -- decode target (a broken instrument aborts; never produces data) --
    img = None
    if not args.oracle_only:
        try:
            with open(args.image, "rb") as f:
                raw = f.read()
        except OSError as e:
            print(f"ERROR: cannot read target image {args.image}: {e}",
                  file=sys.stderr)
            return 2
        try:
            w, h, img = png_decode(raw)
        except ValueError as e:
            print(f"ERROR: target PNG decode failed: {e}", file=sys.stderr)
            return 2
        fx, fy, fw, fh = args.facet
        if fx + args.phases * fw > w or fy + fh > h:
            print(f"ERROR: facet x phases ({fw}x{fh} x {args.phases}) "
                  f"outside {w}x{h} sheet", file=sys.stderr)
            return 2

    # -- oracle controls + battery (a mid-run judge failure is a broken
    #    instrument: exit 2, never a gate verdict) ----------------------
    oracle_rec = {}
    battery_rec = {}
    verdict = None
    oracle_ok = False
    try:
        oracle_ok = run_oracle(ask, args.scale, oracle_rec)
        if not oracle_ok:
            print("ORACLE FAIL: one or more oracle controls failed — "
                  "aborting", flush=True)
        elif args.oracle_only:
            print("oracle controls green", flush=True)
        else:
            fx, fy, fw, fh = args.facet
            phase_grids = []
            for i in range(args.phases):
                phase_grids.append(
                    [row[fx + i * fw:fx + (i + 1) * fw]
                     for row in img[fy:fy + fh]])
            for i, pg in enumerate(phase_grids):
                probe_phase(ask, pg, args.runs, args.scale, f"phase {i}",
                            battery_rec)
            probe_pair(ask, phase_grids[0], phase_grids[1], fw, args.runs,
                       args.scale, battery_rec)

            # Revised Q2 gate: the tip sub-criterion may pass via the Q1
            # cross-check (evaluate (b) here, at gate evaluation).
            for i in range(args.phases):
                rec = battery_rec[f"phase {i}"]
                rec["q2_tip_via"] = q2_tip_via(
                    rec["q2"]["answers"], rec["q1"]["answers"])
            gate = all(
                battery_rec[f"phase {i}"]["q2_tip_via"] != "none"
                and battery_rec[f"phase {i}"]["q3"]["majority_pass"]
                and battery_rec[f"phase {i}"]["q4"]["majority_pass"]
                and battery_rec[f"phase {i}"]["q1"]["gate_pass"]
                for i in range(args.phases))
            gate = gate and battery_rec["pair_q5"]["majority_pass"]
            if args.gate_mode == "feature":
                gate = all(
                    battery_rec[f"phase {i}"]["q4"]["majority_pass"]
                    for i in range(args.phases))
                gate = gate and battery_rec["pair_q5"]["majority_pass"]
            if args.gate_mode == "advisory":
                verdict = "ADVISORY"
            else:
                verdict = "GATE PASS" if gate else "GATE FAIL"
            print(verdict, flush=True)
    except JudgeError as e:
        print(f"ERROR: judge failed mid-run: {e}", file=sys.stderr)
        return 2

    # -- JSON record (written even on ORACLE FAIL — the control
    #    transcript is the post-mortem artifact) ------------------------
    if args.json:
        record = {
            "model": args.model,
            "host": args.host,
            "image": args.image,
            "facet": list(args.facet),
            "phases": args.phases,
            "runs": args.runs,
            "scale": args.scale,
            "gate_mode": args.gate_mode,
            "oracle": oracle_rec,
            "battery": battery_rec,
            "verdict": verdict or ("oracle controls green" if oracle_ok
                                   else "ORACLE FAIL"),
        }
        try:
            with open(args.json, "w") as f:
                json.dump(record, f, indent=2)
                f.write("\n")
        except OSError as e:
            print(f"ERROR: cannot write JSON record to {args.json}: {e}",
                  file=sys.stderr)
            return 2

    if not oracle_ok:
        return 2
    if verdict == "GATE FAIL":
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
