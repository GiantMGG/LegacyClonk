#!/usr/bin/env python3
"""playtest_sweep.py -- shipped-scenario headless playtest sweep (cycle 97).

Runs every shipped playtest scenario (ci.toml [groups.content] minus
in-pack Tests.c4f smokes) headless for N ticks, classifies each outcome
(PASS/FAIL/CRASH/TIMEOUT/OVER-BUDGET), maps allowlisted rows to
KNOWN-RED/PASS-STALE, prints a table and exits non-zero on any
unexpected failure. See spec scenario-playtest-harness.

Exit codes: 0 all PASS/KNOWN-RED; 1 unexpected failure; 2 usage or
infrastructure error (missing engine/content/ci.toml, zero scenarios,
missing shipped pack dir).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FRAME_RATE_CAP = 1000  # hardcoded (pxs_perf_gate precedent; 13x speedup)
MAX_JOBS = 4  # resource-hygiene: at most 4 concurrent engine procs

KEY_RE = re.compile(  # [groups.content] keys (lint_release_content.py idiom)
	r"""^\[groups\.content\.'([^']+)'\]|^\[groups\.content\."([^"]+)"\]""",
	re.MULTILINE)
DEFAULT_CI_TOML = Path(__file__).resolve().parent.parent / "autobuild/ci.toml"
DEFAULT_ALLOWLIST = Path(__file__).resolve().parent / "playtest_allowlist.txt"
DEFAULT_PLAYER_FILE = (
	Path(__file__).resolve().parent.parent / "tests/fixtures/TestPlayer.c4p")

def die(msg: str) -> None:
	print(f"ERROR: {msg}", file=sys.stderr)
	sys.exit(2)

def parse_keys(toml_text: str) -> list[str]:
	return [m.group(1) or m.group(2) for m in KEY_RE.finditer(toml_text)]

def load_allowlist(path: str) -> set[str]:
	"""One scenario path per line; '#' starts a comment."""
	allow = set()
	if os.path.exists(path):
		with open(path, encoding="utf-8") as f:
			for line in f:
				entry = line.split("#", 1)[0].strip()
				if entry:
					allow.add(entry)
	return allow

def derive_roster(content_dir: Path, keys: list[str]) -> list[str]:
	"""Content-relative .c4s paths per shipped pack; Tests.c4f pruned."""
	roster: list[str] = []
	for key in keys:
		pack_dir = content_dir / key
		if not pack_dir.is_dir():
			die(f"shipped pack missing from content dir: {pack_dir}")
		pack: list[str] = []
		for root, dirs, files in os.walk(pack_dir):
			dirs[:] = sorted(d for d in dirs if d != "Tests.c4f")
			for name in sorted(dirs) + sorted(files):
				if name.endswith(".c4s"):
					pack.append(os.path.relpath(os.path.join(root, name),
						content_dir).replace(os.sep, "/"))
		roster.extend(sorted(pack))
	return roster

def scan_mission_access(roster: list[str], content_dir: Path) -> list[str]:
	"""MissionAccess= passwords across the roster (any Scenario.txt line)."""
	passwords: list[str] = []
	for rel in roster:
		scen = content_dir / rel
		if not scen.is_dir():
			continue  # loose packed .c4s files cannot be scanned in place
		txt = scen / "Scenario.txt"
		if not txt.is_file():
			continue
		with open(txt, encoding="utf-8", errors="replace") as f:
			for line in f:
				key, sep, value = line.partition("=")
				if sep and key.strip().lower() == "missionaccess":
					pw = value.strip()
					if pw and pw not in passwords:
						passwords.append(pw)
	return passwords

def write_grant_config(path: Path, passwords: list[str]) -> None:
	"""The MissionAccess value MUST be quoted: unquoted INI string values
	silently fail StdCompilerINIRead and fall back to MissionAccess=""."""
	path.write_text('[General]\nMissionAccess="' + ";".join(passwords) + '"\n',
		encoding="utf-8")

def first_fatal(log_text: str) -> str:
	"""First FATAL ERROR line, truncated to 120 chars."""
	for line in log_text.splitlines():
		if "FATAL ERROR" in line:
			return line.strip()[:120]
	return ""

