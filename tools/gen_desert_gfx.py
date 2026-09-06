#!/usr/bin/env python3
"""Deterministic desert sprite-sheet batch generator (cycle 100).

Subcommand-per-def batch generator: gen_desert_gfx.py <DefName>
[output] [--check] renders (or byte-gates) that def's Graphics.png
from the transcribed ASCII maps and the shared 12-char pack
palette. Validate-then-encode: the per-def clonkgfx.Invariants
gate runs before the deterministic PNG encode.

Sheet layouts + expected ActMap/DefCore wiring:
- DatePalm: 60x36 sheet; action "Stages" with 3 phases of 20x36 at
  x=0/20/40. ActMap.txt stages Seedling/Growing/Ready with facets
  (0,0,20,36)/(20,0,20,36)/(40,0,20,36), Length=1, Delay=10,
  Directions=1; DefCore Picture=40,0,20,36 (the Ready stage).
- Date: 8x8 single-phase sheet; Picture=0,0,8,8.
- Oasis: 24x8; Picture=0,0,24,8.
- Quarry: 30x24; Picture=0,0,30,24.
- Quicksand: 20x6; Picture=0,0,20,6.
- SandDrift: 10x10; Picture=0,0,10,10.
- SandstoneBlock: 8x8; Picture=0,0,8,8.

The committed Graphics.png must byte-match this script's output
(verify with --check). Stdlib only. Python 3.10+. Tabs.
"""

import argparse
import os

import clonkgfx

PALETTE = clonkgfx.Palette({
	"K": (43, 26, 12, 255),
	"B": (176, 128, 80, 255),
	"H": (222, 184, 135, 255),
	"S": (120, 84, 52, 255),
	"g": (74, 122, 47, 255),
	"d": (47, 90, 31, 255),
	"o": (139, 74, 47, 255),
	"p": (42, 90, 138, 255),
	"q": (122, 106, 84, 255),
	"s": (200, 164, 110, 255),
	"t": (169, 131, 90, 255),
	"n": (196, 160, 106, 255),
})

SEEDLING = (
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	".......K....K.......",
	"......KdK..KdK......",
	".....KgggKKgggK.....",
	".....KggggggggK.....",
	"......KKKggKKK......",
	"........KSSK........",
	"........KSSK........",
	"........KSSK........",
	"........KSSKKK......",
	".......KBSSBBBK.....",
	"......KBBBBBBBBK....",
	".....KBBBBBBBBBBK...",
	"....KBBBBBBBBBBBBK..",
	"...KBBBBBBBBBBBBBBK.",
	"..KBBBBBBBBBBBBBBBBK",
)

GROWING = (
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"........KKKKK.......",
	".......KggdggK......",
	".......KgdgggK......",
	".......KddgggK......",
	"......KddSSKggK.....",
	"......KdKSKKKgK.....",
	".....KoooSSK.K......",
	".....KooKSSK........",
	".....KooKSSK........",
	"......KKKSKK........",
	"........KSSK........",
	"........KSSSK.......",
	"........KSSSK.......",
	"........KSKSK.......",
	"........KSSSKK......",
	".......KBSSSBBK.....",
	"......KBBSSSBBBK....",
	".....KBBBSKSBBBBK...",
	"....KBBBBBBBBBBBBK..",
	"...KBBBBBBBBBBBBBBK.",
	"..KBBBBBBBBBBBBBBBBK",
	".KBBBBBBBBBBBBBBBBBB",
	"KBBBBBBBBBBBBBBBBBBB",
)

READY = (
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	"....................",
	".......KKKKKKK......",
	"......KgggdgggK.....",
	".....KgggdgggggK....",
	".....KgKddgggKgK....",
	"......KdddSgggK.....",
	"...KKKKddSSKggKK....",
	"..KooodKdSKKgoooK...",
	"..KooKddKSSKKooK....",
	"..KoodKdKSSKKoogK...",
	"...KKdKKKSSSKKKgK...",
	".....KdKKSKSKKgK....",
	".....KdKKSSSKKgK....",
	"......K.KSSSK.K.....",
	"........KSSSK.......",
	"........KSKSK.......",
	"........KSSSK.......",
	"........KSSSK.......",
	"........KSSSK.......",
	"........KSKSK.......",
	".......KSSSSK.......",
	".......KSSSSKK......",
	".......KSSSSBBK.....",
	"......KBSKSKBBBK....",
	".....KBBSSSSBBBBK...",
	"....KBBBSSSSBBBBBK..",
	"...KBBBBBBBBBBBBBBK.",
	"..KBBBBBBBBBBBBBBBBK",
	".KBBBBBBBBBBBBBBBBBB",
)

DATE = (
	"...KK...",
	"..KooK..",
	".KHHooK.",
	"KooooooK",
	"KooooooK",
	".KooooK.",
	"..KooK..",
	"...KK...",
)

OASIS = (
	"........................",
	".sstsstsstsstsstsstssts.",
	"ttpppppppppppppppppppptt",
	".ppppHppppppppppHpppppp.",
	".pppppHppppppppHppppppp.",
	".pppppppppppppppppppppp.",
	".pppppppppppppppppppppp.",
	".pppppppppppppppppppppp.",
)

