#!/usr/bin/env python3
"""Selftest for tools/clonkgfx.py (cycle 99, spec section 4).

Stdlib unittest battery - seven case groups:
  1. PhaseMap validation (ragged/empty/unknown char).
  2. Sheet packing (facets, band overflow, duplicate names).
  3. Invariants.check (window, color count, phase diff).
  4. Determinism (png_bytes twice).
  5. Decode round-trip via the lint's png_rgba (importlib file-load).
  6. render_variant (swap, determinism, decode, rejects).
  7. cli_main (generate, --check green, corrupt -> FAIL).
"""

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clonkgfx
from clonkgfx import Action, Invariants, Palette, PhaseMap, Sheet


def load_png_rgba():
	spec = importlib.util.spec_from_file_location(
		"lint_placeholder_gfx", os.path.join(HERE, "lint_placeholder_gfx.py"))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod.png_rgba


png_rgba = load_png_rgba()

# Mini maps: 4 cols x 3 rows.
MAP_P0 = [
	"KBK.",
	"BHHB",
	".KK.",
]
MAP_P1 = [
	"KBK.",
	"BHHB",
	"KK..",
]
MAP_FLAT = [
	"BB..",
	"BBBB",
	"..BB",
]
MAP_Q0 = [
	"HHH.",
	".KK.",
	"....",
]


def make_palette():
	return Palette({"K": (0, 0, 0, 255), "B": (255, 0, 0, 255),
	                "H": (0, 255, 0, 255)})


def make_sheet():
	pal = make_palette()
	walk = Action("Walk", [PhaseMap("P0", MAP_P0), PhaseMap("P1", MAP_P1)])
	idle = Action("Idle", [PhaseMap("Q0", MAP_Q0)])
	return Sheet(8, 6, pal, [walk, idle])


class PhaseMapTests(unittest.TestCase):
	def test_ragged_rows_rejected(self):
		with self.assertRaises(SystemExit):
			PhaseMap("bad", ["KBK.", "BHH"])

	def test_empty_map_rejected(self):
		with self.assertRaises(SystemExit):
			PhaseMap("bad", [])

	def test_all_empty_rows_rejected(self):
		with self.assertRaises(SystemExit):
			PhaseMap("bad", ["", "", ""])

	def test_unknown_char_rejected_at_pixels(self):
		pm = PhaseMap("bad", ["ZB..", "....", "...."])
		with self.assertRaises(SystemExit):
			pm.pixels(make_palette())

	def test_dimensions(self):
		pm = PhaseMap("ok", MAP_P0)
		self.assertEqual((pm.width, pm.height), (4, 3))


class SheetPackingTests(unittest.TestCase):
	def test_facets_are_row_bands(self):
		sheet = make_sheet()
		self.assertEqual(sheet.facets(),
		                 {"Walk": (0, 0, 4, 3), "Idle": (0, 3, 4, 3)})

	def test_facet_lookup(self):
		sheet = make_sheet()
		self.assertEqual(sheet.facet("Idle"), (0, 3, 4, 3))
		with self.assertRaises(SystemExit):
			sheet.facet("Nope")

	def test_band_overflow_rejected(self):
		pal = make_palette()
		a = Action("A", [PhaseMap("a0", MAP_P0)])
		b = Action("B", [PhaseMap("b0", MAP_Q0)])
		with self.assertRaises(SystemExit):
			Sheet(8, 5, pal, [a, b])  # second band 3+3 > 5

	def test_horizontal_overflow_rejected(self):
		pal = make_palette()
		a = Action("A", [PhaseMap("a0", MAP_P0), PhaseMap("a1", MAP_P1)])
		with self.assertRaises(SystemExit):
			Sheet(7, 3, pal, [a])  # 2 phases x 4 > 7

	def test_duplicate_action_names_rejected(self):
		pal = make_palette()
		a = Action("A", [PhaseMap("a0", MAP_P0)])
		b = Action("A", [PhaseMap("b0", MAP_Q0)])
		with self.assertRaises(SystemExit):
			Sheet(8, 6, pal, [a, b])

	def test_nonpositive_dims_rejected(self):
		pal = make_palette()
		with self.assertRaises(SystemExit):
			Sheet(0, 6, pal, [])


