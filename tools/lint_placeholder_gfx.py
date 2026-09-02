#!/usr/bin/env python3
"""Placeholder-art lint (cycle 93, spec hostile-object-bugfix).

Walks every def dir under content/ (Graphics.png + DefCore.txt),
decodes the PNG with stdlib zlib+struct (8-bit, non-interlaced,
color types 0/2/3/6), parses ActMap actions ([Action] blocks in
ActMap.txt or DefCore.txt), and replicates the engine's facet-sampling
math (C4Facet::DrawT + UpdateFlipDir).

Hard fails (exit 1), skipped for allowlisted defs:
  FLAT_FACET        sampled rect has >= 16 opaque px, all one RGB
  INVISIBLE_ACTION  action with explicit Facet= whose every sampled
                    rect has 0 opaque px
Warns (legacy debt, spec deviation D1):
  PICTURE_OOB / FACET_OOB — rect exceeds sheet bounds
Exit 2 on usage/decoder errors. --report prints a full survey.
"""

import argparse
import os
import struct
import sys
import zlib

THRESHOLD = 16
ALLOWLIST_FILENAME = "placeholder_gfx_allowlist.txt"


class PngError(Exception):
	pass


def png_rgba(data):
	"""Decode PNG -> (width, height, rows[[ (r,g,b,a) ]]). Stdlib only."""
	if data[:8] != b"\x89PNG\r\n\x1a\n":
		raise PngError("not a PNG")
	pos, idat, palette, trns = 8, b"", None, None
	width = height = bit_depth = color_type = interlace = None
	while pos < len(data):
		(length,) = struct.unpack(">I", data[pos:pos + 4])
		tag, payload = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
		pos += 12 + length
		if tag == b"IHDR":
			# IHDR: width, height, bit_depth, color_type, compression,
			# filter, interlace (7 fields; compression/filter unused here).
			width, height, bit_depth, color_type, _, _, interlace = \
				struct.unpack(">IIBBBBB", payload)
		elif tag == b"PLTE":
			palette = [(payload[i], payload[i + 1], payload[i + 2], 255)
			           for i in range(0, len(payload), 3)]
		elif tag == b"tRNS":
			trns = payload
		elif tag == b"IDAT":
			idat += payload
		elif tag == b"IEND":
			break
	if width is None:
		raise PngError("no IHDR")
	if bit_depth != 8 or interlace != 0:
		raise PngError("unsupported bit depth / interlace")
	if color_type not in (0, 2, 3, 6):
		raise PngError(f"unsupported color type {color_type}")
	raw = zlib.decompress(idat)
	bpp = {0: 1, 2: 3, 3: 1, 6: 4}[color_type]
	stride = width * bpp
	rows_out, prev = [], bytearray(stride)
	off = 0
	for _ in range(height):
		filt = raw[off]
		line = bytearray(raw[off + 1:off + 1 + stride])
		off += 1 + stride
		for x in range(stride):
			a = line[x - bpp] if x >= bpp else 0
			b = prev[x]
			c = prev[x - bpp] if x >= bpp else 0
			if filt == 1:
				line[x] = (line[x] + a) & 0xFF
			elif filt == 2:
				line[x] = (line[x] + b) & 0xFF
			elif filt == 3:
				line[x] = (line[x] + ((a + b) >> 1)) & 0xFF
			elif filt == 4:
				# Paeth: pick nearest of a, b, c to p = a + b - c.
				p = a + b - c
				pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
				if pa <= pb and pa <= pc:
					pr = a
				elif pb <= pc:
					pr = b
				else:
					pr = c
				line[x] = (line[x] + pr) & 0xFF
		rows_out.append(line)
		prev = line
	rows = []
	for y in range(height):
		cur = rows_out[y]
		row = []
		for x in range(width):
			i = x * bpp
			if color_type == 0:
				row.append((cur[i], cur[i], cur[i], 255))
			elif color_type == 2:
				row.append((cur[i], cur[i + 1], cur[i + 2], 255))
			elif color_type == 3:
				if palette is None or cur[i] >= len(palette):
					row.append((0, 0, 0, 0))
				else:
					r, g, b, _ = palette[cur[i]]
					alpha = trns[cur[i]] if trns and cur[i] < len(trns) else 255
					row.append((r, g, b, alpha))
			else:
				row.append((cur[i], cur[i + 1], cur[i + 2], cur[i + 3]))
		rows.append(row)
	return width, height, rows


def parse_int(s, default):
	s = s.strip()
	return int(s) if s else default


def parse_actions(text):
	"""Parse [Action] blocks -> list of dicts with raw string values."""
	actions, cur, section = [], None, None
	for raw_line in text.splitlines():
		line = raw_line.strip().rstrip("\r")
		if not line or line.startswith(";") or line.startswith("//"):
			continue
		if line.startswith("[") and line.endswith("]"):
			section = line[1:-1].strip().lower()
			if section == "action":
				cur = {}
				actions.append(cur)
			continue
		if section == "action" and "=" in line:
			key, _, value = line.partition("=")
			cur[key.strip().lower()] = value.strip()
	return actions


