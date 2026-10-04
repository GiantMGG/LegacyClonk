#!/usr/bin/env python3
"""Deterministic SaltPan sprite-sheet generator (cycle 193, spec
trade-campaign-merge). Sheet 64x64: a single 28x12 row band at the
sheet origin holding a two-phase shimmer action -- phase 0 the plain
wooden evaporation pan, phase 1 the same pan with brine-crystal glints.

The def has no ActMap, so the engine draws the actionless object from
the shape rect at the sheet origin (C4Object::DrawFace: source
(0,0,Width,Height)): the committed in-game sprite is exactly the
top-left 28x12 region, i.e. phase 0. The 64x64 picture (DefCore
Picture=0,0,64,64) carries both phases for the menu icon; the second
phase also lets a vision battery (which requires >= 2 phases) probe the
committed art.

Base art faces LEFT (Directions=2 + FlipDir=1 mirrors for DIR_Right);
the pan is drawn near-symmetric. Palette: wood browns (K/B/H) + brine
white (W) + pale brine (S), <= 5 chars. Same input -> same output
bytes (pinned filter-0 / zlib-9 encode); --check is the byte gate.

Stdlib only. Python 3.10+. Tabs.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "TradeGoods.c4d", "SaltPan.c4d",
                           "Graphics.png")
PALETTE = clonkgfx.Palette({
	"K": (58, 36, 20, 255),     # dark wood -- legs / lip / rim frame
	"B": (96, 62, 34, 255),     # mid wood -- plank faces
	"H": (146, 100, 55, 255),   # light wood -- rim tops
	"S": (196, 196, 188, 255),  # pale brine -- evaporation surface
	"W": (245, 245, 238, 255),  # brine crystal -- crust / glints
})

# Phase 0: the plain pan. A wide, shallow 28x12 evaporation pan: far rim,
# brine surface with a growing crystal crust along the edges, near rim,
# and four support legs (legs at columns 3-4/10-11/17-18/24-25 -- the
# visible leg count feeds the vision battery's Q4). 262 opaque px,
# 5 opaque colors.
_P0 = (
	"..HHHHHHHHHHHHHHHHHHHHHHHH..",   # 0 far rim top (light wood)
	"..KBBBBBBBBBBBBBBBBBBBBBBK..",   # 1 far rim face (planks)
	"..SSSSSSSSSSSSSSSSSSSSSSSS..",   # 2 brine surface
	"..SSSSSSSSSSSSSSSSSSSSSSSS..",   # 3 brine surface
	"..WSSSSSSSSSSSSSSSSSSSSSSW..",   # 4 crust starts at both ends
	".SWWSSSSSSSSSSSSSSSSSSSSWWS.",   # 5 crust band builds inward
	".SWSWSSSSSSSSSSSSSSWWWWSWSW.",   # 6 scattered flakes
	"..SSSSSSSSSSSSSSSSSSSSSSSS..",   # 7 brine surface
	"..KKKKKKKKKKKKKKKKKKKKKKKK..",   # 8 near inner lip (dark)
	".HHHHHHHHHHHHHHHHHHHHHHHHHH.",   # 9 near rim top edge (light)
	"...KK.....KK.....KK.....KK..",   # 10 four support legs
	"...KK.....KK.....KK.....KK..",   # 11 leg feet (shadow)
)

# Phase 1: shimmer -- extra white brine glints scatter across the surface;
# everything else identical. Exactly 14 px differ between the phases
# (>= the 8 px invariant minimum).
_P1 = (
	"..HHHHHHHHHHHHHHHHHHHHHHHH..",
	"..KBBBBBBBBBBBBBBBBBBBBBBK..",
	"..SSWSSSSSWSSSSSSWSSSSSSSS..",   # 2 scattered glints
	"..SSSSSSSWSSSSSSWSSSSSSSSS..",   # 3 more glints
	"..WSSSSSSSSSSSSSSSSSSSSWWW..",   # 4 richer crust at the right end
	".SWWSSSSSSSSSSSSSSSSSWWSSWS.",
	".SWSWWSSSSSSSSWSSSSSWWWSWSW.",   # 6 glint drift
	"..SSSSSSSWSSSSSSSSSSSSSSSS..",
	"..KKKKKKKKKKKKKKKKKKKKKKKK..",
	".HHHHHHHHHHHHHHHHHHHHHHHHHH.",
	"...KK.....KK.....KK.....KK..",
	"...KK.....KK.....KK.....KK..",
)

def make_png():
	shimmer = clonkgfx.Action("Shimmer", [
		clonkgfx.PhaseMap("s0", list(_P0)),
		clonkgfx.PhaseMap("s1", list(_P1)),
	])
	# 28x12 maps: observed opaque range ~260-275 px, 5 opaque colors.
	invariants = clonkgfx.Invariants(min_opaque_colors=3,
	                                opaque_window=(200, 500),
	                                min_phase_diff=8)
	invariants.check(shimmer, PALETTE)
	return clonkgfx.Sheet(64, 64, PALETTE, [shimmer]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
