#!/usr/bin/env python3
"""Deterministic siege-engine sprite-sheet batch generator (cycle 181).

Subcommand-per-def batch generator: gen_siege_gfx.py <Subcommand>
[--check] renders (or byte-gates) that def's Graphics PNG(s) from
the ASCII maps and the per-sheet palettes. Validate-then-encode:
the clonkgfx.Invariants gate runs per action before the deterministic
PNG encode.

Subcommand `gate` (cycle 181 T2) renders the four SiegeGate stage
sheets, canvas 160x74 each:
- Graphics.png: 4-column Open band at y=0 (40x60 each): phase 0 =
  the closed gate, phases 1-3 = the gate sliding up (bottom gap
  reveals the opening). Idle shares facet 0,0,40,60 (phase 0).
  No ActMap edit needed -- the declared Facet=0,0,40,60 per-phase
  grid (Open Length=4) is in-bounds on the wider canvas.
- GraphicsCrack1.png: the same closed/open sequence with light crack
  seams + slight darkening (wood palette ~10% darker).
- GraphicsCrack2.png: same sequence, heavier crack network + stronger
  darkening (~25%).
- GraphicsRuin.png: collapsed-rubble base-graphics sheet (drawn via
  the SetGraphics(...,0,5) base-graphics path while the gate lingers
  destroyed). Column 0 = main rubble; columns 1-3 = debris-settle
  variants.

Crack-visibility constraint: the crack overlays are applied via
SetGraphics(..., 1, 3), i.e. a MODE_Picture overlay that samples the
def Picture rect (0,0,64,64) and min-aspect-zooms it ~40x40 centered
on the 40x60 gate (rows ~10..50 of the gate). The load-bearing crack
seams are therefore painted into rows 14..51 of the sheet (the
upper/middle band that lands on the visible gate).

The four sheets are pairwise distinct; the retire-placeholder hashes
9ab00a2513435ceafca69462121daf02 / 8d672ea6d7c712c84ef3f4399d387207
must never reappear (check_siege_stage_gfx.py, T6).

Cauldron + trebuchet subcommands land in later tasks (T4/T5) and are
deliberately NOT stubbed here; argparse registers only `gate`.

Subcommand `cauldron` (cycle 181 T4) renders the single BoilingOilCauldron
facet as a 40x25 sheet whose phase-0 facet is 20x25 (matches DefCore
Picture=0,0,20,25 and the Idle Facet=0,0,20,25; DefCore geometry
untouched -- clonk-gfx hard rule). The right half is transparent padding
so the vision-QA harness can slice its mandatory --phases 2 probe
in-bounds (RTAP cycle-128 precedent for Length=1 single facets).
One Idle phase: iron lip + rim highlight, dark oil surface lens in the
opening, bulging iron bowl with left highlight / right shade, rounded
bottom and two tripod feet. Byte-identical Graphics.png is written into
BOTH def copies (scenario-local + smoke-local).

Stdlib only. Python 3.10+. Tabs.
"""

import argparse
import os

import clonkgfx

# ---------------------------------------------------------------------------
# palettes
# ---------------------------------------------------------------------------
# d dark wood, w plank body, W plank highlight, m joint/shade,
# i iron body, I iron rivet, c crack, s dust/splinter.

PALETTE_BASE = {
	"d": (56, 37, 20, 255),
	"w": (140, 90, 44, 255),
	"W": (184, 126, 68, 255),
	"m": (98, 63, 31, 255),
	"i": (70, 74, 86, 255),
	"I": (130, 136, 150, 255),
}

# ~10% darkened wood + crack color (Crack1)
PALETTE_CRACK1 = {
	"d": (48, 31, 17, 255),
	"w": (124, 80, 39, 255),
	"W": (162, 111, 60, 255),
	"m": (86, 55, 27, 255),
	"i": (62, 66, 76, 255),
	"I": (116, 121, 133, 255),
	"c": (22, 14, 8, 255),
}

