#!/usr/bin/env python3
"""Deterministic agriculture sprite-sheet batch generator (cycle 110).

Subcommand-per-def batch generator: gen_agriculture_gfx.py <DefName>
[output] [--check] renders (or byte-gates) that def's Graphics.png
from the transcribed ASCII maps and the shared 15-char Agriculture
shoreline palette. Validate-then-encode: the per-def
clonkgfx.Invariants gate runs before the deterministic PNG encode.

Sheet layouts + expected ActMap/DefCore wiring:
- Lobster: 64x48 sheet. Walk band = 3 phases of 16x12 at y=0
  (phase 0/1 = walk pair at x=0/16, phase 2 = the belly-up Dead
  frame at x=32). Swim/Jump/Turn bands = 2 phases of 16x12 at
  y=12/24/36. ActMap: Walk/Swim/Jump/Turn Length=2, Dead
  Facet=(32,0,16,12). DefCore Picture=(0,0,16,12) unchanged.
- CookedLobster: 32x24 sheet; cooked-curl pose at (0,0,16,12);
  Picture (0,0,32,24) -> (0,0,16,12). Committed PNG is the
  render_variant output (first committed variant sheet).
- DeadLobster: 32x24 sheet; belly-up corpse at (0,0,16,12); Dead
  and Decay share the facet; Picture -> (0,0,16,12). render_variant
  output.
- Pearl: 12x12 sheet; radial white-blue pearl at (0,0,6,6);
  Picture (0,0,12,12) -> (0,0,6,6).
- Oyster: 32x32 sheet; Closed (0,0,16,16), Open (16,0,16,16) with
  pearl glint; Picture (0,0,32,32) -> (0,0,16,16).
- TidalPool: 80x48 sheet; Exposed wet-sand (0,0,40,24), Flooded
  water-shimmer (40,0,40,24); Picture (0,0,80,48) -> (0,0,40,24).
- LobsterTrap: 40x48 sheet; slatted wooden pot (0,0,20,24);
  Picture (0,0,40,48) -> (0,0,20,24).
- Wheat: 64x64 sheet; Seedling (0,0,12,20), Growing (12,0,12,20),
  Ready Len=2 golden sway pair (24,0,12,20)+(36,0,12,20);
  Picture (0,0,24,40) -> (24,0,12,20) (the golden Ready phase).
- AppleTree: 64x64 sheet; one mature 24x40 canopy at (0,0,24,40);
  Picture (0,0,48,80) -> (0,0,24,40) (fixes the verified
  PICTURE_OOB).

The committed Graphics.png must byte-match this script's output
(verify with --check). Stdlib only. Python 3.10+. Tabs.
"""

import argparse
import os

import clonkgfx

PALETTE = clonkgfx.Palette({
	"K": (43, 26, 12, 255),
	"o": (139, 74, 47, 255),
	"d": (94, 46, 26, 255),
	"H": (222, 184, 135, 255),
	"s": (200, 164, 110, 255),
	"B": (176, 128, 80, 255),
	"S": (120, 84, 52, 255),
	"p": (42, 90, 138, 255),
	"u": (88, 140, 190, 255),
	"W": (240, 240, 245, 255),
	"P": (150, 180, 220, 255),
	"G": (222, 196, 90, 255),
	"g": (74, 122, 47, 255),
	"e": (47, 90, 31, 255),
	"r": (188, 32, 32, 255),
})

# render_variant swaps: the cooked/dead lobster sheets are palette
# swaps of the shared LobsterKit posture maps (first committed
# render_variant outputs).
COOKED_SWAP = {
	"o": (196, 60, 32, 255),
	"d": (140, 36, 20, 255),
	"H": (235, 225, 215, 255),
}
DEAD_SWAP = {
	"o": (130, 114, 98, 255),
	"d": (96, 86, 74, 255),
	"H": (186, 172, 152, 255),
}

# --- Map constants ------------------------------------------------------
# Transcribed VERBATIM from scratch/agri_literals.py (21 constants).
# Each is a tuple of equal-length strings; '.' = transparent. The
# Task-3.4 pixel-parity proof enforces byte-equality with the
# probe-validated scratch sheets.
WALK_0 = (
	"..dd.d..........",
	"dododdd.........",
	".oooo..d.....dd.",
	"dooodddddd.dooHH",
	"....oKdooooooood",
	"dooooooodooooood",
	".oo.HHHHHHHHHHH.",
	"d..dd.dd.dd.dd..",
	"..dd..dd.dd.dd..",
	"..dd.dd.dd...dd.",
	".dd..dd.dd...dd.",
	".dd..........dd.",
)

