#!/usr/bin/env python3
"""Deterministic Cog sprite generator (cycle 144/167, art-pipeline-v3).

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

Cycle 167 silhouette rework (judge: "table with a placard", cycle 144):
the doubled crop carries a light-GRAY frame around the wooden band that
made the facet read as a flat slab. The silhouette pass (`_silhouette_fill`)
1) drops that non-wood frame, 2) reshapes the ends into a classic cog
curvature -- an upswept sternpost and a curved bow stem whose sheer line
rises at both ends -- and 3) finishes the band with a donor-toned sheer
rail and a dark keel/waterline. The donor wooden band (cols 10-48) and
its palette are unchanged; every new pixel uses a donor-sampled color.

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

# --- Cog hull silhouette (cycle 167; all colors sampled from the donor) ----
# Classic cog sheer: the hull top edge dips amidships and sweeps up at both
# ends into a high, curved sternpost (left) and stem (right). POST_TOP maps
# facet x to the top row of the hull at that column outside the donor band;
# the amidships band is capped at the sail's lower edge (y=21).
WOOD_RAIL = (152, 110, 69, 255)    # donor raised-end tan -- sheer rail
WOOD_UNDER = (102, 71, 35, 255)    # donor mast/band brown -- under-rail
WOOD_MID = (118, 82, 39, 255)      # donor band mid brown -- hull body
WOOD_MID2 = (126, 88, 43, 255)     # donor band brown -- lower body
WOOD_WATER = (79, 49, 15, 255)     # donor dark brown -- waterline shadow
WOOD_KEEL = (56, 33, 10, 255)      # donor dark brown -- keel row
POST_TOP = {
	# sternpost: rises to y=6 at x=1..2, sheer sweeps down to the band
	0: 9, 1: 7, 2: 6, 3: 7, 4: 8, 5: 9, 6: 12, 7: 15, 8: 18, 9: 20,
	# bow stem: band rises sharply to a projecting tip at x=57 (y=4)
	49: 21, 50: 21, 51: 17, 52: 13, 53: 10, 54: 8, 55: 6, 56: 5, 57: 4,
	58: 5, 59: 8,
}
AMID_CAP = 21  # hull band top edge under the sail (y=21, sail bottom=20)

def _billow(r: int, rows: int) -> int:
	"""Parabolic wind-billow offset for canvas row r of rows.

	Returns rows//2 at mid-sail and 0 at the top/bottom rows (integer
	math only) -- the shade bands bulge outward at mid-height, so the
	canvas reads as wind-filled instead of a flat panel.
	"""
	half = (rows - 1) // 2
	t = r - half
	peak = (t * t) // (rows // 2)
	return (rows // 2) - peak

def _mask_hull(hull: list[list]) -> list[list]:
	"""Drop the donor crop's light-gray frame and anti-aliased ghosts.

	The doubled SLBT crop is a solid 60x40 block: the wooden band sits on a
	light-GRAY surround (the sailboat's white/gray topside) that made the
	facet read as a "table with a placard". Neutral light grays
	(alpha 255, r~=g~=b >= 140) and sub-1-alpha edge ghosts become
	transparent; every wood tone (light tan, brown, dark brown) survives.
	"""
	out = [list(row) for row in hull]
	for y in range(len(out)):
		for x in range(len(out[y])):
			p = out[y][x]
			if p[3] == 0:
				continue
			if p[3] < 255:
				out[y][x] = (0, 0, 0, 0)
				continue
			r, g, b = p[0], p[1], p[2]
			if abs(r - g) < 16 and abs(g - b) < 16 and r >= 140:
				out[y][x] = (0, 0, 0, 0)
	return out

def _silhouette_fill(hull: list[list]) -> list[list]:
	"""Reshape the masked band into the cog hull silhouette.

	- Ends (POST_TOP): solid fill from the designed top edge down to the
	  keel -- posts get a light sheer rail (2px), an under-rail contrast
	  row, a two-tone wood body, a waterline band and a dark keel row.
	- Amidships (cols 10-48): every transparent pixel below the sail's
	  lower edge is closed with WOOD_MID so the band reads solid under the
	  canvas (donor wood pixels are left untouched).
	- Full-width keel: rows 38 (waterline shadow) and 39 (dark keel).
	"""
	out = [list(row) for row in hull]
	for x, top in POST_TOP.items():
		# clear any donor pixels above the designed sheer edge, then build
		# the solid post/stem: rail + under-rail + body + waterline + keel
		for y in range(0, top):
			out[y][x] = (0, 0, 0, 0)
		out[top][x] = WOOD_RAIL
		out[top + 1][x] = WOOD_RAIL
		for y in range(top + 2, 28):
			out[y][x] = WOOD_UNDER if y == top + 2 else WOOD_MID
		for y in range(28, 38):
			out[y][x] = WOOD_MID2
		out[38][x] = WOOD_WATER
		out[39][x] = WOOD_KEEL
	for x in range(10, 49):
		for y in range(AMID_CAP, 40):
			if out[y][x][3] == 0:
				out[y][x] = WOOD_MID
	for x in range(60):
		out[38][x] = WOOD_WATER
		out[39][x] = WOOD_KEEL
	# sheer rail along the amidships band edge (under the sail it peeks
	# from beneath the canvas bottom -- keep continuity with the posts)
	for x in range(10, 49):
		if x in (28, 29):
			continue  # mast column, drawn later
		e = next((y for y in range(AMID_CAP, 40) if out[y][x][3] != 0), None)
		if e is None:
			continue
		out[e][x] = WOOD_RAIL
	return out

def make_cog_sheet() -> bytes:
	donor = classicart.decode_png(
		os.path.join(os.path.dirname(os.path.abspath(__file__)), SLBT_DONOR[0]))[2]
	hull_src = classicart.crop(donor, *HULL_CROP)
	opaque = sum(1 for row in hull_src for p in row if p[3] > 0)
	if opaque != HULL_OPAQUE_PX:
		raise SystemExit(f"hull crop: {opaque} opaque px (expected {HULL_OPAQUE_PX})")
	hull = classicart.pixel_double(hull_src)   # 60x40
	hull = _silhouette_fill(_mask_hull(hull))  # cycle 167: cog sheer/bow+stern
	canvas = classicart.blank(*SHEET_SIZE)
	canvas = classicart.alpha_over(canvas, hull, 0, 0)
	canvas = classicart.fill_rect(canvas, *MAST_RECT, MAST_COLOR)
	canvas = classicart.fill_rect(canvas, *YARD_RECT, YARD_COLOR)
	canvas = classicart.fill_rect(canvas, *SAIL_RECT, CANVAS_WHITE)
	# Billow shading: per-row 2px shade runs whose x offset follows a
	# parabola (deepest near the canvas edges at mid-sail) -- curved
	# fabric folds, not straight shade rows.
	sail_x0 = SAIL_RECT[0]
	sail_x1 = SAIL_RECT[0] + SAIL_RECT[2] - 1
	for r in range(SAIL_RECT[3]):
		q = _billow(r, SAIL_RECT[3])          # 0 top/bottom, peak mid-sail
		canvas = classicart.fill_rect(canvas, sail_x0 + 9 - q,
		                              SAIL_RECT[1] + r, 2, 1, CANVAS_SHADE)
		canvas = classicart.fill_rect(canvas, sail_x1 - 9 + q,
		                              SAIL_RECT[1] + r, 2, 1, CANVAS_SHADE)
	# Mast passes IN FRONT of the canvas (but still under the yard at y=3):
	# a continuous 2px vertical line from the yard down to its bottom.
	canvas = classicart.fill_rect(canvas, MAST_RECT[0], SAIL_RECT[1],
	                              MAST_RECT[2], SAIL_RECT[3], MAST_COLOR)
	return classicart.encode_png(SHEET_SIZE[0], SHEET_SIZE[1], canvas)

def render() -> list[bytes]:
	return [make_cog_sheet()]

if __name__ == "__main__":
	raise SystemExit(classicart.cli_main(
		"gen_cog_gfx: deterministic Cog donor art (cog sheet)", render))