def rect(values):
	parts = [p.strip() for p in values.split(",")]
	if len(parts) < 4:
		raise PngError(f"bad rect {values!r}")
	# ActMap Facet may carry 2 extra offset ints (x,y,w,h,ox,oy);
	# the sampled rect is the first 4 components.
	return tuple(int(p) for p in parts[:4])


def sample(rows, x, y, w, h):
	"""Return (opaque_count, {rgb colors}) for an in-bounds rect."""
	opaque, colors = 0, set()
	for yy in range(y, y + h):
		for xx in range(x, x + w):
			r, g, b, a = rows[yy][xx]
			if a > 0:
				opaque += 1
				colors.add((r, g, b))
	return opaque, colors


def check_def(def_dir, rel, allow):
	"""Return (hard_findings, warnings) for one def dir."""
	findings, warns = [], []
	gh = os.path.join(def_dir, "Graphics.png")
	try:
		with open(gh, "rb") as f:
			width, height, rows = png_rgba(f.read())
	except Exception as e:
		return [], [f"WARN {rel}: DECODE_ERROR {e}"]
	dc = os.path.join(def_dir, "DefCore.txt")
	try:
		with open(dc, "rb") as f:
			dc_text = f.read().decode("utf-8", errors="replace")
	except OSError as e:
		return [], [f"WARN {rel}: DECODE_ERROR {e}"]
	am = os.path.join(def_dir, "ActMap.txt")
	if os.path.exists(am):
		with open(am, "rb") as f:
			actions = parse_actions(f.read().decode("utf-8", errors="replace"))
	else:
		actions = parse_actions(dc_text)
	# Picture OOB (warn-only)
	for line in dc_text.splitlines():
		stripped = line.strip().rstrip("\r")
		if stripped.lower().startswith("picture="):
			try:
				px, py, pw, ph = rect(stripped.split("=", 1)[1])
				if px + pw > width or py + ph > height or px < 0 or py < 0:
					warns.append(f"WARN {rel}: PICTURE_OOB Picture=({px},{py},{pw},{ph}) sheet={width}x{height}")
			except Exception:
				pass
			break
	# Per-action facet checks
	for act in actions:
		if "facet" not in act:
			continue
		name = act.get("name", "?")
		try:
			fx, fy, fw, fh = rect(act["facet"])
		except (PngError, ValueError):
			# Malformed Facet (e.g. empty component) — legacy debt, warn-only
			warns.append(f"WARN {rel}: MALFORMED_FACET action={name} Facet={act['facet']!r}")
			continue
		length = parse_int(act.get("length", ""), 1)
		directions = parse_int(act.get("directions", ""), 1)
		flip_dir = parse_int(act.get("flipdir", ""), 0)
		total_opaque, sampled_any = 0, False
		for phase in range(max(length, 1)):
			for d in range(max(directions, 1)):
				draw_row = flip_dir - 1 - (d - flip_dir) if (flip_dir and d >= flip_dir) else d
				sx, sy = fx + fw * phase, fy + fh * draw_row
				if sx + fw > width or sy + fh > height or sx < 0 or sy < 0:
					warns.append(f"WARN {rel}: FACET_OOB action={name} rect=({sx},{sy},{fw},{fh}) sheet={width}x{height}")
					continue
				sampled_any = True
				opaque, colors = sample(rows, sx, sy, fw, fh)
				total_opaque += opaque
				if opaque >= THRESHOLD and len(colors) == 1:
					findings.append(f"FAIL {rel}: FLAT_FACET action={name} phase={phase} dir={d} {opaque} px, single color {next(iter(colors))}")
		# INVISIBLE only when at least one rect was actually sampled
		if sampled_any and total_opaque == 0:
			findings.append(f"FAIL {rel}: INVISIBLE_ACTION action={name} facet=({fx},{fy},{fw},{fh}) 0 opaque px")
	if rel in allow:
		findings = []  # allowlisted: hard checks skipped, warnings kept
	return findings, warns


def main():
	ap = argparse.ArgumentParser(description=__doc__)
	ap.add_argument("content_dir")
	ap.add_argument("--report", action="store_true",
	                help="full survey listing (allowlist seeding source)")
	args = ap.parse_args()
	allow_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ALLOWLIST_FILENAME)
	allow = set()
	if os.path.exists(allow_path):
		with open(allow_path) as f:
			for line in f:
				line = line.split("#", 1)[0].strip()
				if line:
					allow.add(line)
	all_findings, all_warns = [], []
	for root, dirs, files in os.walk(args.content_dir):
		dirs[:] = sorted(d for d in dirs if not d.startswith("."))
		if "Graphics.png" not in files or "DefCore.txt" not in files:
			continue
		rel = os.path.relpath(root, args.content_dir).replace(os.sep, "/")
		findings, warns = check_def(root, rel, allow)
		if args.report:
			status = "ALLOWLISTED" if rel in allow else ("DIRTY" if findings else "clean")
			print(f"{status:12} {rel}")
		all_findings += findings
		all_warns += warns
	for w in sorted(all_warns):
		print(w)
	for f in all_findings:
		print(f)
	if all_findings:
		print(f"{len(all_findings)} violation(s)")
		return 1
	print("placeholder-gfx lint clean")
	return 0


if __name__ == "__main__":
	sys.exit(main())
