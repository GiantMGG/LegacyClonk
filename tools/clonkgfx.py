#!/usr/bin/env python3
"""clonkgfx - shared deterministic sprite-sheet library (cycle 99).

Generalizes the proven gen_scorpion_gfx.py pattern to multi-action
row-band sheets: ASCII phase maps -> Palette/PhaseMap/Action/Invariants
-> deterministic stdlib-only PNG encode -> shared --check byte-gate CLI.

Packing convention (Wolf/Fish): actions stack vertically in declared
order, first band at y=0, facet origin x=0; phases advance horizontally
from the facet origin (sx = fx + fw*phase). Base art faces LEFT
(Directions=2 + FlipDir=1 -> the engine mirrors for DIR_Right).

Stdlib only. Python 3.10+. Tabs.
"""

import argparse
import struct
import zlib
from typing import Callable, Mapping, Sequence

RGBA = tuple[int, int, int, int]

class Palette:
	"""Character -> RGBA color map. '.' is reserved for transparency."""

	def __init__(self, colors: Mapping[str, RGBA]) -> None:
		if not colors:
			raise SystemExit("palette: at least one color required")
		for key, value in colors.items():
			if not isinstance(key, str) or len(key) != 1:
				raise SystemExit(f"palette: key {key!r} must be a single char")
			if key == ".":
				raise SystemExit("palette: '.' is reserved for transparency")
			if not isinstance(value, tuple) or len(value) != 4:
				raise SystemExit(f"palette: {key!r} must map to a 4-tuple")
			if any(not isinstance(c, int) or c < 0 or c > 255 for c in value):
				raise SystemExit(f"palette: {key!r} components must be 0..255")
		self.colors: dict[str, RGBA] = dict(colors)

	def __contains__(self, key: str) -> bool:
		return key in self.colors

	def __getitem__(self, key: str) -> RGBA:
		return self.colors[key]

class PhaseMap:
	"""One ASCII phase map. Rows are palette chars; '.' = transparent."""

	def __init__(self, name: str, rows: Sequence[str]) -> None:
		if not rows:
			raise SystemExit(f"{name}: empty phase map")
		width = len(rows[0])
		if width == 0:
			raise SystemExit(f"{name}: empty phase map")
		for row in rows:
			if len(row) != width:
				raise SystemExit(f"{name}: ragged rows (mixed widths)")
		self.name = name
		self.rows = list(rows)

	@property
	def width(self) -> int:
		return len(self.rows[0])

	@property
	def height(self) -> int:
		return len(self.rows)

	def pixels(self, palette: Palette) -> dict[tuple[int, int], RGBA]:
		px: dict[tuple[int, int], RGBA] = {}
		for y, row in enumerate(self.rows):
			for x, ch in enumerate(row):
				if ch == ".":
					px[(x, y)] = (0, 0, 0, 0)
				elif ch in palette:
					px[(x, y)] = palette[ch]
				else:
					raise SystemExit(f"{self.name}: bad char {ch!r}")
		return px

class Action:
	"""One action's row band: >=1 phase, all phases the same size."""

	def __init__(self, name: str, phases: Sequence[PhaseMap]) -> None:
		if not phases:
			raise SystemExit(f"{name}: action needs at least one phase")
		size = (phases[0].width, phases[0].height)
		for phase in phases:
			if (phase.width, phase.height) != size:
				raise SystemExit(f"{name}: mixed phase sizes")
		self.name = name
		self.phases = list(phases)

	@property
	def length(self) -> int:
		return len(self.phases)

	@property
	def facet_size(self) -> tuple[int, int]:
		phase = self.phases[0]
		return (phase.width, phase.height)

class Invariants:
	"""Per-def quality gates. Defaults mirror the scorpion's
	check_invariants (proven values); per-def generators override."""

	def __init__(self, min_opaque_colors: int = 3,
	             opaque_window: tuple[int, int] = (60, 140),
	             min_phase_diff: int = 8) -> None:
		self.min_opaque_colors = min_opaque_colors
		self.opaque_window = opaque_window
		self.min_phase_diff = min_phase_diff

	def check(self, action: Action, palette: Palette) -> None:
		lo, hi = self.opaque_window
		rendered = [phase.pixels(palette) for phase in action.phases]
		for i, px in enumerate(rendered):
			opaque = [v for v in px.values() if v[3] > 0]
			colors = {v for v in px.values() if v[3] > 0}
			if len(colors) < self.min_opaque_colors:
				raise SystemExit(
					f"{action.name} phase {i}: {len(colors)} opaque colors "
					f"< {self.min_opaque_colors}")
			if not lo <= len(opaque) <= hi:
				raise SystemExit(
					f"{action.name} phase {i}: {len(opaque)} opaque px "
					f"outside [{lo},{hi}]")
		for i in range(len(rendered) - 1):
			a, b = rendered[i], rendered[i + 1]
			keys = set(a) | set(b)
			diff = sum(1 for k in keys if a.get(k) != b.get(k))
			if diff < self.min_phase_diff:
				raise SystemExit(
					f"{action.name} phases {i}/{i + 1}: differ in only "
					f"{diff} px (minimum {self.min_phase_diff})")

