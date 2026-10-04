#!/usr/bin/env python3
"""Deterministic PirateSloop sprite-sheet generator (cycle 193, spec
trade-campaign-merge). Sheet 64x64: the single Float facet (0,0,60,30),
one phase -- a sloop silhouette facing LEFT: dark hull with upswept
clipper bow and sternpost, a low mast with a war pennant, and one big
triangular mainsail (white canvas, shaded lee edge).

Drives the committed content art at
content/OceanTrade.c4d/PirateSloop.c4d/Graphics.png (float facet
(0,0,60,30), DefCore Picture=0,0,64,64; the sheet top-left 60x30 region
IS the in-game sprite). Replaces the 96-byte transparent placeholder.

Base art faces LEFT (Directions=2 + FlipDir=1 mirrors for DIR_Right).
Palette: dark hull (K) + hull body (B) + sheer rail (H) + sail white
(W) + sail shade (S), <= 5 chars. Same input -> same output bytes
(pinned filter-0 / zlib-9 encode); --check is the byte gate.

Stdlib only. Python 3.10+. Tabs.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "OceanTrade.c4d", "PirateSloop.c4d",
                           "Graphics.png")
PALETTE = clonkgfx.Palette({
	"K": (46, 30, 20, 255),     # dark hull / mast / keel
	"B": (92, 58, 32, 255),     # hull body (plank brown)
	"H": (158, 112, 66, 255),   # sheer rail (light wood)
	"W": (250, 250, 248, 255),  # sail canvas (sunlit)
	"S": (196, 198, 204, 255),  # sail shade (lee edge)
})

# One 60x30 phase at the sheet origin (the ActMap Float facet). The
# sheer line maps each column to the rail row; bow and stern rise clear
# of the 23-deck, so the profile reads as an upswept hull, not a slab.
_P0 = (
	"............................................................",
	"............................................................",
	"............................................................",
	"............................................................",
	"............................................................",
	"........................................KKWWWW..............",
	"........................................KKWWWWW.............",
	"........................................KK..................",
	"........................................KK..................",
	"......................................WWKK..................",
	"....................................WWWWKKS.................",
	"..................................WWWWWWKKWSS...............",
	"................................WWWWWWWWKKWWSS..............",
	"..............................WWWWWWWWWWKKWWWSS.............",
	"............................WWWWWWWWWWWWKKWWWWSS............",
	".........................WWWWWWWWWWWWWWWKKWWWWWWSS..........",
	".......................WWWWWWWWWWWWWWWWWKKWWWWWWWSS.........",
	"....HH...............WWWWWWWWWWWWWWWWWWWKKWWWWWWWWSS....H...",
	"...HBBH............WWWWWWWWWWWWWWWWWWWWWKKWWWWWWWWWSS..HBH..",
	"...BBBBH.........WWWWWWWWWWWWWWWWWWWWWWWKKWWWWWWWWWWWSSBBB..",
	"..HBBBBBH......WWWWWWWWWWWWWWWWWWWWWWWWWKKWWWWWWWWSSSSSSBBH.",
	".HBBBBBBBH...WWWWWWWWWWWWWWWWWWWWWWWWWWWKKWWWWWWWWSSSSSSSBBH",
	"HBBBBBBBBBH.............................KK.........HBBBBBBBB",
	"BBBBBBBBBBBHHHHHHHHHHHHHHHHHHHHHHHHHHHHHKKHHHHHHHHHBBBBBBBBB",
	"BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBKKBBBBBBBBBBBBBBBBBB",
	"BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBKKBBBBBBBBBBBBBBBBBB",
	"BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
	"....KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK....",
	"....KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK....",
	"............................................................",
)

def make_png():
	fl = clonkgfx.Action("Float", [clonkgfx.PhaseMap("s0", list(_P0))])
	# 60x30 maps: observed opaque 737 px, 5 opaque colors (one phase:
	# no phase-diff invariant applies).
	invariants = clonkgfx.Invariants(min_opaque_colors=3,
	                                opaque_window=(300, 1300))
	invariants.check(fl, PALETTE)
	return clonkgfx.Sheet(64, 64, PALETTE, [fl]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
