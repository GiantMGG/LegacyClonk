#!/usr/bin/env python3
"""Deterministic scorpion sprite-sheet generator v2 (cycle 105, spec
scorpion-36x26-scaleup). Sheet 72x26: two 36x26 walk phases (Walk at
(0,0,36,26), Length=2). The committed Graphics.png must byte-match
this script's output (verify with --check). Stdlib only.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "Desert.c4d", "Scorpion.c4d", "Graphics.png")
PALETTE = clonkgfx.Palette({
	"K": (43, 26, 12, 255),
	"B": (90, 58, 31, 255),
	"H": (133, 90, 48, 255),
	"S": (176, 128, 80, 255),
})

PHASE0 = (
	".....................KKKK.KKKKK.....",
	"...............KKKKKKSSSSKHBBBK.....",
	"...............KKKKSSSSSSSSBBBK.....",
	"...................KKSSSSKKKKKKKK...",
	".....................KKKK....KBBK...",
	"KKKKKKK......................KBBK...",
	"KKKKBBBK.....................KBBK...",
	"....KBBBK....................KKKK...",
	"....KSBBK....................KBBK...",
	"....KBBBK....................KBBK...",
	"KKKKBBBK...KKK...............KBBK...",
	"KKKKKKK..KKHHHKK...........KKKKKK...",
	".........KBSBBBK..KKKKKKKKKBBBK.....",
	"KKKKKKK..KBSBBBBKKKHHHKHHHKBBBK.....",
	"KKKKBBBK.KKBBBKKBBKBBBKBBBKBBKK.....",
	"....KBBBK..KKK..KBKBBBKBBBKBK.......",
	"....KSBBBKKK...KBBKKKBKBKKKBBK......",
	"....KBBBKBBK...KBK...KBK...KBK......",
	"KKKKBBBK.KBK...KBK...KBK...KBK......",
	"KKKKKKK..KBK...KBK...KBK...KBK......",
	".........KBK...KKK...KBK...KKK......",
	".........KBK.........KBK............",
	".........KBK.........KBK............",
	".........KBK.........KBK............",
	".........KBK.........KBK............",
	".........KKK.........KKK............",
)

PHASE1 = (
	".....................KKKK.KKKKK.....",
	"...............KKKKKKSSSSKHBBBK.....",
	"...............KKKKSSSSSSSSBBBK.....",
	"...................KKSSSSKKKKKKKK...",
	".....................KKKK....KBBK...",
	"KKKKKKK......................KBBK...",
	"KKKKBBBK.....................KBBK...",
	"....KBBBK....................KKKK...",
	"....KSBBK....................KBBK...",
	"....KBBBK....................KBBK...",
	"KKKKBBBK...KKK...............KBBK...",
	"KKKKKKK..KKHHHKK...........KKKKKK...",
	".........KBSBBBK..KKKKKKKKKBBBK.....",
	"KKKKKKK..KBSBBBBKKKHHHKHHHKBBBK.....",
	"KKKKBBBK.KKBBBKKBBKBBBKBBBKBBKK.....",
	"....KBBBK..KKK..KBKBBBKBBBKBK.......",
	"....KSBBBKKK...KBBKKKBKBKKKBBK......",
	"....KBBBKBBK...KBK...KBK...KBK......",
	"KKKKBBBK.KBK...KBK...KBK...KBK......",
	"KKKKKKK..KBK...KBK...KBK...KBK......",
	".........KKK...KBK...KKK...KBK......",
	"...............KBK.........KBK......",
	"...............KBK.........KBK......",
	"...............KBK.........KBK......",
	"...............KBK.........KBK......",
	"...............KKK.........KKK......",
)

def make_png():
	walk = clonkgfx.Action("Walk", [
		clonkgfx.PhaseMap("p0", PHASE0),
		clonkgfx.PhaseMap("p1", PHASE1),
	])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(260, 700),
	                    min_phase_diff=20).check(walk, PALETTE)
	return clonkgfx.Sheet(72, 26, PALETTE, [walk]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