class Sheet:
	"""Row-band packed sprite sheet plus deterministic PNG encode."""

	def __init__(self, width: int, height: int, palette: Palette,
	             actions: Sequence[Action]) -> None:
		if width <= 0 or height <= 0:
			raise SystemExit("sheet: non-positive dimensions")
		self.width = width
		self.height = height
		self.palette = palette
		self.actions = list(actions)
		self._bands: dict[str, tuple[int, int, int, int]] = {}
		y = 0
		seen: set[str] = set()
		for action in self.actions:
			if action.name in seen:
				raise SystemExit(f"sheet: duplicate action name {action.name!r}")
			seen.add(action.name)
			fw, fh = action.facet_size
			if y + fh > height:
				raise SystemExit(
					f"sheet: band overflow at {action.name!r} "
					f"(y={y} fh={fh} > height={height})")
			if action.length * fw > width:
				raise SystemExit(
					f"sheet: horizontal overflow at {action.name!r} "
					f"({action.length} phases x {fw} > width={width})")
			self._bands[action.name] = (0, y, fw, fh)
			y += fh

	def facet(self, action_name: str) -> tuple[int, int, int, int]:
		if action_name not in self._bands:
			raise SystemExit(f"sheet: unknown action {action_name!r}")
		return self._bands[action_name]

	def facets(self) -> dict[str, tuple[int, int, int, int]]:
		return dict(self._bands)

	def _grid(self, palette: Palette) -> dict[tuple[int, int], RGBA]:
		grid: dict[tuple[int, int], RGBA] = {}
		for action in self.actions:
			fx, fy, fw, fh = self._bands[action.name]
			for i, phase in enumerate(action.phases):
				px = phase.pixels(palette)
				for (x, y), color in px.items():
					grid[(fx + fw * i + x, fy + y)] = color
		return grid

	def _encode(self, grid: Mapping[tuple[int, int], RGBA]) -> bytes:
		raw = bytearray()
		for y in range(self.height):
			raw.append(0)  # filter: none
			for x in range(self.width):
				raw.extend(grid.get((x, y), (0, 0, 0, 0)))

		def chunk(tag: bytes, data: bytes) -> bytes:
			return (struct.pack(">I", len(data)) + tag + data
			        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

		return (b"\x89PNG\r\n\x1a\n"
		        + chunk(b"IHDR",
		                struct.pack(">IIBBBBB", self.width, self.height,
		                            8, 6, 0, 0, 0))
		        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
		        + chunk(b"IEND", b""))

	def png_bytes(self) -> bytes:
		return self._encode(self._grid(self.palette))

	def render_variant(self, swaps: Mapping[str, RGBA]) -> bytes:
		colors = dict(self.palette.colors)
		for key, value in swaps.items():
			if key not in colors:
				raise SystemExit(f"render_variant: {key!r} not in palette")
			colors[key] = value
		return self._encode(self._grid(Palette(colors)))

def cli_main(description: str, out_default: str,
             make_png: Callable[[], bytes]) -> int:
	"""Shared per-def generator CLI (the gen_scorpion_gfx.py main()
	pattern): positional [output] + --check byte gate."""
	ap = argparse.ArgumentParser(description=description)
	ap.add_argument("output", nargs="?", default=out_default)
	ap.add_argument("--check", action="store_true",
	                help="byte-compare output against the existing file")
	args = ap.parse_args()
	png = make_png()
	if args.check:
		with open(args.output, "rb") as f:
			committed = f.read()
		if committed != png:
			print(f"FAIL: {args.output} does not match generator output")
			return 1
		print(f"OK: {args.output} matches generator output")
		return 0
	with open(args.output, "wb") as f:
		f.write(png)
	print(f"wrote {args.output} ({len(png)} bytes)")
	return 0
