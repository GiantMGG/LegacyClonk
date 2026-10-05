#!/usr/bin/env python3
"""Deterministic Lighthouse sprite-sheet generator (cycle 196, frontier-mvp
ART-PREREQ "LHGT" -- the last invisible Coastal def: its Graphics.png was a
96-byte fully-transparent placeholder until this cycle). Sheet 64x64: a
single Idle row band at the sheet origin holding two 20x40 phases -- phase
0 the real lighthouse tower with an unlit lantern, phase 1 the IDENTICAL
tower with the lantern glass lit-bright plus beam glints (the thematic
day/night pair, saltpan/cycle-194 Dock pattern).

The engine draws the ActIdle object from the shape rect at the sheet
origin (C4Object::DrawFace: source (0,0,Width,Height) -> the top-left
20x40 region, Windmill/Oyster convention: the Idle facet equals the shape
rect). DefCore width/height/offset stay 20/40/-10,-20 (physical geometry
is gameplay-coupled and untouched); the committed in-game sprite is
exactly the top-left 20x40 region, i.e. phase 0 (unlit -- the FxBeacon
particle sweep supplies the "lit" read in game). The second phase at
(20,0) lets the vision battery (which requires >= 2 phases) probe the
committed art; ActMap Length=1 keeps the game on phase 0.

The 20x40 sprite reads as a striped coastal beacon tower, side view,
Clonk-style chunky pixel art: a dark domed lantern-roof cap (rows 0-3),
the lantern room with dark frames and a dusk-glass panel (rows 4-8), the
gallery balcony -- platform + railing posts (rows 9-10) -- then a
tapered tower body in alternating white/red paint bands with dark edge
columns and a 1-px step at each width transition (the taper), ending in a
dark doorway let into the bottom white plinth band (rows 36-39).

Phase 1 flips every dusk-glass pixel to warm lit glass and sparkles a
few pale glints onto the pane -- 36 px of change, structure identical, so
the pair reads as the same tower (vision Q5 coherence, Dock precedent).

Palette: white paint (W) / red paint (R) / dark metal+shadow (D) / dusk
glass (G) / warm lit glass (L), <= 5 chars. Same input -> same output
bytes (pinned filter-0 / zlib-9 encode); --check is the byte gate.
Output default: ../content/Coastal.c4d/Lighthouse.c4d/Graphics.png.

Stdlib only. Python 3.10+. Tabs.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "Coastal.c4d", "Lighthouse.c4d",
                           "Graphics.png")
PALETTE = clonkgfx.Palette({
	"W": (244, 240, 230, 255),    # white paint -- tower bands / door surround
	"R": (176, 48, 48, 255),      # red paint -- tower bands
	"D": (46, 42, 40, 255),       # dark metal -- roof / frames / shadow edges
	"G": (96, 108, 132, 255),     # dusk glass -- unlit lantern pane
	"L": (255, 224, 130, 255),    # warm lit glass -- beacon lantern
})

# Phase 0: the unlit tower. 20x40 grid, columns 0-19. The lantern-roof
# cap (dark, rows 0-3) steps from 5 to 10 px wide; the lantern room
# (rows 4-8) is a dusk-glass panel (cols 7-12 x6px) inside dark frames
# whose trim spans the eave (cols 5-14), the taller glass panes at
# cols 6-13 (rows 5-7); the gallery below is a platform (cols 3-16,
# row 9) with railing posts (row 10); the tower body tapers in three
# width steps -- narrow band cols 4-15 (rows 11-20), mid band cols 3-16
# (rows 21-30), wide band cols 2-17 (rows 31-37) -- with dark edge
# columns and white/red alternating paint bands, and a flat-topped dark
# doorway (cols 6-11) is let into the bottom white plinth (rows 38-39).
# 508 opaque px, 4 opaque colors.
_P0 = (
	".......DDDDD........",
	"......DDDDDDDD......",
	".....DDDDDDDDDD.....",
	".....DDDDDDDDDD.....",
	".....DDGGGGGGDD.....",
	".....DGGGGGGGGD.....",
	".....DGGGGGGGGD.....",
	".....DGGGGGGGGD.....",
	".....DDGGGGGGDD.....",
	"...DDDDDDDDDDDDDD...",
	"....D.D.D.D.D.D.D...",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDRRRRRRRRRRRRDD..",
	"..DDRRRRRRRRRRRRDD..",
	"..DDWWDDDDDDWWWWDD..",
	"..DDWWDDDDDDWWWWDD..",
)

# Phase 1: the lit beacon -- every dusk-glass pixel in the lantern
# (rows 4-8) flips to warm lit glass L and three pale glint pixels
# sparkle on the pane (row 5 col 8, row 7 cols 7 and 12); the tower is
# byte-identical otherwise. 36 px of change vs phase 0 (>= the 8 px
# invariant minimum), same opaque count, same outline -- the pair reads
# as the same structure day/night.
_P1 = (
	".......DDDDD........",
	"......DDDDDDDD......",
	".....DDDDDDDDDD.....",
	".....DDDDDDDDDD.....",
	".....DDLLLLLLDD.....",
	".....DLLWLLLLLD.....",
	".....DLLLLLLLLD.....",
	".....DLWLLLLWLD.....",
	".....DDLLLLLLDD.....",
	"...DDDDDDDDDDDDDD...",
	"....D.D.D.D.D.D.D...",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DWWWWWWWWWWD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"....DRRRRRRRRRRD....",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDWWWWWWWWWWDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"...DDRRRRRRRRRRDD...",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDWWWWWWWWWWWWDD..",
	"..DDRRRRRRRRRRRRDD..",
	"..DDRRRRRRRRRRRRDD..",
	"..DDWWDDDDDDWWWWDD..",
	"..DDWWDDDDDDWWWWDD..",
)

def make_png():
	idle = clonkgfx.Action("Idle", [
		clonkgfx.PhaseMap("w0", list(_P0)),
		clonkgfx.PhaseMap("w1", list(_P1)),
	])
	# 20x40 maps (800 px max): observed opaque 508 px / 508 px, 4 opaque
	# colors per phase; the two phases differ in exactly 36 px.
	invariants = clonkgfx.Invariants(min_opaque_colors=3,
	                                opaque_window=(160, 560),
	                                min_phase_diff=8)
	invariants.check(idle, PALETTE)
	return clonkgfx.Sheet(64, 64, PALETTE, [idle]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