WALK_1 = (
	"..dd.d..........",
	"....ddd......dd.",
	"dodo...d........",
	".ooooddddd.dooHH",
	"dooooKdooooooood",
	"dooooooodooooood",
	".oo.HHHHHHHHHHH.",
	"d..dd.dd.dd.dd..",
	"...dd.dd.dd.dd..",
	"...dd.dd..dd.dd.",
	"...dd.dd..dd.dd.",
	"......dd..dd....",
)

SWIM_0 = (
	"........ddd.....",
	"d......d..d.....",
	"oooo....dd......",
	"oooodddddd.doodd",
	"....oKdooooooood",
	".ooooooodooooood",
	"doo.HHHHHHHHHHHd",
	"...dd.dd.dd.ddHd",
	"...dd.dd.dd.ddHd",
	"...dd.dd.dd.ddHd",
	"................",
	"................",
)

SWIM_1 = (
	"........ddd..dd.",
	"d......d..d.....",
	"oooo....dd.doood",
	"oooodddddd.doood",
	"....oKdooooooood",
	".ooooooodooooood",
	"doo.HHHHHHHHHHH.",
	"...dd.dd.dd.dd..",
	"...dd.dd.dd.dd..",
	"...dd.dd.dd.dd..",
	"................",
	"................",
)

JUMP_0 = (
	"d.dd.d.........d",
	"ooo.ddd.......d.",
	"oooo...d.....d..",
	"....dddddd....H.",
	"....oKdoooooo...",
	"dooooooodoodod.d",
	"doooHHHHHHHHH...",
	"...dd.dd.dd.dd..",
	"..dd..dd.dd..dd.",
	".dd..dd...dd.dd.",
	"dd...dd...dd..dd",
	".....dd...dd....",
)

JUMP_1 = (
	"d.dd.d..........",
	"ooo.ddd.........",
	"oooo...d.....dd.",
	"....dddddd.dooHH",
	"....oKdooooooood",
	"dooooooodooooood",
	"doooHHHHHHHHHHH.",
	"...dd.dd.dd.dd..",
	"...dd.dd.dd.dd..",
	"...dd.dd.dd.dd..",
	"................",
	"................",
)

TURN_0 = (
	"..dd.d..........",
	"dododdd.......dd",
	".oooo..d.....d..",
	"dooodddddd..o.H.",
	"....oKdooooodd..",
	"dooooooodoodo...",
	".oo.HHHHHHHHH...",
	"d..dd.dd.dd.dd..",
	"..dd..dd.dd.dd..",
	"..dd.dd.dd...dd.",
	".dd..dd.dd...dd.",
	".dd..........dd.",
)

TURN_1 = (
	"..dd.d..........",
	"dododdd.........",
	".oooo..d.....dd.",
	"dooodddddd.dooHH",
	"....oKdooooooood",
	"dooooooodooooood",
	".oo.HHHHHHHHHHH.",
	"d..dd.dd.dd.dd..",
	"...dd.dd.dd.dd..",
	"...dd.dd..dd.dd.",
	"...dd.dd..dd.dd.",
	"......dd..dd....",
)

BELLY_UP = (
	".dd..........dd.",
	".dd..dd.dd...dd.",
	"..dd.dd.dd...dd.",
	"..dd..dd.dd.dd..",
	"d..dd.dd.dd.dd..",
	".oo.HHHHHHHHHHH.",
	"dooooooodooooood",
	"....oKdooooooood",
	"dooodddddd.dooHH",
	".oooo..d.....dd.",
	"dododdd.........",
	"..dd.d..........",
)

COOKED_CURL = (
	"d.dd............",
	"ooo.d...........",
	"ood.............",
	"oooddddddd......",
	"d..ooKoooooo.H..",
	"...ooooooododH..",
	"...ooooooooodH..",
	"...HHHHHHHo.dd..",
	"...HdHdHdH.dd...",
	"...HdHdHddd.....",
	"................",
	"................",
)

PEARL = (
	"..PP..",
	".uPPP.",
	"PPWWPP",
	"PPWWPP",
	".PPPu.",
	"..PP..",
)

