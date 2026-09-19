#!/usr/bin/env python3
"""Deterministic Escape-Room helper sprite-sheet batch generator.

Subcommand-per-def batch generator (cycle 147, roadmap item
escape-rooms): gen_escape_gfx.py [egat|erlv|erky] [--check] renders (or
byte-gates) that def's Graphics.png from the transcribed ASCII maps and
the shared 10-char pack palette. Run bare (no def name) with --check to
byte-gate all three defs at once. Validate-then-encode: the per-def
clonkgfx.Invariants gate runs before the deterministic PNG encode.

Sheet layouts + expected ActMap/DefCore wiring:
- EGAT (escape gate): 32x28 sheet, one band with 2 phases of 16x28 at
  x=0/16. ActMap.txt splits the band into two Length=1 actions -- Gate
  (closed portcullis, Facet=0,0,16,28) and GateOpen (empty arch frame,
  Facet=16,0,16,28) -- which the Script flips between via SetAction.
  DefCore Picture=0,0,16,28.
- ERLV (furnace lever): 20x12 sheet, "Lever" action with 2 phases of
  10x12 at x=0/10 (phase 0 = handle up, phase 1 = handle thrown left).
  ActMap Lever Length=2 Facet=0,0,10,12; DefCore Picture=0,0,10,12.
- ERKY (escape key): 8x4 single-phase sheet (KeyBase shape: bow ring at
  left, shaft + chunky end right). No ActMap; DefCore Picture=0,0,8,4.

The committed Graphics.png must byte-match this script's output
(verify with --check). Stdlib only. Python 3.10+. Tabs.
"""

import argparse
import os

import clonkgfx

PALETTE = clonkgfx.Palette({
	"K": (36, 28, 22, 255),    # dark outline / iron (warm dark)
	"S": (120, 112, 100, 255), # stone / steel mid
	"T": (180, 172, 158, 255), # stone / steel highlight
	"I": (78, 74, 82, 255),    # iron bars
	"b": (146, 104, 42, 255),  # brass lever knob
	"k": (82, 58, 18, 255),    # dark gold outline
	"g": (198, 152, 58, 255),  # gold mid
	"G": (248, 216, 126, 255), # gold bright
})

# -- EGAT: closed portcullis (16x28) -----------------------------------
GATE_CLOSED = (
	"KKKKKKKKKKKKKKKK",
	"KTTTTTTTTTTTTTTK",
	"KSSSSSSSSSSSSSSK",
	"KSKKKKKKKKKKKKSK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KSIIIIIIIIIIIISK",
	"KSTTTTTTTTTTTTSK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KSIIIIIIIIIIIISK",
	"KSTTTTTTTTTTTTSK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KSIIIIIIIIIIIISK",
	"KSTTTTTTTTTTTTSK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KS.TI..TI..TI.SK",
	"KSSSSSSSSSSSSSSK",
	"KKKKKKKKKKKKKKKK",
)

# -- EGAT: open arch frame (16x28) -------------------------------------
GATE_OPEN = (
	"KKKKKKKKKKKKKKKK",
	"KTTTTTTTTTTTTTTK",
	"KSSSSSSSSSSSSSSK",
	"KSTST......TSTSK",
	"KSST........TSSK",
	"KSS..........SSK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KS............SK",
	"KSSSSSSSSSSSSSSK",
	"KKKKKKKKKKKKKKKK",
)

# -- ERLV: lever handle up (10x12) / thrown (10x12) --------------------
LEVER_UP = (
	"....bb....",
	"...bTTb...",
	"....ST....",
	"....ST....",
	"....ST....",
	"....ST....",
	"....ST....",
	"....ST....",
	"KKKKKKKKKK",
	"KSTTTTTTSK",
	"KSSSSSSSSK",
	"KKKKKKKKKK",
)

LEVER_THROW = (
	"..bb......",
	".bTTb.....",
	".b..b.....",
	"..ST......",
	"..ST......",
	"...ST.....",
	"...ST.....",
	"....ST....",
	"KKKKKKKKKK",
	"KSTTTTTTSK",
	"KSSSSSSSSK",
	"KKKKKKKKKK",
)

# -- ERKY: golden key (8x4, bow at left, shaft + chunky end right) -----
ERKY = (
	"kgggkkkk",
	"g..gGggk",
	"g..ggggk",
	"kggkkkkk",
)

def build_gate():
	action = clonkgfx.Action("Gate", [
		clonkgfx.PhaseMap("Gate", GATE_CLOSED),
		clonkgfx.PhaseMap("GateOpen", GATE_OPEN),
	])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(170, 410),
	                    min_phase_diff=80).check(action, PALETTE)
	sheet = clonkgfx.Sheet(32, 28, PALETTE, [action])
	return sheet.png_bytes()

def build_lever():
	action = clonkgfx.Action("Lever", [
		clonkgfx.PhaseMap("LeverUp", LEVER_UP),
		clonkgfx.PhaseMap("LeverThrow", LEVER_THROW),
	])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(30, 80),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(20, 12, PALETTE, [action])
	return sheet.png_bytes()

def build_key():
	action = clonkgfx.Action("Key", [clonkgfx.PhaseMap("Key", ERKY)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(16, 30),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(8, 4, PALETTE, [action])
	return sheet.png_bytes()

BUILDERS = {
	"egat": build_gate,
	"erlv": build_lever,
	"erky": build_key,
}

def out_default(def_name):
	return os.path.join("..", "content", "EscapeRooms.c4f", "Helpers.c4d",
	                    def_name.upper() + ".c4d", "Graphics.png")

def emit(def_name, check):
	output = out_default(def_name)
	png = BUILDERS[def_name]()
	if check:
		with open(output, "rb") as f:
			committed = f.read()
		if committed != png:
			print(f"FAIL: {output} does not match generator output")
			return 1
		print(f"OK: {output} matches generator output")
		return 0
	with open(output, "wb") as f:
		f.write(png)
	print(f"wrote {output} ({len(png)} bytes)")
	return 0

def main():
	ap = argparse.ArgumentParser(description=__doc__)
	ap.add_argument("def_name", nargs="?", choices=list(BUILDERS),
	                help="one of egat/erlv/erky; omit to cover all three")
	ap.add_argument("--check", action="store_true",
	                help="byte-compare output(s) against the existing file(s)")
	args = ap.parse_args()
	if args.def_name:
		return emit(args.def_name, args.check)
	# Bare invocation (no def name): cover all three so a plain
	# `gen_escape_gfx.py --check` is a complete byte gate.
	status = 0
	for name in BUILDERS:
		status |= emit(name, args.check)
	return status

if __name__ == "__main__":
	raise SystemExit(main())
