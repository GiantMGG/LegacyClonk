#!/usr/bin/env python3
"""Deterministic camel sprite-sheet generator (cycle 99, first clonkgfx
customer). Multi-action row-band sheet 72x104: Walk (2 phases) in the
band at y=0 with facets at x=0/36, Jump at y=26, Tumble at y=52, Swim
at y=78. Expected ActMap facets: Walk=0,0,36,26 (Length=2);
Jump=0,26,36,26; Tumble=0,52,36,26; Swim=0,78,36,26. Base art faces
LEFT (Directions=2 + FlipDir=1 -> engine mirrors for DIR_Right).
The committed Graphics.png must byte-match this script's output
(verify with --check). Stdlib only.
"""

import os

import clonkgfx

W, H = 72, 104
FW, FH = 36, 26
OUT_DEFAULT = os.path.join("..", "content", "Desert.c4d", "Camel.c4d", "Graphics.png")
PALETTE = clonkgfx.Palette({
	"K": (43, 26, 12, 255),
	"B": (176, 128, 80, 255),
	"H": (222, 184, 135, 255),
	"S": (120, 84, 52, 255),
})

WALK0 = (
	"....................................",
	"....................................",
	"....................................",
	"..KKKKKKK......KKKKKKKK.............",
	".KBBBBBBBK....KHHHHHHHHK............",
	".KHHBBKBBK....KHHHHHHHHK............",
	".KHHBBBBBK....KBBBBBBBBK............",
	".KHHBBBBBKK..KBBBBBBBBBBK...........",
	".KHHBBBBBBBK.KBBBBBBBBBBK...........",
	".KBBBBBBBBBBKKBBBBBBBBBBK...........",
	"..KKKKKKKBBBKBBBBBBBBBBBBKKKKKKK....",
	".........KBBBBSSSSSSSSSSBBBBBBBBKK..",
	".........KBBBBBBBBBBBBBBBBBBBBBBBBK.",
	".........KBBBBBBBBBBBBBBBBBBBBKBBBBK",
	".........KBBBBBBBBBBBBBBBBBBBBKKBBBK",
	".........KBBBBBBBBBBBBBBBBBBBBK.KBBK",
	".........KBBHHHHHHHHHHHHHHHHBBK..KK.",
	"..........KSSSKBBBKKKKKSSSKBBBK.....",
	"..........KSSSKBBBK...KSSSKBBBK.....",
	"..........KSSSKBBBK...KSSSKBBBK.....",
	"..........KSSSKBBBK...KSSSKBBBK.....",
	"..........KSSSKBBBK...KSSSKBBBK.....",
	"..........KSSSKBBBK...KSSSKBBBK.....",
	"..........KSSSKBBBK...KSSSKBBBK.....",
	"..........KKKKKKKKK...KKKKKKKKK.....",
	"...........KKK.KKK.....KKK.KKK......",
)

WALK1 = (
	"....................................",
	"....................................",
	"....................................",
	"..KKKKKKK......KKKKKKKK.............",
	".KBBBBBBBK....KHHHHHHHHK............",
	".KHHBBKBBK....KHHHHHHHHK............",
	".KHHBBBBBK....KBBBBBBBBK............",
	".KHHBBBBBKK..KBBBBBBBBBBK...........",
	".KHHBBBBBBBK.KBBBBBBBBBBK...........",
	".KBBBBBBBBBBKKBBBBBBBBBBK...........",
	"..KKKKKKKBBBKBBBBBBBBBBBBKKKKKKK....",
	".........KBBBBSSSSSSSSSSBBBBBBBBKK..",
	".........KBBBBBBBBBBBBBBBBBBBBBBBBK.",
	".........KBBBBBBBBBBBBBBBBBBBBKBBBBK",
	".........KBBBBBBBBBBBBBBBBBBBBKKBBBK",
	".........KBBBBBBBBBBBBBBBBBBBBK.KBBK",
	".........KBBHHHHHHHHHHHHHHHHBBK..KK.",
	"..........KSSSKBBBKKKKKSSSKBBBK.....",
	"..........KSSSKBBBK...KSSSKBBBK.....",
	"..........KSSSBBBK....KSSSKKBBBK....",
	"..........KSSSBBBK....KSSSKKBBBK....",
	"..........KSSSBBBK....KSSSKKBBBK....",
	"..........KSSBBBK.....KSSSK.KBBBK...",
	"..........KSSBBBK.....KSSSK.KBBBK...",
	"..........KKKKKKK.....KKKKK.KKKKK...",
	"...........KKKKK.......KKK...KKK....",
)