OYSTER_CLOSED = (
	"................",
	"................",
	".....KKKKKK.....",
	"...KKHHHHHHKK...",
	"..KHHHHHHHHHHK..",
	"..KSSSSSSSSSSK..",
	".KBSSSSSSSSSSBK.",
	".KBSBBSBBSBBSBK.",
	"KBBSBBSBBSBBSBBK",
	"KBBSBBSBBSBBSBBK",
	"KBBSBBSBBSBBSBBK",
	".KBSBBSBBSBBSBK.",
	".KBSBBSBBSBBSBK.",
	"..KSBBSBBSBBSK..",
	"..KSBBSBBSBBSK..",
	"...KKKBBBBKKK...",
)

OYSTER_OPEN = (
	"................",
	"................",
	".......KK.......",
	"......KWWK......",
	"...KKKPWWPKKK...",
	"..KSSSSSSSSSSK..",
	".KBSBBSBBSBBSBK.",
	".KBSBBSBBSBBSBK.",
	"KBBSBBSBBSBBSBBK",
	"KBBSBBSBBSBBSBBK",
	"KBBSBBSBBSBBSBBK",
	".KBSBBSBBSBBSBK.",
	".KBSBBSBBSBBSBK.",
	"..KSBBSBBSBBSK..",
	"..KSBBSBBSBBSK..",
	"...KKKBBBBKKK...",
)

TIDAL_EXPOSED = (
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"ssss................................ssss",
	"BBsSBBBBsBBBBBBsBBBBBBsBBBBBBsBBBBBBSsBB",
	"sssSBBsBBBBBBsBBBBBBsBBBBBBsBBBBBBsBSsss",
	"sssSsBBBBBBsBBBBBBsBBBBBBsBBBBBBsBBBSsss",
	"BBssSBBBBsBBBBBBsBBBBBBsBBBBBBsBBBBSBBss",
	"sssssSBsBBBBBBsBBBBBBsBBBBBBsBBBBBSsssss",
	"ssssssSBBBBBsBBBBBBsBBBBBBsBBBBBBSssssss",
	"BBssBBsSSBsBBBBBBsBBBBBBsBBBBBBSSBssBBss",
	"sssssssssSSppuupppuupppuupppuSSsssssssss",
	"sssssssssssSSSSppuupppuupSSSSsssssssssss",
	"BBssBBssBBssBBsSSSSSSSSSSBssBBssBBssBBss",
	"ssssssssssssssssssssssssssssssssssssssss",
	"ssssssssssssssssssssssssssssssssssssssss",
	"BBssBBssBBssBBssBBssBBssBBssBBssBBssBBss",
	"ssssssssssssssssssssssssssssssssssssssss",
)

TIDAL_FLOODED = (
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	"ssss................................ssss",
	"BBsSppuuppuuppuuppuuppuuppuuppuuppuuSsBB",
	"sssSpuuppuuppuuppuuppuuppuuppuuppuupSsss",
	"sssSuuppuuppuuppuuppuuppuuppuuppuuppSsss",
	"BBssSppppppppppppppppppppppppppppppSBBss",
	"sssssSppppppppppppppppppppppppppppSsssss",
	"ssssssSppppppppppppppppppppppppppSssssss",
	"BBssBBsSSpuuppppuuppppuuppppuupSSBssBBss",
	"sssssssssSSpppuuppppuuppppuupSSsssssssss",
	"sssssssssssSSSSpppuuppppuSSSSsssssssssss",
	"BBssBBssBBssBBsSSSSSSSSSSBssBBssBBssBBss",
	"ssssssssssssssssssssssssssssssssssssssss",
	"ssssssssssssssssssssssssssssssssssssssss",
	"BBssBBssBBssBBssBBssBBssBBssBBssBBssBBss",
	"ssssssssssssssssssssssssssssssssssssssss",
)

TRAP = (
	"....................",
	".......KKKKKK.......",
	".....KKSSSSSSKK.....",
	"....KSSSSSSSSSSKK...",
	"...KBSSBKKBKKBSSBK..",
	"..KSBKKBKKBKKBKSBK..",
	"..KSBKKBKKBKKBKKBSK.",
	"..KKBKKBKKBKKBKKBSK.",
	".KSKBKKBKKBKKBKKBKSK",
	".KSHHHHHHHHHHHHHHHSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSHHHHHHHHHHHHHHHSK",
	".KKKKKKBKKBKKBKKBKSK",
	".KKKKKKBKKBKKBKKBKSK",
	".KKKKKKBKKBKKBKKBKSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSKBKKBKKBKKBKKBKSK",
	".KSSSSSSSSSSSSSSSSSK",
	".KBBBBBBBBBBBBBBBBBK",
)

