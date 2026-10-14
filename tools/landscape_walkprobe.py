#!/usr/bin/env python3
"""landscape_walkprobe — generic headless terrain-corridor probe (cycle 232).

Boots ANY scenario headless and asserts a clonk-reachable surface corridor
exists in the generated terrain BEFORE build cycles burn runs on it
(roadmap Epic 7; the cycle-226 SaltRoad04 bozo-belt lesson: 5-18 of 23
sampled columns had GroundY==0 — ceiling-touching walls — on every seed).

Protocol (adapted from the cycle-226 scratch probes):
  - Boot argv (scratch/226 walkprobe_v1.py): the console entry shape
    ("/console --console" flips the engine into DebugMode so the stdin
    /script seam exists) plus the frame-rate cap and the pinned Seed,
    joining ONE TestPlayer fixture — copied to a fresh temp file first
    (writeback isolation: the engine writes player state back into any
    .c4p it joins on game over).
  - The console stdin reader drops lines raced with startup, so every
    sample is RESENT until the engine answers it (~0.3 s cadence, the
    walkprobe_v1 resend discipline). Single-%d Format forms only: the
    %%-escaped forms are mangled by the seam (fmt_probe.log finding).
  - First /script Log(Format("LW %d", LandscapeWidth())) to learn the map
    width (optionally --query-lh also asks Log(Format("LH %d",
    LandscapeHeight())) the same way), then the GroundY batch across the
    requested band; each answered sample echoes "GY <x> <y>" into the
    engine log, which is polled.

GroundY is NOT engine-generic: it is a global func defined by the
SaltRoad04 scenario script (cycle-232 finding — Outset.c4s answers the
seam with "unknown identifier: GroundY"), and the console seam is parsed
expression-only (C4AulParse.cpp ParseFn fExprOnly=true — no var, no
statements). So the probe sends, per column, ONE self-contained
arithmetic expression over the engine-global GBackSolid that computes
the first solid y within the passable window [y_start, y_start+height)
— anchored at --y-start (default 0 = map top; the generated expression
is byte-identical to the cycle-232 one then):

  GY' = height*(1-Min(1, S)) + sum_{y=1..height-1} y*s(y)*(1-Min(1, s(0)+..+s(y-1)))

where s(y) = GBackSolid(x, y_start+y) and S = s(0)+..+s(height-1). GY'
is the first-solid OFFSET FROM THE WINDOW TOP (absolute surface y =
y_start + GY'), and = height when the window is solid-free. The verdict
rule "passable iff GY >= height" and the GY=0 window-top-touching
headline are unchanged; the exact depth beyond the window does not
affect the corridor verdict. --query-lh (optional, non-breaking) makes
the probe additionally ask LandscapeHeight() over the seam and report
it as a note, mirroring the LW resend pattern.

Analysis: a sample column is PASSABLE iff GY >= --height (the walker fits
under the sky; GY==0 columns are ceiling-touching walls). The corridor is
the longest contiguous passable run * --step in px. Every requested sample
must be answered (coverage assert). Verdict lines are exactly
"landscape_walkprobe PASS" / "landscape_walkprobe FAIL (...)" so CTest's
PASS_REGULAR_EXPRESSION targets them; exit 0 only on a full pass.

The raw engine log is saved to --out-log for evidence.

Python 3 stdlib only.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYER_FIXTURE = os.path.join(REPO_DIR, "tests", "fixtures", "TestPlayer.c4p")

SMOKE_RUN = "9000"     # the cycle-226 probe budget: sampling ends long before
RESEND_INTERVAL = 0.3  # s between resends of unanswered samples
BATCH_SPACING = 0.02   # s between initial sends of the sample batch

GAME_STARTED_RE = re.compile(r"Game started\.")

LW_RE = re.compile(r"\[info\] LW (\d+)\s*$", re.MULTILINE)
LH_RE = re.compile(r"\[info\] LH (\d+)\s*$", re.MULTILINE)
GY_RE = re.compile(r"\[info\] GY (\d+) (-?\d+)\s*$", re.MULTILINE)

def parse_args(argv=None):
	parser = argparse.ArgumentParser(
		description="Generic terrain-corridor walkability probe")
	parser.add_argument("--engine", required=True,
	                    help="path to the clonk binary")
	parser.add_argument("--content-dir", required=True,
	                    help="content checkout root")
	parser.add_argument("--scenario", required=True,
	                    help="scenario path relative to the content dir "
	                         "(e.g. Worlds.c4f/Outset.c4s)")
	parser.add_argument("--seed", required=True, type=int,
	                    help="pinned landscape seed (deterministic map)")
	parser.add_argument("--height", type=int, default=26,
	                    help="min open sky above ground for a passable "
	                         "column (default 26, camel-scale; clonk-scale "
	                         "20 also plausible)")
	parser.add_argument("--x-start", type=int, default=None,
	                    help="first sampled column (default 0)")
	parser.add_argument("--x-end", type=int, default=None,
	                    help="last sampled column (default map width - 1)")
	parser.add_argument("--step", type=int, default=20,
	                    help="sampling stride in px (default 20)")
	parser.add_argument("--y-start", type=int, default=0,
	                    help="absolute map-y anchor of the GY window "
	                         "(default 0 = map top). GY reports the "
	                         "first-solid offset from y_start; a column "
	                         "is passable iff no solid lies within "
	                         "[y_start, y_start+height)")
	parser.add_argument("--query-lh", action="store_true",
	                    help="additionally ask LandscapeHeight() over the "
	                         "seam and report it as a note (mirrors the "
	                         "LW resend pattern)")
	parser.add_argument("--min-run-px", required=True, type=int,
	                    help="min acceptable corridor length in px")
	parser.add_argument("--timeout", type=int, default=240,
	                    help="wall-clock cap in s for the whole sampling "
	                         "phase (default 240)")
	parser.add_argument("--out-log", default=None,
	                    help="where to save the raw engine log")
	return parser.parse_args(argv)

class Sample:
	__slots__ = ("x", "y", "answered")

	def __init__(self, x):
		self.x = x
		self.y = None
		self.answered = False

def run_probe(args):
	"""Boot the engine, harvest LW + the GY batch; return (samples, lw, notes).

	notes is a list of non-fatal observations (readiness wait, resend counts).
	"""
	workdir = tempfile.mkdtemp(prefix="landscape_walkprobe_")
	fixture = os.path.join(workdir, "TestPlayer.c4p")
	shutil.copyfile(PLAYER_FIXTURE, fixture)
	scenario = os.path.join(args.content_dir, args.scenario)
	if args.out_log:
		log_path = os.path.abspath(args.out_log)
		os.makedirs(os.path.dirname(log_path), exist_ok=True)
	else:
		log_path = os.path.join(workdir, "engine.log")
	logf = open(log_path, "w", encoding="utf-8")
	try:
		cmd = [args.engine, "/console", "--console",
		       "--smoke-run", SMOKE_RUN, "--frame-rate-cap", "1000",
		       "--parameter", "Seed=%d" % args.seed,
		       "-s", scenario, fixture]
		proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=logf,
		                        stderr=subprocess.STDOUT,
		                        cwd=args.content_dir,
		                        encoding="utf-8", errors="replace")
	except OSError as e:
		logf.close()
		shutil.rmtree(workdir, ignore_errors=True)
		raise RuntimeError("spawn error: %s" % e)

	notes = []

	def send(line):
		try:
			proc.stdin.write(line + "\n")
			proc.stdin.flush()
			return True
		except (BrokenPipeError, OSError, ValueError):
			return False

	def log_text():
		try:
			with open(log_path, "r", errors="replace") as rf:
				return rf.read()
		except OSError:
			return ""

	def new_samples(lw):
		x_start = args.x_start if args.x_start is not None else 0
		x_end = args.x_end if args.x_end is not None else lw - 1
		x_end = min(x_end, lw - 1)
		return [Sample(x) for x in range(x_start, x_end + 1, args.step)]

	def gy_line(x):
		"""One self-contained /script line per column (see docstring)."""
		y0 = args.y_start
		terms = []
		for y in range(1, args.height):
			above = "+".join("GBackSolid(%d,%d)" % (x, y0 + z)
			                 for z in range(y))
			terms.append("%d*GBackSolid(%d,%d)*(1-Min(1,%s))"
			             % (y, x, y0 + y, above))
		window = "+".join("GBackSolid(%d,%d)" % (x, y0 + z)
		                  for z in range(args.height))
		expr = "%d*(1-Min(1,%s))+%s" % (args.height, window,
		                                "+".join(terms))
		return '/script Log(Format("GY %%d %%d", %d, %s));' % (x, expr)

	samples = []
	lw = None
	lh = None
	lw_attempts = 0
	lh_attempts = 0
	lh_last = 0.0
	lw_last = [0.0]
	deadline = time.time() + args.timeout
	spawn_at = time.time()

	# Phase 1: wait for the engine's generic readiness line, then get LW.
	# The console stdin reader drops lines raced with startup; resend LW
	# every RESEND_INTERVAL until it is answered.
	while time.time() < deadline:
		if proc.poll() is not None:
			break
		txt = log_text()
		if lw is None:
			m = LW_RE.search(txt)
			if m:
				lw = int(m.group(1))
				samples = new_samples(lw)
				notes.append("LW=%d (%d samples)" % (lw, len(samples)))
				break
			if GAME_STARTED_RE.search(txt):
				# readiness reached but LW not answered yet: resend
				now = time.time()
				if now - lw_last[0] >= RESEND_INTERVAL:
					lw_last[0] = now
					lw_attempts += 1
					send('/script Log(Format("LW %d", '
					     'LandscapeWidth()));')
		time.sleep(0.002)

	if lw is not None:
		# Phase 2: send the GY batch, then resend missing samples until
		# all answered (or the deadline / engine exit).
		last_send = [0.0] * len(samples)

		def send_batch(initial):
			now = time.time()
			n = 0
			for i, s in enumerate(samples):
				if s.answered:
					continue
				if initial or now - last_send[i] >= RESEND_INTERVAL:
					last_send[i] = now
					send(gy_line(s.x))
					n += 1
					if initial:
						time.sleep(BATCH_SPACING)
						now = time.time()
			return n

		send_batch(initial=True)
		while any(not s.answered for s in samples) and time.time() < deadline:
			if proc.poll() is not None:
				break
			txt = log_text()
			# Optional LH echo (--query-lh): informational map height,
			# resent on the LW cadence until it is answered.
			if args.query_lh and lh is None:
				mlh = LH_RE.search(txt)
				if mlh:
					lh = int(mlh.group(1))
				elif time.time() - lh_last >= RESEND_INTERVAL:
					lh_last = time.time()
					lh_attempts += 1
					send('/script Log(Format("LH %d", '
					     'LandscapeHeight()));')
			for m in GY_RE.finditer(txt):
				x, y = int(m.group(1)), int(m.group(2))
				for s in samples:
					if s.x == x and not s.answered:
						s.x, s.y, s.answered = x, y, True
			send_batch(initial=False)
			time.sleep(0.002)
		notes.append("LW resends: %d" % lw_attempts)

	# Sampling done (or hopeless): terminate the engine.
	if proc.poll() is None:
		proc.kill()
	try:
		proc.wait(timeout=15)
	except subprocess.TimeoutExpired:
		pass
	try:
		proc.stdin.close()
	except (BrokenPipeError, OSError, ValueError):
		pass
	logf.close()

	# Final harvest (the engine may have answered lines between polls).
	txt = log_text()
	if lw is None:
		m = LW_RE.search(txt)
		if m:
			lw = int(m.group(1))
			samples = new_samples(lw)
			notes.append("LW=%d harvested after exit" % lw)
	for m in GY_RE.finditer(txt):
		x, y = int(m.group(1)), int(m.group(2))
		for s in samples:
			if s.x == x and not s.answered:
				s.x, s.y, s.answered = x, y, True
	if args.query_lh and lh is None:
		mlh = LH_RE.search(txt)
		if mlh:
			lh = int(mlh.group(1))
	if args.query_lh:
		if lh is not None:
			notes.append("LH=%d (LH resends: %d)"
			             % (lh, lh_attempts))
		else:
			notes.append("LH: no echo (never answered)")

	shutil.rmtree(workdir, ignore_errors=True)
	return samples, lw, notes, log_path

def analyze(args, samples, lw):
	"""Print per-assert lines; return the failure list."""
	failures = []
	if lw is None:
		print("map width: FAIL (no LW echo — engine never reached the "
		      "console seam)")
		failures.append("no LW echo")
		return failures
	print("map width: PASS (LW=%d, %d samples at step %d)"
	      % (lw, len(samples), args.step))

	unanswered = [s.x for s in samples if not s.answered]
	if unanswered:
		print("coverage: FAIL (%d of %d samples unanswered, e.g. x=%s)"
		      % (len(unanswered), len(samples), unanswered[:5]))
		failures.append("coverage %d/%d unanswered"
		                % (len(unanswered), len(samples)))
	else:
		print("coverage: PASS (%d/%d samples answered)"
		      % (len(samples), len(samples)))

	if not samples:
		failures.append("empty sample band")
		return failures
	if unanswered:
		# A corridor through partially-unknown ground proves nothing.
		return failures

	ceilings = sum(1 for s in samples if s.y == 0)
	blocked = [s.x for s in samples if s.y < args.height]
	best_len = 0
	best_span = None
	run = 0
	run_start = None
	for s in samples:
		if s.y >= args.height:
			if run == 0:
				run_start = s.x
			run += 1
			if run > best_len:
				best_len = run
				best_span = (run_start, s.x)
		else:
			run = 0
	corridor_px = best_len * args.step
	print("columns: %d ceiling-touching (GY=0), %d blocked below height "
	      "%d of %d" % (ceilings, len(blocked), args.height, len(samples)))
	if best_span:
		print("corridor: longest passable run x=%d..%d = %d samples = "
		      "%d px" % (best_span[0], best_span[1], best_len,
		                 corridor_px))
	else:
		print("corridor: FAIL (no passable column at all)")
	if corridor_px >= args.min_run_px:
		print("corridor length: PASS (%d px >= min-run-px %d)"
		      % (corridor_px, args.min_run_px))
	else:
		print("corridor length: FAIL (%d px < min-run-px %d)"
		      % (corridor_px, args.min_run_px))
		failures.append("corridor %d px < min-run-px %d"
		                % (corridor_px, args.min_run_px))
	return failures

def main(argv=None):
	args = parse_args(argv)
	args.engine = os.path.abspath(args.engine)
	args.content_dir = os.path.abspath(args.content_dir)

	samples, lw, notes, log_path = run_probe(args)
	for n in notes:
		print("note: %s" % n)
	failures = analyze(args, samples, lw)

	if args.out_log:
		print("engine log: %s" % log_path)

	if failures:
		print("landscape_walkprobe FAIL (%d failure(s): %s)"
		      % (len(failures), "; ".join(failures)))
		return 1
	print("landscape_walkprobe PASS")
	return 0

if __name__ == "__main__":
	sys.exit(main())
