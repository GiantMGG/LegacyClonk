#!/usr/bin/env python3
"""Deterministic RTAP (ReactionTap) sprite generator (cycle 128).

Produces the 32x24 Graphics.png for content/ReactionLab.c4f/RTAP.c4d:
a 16x24 metallic standpipe with a valve handwheel. The ActMap's Idle
and Open actions both reference Facet=(0,0,16,24) with Length=1, so the
sheet carries ONE 16x24 frame; the right half (cols 16-31) is
transparent padding. The padding exists so the vision-QA harness can
run its mandated --phases 2 probe on a single-frame def (the
agriculture-batch precedent: Pearl 6x6 on a 12x12 sheet, AppleTree
24x40 on 64x64, all advisory --record-only -- because a Len=1 single
facet structurally cannot produce the Q5 phase pair the harness
requires, vision_qa.py hard-errors on --phases < 2).

Sprite spec (task 9): metallic standpipe + valve wheel; base occupies
the bottom 6 px; pipe riser up the middle; three palette tone chars:
M = light steel, D = steel body, K = shadow.

INTERPRETER CONTRACT (cycle-125 lesson): the --check byte gate is
zlib-interpreter-sensitive (different Python versions produce
different deflate streams for pixel-identical art). Generate and
commit under the same interpreter CTest resolves for PYTHON3
(/usr/bin/python3 on this machine) -- otherwise gfx_check goes RED.

The committed Graphics.png must byte-match this script's output
(verify with --check). Stdlib only. Python 3.10+. Tabs.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "ReactionLab.c4f", "RTAP.c4d",
                           "Graphics.png")
PALETTE = clonkgfx.Palette({
	"M": (168, 178, 188, 255),  # light steel (wheel face / rim highlight)
	"D": (104, 112, 124, 255),  # steel body (pipe, base, wheel rim)
	"K": (48, 55, 64, 255),     # shadow (left edge, under-wheel, contact)
})

# 16x24 standpipe with a valve handwheel. Rows 0-2 empty sky; rows 3-8
# the handwheel (rim + light face + hub); rows 9-17 the pipe riser up
# the middle; rows 18-23 the base (bottom 6 px).
VALVE = (
	"................",
	"................",
	"................",
	"......KKKK......",
	".....KDDDDD.....",
	"....KDDDDDDK....",
	"....KDMDDDMDK...",
	"....KDDDDDDDK...",
	"....KDDDDDDK....",
	".....KDDDKK.....",
	"......KDDK......",
	"......KDDK......",
	".....KDDDD......",
	".....KDMDD......",
	".....KDMDD......",
	".....KDMDD......",
	".....KDMDD......",
	".....KDDDD......",
	"....KDDDDDD.....",
	"...KDDDDDDDD....",
	"...KDMMMMMDD....",
	"...KDMMMMMDD....",
	"...KDDDDDDDD....",
	"...KKKKKKKK.....",
)

def make_png():
	action = clonkgfx.Action("Idle", [
		clonkgfx.PhaseMap("Standpipe", VALVE)])
	# Single 16x24 frame -> ~140 opaque px; window (80,200) + 3 colors.
	clonkgfx.Invariants(min_opaque_colors=3,
	                    opaque_window=(80, 200),
	                    min_phase_diff=8).check(action, PALETTE)
	# 32 wide: right half transparent, the vision-QA --phases 2 probe
	# slot (phase 0 = the valve at 0,0,16,24; phase 1 = blank).
	return clonkgfx.Sheet(32, 24, PALETTE, [action]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