WHEAT_SEEDLING = (
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	"............",
	".....GG.....",
	".gg..ee..gg.",
	".gg..ee..gg.",
	"..gg.ee.gg..",
	"..gg.ee.gg..",
	"...ggeegg...",
	"...ggeegg...",
)

WHEAT_GROWING = (
	"............",
	"............",
	"............",
	"............",
	".....gg.....",
	".....GG.....",
	".....ee.....",
	".....ee.....",
	".....ee..g..",
	"..g..ee.g...",
	"...g.eeg....",
	"....gee.....",
	".....ee..g..",
	"..g..ee.g...",
	"...g.eeg....",
	"....gee.....",
	".....ee.....",
	".....ee.....",
	".....ee.....",
	".....ee.....",
)

WHEAT_READY_0 = (
	"....eee.....",
	"...GGGGG....",
	"...GGGGG....",
	"...GGGGG....",
	"...GGGGG....",
	"...GGGGG....",
	"...GGGGG....",
	"...GGGGG....",
	".....ee.....",
	"....gee.....",
	".....ee..g..",
	".....ee.g...",
	".....eeg....",
	"..g..ee.....",
	"...g.ee.....",
	"....gee.....",
	".....ee.....",
	".....ee.....",
	".....ee.....",
	".....ee.....",
)

WHEAT_READY_1 = (
	".....eee....",
	"....GGGGG...",
	"....GGGGG...",
	"....GGGGG...",
	"....GGGGG...",
	"....GGGGG...",
	"....GGGGG...",
	"....GGGGG...",
	"......ee....",
	".....gee....",
	"......ee..g.",
	"......ee.g..",
	".....eeg....",
	"..g..ee.....",
	"...g.ee.....",
	"....gee.....",
	".....ee.....",
	".....ee.....",
	".....ee.....",
	".....ee.....",
)

APPLE_TREE = (
	"........................",
	"........................",
	"............K...........",
	".......KKKKKgKKKK.......",
	".....KKeeggggggeeKK.....",
	"....KeggggggggggggeK....",
	"...KeggggggggggrrggeK...",
	"..KegggggggggggrrgggeK..",
	"..KegrrgggggggggggggeK..",
	".KeegrrgggggggggggggeeK.",
	".KeeggggggggggggggggeeK.",
	".KeeggggggggggggggrreeK.",
	".KerrgggggggggggggrrgeK.",
	".KerrggggrrggggggggggeK.",
	".KgggggggrrgggggggggggK.",
	"..KggggggggggggggggggK..",
	"..KggggggeeeeeeggggggK..",
	"...KKeeeeeeeeeeeeeeKK...",
	".....KKeeeeeeeeeeKK.....",
	".......KKKKKKKKKK.......",
	"..........KSSK..........",
	"..........KSSK..........",
	"..........KSSK..........",
	".........KKSSK..........",
	"........KKKSSKK.........",
	".........KKSSK..........",
	"..........KSSK..........",
	".........KKSSK..........",
	"........KKKSSKK.........",
	".........KKSSK..........",
	"..........KSSK..........",
	".........KSSSK..........",
	"........KKSSSKK.........",
	".........KSSSK..........",
	".........KSSSK..........",
	".........KSSSK..........",
	"........KKSSSKK.........",
	".........KSSSSK.........",
	".........KSSSSK.........",
	".........KSSSSK.........",
)

def build_lobster():
	walk = clonkgfx.Action("Walk", [
		clonkgfx.PhaseMap("Walk0", WALK_0),
		clonkgfx.PhaseMap("Walk1", WALK_1),
		clonkgfx.PhaseMap("Dead", BELLY_UP),
	])
	swim = clonkgfx.Action("Swim", [
		clonkgfx.PhaseMap("Swim0", SWIM_0),
		clonkgfx.PhaseMap("Swim1", SWIM_1),
	])
	jump = clonkgfx.Action("Jump", [
		clonkgfx.PhaseMap("Jump0", JUMP_0),
		clonkgfx.PhaseMap("Jump1", JUMP_1),
	])
	turn = clonkgfx.Action("Turn", [
		clonkgfx.PhaseMap("Turn0", TURN_0),
		clonkgfx.PhaseMap("Turn1", TURN_1),
	])
	for action in (walk, swim, jump, turn):
		clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(95, 160),
		                    min_phase_diff=12).check(action, PALETTE)
	sheet = clonkgfx.Sheet(64, 48, PALETTE, [walk, swim, jump, turn])
	return sheet.png_bytes()

