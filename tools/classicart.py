#!/usr/bin/env python3
"""classicart - deterministic donor-derived sprite raster pipeline (cycle 144).

Art-pipeline v3: decode classic Clonk Rage donor PNGs, transform them
with deterministic integer raster ops, and re-encode with a pinned
encoder (filter-0 rows, zlib-9, IHDR/IDAT/IEND only, no ancillary
chunks -- mirrors clonkgfx.Sheet._encode). Every committed output
byte-gates via the per-def generators' --check (this module's
cli_main/check_output), because decode -> transform -> encode is a pure
function of the committed donor bytes.

Ops (all pure -- take a grid, return a new grid; never mutate input):
crop, alpha_over (Porter-Duff-style integer over), hflip, pixel_double
(exact 2x nearest), box_downscale_2x (exact 2:1 alpha-weighted box
downscale: per 2x2 block Sa=sum alpha; Sa==0 -> transparent; else
RGB=(sum rgb*alpha)//Sa per channel, A=Sa//4), fill_rect, recolor
(exact RGBA-key match), blank.

Provenance/licensing: donors are in-tree classic Clonk Rage packs under
content/ (each with its own COPYING), CC BY-NC 4.0 RedWolf Design --
Adapt ("remix, transform, and build upon") is explicitly granted.
Attribution stays with the in-tree COPYING files; per-def generator
docstrings record the donor chain for each output sheet.

Stdlib only. PIL is imported ONLY inside --selftest, as a read-only
cross-validation oracle. Python 3.10+. Tabs.
"""

import argparse
import os
import struct
import zlib

RGBA = tuple[int, int, int, int]

# --------------------------------------------------------------------------
# PNG decode (full filter set: None/Sub/Up/Average/Paeth; RGBA8; non-interlaced)
# --------------------------------------------------------------------------

def _decode(data: bytes) -> tuple[int, int, list[list[RGBA]]]:
	"""Decode a non-interlaced RGBA8 PNG with the full filter set.

	Generalizes .opencode/scratch/144-probe/probe_sheets.py lines 22-65
	(PIL-cross-validated decoder lineage).
	"""
	if data[:8] != b"\x89PNG\r\n\x1a\n":
		raise SystemExit("decode: not a PNG (bad signature)")
	w = h = None
	bitdepth = colortype = interlace = None
	idat = b""
	i = 8
	while i < len(data):
		n = struct.unpack(">I", data[i:i + 4])[0]
		tag = data[i + 4:i + 8]
		payload = data[i + 8:i + 8 + n]
		if tag == b"IHDR":
			(w, h, bitdepth, colortype, _cm, _fm, interlace) = struct.unpack(">IIBBBBB", payload)
		elif tag == b"IDAT":
			idat += payload
		i += 12 + n
	if w is None or h is None:
		raise SystemExit("decode: missing IHDR")
	if bitdepth != 8 or colortype != 6:
		raise SystemExit(f"decode: not RGBA8 (bitdepth={bitdepth}, colortype={colortype})")
	if interlace:
		raise SystemExit("decode: interlaced PNG unsupported")
	raw = zlib.decompress(idat)
	stride = w * 4 + 1
	if len(raw) != stride * h:
		raise SystemExit("decode: truncated IDAT data")
	px: list[list[RGBA]] = []
	prev = bytearray(w * 4)
	for y in range(h):
		row = raw[y * stride:(y + 1) * stride]
		ft = row[0]
		line = bytearray(row[1:])
		if ft == 0:
			pass
		elif ft == 1:  # Sub
			for x in range(4, len(line)):
				line[x] = (line[x] + line[x - 4]) & 0xFF
		elif ft == 2:  # Up
			for x in range(len(line)):
				line[x] = (line[x] + prev[x]) & 0xFF
		elif ft == 3:  # Average
			for x in range(len(line)):
				a = line[x - 4] if x >= 4 else 0
				line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
		elif ft == 4:  # Paeth
			for x in range(len(line)):
				a = line[x - 4] if x >= 4 else 0
				b = prev[x]
				c = prev[x - 4] if x >= 4 else 0
				p = a + b - c
				pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
				pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
				line[x] = (line[x] + pr) & 0xFF
		else:
			raise SystemExit(f"decode: bad filter type {ft} at row {y}")
		prev = line
		px.append([tuple(line[4 * x:4 * x + 4]) for x in range(w)])
	return w, h, px


