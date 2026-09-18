#!/usr/bin/env python3
"""Deterministic Cog sprite generator (cycle 144, art-pipeline-v3).

Pipeline v3: donor-derived raster art via classicart -- decode -> transform
-> pinned encode -> --check byte gate (pure function of the committed donor
bytes; no hand-edited pixels).

Donor provenance (CC BY-NC 4.0 RedWolf Design; Adapt explicitly granted;
the classic pack stays in-tree under content/ with its COPYING):
- Hull: classic SLBT `Objects.c4d/Vehicles.c4d/Sailboat.c4d/Graphics.png`
  (72x108, filters 1/2/3/4), idle-boat hull crop (17,84,30,20) -- 572
  opaque px -- pixel-doubled 2x to 60x40 (integer upscale, crisp, same
  palette).
- Mast/yard/square-sail rig: code-drawn with donor-sampled constants
  (plan-pinned): mast brown (102,71,35), yard brown (91,61,31), canvas
  whites (255,255,255) / shaded (211,211,211).

Output: Cog (CGSH) sheet 64x64; the existing ActMap Sailing facet
(0,0,60,40) is preserved (Delay=20 StartCall=Wind2Sail). DefCore
`Picture=0,0,64,64` stays in-bounds -- no DefCore/ActMap change.

Stdlib only. Python 3.10+. Tabs.
"""

import os

import classicart

# --- Donor (resolved from this file: tools/ -> LegacyClonk/ -> ws/) --------
SLBT_DONOR = ("../../content/Objects.c4d/Vehicles.c4d/Sailboat.c4d/Graphics.png",
              "SLBT sailboat 72x108")

# --- Sheet + recipe (plan-pinned constants) --------------------------------
SHEET_SIZE = (64, 64)
HULL_CROP = (17, 84, 30, 20)      # SLBT idle-boat hull crop
HULL_OPAQUE_PX = 572              # probe-verified opaque count of the crop
MAST_COLOR = (102, 71, 35, 255)   # donor-sampled mast brown
YARD_COLOR = (91, 61, 31, 255)    # donor-sampled yard brown
CANVAS_WHITE = (255, 255, 255, 255)
CANVAS_SHADE = (211, 211, 211, 255)
MAST_RECT = (28, 2, 2, 21)
YARD_RECT = (8, 3, 44, 1)
SAIL_RECT = (10, 4, 40, 17)
SAIL_SHADE_ROWS = (8, 12, 16)     # shaded rows inside the sail rect


def make_cog_sheet() -> bytes:
	donor = classicart.decode_png(
		os.path.join(os.path.dirname(os.path.abspath(__file__)), SLBT_DONOR[0]))[2]
	hull_src = classicart.crop(donor, *HULL_CROP)
	opaque = sum(1 for row in hull_src for p in row if p[3] > 0)
	if opaque != HULL_OPAQUE_PX:
		raise SystemExit(f"hull crop: {opaque} opaque px (expected {HULL_OPAQUE_PX})")
	hull = classicart.pixel_double(hull_src)   # 60x40
	canvas = classicart.blank(*SHEET_SIZE)
	canvas = classicart.alpha_over(canvas, hull, 0, 0)
	canvas = classicart.fill_rect(canvas, *MAST_RECT, MAST_COLOR)
	canvas = classicart.fill_rect(canvas, *YARD_RECT, YARD_COLOR)
	canvas = classicart.fill_rect(canvas, *SAIL_RECT, CANVAS_WHITE)
	for row_y in SAIL_SHADE_ROWS:
		canvas = classicart.fill_rect(canvas, SAIL_RECT[0], row_y,
		                              SAIL_RECT[2], 1, CANVAS_SHADE)
	return classicart.encode_png(SHEET_SIZE[0], SHEET_SIZE[1], canvas)


def render() -> list[bytes]:
	return [make_cog_sheet()]


if __name__ == "__main__":
	raise SystemExit(classicart.cli_main(
		"gen_cog_gfx: deterministic Cog donor art (cog sheet)", render))