class InvariantsTests(unittest.TestCase):
	def test_below_window_rejected(self):
		pal = make_palette()
		action = Action("A", [PhaseMap("a0", MAP_P0)])  # 9 opaque px
		inv = Invariants(min_opaque_colors=3, opaque_window=(10, 20),
		                 min_phase_diff=1)
		with self.assertRaises(SystemExit):
			inv.check(action, pal)

	def test_single_color_phase_rejected(self):
		pal = make_palette()
		action = Action("A", [PhaseMap("flat", MAP_FLAT)])  # 1 opaque color
		inv = Invariants(min_opaque_colors=2, opaque_window=(1, 100),
		                 min_phase_diff=1)
		with self.assertRaises(SystemExit):
			inv.check(action, pal)

	def test_phase_diff_below_minimum_rejected(self):
		pal = make_palette()
		action = Action("A", [PhaseMap("a0", MAP_P0),
		                      PhaseMap("a1", MAP_P0)])  # identical phases
		inv = Invariants(min_opaque_colors=3, opaque_window=(1, 100),
		                 min_phase_diff=5)
		with self.assertRaises(SystemExit):
			inv.check(action, pal)

	def test_valid_action_passes(self):
		pal = make_palette()
		action = Action("A", [PhaseMap("a0", MAP_P0),
		                      PhaseMap("a1", MAP_P1)])
		inv = Invariants(min_opaque_colors=3, opaque_window=(9, 9),
		                 min_phase_diff=1)
		inv.check(action, pal)  # no SystemExit


class DeterminismTests(unittest.TestCase):
	def test_png_bytes_deterministic(self):
		sheet = make_sheet()
		self.assertEqual(sheet.png_bytes(), sheet.png_bytes())


class DecodeRoundTripTests(unittest.TestCase):
	def test_decoded_pixels_match_maps(self):
		pal = make_palette()
		sheet = make_sheet()
		width, height, rows = png_rgba(sheet.png_bytes())
		self.assertEqual((width, height), (8, 6))
		for action in sheet.actions:
			fx, fy, fw, fh = sheet.facet(action.name)
			for i, phase in enumerate(action.phases):
				px = phase.pixels(pal)
				for y in range(fh):
					for x in range(fw):
						gx, gy = fx + fw * i + x, fy + y
						expect = px.get((x, y), (0, 0, 0, 0))
						self.assertEqual(rows[gy][gx], expect,
						                 f"{action.name} phase {i} ({gx},{gy})")
		# Outside every band: fully transparent.
		self.assertEqual(rows[0][7], (0, 0, 0, 0))  # right of Walk phase 1
		self.assertEqual(rows[3][7], (0, 0, 0, 0))  # right of Idle band


class RenderVariantTests(unittest.TestCase):
	def test_variant_differs_from_base_and_is_deterministic(self):
		sheet = make_sheet()
		base = sheet.png_bytes()
		v1 = sheet.render_variant({"K": (9, 9, 9, 255)})
		v2 = sheet.render_variant({"K": (9, 9, 9, 255)})
		self.assertEqual(v1, v2)
		self.assertNotEqual(v1, base)

	def test_decoded_variant_shows_swap(self):
		sheet = make_sheet()
		_, _, rows = png_rgba(sheet.render_variant({"K": (9, 9, 9, 255)}))
		self.assertEqual(rows[0][0], (9, 9, 9, 255))  # was K
		self.assertEqual(rows[0][1], (255, 0, 0, 255))  # B unchanged
		self.assertEqual(rows[0][2], (9, 9, 9, 255))  # was K
		self.assertEqual(rows[1][2], (0, 255, 0, 255))  # H unchanged
		self.assertEqual(rows[0][3], (0, 0, 0, 0))  # '.' stays transparent

	def test_unknown_swap_char_rejected(self):
		sheet = make_sheet()
		with self.assertRaises(SystemExit):
			sheet.render_variant({"Z": (1, 1, 1, 255)})

	def test_transparent_swap_char_rejected(self):
		sheet = make_sheet()
		with self.assertRaises(SystemExit):
			sheet.render_variant({".": (1, 1, 1, 255)})


class CliMainTests(unittest.TestCase):
	def test_generate_check_and_corrupt_cycle(self):
		sheet = make_sheet()
		payload = sheet.png_bytes()
		with tempfile.TemporaryDirectory() as tmp:
			out = os.path.join(tmp, "sheet.png")
			argv = sys.argv
			try:
				sys.argv = ["gen", out]
				captured = io.StringIO()
				with redirect_stdout(captured):
					rc = clonkgfx.cli_main("test", out, sheet.png_bytes)
				self.assertEqual(rc, 0)
				self.assertIn(f"wrote {out} ({len(payload)} bytes)",
				              captured.getvalue())
				with open(out, "rb") as f:
					self.assertEqual(f.read(), payload)

				sys.argv = ["chk", out, "--check"]
				captured = io.StringIO()
				with redirect_stdout(captured):
					rc = clonkgfx.cli_main("test", out, sheet.png_bytes)
				self.assertEqual(rc, 0)
				self.assertIn(f"OK: {out} matches generator output",
				              captured.getvalue())

				data = bytearray(payload)
				data[len(data) // 2] ^= 0xFF
				with open(out, "wb") as f:
					f.write(data)
				sys.argv = ["chk", out, "--check"]
				captured = io.StringIO()
				with redirect_stdout(captured):
					rc = clonkgfx.cli_main("test", out, sheet.png_bytes)
				self.assertEqual(rc, 1)
				self.assertIn(f"FAIL: {out} does not match generator output",
				              captured.getvalue())
			finally:
				sys.argv = argv


if __name__ == "__main__":
	unittest.main()
