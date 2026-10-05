#!/usr/bin/env python3
"""Deterministic Dock sprite-sheet generator (cycle 194, release blocker
v376: Colony Bay's "working dock" was invisible in-game, its Graphics.png
a 96-byte fully-transparent placeholder). Sheet 64x64: a single Idle row
band at the sheet origin holding two 20x20 phases -- phase 0 the real
dock sprite, phase 1 the same dock with waterline glints (the shimmer
variant; saltpan pattern).

The engine draws the ActIdle object from the shape rect at the sheet
origin (C4Object::DrawFace: source (0,0,Width,Height) -> the top-left
20x20 region, Windmill/Oyster convention: the Idle facet equals the
shape rect). DefCore width/height/offset stay 20/20/-10,-10 (physical
geometry is gameplay-coupled and untouched); the committed in-game
sprite is exactly the top-left 20x20 region, i.e. phase 0. The second
phase at (20,0) lets the vision battery (which requires >= 2 phases)
probe the committed art; ActMap Length=1 keeps the game on phase 0.

The 20x20 sprite reads as a moored-trade pier on a tidal flat, side
view, Clonk-style chunky pixel art: two tall end posts flanking a
3-row plank deck (plank tops + faces + under-deck shadow) with a rope
coil on deck, a mooring ring on the left end post, four pilings
descending into the water (the visible leg count feeds the vision
battery's Q4), and a waterline with wave tips.

Base art faces LEFT (Directions=2 + FlipDir=1 mirrors for DIR_Right);
the dock is near-symmetric. Palette: dark/mid/light wood (K/B/H) +
sea water (S) + pale rope/glint (W), <= 5 chars. Same input -> same
output bytes (pinned filter-0 / zlib-9 encode); --check is the byte
gate. Output default: ../content/Coastal.c4d/Dock.c4d/Graphics.png.

Stdlib only. Python 3.10+. Tabs.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "Coastal.c4d", "Dock.c4d",
                           "Graphics.png")
PALETTE = clonkgfx.Palette({
	"K": (44, 28, 18, 255),      # dark wood -- pilings / deck shadow / seams
	"B": (96, 62, 34, 255),      # mid wood -- deck plank faces
	"H": (150, 104, 58, 255),    # light wood -- plank tops / post caps
	"S": (86, 138, 186, 255),    # sea water accent -- waterline + wave tips
	"W": (238, 232, 210, 255),   # pale rope -- mooring ring / rope coil / glints
})

# Phase 0: the moored-trade pier. 20x20 grid, columns 0-19. The deck
# band (plank tops y7 + faces y8 + under-deck shadow y9) sits just
# below the top third; four pilings descend from the deck shadow into
# the waterline (posts at 1-2 / 6-7 / 11-12 / 16-17, visible y10-y18);
# the two end posts rise above the deck as pier headposts (y3-y6), the
# left one carrying a rope mooring ring (y6), and a rope coil rests on
# the deck (y7-y8, cols 9-10). Sea water tips lap the pilings at the
# base (y17-y19). 184 opaque px, 5 opaque colors.
_P0 = (
	"....................",
	"....................",
	"....................",
	".KK.............KK..",
	".KK.............KK..",
	".KK.............KK..",
	"WKKW............KK..",
	"HHKHHKHHKWWKHHKHHKHH",
	"BBBBBBBBBWWBBBBBBBBB",
	"KKKKKKKKKKKKKKKKKKKK",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	"SKK.S.KK.S.KK.S.KK.S",
	"SKKSS.KK.SSKKSS.KKSS",
	"SSSSSSSSSSSSSSSSSSSS",
)

# Phase 1: waterline shimmer -- nine S pixels along the water rows
# flip to pale W glints (wave crest sparkle); everything else identical
# (>= the 8 px invariant minimum). The dock outline is unchanged so the
# pair reads as the same structure in the vision battery's Q5.
_P1 = (
	"....................",
	"....................",
	"....................",
	".KK.............KK..",
	".KK.............KK..",
	".KK.............KK..",
	"WKKW............KK..",
	"HHKHHKHHKWWKHHKHHKHH",
	"BBBBBBBBBWWBBBBBBBBB",
	"KKKKKKKKKKKKKKKKKKKK",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	".KK...KK...KK...KK..",
	"SKK.W.KK.S.KK.W.KK.S",
	"SKKSS.KK.WSKKWS.KKSS",
	"SSSWSSSWSSSWSSSWSSSW",
)

def make_png():
	idle = clonkgfx.Action("Idle", [
		clonkgfx.PhaseMap("w0", list(_P0)),
		clonkgfx.PhaseMap("w1", list(_P1)),
	])
	# 20x20 maps (400 px max): observed opaque ~184/193 px, 5 opaque
	# colors; the two phases differ in exactly 9 px.
	invariants = clonkgfx.Invariants(min_opaque_colors=3,
	                                opaque_window=(100, 360),
	                                min_phase_diff=8)
	invariants.check(idle, PALETTE)
	return clonkgfx.Sheet(64, 64, PALETTE, [idle]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