QUARRY = (
	"..............................",
	"..............................",
	"........KKKKKKKKKKKKK.........",
	".......KHqHqHqHqHqHqHK........",
	".......KqqqqqqqqqqqqqK........",
	".......KqqqqqqqqqqqqqK........",
	".......KqqqqSqqqqqqqqK........",
	".......KqqqqqSqqqqqqqK........",
	".......KqqqqqqSqqqqqqK........",
	"....KKKKqqqqqqqqqqqqqKKKKK....",
	"...KqSHqqHSqHqqHqqHqSHqqHSK...",
	"...KqqqqqqqqqqqqqqqqqqqqqqK...",
	"..KKqqqqqqqqqqqqqqqqqqqqqqKK..",
	".KSKqqqSqqqqSqqqqSqqSqSqqqKSK.",
	"..KKqqqqqqqqqqqqqqqqqSqqqqKK..",
	"...KqqqqqqqqqqqqqqqqqqqqqqK...",
	"...KSqqqqSqqqqSqqqqSqqqqSqK...",
	"...KqqqqqqqqqqqqqqqqqqqqqqK...",
	".KKKqqqqqqqqqqqqqqqqqqqqqqKKK.",
	"KqqqqqSqqqqSqqqqSqqqqSqqqqSqqK",
	"KqqqqqqSqqqqqqqqqqqqqqqqqqqqqK",
	"KqqqqqqqSqqqqqqqqqqqqqqqqqqqqK",
	"KqqSqqqqSqqqqSqqqqSqqqqSqqqqqK",
	"KqqqqqqqqqqqqqqqqqqqqqqqqqqqqK",
)

QUICKSAND = (
	"..BBsBBBsBBBsBBBsB..",
	".ssstsstsssssssssss.",
	"ssssstsstsstsstsssss",
	"sssssstsstsstsstssss",
	"ssssssssssssstsstsss",
	"ssssssssssssssssssss",
)

SANDDRIFT = (
	"..........",
	"..........",
	"...HHHHH..",
	"..Hssttt..",
	"..ssstttt.",
	".ssssstttt",
	".ssssstttt",
	".ssssstttt",
	".ssssssttt",
	".ssssssttt",
)

SANDSTONE = (
	".KKKKKK.",
	"KHHHHHHK",
	"KnnnnnnK",
	"KntntntK",
	"KnnnnnnK",
	"KntntntK",
	"KnnnnnnK",
	".KKKKKK.",
)

def build_datepalm():
	action = clonkgfx.Action("Stages", [
		clonkgfx.PhaseMap("Seedling", SEEDLING),
		clonkgfx.PhaseMap("Growing", GROWING),
		clonkgfx.PhaseMap("Ready", READY),
	])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(70, 430),
	                    min_phase_diff=30).check(action, PALETTE)
	sheet = clonkgfx.Sheet(60, 36, PALETTE, [action])
	return sheet.png_bytes()

def build_date():
	action = clonkgfx.Action("Date", [clonkgfx.PhaseMap("Date", DATE)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(30, 60),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(8, 8, PALETTE, [action])
	return sheet.png_bytes()

def build_oasis():
	action = clonkgfx.Action("Oasis", [clonkgfx.PhaseMap("Oasis", OASIS)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(110, 185),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(24, 8, PALETTE, [action])
	return sheet.png_bytes()

def build_quarry():
	action = clonkgfx.Action("Quarry", [clonkgfx.PhaseMap("Quarry", QUARRY)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(350, 700),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(30, 24, PALETTE, [action])
	return sheet.png_bytes()

def build_quicksand():
	action = clonkgfx.Action("Quicksand",
	                          [clonkgfx.PhaseMap("Quicksand", QUICKSAND)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(60, 118),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(20, 6, PALETTE, [action])
	return sheet.png_bytes()

def build_sanddrift():
	action = clonkgfx.Action("SandDrift",
	                          [clonkgfx.PhaseMap("SandDrift", SANDDRIFT)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(40, 98),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(10, 10, PALETTE, [action])
	return sheet.png_bytes()

def build_sandstoneblock():
	action = clonkgfx.Action("SandstoneBlock",
	                         [clonkgfx.PhaseMap("SandstoneBlock", SANDSTONE)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(30, 62),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(8, 8, PALETTE, [action])
	return sheet.png_bytes()

BUILDERS = {
	"DatePalm": build_datepalm,
	"Date": build_date,
	"Oasis": build_oasis,
	"Quarry": build_quarry,
	"Quicksand": build_quicksand,
	"SandDrift": build_sanddrift,
	"SandstoneBlock": build_sandstoneblock,
}

def out_default(def_name):
	return os.path.join("..", "content", "Desert.c4d",
	                    def_name + ".c4d", "Graphics.png")

def main():
	ap = argparse.ArgumentParser(description=__doc__)
	ap.add_argument("def_name", choices=list(BUILDERS))
	ap.add_argument("output", nargs="?", default=None)
	ap.add_argument("--check", action="store_true",
	                help="byte-compare output against the existing file")
	args = ap.parse_args()
	output = args.output
	if output is None:
		output = out_default(args.def_name)
	png = BUILDERS[args.def_name]()
	if args.check:
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

if __name__ == "__main__":
	raise SystemExit(main())
