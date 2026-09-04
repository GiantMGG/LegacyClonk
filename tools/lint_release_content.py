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
			with open(os.path.join(root, "Scenario.txt"),
				encoding="utf-8", errors="replace") as f:
				refs = parse_scenario_refs(f.read())
			for ref in refs:
				if ref not in shipped:
					findings.append(
						f"FAIL closure {rel} -> {ref} "
						f"(not in [groups.content])")

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