# ~25% darkened wood + deeper crack color (Crack2)
PALETTE_CRACK2 = {
	"d": (40, 26, 14, 255),
	"w": (106, 68, 33, 255),
	"W": (140, 96, 52, 255),
	"m": (74, 47, 23, 255),
	"i": (54, 58, 66, 255),
	"I": (102, 107, 117, 255),
	"c": (18, 11, 6, 255),
}

PALETTE_RUIN = {
	"d": (56, 37, 20, 255),
	"w": (140, 90, 44, 255),
	"W": (184, 126, 68, 255),
	"m": (98, 63, 31, 255),
	"i": (70, 74, 86, 255),
	"I": (130, 136, 150, 255),
	"s": (150, 140, 125, 255),
}

# cauldron: i dark iron bowl, I iron highlight (rim/bulge), o dark oil
# surface, d iron mid-shade (bottom + right-side shadow).
PALETTE_CAULDRON = {
	"i": (70, 74, 86, 255),
	"I": (132, 138, 154, 255),
	"o": (26, 22, 30, 255),
	"d": (44, 46, 56, 255),
}

# ---------------------------------------------------------------------------
# ASCII phase maps (the maps ARE the diff)
# ---------------------------------------------------------------------------

GATE_CLOSED = (
	"dddddddddddddddddddddddddddddddddddddddd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dddddddddddddddddddddddddddddddddddddddd",
	"iiiiiiIiiiiiiiIiiiiiiiIiiiiiiiIiiiiiiiii",
	"iiiiiiiiiIiiiiiiiIiiiiiiiIiiiiiiiIiiiiii",
	"dddddddddddddddddddddddddddddddddddddddd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dddddddddddddddddddddddddddddddddddddddd",
	"iiiiiiIiiiiiiiIiiiiiiiIiiiiiiiIiiiiiiiii",
	"iiiiiiiiiIiiiiiiiIiiiiiiiIiiiiiiiIiiiiii",
	"dddddddddddddddddddddddddddddddddddddddd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dddddddddddddddddddddddddddddddddddddddd",
	"iiiiiiIiiiiiiiIiiiiiiiIiiiiiiiIiiiiiiiii",
	"iiiiiiiiiIiiiiiiiIiiiiiiiIiiiiiiiIiiiiii",
	"dddddddddddddddddddddddddddddddddddddddd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwwmwWwd",
	"dwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWwmwwWd",
	"dmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwwmmwwd",
	"dddddddddddddddddddddddddddddddddddddddd",
)

CRACK_LIGHT = (
	"...............................c........",
	"...............................c........",
	".........................c....c.........",
	".........................c....c.........",
	".........................c...c..........",
	".........................c...c..........",
	".........................c...c..........",
	".............cc..........c..c...........",
	"...............ccc.......c..c...........",
	"..............cc.........c.c............",
	"................ccc......c.c............",
	".........................cc.............",
	".........................cc.............",
	".........................cc.............",
	".........................c..............",
	".........................c..............",
	"........................cc..............",
	"......ccc...............cc..............",
	".........cccc...........cc..............",
	".......................c.c..............",
	".......................c.c..............",
	"......................c..c..............",
	"......................cccc..............",
	".....................cc.................",
	".....................cc.................",
	"....................c.c.................",
	"...................c..c.................",
	"...................c..c.................",
	"..................c...c.................",
	"..................c...c.................",
	".................c......................",
	"................c.......................",
	"................c.......................",
	"...............c........................",
)

CRACK_HEAVY = (
	"................................cc......",
	"................................cc......",
	"...............................cc.......",
	"...............................cc.......",
	"................c.............cc........",
	".................cc...........cc........",
	"...................cc....c...cc.........",
	".....................cc..c...cc.........",
	"....................c..c.c...c..........",
	"....................c...ccc.cc..........",
	"....................c....cccc...........",
	".....................c..cc.ccc..........",
	"....................cc.c.c.c..c.........",
	".............cc.....ccc..c.c............",
	"...............cccc.ccc..ccc............",
	"...................cccc..cc.............",
	"....................ccc..cc.............",
	"....................c.c..c..............",
	"....................c.c.cc..............",
	"......................c.cc..............",
	"....................cccccc..............",
	"....................c.cc................",
	"....................c..c................",
	"....................c.cc................",
	"....................c.cc......c.........",
	"....................cc.c......ccc.......",
	"....................cc.c.....c...cc.....",
	"....................c..c.....c..........",
	"....................c...c...c...........",
	"...................cc...c...c...........",
	"..................c.c...c...c...........",
	"..................c.c......c............",
	".................c..c......c............",
	"................c...c.....c.............",
	"................c...c.....c.............",
	"...............c........................",
	"...............c........................",
	"..............c.........................",
)

