#!/usr/bin/env python3
"""Release-content lint (cycle 96, spec release-content-groups-lint).

Models the release manifest (autobuild/ci.toml [groups.content]) against
the content tree. The v366 bug class -- a shipped scenario referencing a
pack absent from [groups.content] -- fails here at push time instead of
at player launch (LogFatal(IDS_PRC_DEFNOTFOUND)).

Checks (any finding -> exit 1):
  KEY-FORMAT     every [groups.content] key must match *.c4? (the ps1
                 pack filter, MakeContentGroupsAndUpdateGroups.ps1:29);
                 a non-matching key is listed-but-never-packed
  EXISTENCE      every key must exist as a top-level content/<key>
                 directory (catches typos at push time, not tag time)
  COMPLETENESS   every top-level content/*.c4? must be a key or an
                 explicit allowlist entry
                 (tools/release_content_allowlist.txt)
  CLOSURE        for every Scenario.txt under a shipped pack subtree,
                 every [Definitions] ref must have its first path
                 component in the shipped set. Both engine forms
                 (src/C4Scenario.cpp:563-584): Definitions=<comma-list>
                 takes precedence when non-empty, else Definition1..10=
                 (C4S_MaxDefinitions = 10). Backslash paths normalized;
                 comparison is case-sensitive (Linux runtime is).
                 Scenarios under a Tests.c4f folder are skipped: the
                 release packer strips Tests.c4f at pack time (spec
                 content-cleanup 4.2), so their refs never ship.
  DUP-ID         every DefCore id= under a shipped pack subtree must be
                 unique unless the colliding pair is baselined in
                 tools/dup_id_baseline.txt (legacy layered redefs).
  UNUSED         every shipped .c4d key must be enrolled by >=1 shipped
                 non-test scenario ([Definitions]); exemptions in
                 tools/pack_use_exemptions.txt.
  ZERO-BYTE-ART  no 0-byte Icon.png/Title.png/Graphics.png under any
                 shipped pack subtree (CaveExplorer icon regression).

Exit 0 clean / 1 violations / 2 usage or IO error.
"""

import argparse
import os
import re
import sys

ALLOWLIST_FILENAME = "release_content_allowlist.txt"
KEY_RE = re.compile(
	r"""^\[groups\.content\.'([^']+)'\]|^\[groups\.content\."([^"]+)"\]""",
	re.MULTILINE)
PACK_FILTER_RE = re.compile(r"\.c4.$")
CONTENT_PACK_RE = re.compile(r".+\.c4[dfgs]$")
DEF_ID_RE = re.compile(r"^\s*(?:ID|id)\s*=\s*(\w+)", re.MULTILINE)
ART_NAMES = ("Icon.png", "Title.png", "Graphics.png")
DUP_BASELINE_FILENAME = "dup_id_baseline.txt"
PACK_USE_EXEMPTIONS_FILENAME = "pack_use_exemptions.txt"

def parse_keys(toml_text):
	"""Extract [groups.content] sub-table keys, order-preserving."""
	keys = []
	for m in KEY_RE.finditer(toml_text):
		keys.append(m.group(1) or m.group(2))
	return keys

def load_allowlist(path):
	"""One entry per line; '#' starts a comment; '<entry> # <reason>'."""
	allow = set()
	if os.path.exists(path):
		with open(path, encoding="utf-8") as f:
			for line in f:
				entry = line.split("#", 1)[0].strip()
				if entry:
					allow.add(entry)
	return allow

def parse_scenario_refs(text):
	"""Return the [Definitions] first-path components a scenario loads.

	Models C4SDefinitions::CompileFunc (src/C4Scenario.cpp:563-584):
	the Definitions=<comma-list> form wins when present and non-empty;
	otherwise the numbered Definition1..10= keys apply. Refs normalize
	backslashes to forward slashes before the first-component split.
	"""
	refs = []
	in_section = False
	definitions_list = None
	for raw_line in text.splitlines():
		line = raw_line.strip()
		if line.startswith("[") and line.endswith("]"):
			in_section = line[1:-1].strip().lower() == "definitions"
			continue
		if not in_section or "=" not in line:
			continue
		key, _, value = line.partition("=")
		key = key.strip().lower()
		if key == "definitions":
			definitions_list = value.strip()
		elif key.startswith("definition") and key[10:].isdigit():
			n = int(key[10:])
			if 1 <= n <= 10:  # C4S_MaxDefinitions
				refs.append(value.strip())
	if definitions_list:
		refs = [r.strip() for r in definitions_list.split(",") if r.strip()]
	return [r.replace("\\", "/").split("/")[0] for r in refs if r]