JUMP = (
	"....................................",
	"....................................",
	"....................................",
	"....................................",
	"..............KKKKKKKK..............",
	".............KHHHHHHHHK.............",
	".............KHHHHHHHHK........KKKK.",
	".............KBBBBBBBBK.......KBBBBK",
	"............KBBBBBBBBBBK.....KKBBBBK",
	".KKKKKKK....KBBBBBBBBBBK....KBBBBKK.",
	"KBBBBBBBK...KBBBBBBBBBBK...KKBBBBK..",
	"KHHBBBBBKKKKBBBBBBBBBBBBKKKBBBBKK...",
	"KHHBBKBBBBBBBSSSSSSSSSSBBBBBBBBK....",
	"KHHBBBBBBBBBBBBBBBBBBBBBBBBBBKK.....",
	"KHHBBBBBBBBBBBBBBBBBBBBBBBBBBK......",
	"KBBBBBBBBBBBBBBBBBBBBBBBBBBBBK......",
	".KKKKKKKKBBBBBBBBBBBBBBBBBBBBK......",
	"........KBBHHHHHHHHHHHHHHHHBBK......",
	".........KKSSSBBBKKKKKKSSSBBBK......",
	".........KSSSKBBBK...KSSSKBBBK......",
	".........KSSSBBBK....KSSSBBBK.......",
	".........KSSSBBBK....KSSSBBBK.......",
	"..........KKKKKK......KKKKKK........",
	"....................................",
	"....................................",
	"....................................",
)

TUMBLE = (
	"....................................",
	"....................................",
	"....................................",
	"....................................",
	"................KKK.................",
	".............KKKBBBK..KKK...........",
	"............KSSSBBBK.KSSSKKK........",
	"............KSSSBBBK.KSSSBBBK.......",
	"............KSSSBBBK.KSSSBBBK.......",
	"............KSSSBBBK.KSSSBBBKKKKK...",
	"............KSSSBBBK.KSSSBBBKBBBBK..",
	"............KSSSBBBK.KSSSBBBKBBBBK..",
	"............KSSSBBBK.KSSBBBBBBKBBBK.",
	"..........KKKKKKKKKKKBBBBBBBBBBBBBK.",
	"......KKKKHHHHKKKBBBBBBBBBBBBBBKKK..",
	".KKKKKBBBHHHHHHHHBBBBBBBBBBBBBBK....",
	"KBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBK....",
	"KHHBBBBKKBBBBBBBBBBBBBBBBBBBBBK.....",
	"KHHBBKBKBBBBBBBBBBBBBBBBBBBBKK......",
	"KHHBBBBKBSSSSSSBKKKKKKKKKKKK........",
	"KHHBBBBKKKKKKKKK....................",
	"KBBBBBBK............................",
	".KKKKKK.............................",
	"....................................",
	"....................................",
	"....................................",
)

SWIM = (
	"....................................",
	"....................................",
	"....................................",
	"..KKKKKKK...........................",
	".KBBBBBBBK....KKKKKKKK..............",
	".KHHBBKBBK...KHHHHHHHHK.............",
	".KHHBBBBBK...KHHHHHHHHK.............",
	".KHHBBBBBK...KBBBBBBBBK.......KKKK..",
	".KHHBBBBBK...KBBBBBBBBK......KBBBBK.",
	".KBBBBBBBKK.KBBBBBBBBBBK.....KBBBBK.",
	"..KKKKKKBBBKKBBBBBBBBBBK......KKBBBK",
	".......KBBBKKBBBBBBBBBBK.......KBBBK",
	".......KBBBKBBBBBBBBBBBBKKKKKK..KKK.",
	".......KBBBBBSSSSSSSSSSBBBBBBBKKKKK.",
	".......KBBBBBBBBBBBBBBBBBBBBBBBBBBBK",
	".......KBBBBBBBBBBBBBBBBBBBBBBBBBBBK",
	".......KBBBBBBBBBBBBBBBBBBBBBBBBBBBK",
	".......KBBBBBBBBBBBBBBBBBBBBBBSSSSSK",
	".......KBBBBHHHHHHHHHHHHHHHHBBSSSSSK",
	"........KKKKKKKKKKKKKKKKKKKSSSSSSSSK",
	"...........................KKKKKKKK.",
	"....................................",
	"....................................",
	"....................................",
	"....................................",
	"....................................",
)

def make_png():
	walk0 = clonkgfx.PhaseMap("WALK0", WALK0)
	walk1 = clonkgfx.PhaseMap("WALK1", WALK1)
	jump = clonkgfx.PhaseMap("JUMP", JUMP)
	tumble = clonkgfx.PhaseMap("TUMBLE", TUMBLE)
	swim = clonkgfx.PhaseMap("SWIM", SWIM)
	actions = [
		clonkgfx.Action("Walk", [walk0, walk1]),
		clonkgfx.Action("Jump", [jump]),
		clonkgfx.Action("Tumble", [tumble]),
		clonkgfx.Action("Swim", [swim]),
	]
	invariants = clonkgfx.Invariants(opaque_window=(260, 700),
	                                 min_phase_diff=20)
	for action in actions:
		invariants.check(action, PALETTE)
	sheet = clonkgfx.Sheet(W, H, PALETTE, actions)
	return sheet.png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
