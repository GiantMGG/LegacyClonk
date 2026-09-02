#!/usr/bin/env python3
"""Deterministic scorpion sprite-sheet generator (cycle 93, spec
hostile-object-bugfix). Stdlib only. The committed Graphics.png must
byte-match this script's output (verify with --check).

Sheet: 40x64 RGBA. Phase 0 at (0,0,20,12), phase 1 at (20,0,20,12);
rows 12-63 fully transparent. Palette chars: K outline, B body,
H carapace highlight, S accent; '.' = transparent.
"""

import argparse
import os
import struct
import sys
import zlib

W, H, PHASE_W, PHASE_H = 40, 64, 20, 12
OUT_DEFAULT = os.path.join("..", "content", "Desert.c4d", "Scorpion.c4d", "Graphics.png")
PALETTE = {"K": (43, 26, 12, 255), "B": (90, 58, 31, 255),
           "H": (133, 90, 48, 255), "S": (176, 128, 80, 255)}

PHASE0 = [
	"............S.......",
	".....KK...KSK.K.....",
	"....KHHK..K...K.....",
	"....K..KK.K.........",
	"..KKKKKKKKKKKKKKKK..",
	".KBBBHHHHHHHBBBBKKK.",
	".KBBBBHHHHHBBBBBKKSK",
	"..KKBBBBBBBBBBKKKKK.",
	"...KKKKKKKKKKKKKK...",
	"..KK...KK...KK......",
	"..K....K....K.......",
	"....................",
]

PHASE1 = [
	"............S.......",
	"....KK...KSK..K.....",
	"...KHHK..K...K......",
	"...K..KK.K..........",
	"..KKKKKKKKKKKKKKKK..",
	".KBBBHHHHHHHBBBBKKK.",
	".KBBBBHHHHHBBBBBKKSK",
	"..KKBBBBBBBBBBKKKKK.",
	"...KKKKKKKKKKKKKK...",
	"..KK...KK...KK......",
	"...K....K....K......",
	"....................",
]

def phase_pixels(rows, name):
	if len(rows) != PHASE_H or any(len(r) != PHASE_W for r in rows):
		raise SystemExit(f"{name}: map must be {PHASE_H} rows x {PHASE_W} cols")
	px = {}
	for y, row in enumerate(rows):
		for x, ch in enumerate(row):
			if ch == ".":
				px[(x, y)] = (0, 0, 0, 0)
			elif ch in PALETTE:
				px[(x, y)] = PALETTE[ch]
			else:
				raise SystemExit(f"{name}: bad char {ch!r}")
	return px

def check_invariants(p0, p1):
	for name, p in (("phase0", p0), ("phase1", p1)):
		colors = {v for v in p.values() if v[3] > 0}
		opaque = sum(1 for v in p.values() if v[3] > 0)
		if len(colors) < 3:
			raise SystemExit(f"{name}: fewer than 3 opaque colors")
		if not 60 <= opaque <= 140:
			raise SystemExit(f"{name}: {opaque} opaque px outside [60,140]")
	diff = sum(1 for k in p0 if p0[k] != p1[k])
	if diff < 8:
		raise SystemExit(f"phases differ in only {diff} px (minimum 8)")

def make_png():
	p0 = phase_pixels(PHASE0, "PHASE0")
	p1 = phase_pixels(PHASE1, "PHASE1")
	check_invariants(p0, p1)
	raw = bytearray()
	for y in range(H):
		raw.append(0)  # filter: none
		for x in range(W):
			# Phase maps cover rows 0..PHASE_H-1; rows PHASE_H..H-1 and any
			# pixel outside a phase map are fully transparent (0,0,0,0).
			raw.extend(p0.get((x, y), (0, 0, 0, 0)) if x < PHASE_W
			           else p1.get((x - PHASE_W, y), (0, 0, 0, 0)))

	def chunk(tag, data):
		return (struct.pack(">I", len(data)) + tag + data
		        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

	return (b"\x89PNG\r\n\x1a\n"
	        + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
	        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
	        + chunk(b"IEND", b""))

def main():
	ap = argparse.ArgumentParser(description=__doc__)
	ap.add_argument("output", nargs="?", default=OUT_DEFAULT)
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

if __name__ == "__main__":
	sys.exit(main())