def collect_pack_ids(content_dir, shipped):
	"""Map id -> [relative DefCore.txt dir] for shipped pack subtrees."""
	ids = {}
	for k in shipped:
		pack_dir = os.path.join(content_dir, k)
		if not os.path.isdir(pack_dir):
			continue
		for root, dirs, files in os.walk(pack_dir):
			dirs[:] = sorted(d for d in dirs if not d.startswith("."))
			if "DefCore.txt" not in files:
				continue
			with open(os.path.join(root, "DefCore.txt"),
				encoding="utf-8", errors="replace") as f:
				m = DEF_ID_RE.search(f.read())
			if not m:
				continue
			rel = os.path.relpath(root, content_dir).replace(os.sep, "/")
			ids.setdefault(m.group(1), []).append(rel)
	return ids

def load_dup_baseline(path):
	"""Exempted (id, pathA, pathB) pairs from dup_id_baseline.txt.

	Line format: `<ID> <path> <path> [...] # <reason>`; every unordered
	path pair on a line becomes one exempt pair. Paths that contain a
	literal space (e.g. "Command Center.c4d") are %20-encoded by the
	seeding script so the whitespace split stays unambiguous.
	"""
	pairs = set()
	if os.path.exists(path):
		with open(path, encoding="utf-8") as f:
			for line in f:
				entry = line.split("#", 1)[0].strip()
				if not entry:
					continue
				fields = entry.split()
				if len(fields) < 3:
					continue
				idv, paths = fields[0], sorted(
					p.replace("%20", " ") for p in fields[1:])
				for i in range(len(paths)):
					for j in range(i + 1, len(paths)):
						pairs.add((idv, paths[i], paths[j]))
	return pairs