def decode_png(path: str) -> tuple[int, int, list[list[RGBA]]]:
	"""Decode an RGBA8 PNG file; returns (width, height, pixel grid)."""
	with open(path, "rb") as f:
		return _decode(f.read())


# --------------------------------------------------------------------------
# PNG encode (pinned: filter-0 rows, zlib-9, IHDR/IDAT/IEND only)
# --------------------------------------------------------------------------

def encode_png(w: int, h: int, px: list[list[RGBA]]) -> bytes:
	"""Deterministic RGBA8 PNG encode; mirrors clonkgfx.Sheet._encode."""
	if len(px) != h or any(len(row) != w for row in px):
		raise SystemExit("encode: pixel grid dimensions != (w, h)")
	raw = bytearray()
	for y in range(h):
		raw.append(0)  # filter: none
		for x in range(w):
			raw.extend(px[y][x])

	def chunk(tag: bytes, data: bytes) -> bytes:
		return (struct.pack(">I", len(data)) + tag + data
		        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

	return (b"\x89PNG\r\n\x1a\n"
	        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
	        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
	        + chunk(b"IEND", b""))


# --------------------------------------------------------------------------
# Raster ops (pure: input grids are never mutated)
# --------------------------------------------------------------------------

def blank(w: int, h: int) -> list[list[RGBA]]:
	"""w x h fully-transparent grid."""
	if w <= 0 or h <= 0:
		raise SystemExit("blank: non-positive dimensions")
	return [[(0, 0, 0, 0)] * w for _ in range(h)]


def crop(px: list[list[RGBA]], x: int, y: int, w: int, h: int) -> list[list[RGBA]]:
	if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > len(px[0]) or y + h > len(px):
		raise SystemExit(f"crop: rect ({x},{y},{w},{h}) out of bounds")
	return [row[x:x + w] for row in px[y:y + h]]


def alpha_over(base: list[list[RGBA]], over: list[list[RGBA]],
               dx: int, dy: int) -> list[list[RGBA]]:
	"""Return base with 'over' composited at offset (dx, dy).

	Integer alpha-aware over: fully transparent pixels are skipped,
	fully opaque pixels overwrite, partial alpha blends with the base.
	"""
	out = [list(row) for row in base]
	for oy, orow in enumerate(over):
		by = oy + dy
		if by < 0 or by >= len(out):
			continue
		dst_row = out[by]
		for ox, opx in enumerate(orow):
			bx = ox + dx
			if bx < 0 or bx >= len(dst_row):
				continue
			ar, ag, ab, aa = opx
			if aa == 0:
				continue
			if aa == 255:
				dst_row[bx] = opx
			else:
				br, bg, bb, ba = dst_row[bx]
				inv = 255 - aa
				dst_row[bx] = (
					(ar * aa + br * inv) // 255,
					(ag * aa + bg * inv) // 255,
					(ab * aa + bb * inv) // 255,
					aa + (ba * inv) // 255)
	return out


def hflip(px: list[list[RGBA]]) -> list[list[RGBA]]:
	return [list(reversed(row)) for row in px]


def pixel_double(px: list[list[RGBA]]) -> list[list[RGBA]]:
	"""Exact 2x nearest-neighbour integer upscale; each pixel -> 2x2 block."""
	h, w = len(px), len(px[0])
	out: list[list[RGBA]] = [[(0, 0, 0, 0)] * (2 * w) for _ in range(2 * h)]
	for y, row in enumerate(px):
		for x, p in enumerate(row):
			out[2 * y][2 * x] = p
			out[2 * y][2 * x + 1] = p
			out[2 * y + 1][2 * x] = p
			out[2 * y + 1][2 * x + 1] = p
	return out


def box_downscale_2x(px: list[list[RGBA]]) -> list[list[RGBA]]:
	"""Exact 2:1 alpha-weighted box downscale.

	Per 2x2 block: Sa = sum alpha; Sa == 0 -> (0,0,0,0); else
	RGB = (sum rgb*alpha)//Sa per channel, A = Sa//4.
	"""
	h, w = len(px), len(px[0])
	if w % 2 or h % 2:
		raise SystemExit("box_downscale_2x: odd dimensions")
	out: list[list[RGBA]] = []
	for y in range(0, h, 2):
		row: list[RGBA] = []
		for x in range(0, w, 2):
			block = (px[y][x], px[y][x + 1], px[y + 1][x], px[y + 1][x + 1])
			sa = sum(p[3] for p in block)
			if sa == 0:
				row.append((0, 0, 0, 0))
			else:
				row.append((
					sum(p[0] * p[3] for p in block) // sa,
					sum(p[1] * p[3] for p in block) // sa,
					sum(p[2] * p[3] for p in block) // sa,
					sa // 4))
		out.append(row)
	return out


def fill_rect(px: list[list[RGBA]], x: int, y: int, w: int, h: int,
              color: RGBA) -> list[list[RGBA]]:
	"""Return px with the rect (x, y, w, h) filled with color (clipped)."""
	if w <= 0 or h <= 0:
		raise SystemExit("fill_rect: non-positive size")
	out = [list(row) for row in px]
	for yy in range(y, y + h):
		if yy < 0 or yy >= len(out):
			continue
		dst = out[yy]
		for xx in range(x, x + w):
			if 0 <= xx < len(dst):
				dst[xx] = color
	return out


def recolor(px: list[list[RGBA]], mapping: dict[RGBA, RGBA]) -> list[list[RGBA]]:
	"""Return px with every exact-RGBA-match key replaced by its value."""
	out = [list(row) for row in px]
	for row in out:
		for i, p in enumerate(row):
			if p in mapping:
				row[i] = mapping[p]
	return out


# --------------------------------------------------------------------------
# Byte-gate CLI helpers (clonkgfx.cli_main pattern; N output variant)
# --------------------------------------------------------------------------

def check_output(path: str, png: bytes) -> int:
	"""Byte-compare committed file at path against generator bytes."""
	try:
		with open(path, "rb") as f:
			committed = f.read()
	except OSError as e:
		print(f"FAIL: {path}: {e}")
		return 1
	if committed != png:
		print(f"FAIL: {path} does not match generator output")
		return 1
	print(f"OK: {path} matches generator output")
	return 0


def write_output(path: str, png: bytes) -> None:
	with open(path, "wb") as f:
		f.write(png)
	print(f"wrote {path} ({len(png)} bytes)")


def cli_main(description: str, render) -> int:
	"""Generator byte-gate CLI: positional output path(s) + --check.

	render() must return one bytes per positional output path. With
	--check all outputs are byte-compared (exit 1 on any mismatch);
	without it, outputs are written.
	"""
	ap = argparse.ArgumentParser(description=description)
	ap.add_argument("outputs", metavar="output", nargs="+",
	                help="output PNG path(s), one per render result")
	ap.add_argument("--check", action="store_true",
	                help="byte-compare output(s) against the existing file(s)")
	args = ap.parse_args()
	pngs = render()
	if len(pngs) != len(args.outputs):
		raise SystemExit(
			f"render produced {len(pngs)} PNG(s) for {len(args.outputs)} output path(s)")
	if args.check:
		rc = 0
		for path, png in zip(args.outputs, pngs):
			rc |= check_output(path, png)
		return rc
	for path, png in zip(args.outputs, pngs):
		write_output(path, png)
	return 0


# --------------------------------------------------------------------------
# Selftest: PIL cross-validation on the three donors + determinism + round-trip
# --------------------------------------------------------------------------

DONORS = [
	("Objects.c4d/Structures.c4d/Windmill.c4d/Graphics.png", "WMIL mill 112x94"),
	("Objects.c4d/Structures.c4d/Windmill.c4d/Wing.c4d/Graphics.png", "WWNG wing 80x80"),
	("Objects.c4d/Vehicles.c4d/Sailboat.c4d/Graphics.png", "SLBT sailboat 72x108"),
]


def donor_paths() -> list[str]:
	root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "content"))
	paths = [os.path.join(root, rel) for rel, _ in DONORS]
	for path in paths:
		if not os.path.isfile(path):
			raise SystemExit(f"--selftest: donor missing at {path}")
	return paths


def _check_pil(path: str, w: int, h: int, px: list[list[RGBA]], label: str) -> None:
	try:
		from PIL import Image
	except ImportError:
		raise SystemExit("--selftest: PIL not available (cross-validation oracle required)")
	with Image.open(path) as im:
		im = im.convert("RGBA")
		if im.size != (w, h):
			raise SystemExit(f"--selftest: {label} size mismatch ({im.size} != {w}x{h})")
		pil = im.load()
		for y in range(h):
			for x in range(w):
				if px[y][x] != pil[x, y]:
					raise SystemExit(f"--selftest: {label} pixel mismatch at ({x},{y})")


def _sample_grid() -> list[list[RGBA]]:
	"""Nontrivial 16x12 grid: opaque, semi-transparent, and transparent px."""
	grid = blank(16, 12)
	grid = fill_rect(grid, 0, 0, 16, 12, (120, 80, 50, 255))
	grid = fill_rect(grid, 2, 2, 14, 10, (40, 120, 200, 255))
	grid = fill_rect(grid, 4, 4, 6, 6, (200, 40, 200, 128))
	grid = fill_rect(grid, 8, 8, 8, 4, (255, 255, 255, 128))
	return grid


def _check_determinism() -> None:
	"""Every op applied twice yields identical output (and identical bytes)."""
	src = _sample_grid()
	ops = {
		"crop": lambda p: crop(p, 2, 3, 8, 6),
		"alpha_over": lambda p: alpha_over(p, crop(p, 0, 0, 4, 4), 2, 2),
		"hflip": hflip,
		"pixel_double": pixel_double,
		"box_downscale_2x": lambda p: box_downscale_2x(pixel_double(p)),
		"fill_rect": lambda p: fill_rect(p, 1, 1, 3, 3, (255, 0, 0, 255)),
		"recolor": lambda p: recolor(p, {(120, 80, 50, 255): (30, 30, 90, 255)}),
	}
	for name, op in ops.items():
		a = op(src)
		b = op(src)
		if a != b:
			raise SystemExit(f"--selftest: {name} not deterministic")
		wa, ha = len(a[0]), len(a)
		if encode_png(wa, ha, a) != encode_png(wa, ha, b):
			raise SystemExit(f"--selftest: {name} encode not deterministic")


def _check_roundtrip() -> None:
	"""decode(encode(px)) == px for an alpha-bearing grid."""
	grid = _sample_grid()
	w, h = len(grid[0]), len(grid)
	rw, rh, back = _decode(encode_png(w, h, grid))
	if (rw, rh) != (w, h):
		raise SystemExit(f"--selftest: round-trip size mismatch ({rw}x{rh})")
	if back != grid:
		raise SystemExit("--selftest: round-trip pixel mismatch")


def run_selftest() -> None:
	print("classicart selftest")
	for i, path in enumerate(donor_paths(), 1):
		label = DONORS[i - 1][1]
		w, h, px = decode_png(path)
		_check_pil(path, w, h, px, f"donor {i} ({label})")
	print("PIL cross-validation: 3/3 donors exact pixel match")
	_check_determinism()
	print("determinism: all ops deterministic")
	_check_roundtrip()
	print("round-trip: decode(encode(px)) == px")
	print("classicart selftest PASS (3 donors, PIL cross-validated)")


def main(argv: list[str] | None = None) -> int:
	ap = argparse.ArgumentParser(description="classicart raster pipeline selftest")
	ap.add_argument("--selftest", action="store_true",
	                help="run the decoder/ops/encoder cross-validation selftest")
	args = ap.parse_args(argv)
	if not args.selftest:
		ap.print_help()
		return 0
	run_selftest()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
