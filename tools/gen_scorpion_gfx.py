#!/usr/bin/env python3
"""Deterministic scorpion sprite-sheet generator v3 (cycle 125, spec
scorpion-scale-animation-fix). Sheet 144x70: five 24x14 row bands --
Walk (0,0,6 phases), Turn (0,14), Jump (0,28), Tumble (0,42),
Swim (0,56; 2 phases each). Base art faces LEFT (Directions=2 +
FlipDir=1 mirrors for DIR_Right). The committed Graphics.png must
byte-match this script's output (verify with --check). Stdlib only.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "Desert.c4d", "Scorpion.c4d",
                           "Graphics.png")
PALETTE = clonkgfx.Palette({
	"K": (43, 26, 12, 255),
	"B": (90, 58, 31, 255),
	"H": (133, 90, 48, 255),
	"S": (176, 128, 80, 255),
})

WALK_P0 = (
	"........................",
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KKB...KB.........",
	".KKK..KKK...KKK.........",
)
WALK_P1 = (
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK.KB..KBKB.KB.......",
	".KKK.KB...KKB..KB.......",
	".........KKK..KKK.......",
)
WALK_P2 = (
	"........................",
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KBKB..KKB........",
	".KKK..KKK...KKK.........",
)
WALK_P3 = (
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KB.KB.KBKB.......",
	".KKK..KB..KBKB.KB.......",
	".........KKK..KKK.......",
)
WALK_P4 = (
	"........................",
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KB.K..KBK........",
	".KKK..KKK...KKK.........",
)
WALK_P5 = (
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KB.KB.KBKB.......",
	".KKK...K..KB.K.KB.......",
	".........KKK..KKK.......",
)

TURN_P0 = (
	"........................",
	"........................",
	"............KKKKKK......",
	"............KSSSSK......",
	"...........KK....KK.....",
	"........KKKKK....KK.....",
	".......KKSS......KK.....",
	".......KKKK......KK.....",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK.KB.KB.KB.KB.......",
	".KKK.KKKKKKKKKKKK.......",
)
TURN_P1 = (
	"........................",
	"............KKKKKK......",
	"............KSSSSK......",
	"...........KK....KK.....",
	"........KKKKK....KK.....",
	".......KKSS......KK.....",
	".......KKKK......KK.....",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKKB......",
	"KBBBK..KB.KB.KB.KB......",
	".KKK...KB.KB.KB.KB......",
	"......KKKKKKKKKKKK......",
)

JUMP_P0 = (
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KB.KB.KBKB.......",
	".KKK..KB.KB.KBKB........",
	"........................",
)
JUMP_P1 = (
	"........................",
	"........................",
	"..........KKKKKK........",
	"..........KSSSSK........",
	".........KK....KK.......",
	"......KKKKK....KK.......",
	".....KKSS......KK.......",
	".....KKKK......KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KB.KB.KBKB.......",
	".KKK....................",
)

TUMBLE_P0 = (
	"........................",
	"....................K...",
	"......K.....KK...K.KKK..",
	".......KB.KB.KB.KB.KK...",
	".....KKKKKKKKKKKK.KK....",
	"KKKK.KBBBBBBBBBBKKK.....",
	"KSSK.KBHHHHHHHHBK.......",
	"K..K.KKKKKKKKKKKK.......",
	"KBBK....................",
	".KK.....................",
	"........................",
	"........................",
	"........................",
	"........................",
)
TUMBLE_P1 = (
	"........................",
	"........................",
	"....................K...",
	"......K.....KK...K.KKK..",
	".......KB.KB.KB.KB.KK...",
	".....KKKKKKKKKKKK.KK....",
	"KKKK.KBBBBBBBBBBKKK.....",
	"KSSK.KBHHHHHHHHBK.......",
	"K..K.KKKKKKKKKKKK.......",
	"KBBK....................",
	".KK.....................",
	"........................",
	"........................",
	"........................",
)

SWIM_P0 = (
	"............KKKKK.......",
	".............KSK........",
	"............KKKKK.......",
	"...............KK.......",
	"...............KK.......",
	"...............KK.......",
	"...............KK.......",
	"...............KK.......",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKKKKKKKKKKK.......",
	"KBBBK..KB.KB.KB.KB......",
	"......KK.KK.KK.KK.......",
)
SWIM_P1 = (
	"............KKKKK.......",
	".............KSK........",
	"............KKKKK.......",
	"...............KK.......",
	"...............KK.......",
	"...............KK.......",
	"...............KK.......",
	"...............KK.......",
	"........................",
	".....KKKKKKKKKKKK.......",
	"KKKKKKHHHHHHHHHBK.......",
	"KSSSKKBBBBBBBBBBK.......",
	"K...KKKBKKBKKBKKB.......",
	"KBBBK..KK.KK.KK.KK......",
)

def make_png():
	walk = clonkgfx.Action("Walk", [
		clonkgfx.PhaseMap("w0", WALK_P0),
		clonkgfx.PhaseMap("w1", WALK_P1),
		clonkgfx.PhaseMap("w2", WALK_P2),
		clonkgfx.PhaseMap("w3", WALK_P3),
		clonkgfx.PhaseMap("w4", WALK_P4),
		clonkgfx.PhaseMap("w5", WALK_P5),
	])
	turn = clonkgfx.Action("Turn", [
		clonkgfx.PhaseMap("t0", TURN_P0),
		clonkgfx.PhaseMap("t1", TURN_P1),
	])
	jump = clonkgfx.Action("Jump", [
		clonkgfx.PhaseMap("j0", JUMP_P0),
		clonkgfx.PhaseMap("j1", JUMP_P1),
	])
	tumble = clonkgfx.Action("Tumble", [
		clonkgfx.PhaseMap("b0", TUMBLE_P0),
		clonkgfx.PhaseMap("b1", TUMBLE_P1),
	])
	swim = clonkgfx.Action("Swim", [
		clonkgfx.PhaseMap("s0", SWIM_P0),
		clonkgfx.PhaseMap("s1", SWIM_P1),
	])
	# v2 used opaque_window=(260,700) for 36x26 maps; (80,280) is the
	# 24x14 rescale (observed per-phase opaque range 86-132).
	invariants = clonkgfx.Invariants(min_opaque_colors=3,
	                                opaque_window=(80, 280),
	                                min_phase_diff=20)
	for action in (walk, turn, jump, tumble, swim):
		invariants.check(action, PALETTE)
	return clonkgfx.Sheet(144, 70, PALETTE,
	                     [walk, turn, jump, tumble, swim]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
