#!/usr/bin/env python3
"""Deterministic Windmill + Wing sprite generator (cycle 144, art-pipeline-v3).

Pipeline v3: donor-derived raster art via classicart -- decode -> transform
-> pinned encode -> --check byte gate (pure function of the committed donor
bytes; no hand-edited pixels).

Donor provenance (CC BY-NC 4.0 RedWolf Design; Adapt explicitly granted;
the classic packs stay in-tree under content/ with their COPYING files):
- Mill tower: classic WMIL `Objects.c4d/Structures.c4d/Windmill.c4d/
  Graphics.png` (112x94, filters 1/2/4), facet crop (0,0,28,58) at native
  1:1 scale -- 1041 opaque px, identical 28x58 geometry to the loop def.
- Wing rotor: classic WWNG `.../Windmill.c4d/Wing.c4d/Graphics.png`
  (80x80, filters 1/2/4), exact 2:1 alpha-aware box downscale to 40x40,
  tiled 4x. Phases are identical copies on purpose: engine-side rotation
  (`Wind2Turn -> SetRDir`) is the real animator, so strobes against it
  are impossible.

Outputs (ActMaps untouched; only the AGWM DefCore Picture changes):
- Mill sheet 84x116: Idle facet (0,0,28,58) = WMIL tower crop 1:1.
  Grinding band y=58: 3 phases of 28x58 at x=0/28/56 = tower crop +
  code-drawn deltas (lit window glow + flour dust; phase-indexed
  coordinates pinned below). Consecutive phases differ in >= 8 px.
- Wing sheet 160x40: 4 identical 40x40 Turn phases at x=0/40/80/120.
  Donor palette preserved -- no recolor.

Wiring: AGWM DefCore `Picture=0,0,56,116` (OOB against any plausible
sheet) -> `Picture=0,0,28,58`. AGWG DefCore `Picture=0,0,40,40` stays.

Stdlib only. Python 3.10+. Tabs.
"""

import os

import classicart

# --- Donor paths (resolved from this file: tools/ -> LegacyClonk/ -> ws/) --
MILL_DONOR = ("../../content/Objects.c4d/Structures.c4d/Windmill.c4d/Graphics.png",
              "WMIL mill 112x94")
WING_DONOR = ("../../content/Objects.c4d/Structures.c4d/Windmill.c4d/Wing.c4d/Graphics.png",
              "WWNG wing 80x80")

# --- Sheet layout (matches the Agriculture ActMaps 1:1) -------------------
MILL_SIZE = (84, 116)
TOWER_FACET = (0, 0, 28, 58)
GRIND_BAND_Y = 58
TOWER_OPAQUE_PX = 1041          # probe-verified opaque count of (0,0,28,58)
MIN_PHASE_DIFF = 8              # Invariants.min_phase_diff precedent

# --- Code-drawn Grinding deltas (pinned in-sheet coordinates) -------------
# Phase-indexed constants: the window glow sits in the tower's front
# opening; one sparkle pixel walks the window sill per phase; two flour
# puffs drift down-right beside the mill door per phase.
WINDOW_GLOW = (255, 214, 110, 255)
WINDOW_RECT = (11, 18, 3, 5)
WINDOW_SPARK = [(11, 23), (12, 23), (13, 23)]   # per phase 0/1/2
FLOUR_COLOR = (240, 238, 230, 255)
FLOUR_DUST = [                                  # per phase 0/1/2, 2x2 puffs
	[(6, 50), (20, 53)],
	[(7, 51), (21, 54)],
	[(8, 52), (22, 55)],
]


def _donor_grid(rel: str) -> list[list[tuple[int, int, int, int]]]:
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)
	_, _, px = classicart.decode_png(path)
	return px


def _grind_phase(tower, index: int):
	"""One 28x58 Grinding phase: tower crop + phase-indexed deltas."""
	phase = classicart.fill_rect(tower, *WINDOW_RECT, WINDOW_GLOW)
	sx, sy = WINDOW_SPARK[index]
	phase = classicart.fill_rect(phase, sx, sy, 1, 1, WINDOW_GLOW)
	for (dx, dy) in FLOUR_DUST[index]:
		phase = classicart.fill_rect(phase, dx, dy, 2, 2, FLOUR_COLOR)
	return phase


def make_mill_sheet() -> bytes:
	"""84x116 mill sheet: Idle (0,0,28,58) + Grinding band (y=58, 3 phases)."""
	tower = classicart.crop(_donor_grid(MILL_DONOR[0]), 0, 0, 28, 58)
	opaque = sum(1 for row in tower for p in row if p[3] > 0)
	if opaque != TOWER_OPAQUE_PX:
		raise SystemExit(f"tower crop: {opaque} opaque px (expected {TOWER_OPAQUE_PX})")
	canvas = classicart.blank(*MILL_SIZE)
	canvas = classicart.alpha_over(canvas, tower, 0, 0)
	phases = [_grind_phase(tower, i) for i in range(3)]
	for i in range(2):
		diff = sum(1 for y in range(58) for x in range(28)
		           if phases[i][y][x] != phases[i + 1][y][x])
		if diff < MIN_PHASE_DIFF:
			raise SystemExit(
				f"Grinding phases {i}/{i + 1} differ in only {diff} px "
				f"(minimum {MIN_PHASE_DIFF})")
	for i, phase in enumerate(phases):
		canvas = classicart.alpha_over(canvas, phase, i * 28, GRIND_BAND_Y)
	return classicart.encode_png(MILL_SIZE[0], MILL_SIZE[1], canvas)


def make_wing_sheet() -> bytes:
	"""160x40 wing sheet: donor 80x80 -> exact 2:1 alpha-aware downscale -> 4x."""
	rotor = classicart.box_downscale_2x(
		classicart.crop(_donor_grid(WING_DONOR[0]), 0, 0, 80, 80))
	if len(rotor) != 40 or len(rotor[0]) != 40:
		raise SystemExit(f"wing rotor: {len(rotor[0])}x{len(rotor)} (expected 40x40)")
	canvas = classicart.blank(160, 40)
	for i in range(4):
		canvas = classicart.alpha_over(canvas, rotor, i * 40, 0)
	return classicart.encode_png(160, 40, canvas)


def render() -> list[bytes]:
	return [make_mill_sheet(), make_wing_sheet()]


if __name__ == "__main__":
	raise SystemExit(classicart.cli_main(
		"gen_windmill_gfx: deterministic Windmill+Wing donor art "
		"(mill sheet, then wing sheet)", render))
