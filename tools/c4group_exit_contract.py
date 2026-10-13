#!/usr/bin/env python3
"""c4group_exit_contract — permanent exit-code contract gate for the c4group
tool (cycle 228, Epic 7 item 2).

Pins BOTH directions of the exit-code contract:
  - ok case:   `c4group <planet>/Graphics.c4g -l` exits 0 (a clean list op
               on the git-tracked directory-form pack, self-contained — no
               content-repo dependency);
  - fail case: `c4group <garbage> -l` exits NON-zero (a 100-byte garbage
               fixture fails the group magic check in C4Group::OpenReal —
               "Not a valid group" — and the tool must surface that as a
               non-zero exit, not the pre-cycle-228 always-0 `iResult`).

The driver owns fail detection: one PASS/FAIL line per case plus the
aggregate `c4group_exit_contract PASS` line that CTest's
PASS_REGULAR_EXPRESSION targets, exiting 0 only when both cases hold.

Python 3 stdlib only.
"""
import argparse
import os
import subprocess
import sys
import tempfile

FIXTURE_SIZE = 100  # bytes of 'x' — valid size, invalid magic
CASE_TIMEOUT = 30   # wall bound per c4group invocation

def run_case(c4group, pack, out_log):
	"""Run one `c4group <pack> -l`; return (rc, log) or (None, msg) on error."""
	cmd = [c4group, pack, "-l"]
	logf = open(out_log, "w", encoding="utf-8")
	try:
		proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=logf,
			stderr=subprocess.STDOUT)
	except OSError as e:
		logf.close()
		return None, "spawn error: %s" % e
	timed_out = False
	try:
		try:
			rc = proc.wait(timeout=CASE_TIMEOUT)
		except subprocess.TimeoutExpired:
			timed_out = True
			proc.kill()
			rc = proc.wait()
	finally:
		logf.close()
		with open(out_log, "r", errors="replace") as rf:
			log = rf.read()
	if timed_out:
		return None, "<TIMEOUT after %ds>" % CASE_TIMEOUT
	return rc, log

def main():
	parser = argparse.ArgumentParser(description="c4group exit-code contract gate")
	parser.add_argument("--c4group", required=True, help="path to the c4group binary")
	parser.add_argument("--planet", required=True, help="path to the planet/ dir (owns Graphics.c4g)")
	args = parser.parse_args()

	c4group = os.path.abspath(args.c4group)
	graphics = os.path.join(os.path.abspath(args.planet), "Graphics.c4g")
	tmpdir = tempfile.gettempdir()
	out_log = os.path.join(tmpdir, "c4group_exit_contract_%d.log" % os.getpid())

	failures = []

	# ok case: clean list op on the tracked pack must exit 0
	rc, log = run_case(c4group, graphics, out_log)
	if rc is None:
		print("ok case (Graphics.c4g -l): FAIL (%s)" % log)
		failures.append("ok case spawn/timeout")
	elif rc != 0:
		print("ok case (Graphics.c4g -l): FAIL (rc=%s, expected 0; log tail: %r)"
			% (rc, log.splitlines()[-3:]))
		failures.append("ok case rc %s" % rc)
	else:
		print("ok case (Graphics.c4g -l): PASS (rc=0, %d log lines)"
			% len(log.splitlines()))

	# fail case: garbage-bytes fixture must exit non-zero
	fixture_dir = tempfile.mkdtemp(prefix="c4group_exit_contract_")
	try:
		fixture = os.path.join(fixture_dir, "garbage.c4g")
		with open(fixture, "wb") as f:
			f.write(b"x" * FIXTURE_SIZE)
		rc, log = run_case(c4group, fixture, out_log)
		if rc is None:
			print("fail case (garbage -l): FAIL (%s)" % log)
			failures.append("fail case spawn/timeout")
		elif rc == 0:
			print("fail case (garbage -l): FAIL (rc=0 on garbage fixture — "
				"exit-code contract broken; log tail: %r)"
				% log.splitlines()[-3:])
			failures.append("fail case rc 0 on garbage")
		else:
			print("fail case (garbage -l): PASS (rc=%s on garbage fixture)" % rc)
	finally:
		import shutil
		shutil.rmtree(fixture_dir, ignore_errors=True)

	if failures:
		print("c4group_exit_contract FAIL (%d failure(s): %s)"
			% (len(failures), ", ".join(failures)))
		return 1
	print("c4group_exit_contract PASS")
	return 0

if __name__ == "__main__":
	sys.exit(main())
