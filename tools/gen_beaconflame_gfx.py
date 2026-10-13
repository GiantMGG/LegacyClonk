#!/usr/bin/env python3
"""Deterministic BeaconFlame (BFLM) sprite generator (cycle 221,
cove-litbeacon-visual). Single 16x24 frame: a warm drawn flame for the
lit lighthouse lamp top -- the roadmap's "drawn flame sprite at lamp
top" treatment. The engine draws the BFLM from its Idle facet at the
sheet origin; the LHGT sync anchors the object so the flame base sits
on the lamp glass (art row 6 of the 20x40 LHGT facet) and the tip
rises ~18 px clear of the tower silhouette against sky AND the
SetSkyFade-dimmed fog sky (verdict finding 6).

Anchoring (Lighthouse.c4d UpdateBeaconVisual): CreateObject(BFLM, 0,
-14) relative to the tower center; DefCore Offset=-8,-24 puts the
object position at the sprite's bottom-center, so the sprite spans
world y-38..y-14 around the tower -- base on the lamp glass, tip above
the roof cap.

Reads as a chunky Clonk-style flame: deep-orange silhouette edge (E),
orange-gold body (O), white-gold core (W, the lower-center heat), and
a pale warm-halo column pair (H) flanking the widest band. High
contrast against both clear sky and the fog window's dimmed palette.

Palette: <= 6 colors, warm family, matching the lit LHGT facet gold
(255,224,130) and the FxBeacon modulate range. Same input -> same
output bytes (pinned filter-0 / zlib-9 encode); --check is the byte
gate. Output default:
../content/Coastal.c4d/BeaconFlame.c4d/Graphics.png.

Stdlib only. Python 3.10+. Tabs.
"""

import os

import clonkgfx

OUT_DEFAULT = os.path.join("..", "content", "Coastal.c4d",
                           "BeaconFlame.c4d", "Graphics.png")
PALETTE = clonkgfx.Palette({
	"W": (255, 240, 190, 255),    # white-gold core -- hottest inner flame
	"O": (255, 205, 115, 255),    # orange-gold body
	"E": (255, 150, 50, 255),     # deep-orange silhouette edge
	"H": (255, 224, 130, 255),    # warm halo -- matches the lit facet gold
})

# Single 16x24 frame: a teardrop flame, 2 px at the tip (row 0)
# widening to 12 px at the base (rows 14-23); E edge throughout, O
# body, W core from row 9 down, H halo columns flanking the base band.
# 208 opaque px, 4 opaque colors.
_FLAME = (
	".......EE.......",
	".......EE.......",
	"......EOOE......",
	"......EOOE......",
	"......EOOE......",
	".....EOOOOE.....",
	".....EOOOOE.....",
	".....EOOOOE.....",
	"....EEOOOOEE....",
	"....EOOWWOOE....",
	"....EOWWWWOE....",
	"...EEOOWWWOEE...",
	"...EOWWWWWWOE...",
	"...EOWWWWWWOE...",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
	"..HEOWWWWWWOEH..",
)

def make_png():
	idle = clonkgfx.Action("Idle", [
		clonkgfx.PhaseMap("f0", list(_FLAME)),
	])
	invariants = clonkgfx.Invariants(min_opaque_colors=3,
	                                  opaque_window=(160, 260),
	                                  min_phase_diff=8)
	invariants.check(idle, PALETTE)
	return clonkgfx.Sheet(16, 24, PALETTE, [idle]).png_bytes()

def main():
	return clonkgfx.cli_main(__doc__, OUT_DEFAULT, make_png)

if __name__ == "__main__":
	raise SystemExit(main())
