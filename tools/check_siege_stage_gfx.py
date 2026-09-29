#!/usr/bin/env python3
"""Siege stage-art gate (spec siege-flagship, cycle 181).

CTest-registered content gate (siege_stage_gfx, LABELS "lint") guarding
the SiegeOfHighKeep siege-stage art against regression. argv[1] = the
content repo root; exit 0 iff ALL of the following hold:

  (a) the four SiegeGate stage sheets are pairwise md5-distinct
      (Graphics / GraphicsCrack1 / GraphicsCrack2 / GraphicsRuin) —
      MUT-A's plain pairwise check;
  (b) the two BoilingOilCauldron Graphics.png copies (scenario-local
      Knights.c4f/SiegeOfHighKeep + the SiegeSmoke test copy) are
      byte-identical (md5-equal);
  (c) retired-hash blacklist: NONE of the checked PNGs (4 gate sheets +
      2 cauldron copies) md5s to the retired gate placeholder
      9ab00a2513435ceafca69462121daf02 or the retired cauldron
      placeholder 8d672ea6d7c712c84ef3f4399d387207 — reverting only one
      sheet to the placeholder would NOT break (a) (the reverted file is
      still distinct from the three new sheets), so (c) is what makes
      MUT-A and MUT-B detectable;
  (d) `gen_siege_gfx.py <each-subcommand> --check` exits 0 (spawned as a
      subprocess from this script's own directory, so the sibling
      clonkgfx import resolves and the generator's __file__-relative
      content root matches the repo layout).

Prints `siege_stage_gfx PASS` on success; `siege_stage_gfx FAIL: <reason>`
+ exit 1 on the first failure. The Autobuild CI has no content checkout:
the CTest entry is EXISTS-guarded on LEGACYCLONK_CONTENT_DIR, mirroring
content_gfx_lint.

Stdlib only. Python 3.10+. Tabs.
"""

import argparse
import hashlib
import os
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
GEN_SIEGE = os.path.join(TOOLS_DIR, "gen_siege_gfx.py")

# Retired placeholder digests (anchor verification, plan T6): the four
# pre-cycle-181 SiegeGate sheets all md5'd to 9ab00a...; both BOIL copies
# md5'd to 8d672e.... Both hashes are blacklisted for ALL six files.
RETIRED_GATE = "9ab00a2513435ceafca69462121daf02"
RETIRED_CAULDRON = "8d672ea6d7c712c84ef3f4399d387207"

GATE_DIR = ("SiegeEngines.c4d", "Structures.c4d", "SiegeGate.c4d")
GATE_FILES = ("Graphics.png", "GraphicsCrack1.png", "GraphicsCrack2.png",
              "GraphicsRuin.png")

BOIL_COPIES = (
    ("Knights.c4f", "SiegeOfHighKeep.c4s", "BoilingOilCauldron.c4d",
     "Graphics.png"),
    ("SiegeEngines.c4d", "Tests.c4f", "SiegeSmoke.c4s",
     "BoilingOilCauldron.c4d", "Graphics.png"),
)

# Every generator subcommand owns at least one of the checked sheets;
# each must byte-gate green against the shipped tree.
SUBCOMMANDS = ("gate", "cauldron", "trebuchet")

def md5_hex(path):
	"""md5 hex digest of a file, streamed (files are tiny, but play safe)."""
	h = hashlib.md5()
	with open(path, "rb") as f:
		for chunk in iter(lambda: f.read(1 << 16), b""):
			h.update(chunk)
	return h.hexdigest()

def main():
	ap = argparse.ArgumentParser(description=__doc__)
	ap.add_argument("content_dir", help="content repo root (clonk_ws/content)")
	args = ap.parse_args()
	root = os.path.abspath(args.content_dir)

	# (a) gate sheets pairwise md5-distinct; collect md5 for (c).
	gate = []
	for name in GATE_FILES:
		rel = os.path.join(*GATE_DIR, name).replace(os.sep, "/")
		path = os.path.join(root, *GATE_DIR, name)
		if not os.path.isfile(path):
			print(f"siege_stage_gfx FAIL: missing {rel}")
			return 1
		gate.append((rel, md5_hex(path)))
	n = len(gate)
	for i in range(n):
		for j in range(i + 1, n):
			if gate[i][1] == gate[j][1]:
				print(f"siege_stage_gfx FAIL: gate stage sheets not pairwise "
				      f"distinct ({GATE_FILES[i]} == {GATE_FILES[j]}, "
				      f"{gate[i][1]})")
				return 1

	# (b) the two BOIL copies byte-identical (md5-equal); collect for (c).
	boil = []
	for comps in BOIL_COPIES:
		rel = os.path.join(*comps).replace(os.sep, "/")
		path = os.path.join(root, *comps)
		if not os.path.isfile(path):
			print(f"siege_stage_gfx FAIL: missing {rel}")
			return 1
		boil.append((rel, md5_hex(path)))
	if boil[0][1] != boil[1][1]:
		print(f"siege_stage_gfx FAIL: BOIL Graphics.png copies drift "
		      f"({boil[0][0]} {boil[0][1]} != {boil[1][0]} {boil[1][1]})")
		return 1

	# (c) retired-hash blacklist across all six checked sheets.
	for rel, h in gate + boil:
		if h == RETIRED_GATE or h == RETIRED_CAULDRON:
			print(f"siege_stage_gfx FAIL: retired placeholder hash {h} on {rel}")
			return 1

	# (d) generator --check gates for every siege-gfx subcommand.
	for sub in SUBCOMMANDS:
		proc = subprocess.run([sys.executable, GEN_SIEGE, sub, "--check"],
		                      cwd=TOOLS_DIR)
		if proc.returncode != 0:
			print(f"siege_stage_gfx FAIL: gen_siege_gfx.py {sub} --check "
			      f"exit {proc.returncode}")
			return 1

	print("siege_stage_gfx PASS")
	return 0

if __name__ == "__main__":
	sys.exit(main())
