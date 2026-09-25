#!/usr/bin/env python3
"""Deterministic KillTarget goal-icon generator (cycle 172).

Renders (or byte-gates, with --check) the 64x64 Graphics.png files of
the KillTarget goal def (KILT) and its hidden crew-death hook def
(KILH) in the ArenaChampions pack:

- KillTarget.c4d/Graphics.png: bold crossed swords on a dark disc --
  a chunky two/three-color goal-bar icon, not a detailed sprite.
- KillHook.c4d/Graphics.png: fully transparent 64x64 (the hook def
  never renders; it only carries #appendto scripts).

Validate-then-encode: the clonkgfx.Invariants gate runs on the 64x64
phase map before the deterministic PNG encode. Art is derived from
simple geometric masks (disc + diagonal blade bands) so it stays
chunky and readable at 64x64 / goal-bar size.

The committed files must byte-match this script's output (verify with
--check). Stdlib only. Python 3.10+. Tabs.
"""

import math
import os

import clonkgfx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Palette: dark disc, warm blade highlight + blade shade (3 opaque colors)
PALETTE = clonkgfx.Palette({
	"k": (38, 32, 30, 255),
	"w": (240, 228, 206, 255),
	"g": (172, 158, 138, 255),
})

SIZE = 64


def _dist_seg(x, y, x0, y0, x1, y1):
	"""Distance of (x, y) to the line segment (x0,y0)-(x1,y1)."""
	dx, dy = x1 - x0, y1 - y0
	length2 = dx * dx + dy * dy
	if not length2:
		return math.hypot(x - x0, y - y0)
	t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / length2))
	px, py = x0 + t * dx, y0 + t * dy
	return math.hypot(x - px, y - py)


def build_killtarget_rows():
	"""64x64: dark disc + a bold X of crossed swords."""
	grid = [["." for _ in range(SIZE)] for _ in range(SIZE)]
	cx, cy, radius = 32, 31, 29
	for y in range(SIZE):
		for x in range(SIZE):
			if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
				grid[y][x] = "k"
	# crossed blades: two thick diagonal bands; outer fringe shaded
	for y in range(SIZE):
		for x in range(SIZE):
			if grid[y][x] != "k":
				continue
			d1 = _dist_seg(x, y, 11, 11, 53, 53)
			d2 = _dist_seg(x, y, 53, 11, 11, 53)
			d = min(d1, d2)
			if d <= 3.0:
				grid[y][x] = "w"
			elif d <= 4.4:
				grid[y][x] = "g"
	return ["".join(row) for row in grid]


def build_hook_rows():
	"""Fully transparent 64x64 map for the never-rendering hook def."""
	return ["." * SIZE for _ in range(SIZE)]


def make_killtarget_png():
	action = clonkgfx.Action("KillTarget",
	                         [clonkgfx.PhaseMap("KillTarget", build_killtarget_rows())])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(1200, 4700),
	                    min_phase_diff=8).check(action, PALETTE)
	return clonkgfx.Sheet(SIZE, SIZE, PALETTE, [action]).png_bytes()


def make_hook_png():
	action = clonkgfx.Action("KillHook",
	                         [clonkgfx.PhaseMap("KillHook", build_hook_rows())])
	return clonkgfx.Sheet(SIZE, SIZE, PALETTE, [action]).png_bytes()


def out_default():
	base = os.path.normpath(os.path.join(
		SCRIPT_DIR, "..", "..", "content", "ArenaChampions.c4f", "Objects.c4d"))
	return {
		"KillTarget": os.path.join(base, "KillTarget.c4d", "Graphics.png"),
		"KillHook": os.path.join(base, "KillTarget.c4d", "KillHook.c4d", "Graphics.png"),
	}


def gate(outputs, make, check=True):
	for name, path in outputs.items():
		with open(path, "rb") as f:
			committed = f.read()
		if committed != make[name]:
			print(f"FAIL: {name} {path} does not match generator output")
			return 1
		print(f"OK: {name} {path} matches generator output")
	return 0


def main():
	import argparse
	ap = argparse.ArgumentParser(description=__doc__)
	ap.add_argument("--check", action="store_true",
	                help="byte-compare the committed Graphics.png files")
	args = ap.parse_args()
	outputs = out_default()
	if args.check:
		return gate(outputs, {
			"KillTarget": make_killtarget_png(),
			"KillHook": make_hook_png(),
		})
	for name, path in outputs.items():
		with open(path, "wb") as f:
			f.write(make_killtarget_png() if name == "KillTarget" else make_hook_png())
		print(f"wrote {name} {path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