RUIN_A = (
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	".dmdm...................................",
	".dmdm...................................",
	".dmdm.............................wWmdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.........................wW....mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.....................wW........mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.................wW............mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.............wW................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.........wW....................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.....wW........................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm..wW...........................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...W...........................mdmd",
	".dmdm.........................W.....mdmd",
	".wwwwww.wwwwww..WWWWWW.WWWWWW..wwwwwwdmd",
	".wwwww.wwwww.wwwww.WWWWW..WWWWW..WWWWWmd",
	".mmmm..wwww.mmmm..Wwww..wwww.wwww.mmmmmd",
	".ww.ww..mm..ww..WW..mm..mmW.WW.ww.mmmdWW",
	".wwwwww..wwwwww..wwwwww..WWWWWW.wwwwww..",
	".ww..ww.ww.wW.mm..WW.ww..ww.ww.mm..mm.mm",
	".mmmmmm.mmmmmm.wwwwww..WWWWWW..mmmWmm...",
	".www.www.www..mmm..www.mmm..www..www.WW.",
	".ww..WW.WW..ww.ww..wwW.mm.ww..mm..mm..WW",
	".mmmmmm.wwwwww.wwwwww..wwwwww..mmmmmm...",
	".wwwww..WWWWW..mmmmm..wwwww.mmmmm.mmmmm.",
	".mmmmW..wwwww..wwwww..wwwww.mmmmm..wwww.",
	".WWWW.mmmm..wwww..wwww..mmmm..WWWW..mmm.",
	".wwwww.mmmmm..wwwww..mmmmm..Wwwww..WWWW.",
	".mmmm.wwww..wwww..wwww.mmmm..WWWW.wwww..",
	".WWWWW..wwwww..wwwww..WWWWW.wwwww.mmmmm.",
	".msmmmm..wwwsww.mmmmmms.mmmmmm..swwwws..",
	"........................................",
)

RUIN_B = (
	"........................................",
	"........................................",
	"........................................",
	"........................................",
	".dmdm...................................",
	".dmdm...................................",
	".dmdm.............................wWmdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.........................wW....mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.....................wW........mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.................wW............mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.............wW................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.........wW....................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm.....wW........................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm..wW...........................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...............................mdmd",
	".dmdm...W...........................mdmd",
	".dmdm.........................W.....mdmd",
	".wwwwww.wwwwww..WWWWWW.WWWWWW..wwwwwwdmd",
	".wwwww.wwwww.wwwww.WWWWW..WWWWW..WWWWWmd",
	".mmmm..wwww.mmmm..Wwww..wwww.wwww.mmmmmd",
	"..ww.ww..mm..ww..WW..mm..mmW.WW.ww.mmmdW",
	"..wwwwww..wwwwww..wwwwww..WWWWWW.wwwwww.",
	"..ww..ww.ww.wW.mm..WW.ww..ww.ww.mm..mm.m",
	"..mmmmmm.mmmmmm.wwwwww..WWWWWW..mmmWmm..",
	"..www.www.www..mmm..www.mmm..www..www.WW",
	"..ww..WW.WW..wddwwWwdwW.mm.ww..mm..mm..W",
	"..mmmmmm.wwwwww.wwwwww..wwwwww..mmmmmm..",
	"..wwwww..WWWWW..mmmmm..wwwww.mmmmm.mmmmm",
	".mmmmW..wwwww..wwwww..wwwww.mmmmm..wwww.",
	".WWWW.mmmm..wwww..wwww..mmmm..WWWW..mmm.",
	".wwwww.mmmmm..wwwww..mmmmm..Wwwww..WWWW.",
	".mmmm.wwww..wwww..wwww.mmmm..WWWW.wwww..",
	".WWWWW..wwwww..wwwww..WWWWW.wwwww.mmmmm.",
	".msmmmm..wwwsww.mmmmmms.mmmmmm..swwwws..",
	"........................................",
)

