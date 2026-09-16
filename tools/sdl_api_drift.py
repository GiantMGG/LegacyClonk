#!/usr/bin/env python3
"""sdl_api_drift.py - SDL2 -> SDL3 API drift mapper (LegacyClonk cycle 129).

Zero-build static analysis of the SDL call-surface under src/:
  - extracts SDL_/Mix_ symbol sites (file, line, enclosing #if guard)
  - cross-references the symbols a PR diff adds per file
  - classifies every site and emits a predicted-breakage markdown table

The RENAMED/REMOVED tables are seed data for this cycle's three known
surfaces (gamecontrollerdb, audio hints, keymap scancodes). Extend them
when triaging further upstream PRs (#148/#146).

Python 3 stdlib only. This is a prediction aid, not an oracle.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

SYMBOL_RE = re.compile(r'\b((?:SDL|Mix)_[A-Za-z0-9_]+)')
DIFF_HEADER_RE = re.compile(r'^diff --git a/.+? b/(?P<name>.+?)$')
RENAMED = {
	'SDL_GameControllerAddMappingsFromFile': 'SDL_AddGamepadMappingsFromFile',
	'SDL_GameControllerAddMappings': 'SDL_AddGamepadMappings',
	'SDL_GameControllerAddMapping': 'SDL_AddGamepadMapping',
	'SDL_GameControllerOpen': 'SDL_OpenGamepad',
	'SDL_GameControllerClose': 'SDL_CloseGamepad',
	'SDL_GameControllerGetAxis': 'SDL_GetGamepadAxis',
	'SDL_GameControllerGetButton': 'SDL_GetGamepadButton',
	'SDL_GameControllerName': 'SDL_GetGamepadName',
	'SDL_IsGameController': 'SDL_IsGamepad',
	'SDL_GameControllerGetPlayerIndex': 'SDL_GetGamepadPlayerIndex',
	'SDL_GameControllerRumble': 'SDL_RumbleGamepad',
	'SDL_GameControllerHasLED': 'SDL_GamepadHasLED',
}
REMOVED_NO_REPLACEMENT = {
	'SDL_HINT_AUDIO_RESAMPLING_MODE':
		'SDL3_mixer resamples internally; the SDL2_mixer "linear" hint '
		'is gone -> R1 fork-parity-loss candidate',
	'Mix_Linked_Version':
		'SDL3_mixer exposes MIX_Version; SDL2_mixer version query is '
		'gone (heuristic entry, verify against the PR diff)',
}
SOURCE_SUFFIXES = {'.cpp', '.h'}

def iter_source_files(src_root):
	for path in sorted(src_root.rglob('*')):
		if path.is_file() and path.suffix in SOURCE_SUFFIXES:
			yield path

def extract_sites(src_root):
	"""Return [(rel_path, line, symbol, guard)] for every SDL/Mix symbol."""
	sites = []
	for path in iter_source_files(src_root):
		text = path.read_text(encoding='utf-8', errors='replace')
		guard = '(none)'
		for lineno, line in enumerate(text.splitlines(), 1):
			stripped = line.lstrip()
			if stripped.startswith(('#if', '#elif')):
				guard = stripped
			for match in SYMBOL_RE.finditer(line):
				sites.append((path.relative_to(src_root).as_posix(),
				              lineno, match.group(1), guard))
	return sites

def parse_pr_diff(diff_path):
	"""Return {file: {'added': set, 'removed': set}} from a unified diff."""
	per_file = defaultdict(lambda: {'added': set(), 'removed': set()})
	current = None
	with open(diff_path, encoding='utf-8', errors='replace') as handle:
		for line in handle:
			header = DIFF_HEADER_RE.match(line)
			if header:
				current = header.group('name')
				continue
			if current is None or line.startswith('@@'):
				continue
			if line.startswith('+') and not line.startswith('+++'):
				per_file[current]['added'].update(SYMBOL_RE.findall(line))
			elif line.startswith('-') and not line.startswith('---'):
				per_file[current]['removed'].update(SYMBOL_RE.findall(line))
	return dict(per_file)

def classify(symbol, rel_path, pr_added, pr_touched):
	if symbol in RENAMED:
		target = RENAMED[symbol]
		if target in pr_added:
			return 'renamed-covered', f'{symbol} -> {target} (PR adds target)'
		return 'renamed-missing-target', (
			f'{symbol} -> {target} (target NOT in PR-added lines)')
	if symbol in REMOVED_NO_REPLACEMENT:
		return 'removed-no-replacement', REMOVED_NO_REPLACEMENT[symbol]
	if symbol in pr_added:
		return 'covered-by-PR', 'symbol appears in PR-added lines'
	if rel_path in pr_touched:
		return 'PR-silent-in-touched-file', (
			'file touched by PR, symbol untouched')
	return 'outside-PR-surface', 'file not touched by PR'

def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('--src', default='src', type=Path)
	parser.add_argument('--pr-diff', required=True, type=Path)
	parser.add_argument('--out', required=True, type=Path)
	parser.add_argument('--check', action='store_true',
	                    help='assert the three sanity anchors are present')
	args = parser.parse_args()

	pr_data = parse_pr_diff(args.pr_diff)
	pr_added = set()
	for entry in pr_data.values():
		pr_added.update(entry['added'])
	# Normalize the touched-path axis: diff headers are repo-root-relative
	# ("src/Foo.cpp") while site paths are --src-relative ("Foo.cpp"),
	# so map one vocabulary onto the other before classifying sites.
	pr_touched = set(pr_data)
	src_prefix = f'{args.src.name}/'
	pr_touched |= {p[len(src_prefix):] for p in pr_data
	               if p.startswith(src_prefix)}
	sites = extract_sites(args.src)

	rows = []
	for rel_path, lineno, symbol, guard in sites:
		cls, note = classify(symbol, rel_path, pr_added, pr_touched)
		rows.append((rel_path, lineno, symbol, guard, cls, note))
	pr_site_rows = [r for r in rows if r[0] in pr_touched]

	lines = []
	lines.append('# SDL2 -> SDL3 API drift map (cycle 129)\n')
	lines.append(f'- source root: `{args.src}`')
	lines.append(f'- PR diff: `{args.pr_diff}`')
	lines.append(f'- total symbol sites: {len(rows)}\n')
	lines.append('## Summary by classification\n')
	lines.append('| Class | Count |')
	lines.append('|---|---|')
	by_class = defaultdict(int)
	for row in rows:
		by_class[row[4]] += 1
	for cls in sorted(by_class):
		lines.append(f'| {cls} | {by_class[cls]} |')
	lines.append('')

	gamepad = [r for r in rows if 'GameControllerAddMappings' in r[2]]
	hint = [r for r in rows if r[2] == 'SDL_HINT_AUDIO_RESAMPLING_MODE']
	keymap = [r for r in rows
	          if r[0].endswith('C4Config.cpp') and r[2].startswith('SDL_SCANCODE')]

	lines.append('## Predicted breakage (sanity anchors)\n')
	if gamepad:
		locs = ', '.join(f'{r[0]}:{r[1]}' for r in gamepad)
		lines.append(
			f'- FLAG: gamecontrollerdb-load — SDL_GameControllerAddMappings* '
			f'site(s): {locs} — predicted compile fail under SDL3')
	if hint:
		locs = ', '.join(f'{r[0]}:{r[1]}' for r in hint)
		lines.append(
			f'- FLAG: audio-linear-hint — SDL_HINT_AUDIO_RESAMPLING_MODE '
			f'site(s): {locs} — predicted R1 fork-parity loss')
	if keymap:
		lines.append(
			f'- FLAG: keymap-scancodes — {len(keymap)} SDL_SCANCODE_* sites '
			f'in C4Config.cpp — keymap macro surface')
	lines.append('')

	lines.append('## Sites in PR-touched files\n')
	lines.append('| File | Line | Symbol | Guard | Class | Note |')
	lines.append('|---|---|---|---|---|---|')
	for rel_path, lineno, symbol, guard, cls, note in rows:
		if rel_path in pr_touched:
			lines.append(
				f'| {rel_path} | {lineno} | {symbol} | {guard} | {cls} | {note} |')
	lines.append('')

	lines.append('## Rename / removal candidates (all files)\n')
	for rel_path, lineno, symbol, guard, cls, note in rows:
		if cls in ('renamed-covered', 'renamed-missing-target',
		           'removed-no-replacement'):
			lines.append(f'- {rel_path}:{lineno} `{symbol}` [{cls}] {note}')
	lines.append('')

	out = args.out
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
	print(f'wrote {out} ({len(rows)} sites, '
	      f'{sum(1 for l in lines if l.startswith("- FLAG:"))} flags)')

	if args.check:
		missing = []
		if not gamepad:
			missing.append('SDL_GameControllerAddMappingsFromFile')
		if not hint:
			missing.append('SDL_HINT_AUDIO_RESAMPLING_MODE')
		if not keymap:
			missing.append('keymap SDL_SCANCODE sites in C4Config.cpp')
		if pr_data and not pr_site_rows:
			missing.append(
				'PR-touched files table is empty (path normalization broken)')
		if missing:
			print(f'SANITY: FAIL — drift map is missing: {missing}')
			return 1
		print('SANITY: PASS — all three sanity anchors flagged')
	return 0

if __name__ == '__main__':
	sys.exit(main())