def main():
	ap = argparse.ArgumentParser(
		description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("ci_toml", help="path to autobuild/ci.toml")
	ap.add_argument("content_dir", help="path to the content/ tree")
	ap.add_argument("--report", action="store_true",
		help="survey: shipped set + allowlist, no exit-code change")
	args = ap.parse_args()

	try:
		with open(args.ci_toml, encoding="utf-8") as f:
			toml_text = f.read()
	except OSError as e:
		print(f"cannot read {args.ci_toml}: {e}", file=sys.stderr)
		return 2
	if not os.path.isdir(args.content_dir):
		print(f"not a directory: {args.content_dir}", file=sys.stderr)
		return 2

	allow_path = os.path.join(
		os.path.dirname(os.path.abspath(__file__)), ALLOWLIST_FILENAME)
	allow = load_allowlist(allow_path)

	keys = parse_keys(toml_text)
	shipped = set(keys)
	findings = []

	# 1. KEY-FORMAT: every key must match the ps1 *.c4? pack filter.
	for k in keys:
		if not PACK_FILTER_RE.search(k):
			findings.append(
				f"FAIL key-format {k} (does not match *.c4? "
				f"-- listed but never packed)")

	# 2. EXISTENCE: every key must exist as content/<key>.
	for k in keys:
		if not os.path.isdir(os.path.join(args.content_dir, k)):
			findings.append(
				f"FAIL existence {k} (listed in [groups.content] "
				f"but absent from content/)")

	# 3. COMPLETENESS: every top-level content pack ships or is allowlisted.
	for entry in sorted(os.listdir(args.content_dir)):
		if not CONTENT_PACK_RE.match(entry):
			continue
		if entry in shipped or entry in allow:
			continue
		findings.append(
			f"FAIL completeness {entry} (content/ pack not in "
			f"[groups.content]; list it or allowlist it)")

	# 4. CLOSURE: shipped scenarios' Definition refs must resolve.
	for k in keys:
		pack_dir = os.path.join(args.content_dir, k)
		if not os.path.isdir(pack_dir):
			continue  # EXISTENCE already flagged it
		for root, dirs, files in os.walk(pack_dir):
			dirs[:] = sorted(d for d in dirs if not d.startswith("."))
			if "Scenario.txt" not in files:
				continue
			rel = os.path.relpath(root, args.content_dir).replace(os.sep, "/")
			if any(part == "Tests.c4f" for part in rel.split("/")):
				continue  # stripped from the release at pack time (4.2)
			with open(os.path.join(root, "Scenario.txt"),
				encoding="utf-8", errors="replace") as f:
				refs = parse_scenario_refs(f.read())
			for ref in refs:
				if ref in shipped:
					continue
				# Folder-local resolution (Knights.c4f/Camp.c4s precedent):
				# [Definitions] names resolve against the scenario's parent
				# group chain first, so a ref shipped inside this very pack
				# subtree closes even though it is not a top-level pack.
				if os.path.isdir(os.path.join(pack_dir, ref)):
					continue
				findings.append(
					f"FAIL closure {rel} -> {ref} "
					f"(not in [groups.content])")

	# 5. DUP-ID: DefCore id= collisions under shipped packs must be
	# baselined legacy pairs (tools/dup_id_baseline.txt).
	dup_baseline_path = os.path.join(
		os.path.dirname(os.path.abspath(__file__)), DUP_BASELINE_FILENAME)
	baseline_pairs = load_dup_baseline(dup_baseline_path)
	pack_ids = collect_pack_ids(args.content_dir, shipped)
	for idv in sorted(pack_ids):
		paths = sorted(pack_ids[idv])
		for i in range(len(paths)):
			for j in range(i + 1, len(paths)):
				if (idv, paths[i], paths[j]) not in baseline_pairs:
					findings.append(
						f"FAIL dup-id {idv} {paths[i]} <-> {paths[j]} "
						f"(unbaselined duplicate ID)")

	# 6. UNUSED: every shipped .c4d key needs a shipped non-test enroller.
	use_exempt_path = os.path.join(
		os.path.dirname(os.path.abspath(__file__)),
		PACK_USE_EXEMPTIONS_FILENAME)
	use_exempt = load_allowlist(use_exempt_path)
	enrolled = set()
	for k in keys:
		pack_dir = os.path.join(args.content_dir, k)
		if not os.path.isdir(pack_dir):
			continue
		for root, dirs, files in os.walk(pack_dir):
			dirs[:] = sorted(d for d in dirs if not d.startswith("."))
			if "Scenario.txt" not in files:
				continue
			rel = os.path.relpath(root, args.content_dir).replace(os.sep, "/")
			if any(part == "Tests.c4f" for part in rel.split("/")):
				continue
			with open(os.path.join(root, "Scenario.txt"),
				encoding="utf-8", errors="replace") as f:
				enrolled.update(parse_scenario_refs(f.read()))
	for k in sorted(keys):
		if not k.endswith(".c4d") or k in enrolled or k in use_exempt:
			continue
		findings.append(
			f"FAIL unused {k} (shipped .c4d pack enrolled by no "
			f"shipped non-test scenario; enroll it or exempt it)")

	# 7. ZERO-BYTE-ART: no 0-byte icons/titles/graphics under shipped packs.
	for k in keys:
		pack_dir = os.path.join(args.content_dir, k)
		if not os.path.isdir(pack_dir):
			continue
		for root, dirs, files in os.walk(pack_dir):
			dirs[:] = sorted(d for d in dirs if not d.startswith("."))
			for art in ART_NAMES:
				if art in files:
					p = os.path.join(root, art)
					if os.path.getsize(p) == 0:
						rel = os.path.relpath(
							p, args.content_dir).replace(os.sep, "/")
						findings.append(
							f"FAIL zero-byte-art {rel} (0-byte {art})")

	if args.report:
		print(f"shipped set ({len(shipped)}):")
		for k in keys:
			print(f"  {k}")
		print(f"allowlist ({len(allow)}): {sorted(allow)}")

	for f in findings:
		print(f)
	if findings:
		print(f"{len(findings)} violation(s)")
		return 1
	print("release-content lint clean")
	return 0

if __name__ == "__main__":
	sys.exit(main())