def run_scenario(args, engine: Path, engine_dir: Path, grant_cfg: Path,
		rel: str, player_file: Path | None) -> dict:
	scenario = (Path(args.content_dir) / rel).resolve()
	cmd = [str(engine), "--console", "--smoke-run", str(args.ticks),
		"--frame-rate-cap", str(FRAME_RATE_CAP),
		f"/config:{grant_cfg}", str(scenario)]
	if player_file is not None:
		cmd.append(str(player_file))
	# stdin=DEVNULL is MANDATORY: the console engine reads stdin and an
	# inherited pipe with buffered data HANGS it (spec-verified trap).
	log = tempfile.NamedTemporaryFile(mode="w+", delete=False,
		suffix="_playtest.log")
	start = time.monotonic()
	try:
		proc = subprocess.Popen(cmd, cwd=str(engine_dir),
			stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
		try:
			rc: int | None = proc.wait(timeout=args.timeout)
		except subprocess.TimeoutExpired:
			proc.kill()
			proc.wait()
			rc = None
	except OSError as e:
		log.close()
		os.unlink(log.name)
		die(f"cannot spawn engine {engine}: {e}")
	wall = time.monotonic() - start
	log.close()
	with open(log.name, encoding="utf-8", errors="replace") as f:
		log_text = f.read()
	os.unlink(log.name)
	if rc is None:
		cls, note = "TIMEOUT", f"killed at {args.timeout}s wall timeout"
	elif rc == 0:
		cls, note = "PASS", ""
	elif rc == 1:
		cls, note = "FAIL", ""
	else:
		cls, note = "CRASH", ""
	if cls in ("FAIL", "CRASH"):
		note = first_fatal(log_text) or f"rc={rc}"
	if cls == "PASS" and args.perf_budget and wall > args.perf_budget:
		cls, note = "OVER-BUDGET", f"wall {wall:.1f}s > budget {args.perf_budget}s"
	if cls != "PASS" and getattr(args, "log_dir", None):
		try:
			(Path(args.log_dir) / "playtest_logs").mkdir(parents=True, exist_ok=True)
			saved = (Path(args.log_dir) / "playtest_logs"
				/ (rel.replace("/", "__") + ".log"))
			saved.write_text(log_text, encoding="utf-8")
			note = f"{note} [log: {saved}]"
		except OSError:
			pass
	return {"rel": rel, "cls": cls, "rc": rc, "wall": wall, "note": note}

def main() -> int:
	ap = argparse.ArgumentParser(description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--engine", required=True, help="clonk binary")
	ap.add_argument("--content-dir", required=True, help="content/ tree")
	ap.add_argument("--ci-toml", default=str(DEFAULT_CI_TOML),
		help="release manifest (default: %(default)s)")
	ap.add_argument("--ticks", type=int, default=350,
		help="smoke-run tick count (default: %(default)s)")
	ap.add_argument("--timeout", type=int, default=60,
		help="per-scenario wall timeout in s (default: %(default)s)")
	ap.add_argument("--allowlist", default=str(DEFAULT_ALLOWLIST),
		help="known-red allowlist (default: %(default)s)")
	ap.add_argument("--report", default=None,
		help="write a TSV report (scenario/class/rc/wall_s/note) to PATH")
	ap.add_argument("--log-dir", default=None,
		help="retain engine logs of non-PASS scenarios under DIR/playtest_logs")
	ap.add_argument("--perf-budget", type=float, default=0.0,
		help="fail PASS scenarios slower than SECONDS (0 = off)")
	ap.add_argument("--playerful", action="store_true",
		help="append tests/fixtures/TestPlayer.c4p to every run")
	ap.add_argument("--filter", default=".*",
		help="regex on the content-relative scenario path")
	ap.add_argument("--jobs", type=int, default=1,
		help="parallel engine procs, 1..4 (default: %(default)s)")
	args = ap.parse_args()

	if not 1 <= args.jobs <= MAX_JOBS:
		die(f"--jobs must be in 1..{MAX_JOBS}")
	engine = Path(args.engine).resolve()
	if not engine.is_file():
		die(f"engine binary not found: {engine}")
	content_dir = Path(args.content_dir).resolve()
	if not content_dir.is_dir():
		die(f"content dir not found: {content_dir}")
	try:
		with open(args.ci_toml, encoding="utf-8") as f:
			toml_text = f.read()
	except OSError as e:
		die(f"cannot read {args.ci_toml}: {e}")

	keys = parse_keys(toml_text)
	roster = derive_roster(content_dir, keys)
	if not roster:
		die("zero scenarios enumerated")
	filter_re = re.compile(args.filter)
	roster = [r for r in roster if filter_re.search(r)]
	if not roster:
		die("zero scenarios after --filter")
	allow = load_allowlist(args.allowlist)
	passwords = scan_mission_access(roster, content_dir)
	engine_dir = engine.parent
	player_file = DEFAULT_PLAYER_FILE.resolve() if args.playerful else None
	if args.playerful and not player_file.is_file():
		die(f"player file not found: {player_file}")

	# One grant-config copy per job slot: the engine saves the full config
	# back into the /config: file at startup (Config.Save), so two
	# concurrent engines must never share one file.
	tmpdir = Path(tempfile.mkdtemp(prefix="playtest_grant_"))
	try:
		slots = []
		for i in range(args.jobs):
			cfg = tmpdir / f"grant_{i}.cfg"
			write_grant_config(cfg, passwords)
			slots.append(cfg)
		slot_lists: list[list[str]] = [[] for _ in range(args.jobs)]
		for i, rel in enumerate(roster):
			slot_lists[i % args.jobs].append(rel)
		results: dict[str, dict] = {}

		def run_slot(slot: int) -> None:
			for rel in slot_lists[slot]:
				res = run_scenario(args, engine, engine_dir, slots[slot],
					rel, player_file)
				results[rel] = res
				print(f"[{len(results)}/{len(roster)}] {res['cls']:<12} "
					f"{rel} ({res['wall']:.1f}s)")

		if args.jobs == 1:
			run_slot(0)
		else:
			with ThreadPoolExecutor(max_workers=args.jobs) as pool:
				list(pool.map(run_slot, range(args.jobs)))
	finally:
		shutil.rmtree(tmpdir, ignore_errors=True)

	rows = []
	counts: dict[str, int] = {}
	failed = 0
	for rel in roster:
		res = results[rel]
		cls = res["cls"]
		if rel in allow:
			cls = "PASS-STALE" if cls == "PASS" else "KNOWN-RED"
		counts[cls] = counts.get(cls, 0) + 1
		if cls in ("FAIL", "CRASH", "TIMEOUT", "OVER-BUDGET"):
			failed += 1
		if cls == "PASS-STALE":
			print(f"HINT: remove PASSING scenario from allowlist: {rel}")
		rows.append((rel, cls, res["rc"], res["wall"], res["note"]))

	if args.report:
		try:
			report_f = open(args.report, "w", encoding="utf-8")
		except OSError as e:
			die(f"cannot write report {args.report}: {e}")
		with report_f as f:
			f.write("scenario\tclass\trc\twall_s\tnote\n")
			for rel, cls, rc, wall, note in rows:
				clean = lambda s: str(s).replace("\t", " ").replace("\n", " ")
				f.write("\t".join([clean(rel), clean(cls),
					clean("" if rc is None else rc), clean(f"{wall:.2f}"),
					clean(note)]) + "\n")

	print(f"\n{'scenario':<58} {'class':<12} {'rc':>4} {'wall_s':>7}  note")
	for rel, cls, rc, wall, note in rows:
		print(f"{rel:<58} {cls:<12} {'' if rc is None else rc:>4} "
			f"{wall:>7.2f}  {note}")
	summary = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
	print(f"\nplaytest sweep: {len(roster)} scenarios, {summary}")
	if failed:
		print(f"{failed} unexpected failure(s)")
		return 1
	return 0

if __name__ == "__main__":
	sys.exit(main())