# 20x25 single-facet cauldron (Idle, Length=1). Rows: headroom, back
# lip, rim highlight, dark oil surface lens, front lip, bulging iron
# bowl (left highlight / right shade), rounded bottom, tripod feet.
CAULDRON = (
	"....................",
	"....................",
	".iiiiiiiiiiiiiiiiii.",
	".iIIIIIIIIIIIIIIIIi.",
	"..IooooooooooooooI..",
	"..IooooooooooooooI..",
	"..dooooooooooooood..",
	"...dooooooooooood...",
	"....dooooooooood....",
	".....iooooooooi.....",
	"......iIIIIIIi......",
	"..iiiiiiiiiiiiiiii..",
	".iIIIIiiiiiiiiiiiii.",
	".iIIIIIiiiiiiiddddi.",
	".iiIIIIIIiiiidddddd.",
	"..iIIIIIIiiidddddi..",
	"...iIIIIIiiddddii...",
	"....iIIIIiidddii....",
	".....iIIIiiiddd.....",
	".....iIIIIidddd.....",
	"....dddddddddddd....",
	".....dddddddddd.....",
	"....iii......iii....",
	"....iii......iii....",
	".....dd......dd.....",
)

# ---------------------------------------------------------------------------
# map helpers (deterministic composition — the open phases slide the gate
# up; crack overlays are stamped onto the gate before the slide)
# ---------------------------------------------------------------------------

def shift_up(rows, n):
	"""Gate slides up n rows: the top stays, the bottom n rows become
	the transparent opening gap."""
	if not (0 <= n < len(rows)):
		raise SystemExit(f"shift_up: bad offset {n}")
	out = list(rows[n:]) + ["." * len(rows[0])] * n
	assert len(out) == len(rows)
	return out

def stamp(base, overlay, oy):
	"""Stamp overlay (rows, '.' = keep) onto base rows at row offset oy."""
	out = [r for r in base]
	for y, orow in enumerate(overlay):
		t = y + oy
		if t >= len(out):
			break
		r = list(out[t])
		for x, ch in enumerate(orow):
			if ch != ".":
				r[x] = ch
		out[t] = "".join(r)
	return out

# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def _action(phases, palette, lo, hi, min_diff, name="Open"):
	action = clonkgfx.Action(name, [
		clonkgfx.PhaseMap(f"phase{i}", p) for i, p in enumerate(phases)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(lo, hi),
	                    min_phase_diff=min_diff).check(action, palette)
	return action

def build_gate_graphic():
	phases = [GATE_CLOSED] + [shift_up(GATE_CLOSED, n) for n in (15, 30, 45)]
	act = _action(phases, clonkgfx.Palette(PALETTE_BASE), 500, 2500, 30)
	return clonkgfx.Sheet(160, 74, clonkgfx.Palette(PALETTE_BASE), [act]).png_bytes()

def _build_crack(overlay, oy, palette):
	closed = stamp(list(GATE_CLOSED), overlay, oy)
	phases = [closed] + [shift_up(closed, n) for n in (15, 30, 45)]
	act = _action(phases, clonkgfx.Palette(palette), 500, 2500, 30)
	return clonkgfx.Sheet(160, 74, clonkgfx.Palette(palette), [act]).png_bytes()

def build_crack1():
	return _build_crack(CRACK_LIGHT, 16, PALETTE_CRACK1)

def build_crack2():
	return _build_crack(CRACK_HEAVY, 14, PALETTE_CRACK2)

def build_ruin():
	phases = [RUIN_A, RUIN_B, shift_up(RUIN_A, 2), shift_up(RUIN_B, 2)]
	act = _action(phases, clonkgfx.Palette(PALETTE_RUIN), 700, 1700, 30)
	return clonkgfx.Sheet(160, 74, clonkgfx.Palette(PALETTE_RUIN), [act]).png_bytes()

def build_cauldron():
	act = clonkgfx.Action("Idle", [clonkgfx.PhaseMap("phase0", CAULDRON)])
	clonkgfx.Invariants(min_opaque_colors=3, opaque_window=(250, 500),
	                    min_phase_diff=1).check(
		act, clonkgfx.Palette(PALETTE_CAULDRON))
	# 40 wide: the right half (cols 20-39) is transparent padding. The
	# facet stays 0,0,20,25 and DefCore geometry is untouched, but the
	# padding lets the vision-QA harness run its mandatory --phases 2
	# probe in-bounds (phase 1 = blank) — the RTAP cycle-128 precedent
	# for Length=1 single-facet defs.
	return clonkgfx.Sheet(40, 25, clonkgfx.Palette(PALETTE_CAULDRON),
	                      [act]).png_bytes()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

GATE_SPEC = (
	("Graphics.png", build_gate_graphic),
	("GraphicsCrack1.png", build_crack1),
	("GraphicsCrack2.png", build_crack2),
	("GraphicsRuin.png", build_ruin),
)

# Content tree resolved from the script location (tools/ is one level
# inside the engine repo, whose parent sibling is the content repo):
# LegacyClonk/tools -> LegacyClonk -> clonk_ws/content. CWD-independent so
# "python3 LegacyClonk/tools/gen_siege_gfx.py gate --check" works from the
# workspace root AND check_siege_stage_gfx.py can spawn it from any dir.
_CONTENT_ROOT = os.path.normpath(os.path.join(
	os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir,
	"content"))

def out_gate(filename):
	return os.path.join(_CONTENT_ROOT, "SiegeEngines.c4d",
	                    "Structures.c4d", "SiegeGate.c4d", filename)

def out_cauldron():
	"""Both BOIL copies keep byte-identical Graphics.png."""
	return [os.path.join(_CONTENT_ROOT, "Knights.c4f", "SiegeOfHighKeep.c4s",
	                     "BoilingOilCauldron.c4d", "Graphics.png"),
	        os.path.join(_CONTENT_ROOT, "SiegeEngines.c4d", "Tests.c4f",
	                     "SiegeSmoke.c4s", "BoilingOilCauldron.c4d",
	                     "Graphics.png")]

def run_gate(check):
	rc = 0
	for filename, builder in GATE_SPEC:
		png = builder()
		path = out_gate(filename)
		if check:
			with open(path, "rb") as f:
				committed = f.read()
			if committed != png:
				print(f"FAIL: {path} does not match generator output")
				rc = 1
				continue
			print(f"OK: {path} matches generator output")
		else:
			with open(path, "wb") as f:
				f.write(png)
			print(f"wrote {path} ({len(png)} bytes)")
	return rc

def run_cauldron(check):
	png = build_cauldron()
	rc = 0
	for path in out_cauldron():
		if check:
			with open(path, "rb") as f:
				committed = f.read()
			if committed != png:
				print(f"FAIL: {path} does not match generator output")
				rc = 1
				continue
			print(f"OK: {path} matches generator output")
		else:
			with open(path, "wb") as f:
				f.write(png)
			print(f"wrote {path} ({len(png)} bytes)")
	return rc

def main():
	ap = argparse.ArgumentParser(description=__doc__)
	sub = ap.add_subparsers(dest="sub")
	p_gate = sub.add_parser("gate", help="SiegeGate 4 stage sheets")
	p_gate.add_argument("--check", action="store_true",
	                    help="byte-gate all four sheets without writing")
	p_cauldron = sub.add_parser("cauldron",
	                            help="BoilingOilCauldron 20x25 single facet")
	p_cauldron.add_argument("--check", action="store_true",
	                        help="byte-gate both def copies without writing")
	args = ap.parse_args()
	if args.sub == "gate":
		return run_gate(args.check)
	if args.sub == "cauldron":
		return run_cauldron(args.check)
	ap.error(f"unknown subcommand {args.sub!r}")

if __name__ == "__main__":
	raise SystemExit(main())