def build_cookedlobster():
	action = clonkgfx.Action("Idle", [
		clonkgfx.PhaseMap("CookedCurl", COOKED_CURL)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(80, 150),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(32, 24, PALETTE, [action])
	return sheet.render_variant(COOKED_SWAP)

def build_deadlobster():
	action = clonkgfx.Action("Dead", [
		clonkgfx.PhaseMap("Dead", BELLY_UP)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(80, 150),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(32, 24, PALETTE, [action])
	return sheet.render_variant(DEAD_SWAP)

def build_pearl():
	action = clonkgfx.Action("Idle", [clonkgfx.PhaseMap("Pearl", PEARL)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(18, 36),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(12, 12, PALETTE, [action])
	return sheet.png_bytes()

def build_oyster():
	action = clonkgfx.Action("States", [
		clonkgfx.PhaseMap("Closed", OYSTER_CLOSED),
		clonkgfx.PhaseMap("Open", OYSTER_OPEN),
	])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(90, 220),
	                    min_phase_diff=30).check(action, PALETTE)
	sheet = clonkgfx.Sheet(32, 32, PALETTE, [action])
	return sheet.png_bytes()

def build_tidalpool():
	action = clonkgfx.Action("States", [
		clonkgfx.PhaseMap("Exposed", TIDAL_EXPOSED),
		clonkgfx.PhaseMap("Flooded", TIDAL_FLOODED),
	])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(400, 850),
	                    min_phase_diff=60).check(action, PALETTE)
	sheet = clonkgfx.Sheet(80, 48, PALETTE, [action])
	return sheet.png_bytes()

def build_lobstertrap():
	action = clonkgfx.Action("Idle", [
		clonkgfx.PhaseMap("Trap", TRAP)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(140, 420),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(40, 48, PALETTE, [action])
	return sheet.png_bytes()

def build_wheat():
	action = clonkgfx.Action("Stages", [
		clonkgfx.PhaseMap("Seedling", WHEAT_SEEDLING),
		clonkgfx.PhaseMap("Growing", WHEAT_GROWING),
		clonkgfx.PhaseMap("Ready0", WHEAT_READY_0),
		clonkgfx.PhaseMap("Ready1", WHEAT_READY_1),
	])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(30, 200),
	                    min_phase_diff=15).check(action, PALETTE)
	sheet = clonkgfx.Sheet(64, 64, PALETTE, [action])
	return sheet.png_bytes()

def build_appletree():
	action = clonkgfx.Action("Idle", [
		clonkgfx.PhaseMap("Tree", APPLE_TREE)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(250, 800),
	                    min_phase_diff=8).check(action, PALETTE)
	sheet = clonkgfx.Sheet(64, 64, PALETTE, [action])
	return sheet.png_bytes()

BUILDERS = {
	"Lobster": build_lobster,
	"CookedLobster": build_cookedlobster,
	"DeadLobster": build_deadlobster,
	"Pearl": build_pearl,
	"Oyster": build_oyster,
	"TidalPool": build_tidalpool,
	"LobsterTrap": build_lobstertrap,
	"Wheat": build_wheat,
	"AppleTree": build_appletree,
}

DEF_SUBDIR = {
	"Lobster": "Animals.c4d",
	"CookedLobster": "Items.c4d",
	"DeadLobster": "Items.c4d",
	"Pearl": "Items.c4d",
	"Oyster": "Structures.c4d",
	"TidalPool": "Structures.c4d",
	"LobsterTrap": "Tools.c4d",
	"Wheat": "Vegetation.c4d",
	"AppleTree": "Vegetation.c4d",
}

def out_default(def_name):
	return os.path.join("..", "content", "Agriculture.c4d",
	                    DEF_SUBDIR[def_name], def_name + ".c4d",
	                    "Graphics.png")

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
