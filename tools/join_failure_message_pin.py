#!/usr/bin/env python3
"""join_failure_message_pin.py -- join-failure message pin (upstream #91).

Launches the console engine with a bogus ``clonk://`` direct-join address
and asserts that a failed join (a) exits the engine non-zero and (b) logs
the join-failure reason line before exiting -- the console-side half of
the #91 fix. GUI builds additionally present the reason in a modal dialog
before the app exits (C4Game::ShowJoinFailureDlg, src/C4Game.cpp); this
pin pins the console contract: the reason must reach the player somehow,
and the exit code must stay non-zero (LogFatal semantics unchanged).

Hermetic child environment:
  * HOME -> a fresh tempdir, so a persisted ~/.legacyclonk/config cannot
    pin a non-English Language (C4Config::Load, src/C4Config.cpp:512-520);
  * locale -> C, so isGermanSystem() (src/C4Config.cpp:69-71) stays false
    and the engine defaults to the "US - English" string tables -- the
    reason-line assertion below greps the English text
    (planet/System.c4g/LanguageUS.txt: IDS_NET_REFQUERY_FAILED).

The address uses the reserved ``.invalid`` TLD (RFC 2606), so DNS fails
fast with NXDOMAIN and the engine logs
    FATAL ERROR: Could not query reference: <dns error>
within a second (no 20 s query-timeout wait).

Exit codes:
  0 -- PASS (engine exited non-zero AND the reason line is in the log).
  1 -- FAIL (one or both assertions failed; engine log echoed).
  2 -- infrastructure error (missing engine binary / usage).
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

# The join-failure reason for a bogus address, English string table:
# IDS_NET_REFQUERY_FAILED "Could not query reference: %s" -- the text of
# the LogFatal entry emitted by C4Game::InitNetworkFromAddress
# (src/C4Game.cpp). Case-insensitive: the engine capitalizes the spdlog
# line but the reason text keeps its own casing ("Could not query
# reference: ...").
REASON_RE = re.compile(r"Could not query reference", re.IGNORECASE)

def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		description="Join-failure message CTest pin (upstream #91).")
	parser.add_argument("--engine", required=True,
	                    help="Path to the clonk binary.")
	args = parser.parse_args(argv)

	engine_path = Path(args.engine).resolve()
	if not engine_path.is_file():
		print(f"ERROR: engine binary not found: {engine_path}",
		      file=sys.stderr)
		return 2

	home_dir = tempfile.mkdtemp(prefix="join_failure_pin_home_")
	env = dict(os.environ)
	env.update(HOME=home_dir, LC_ALL="C", LANG="C", LANGUAGE="C",
	           LC_MESSAGES="C")

	cmd = [str(engine_path), "--console",
	       "clonk://join-failure-pin.invalid"]
	print(f"engine: {shlex.join(cmd)}")

	try:
		proc = subprocess.run(cmd, cwd=engine_path.parent,
		                      stdout=subprocess.PIPE,
		                      stderr=subprocess.STDOUT,
		                      stdin=subprocess.DEVNULL, env=env,
		                      text=True, errors="replace", timeout=90)
	except subprocess.TimeoutExpired as exc:
		print("FAIL: engine did not exit within 90s")
		out = exc.stdout or ""
		if isinstance(out, bytes):
			out = out.decode(errors="replace")
		print("\n".join(out.splitlines()[-25:]))
		return 1

	out = proc.stdout or ""
	failures: list[str] = []
	if proc.returncode == 0:
		failures.append("engine exited 0; expected non-zero "
		                "(join failure must be fatal)")
	else:
		print(f"engine exit code: {proc.returncode} (expected non-zero)")

	if REASON_RE.search(out):
		print("reason line present: yes")
	else:
		failures.append("join-failure reason line not in engine log; "
		                f"expected a '{REASON_RE.pattern}' line")

	# Echo the fatal line(s) as evidence.
	for line in out.splitlines():
		if "critical" in line.lower():
			print(f"[engine] {line}")

	if failures:
		for failure in failures:
			print(f"FAIL: {failure}")
		print("--- engine log (tail) ---")
		print("\n".join(out.splitlines()[-25:]))
		return 1

	print("join_failure_message_pin PASS: non-zero exit and the "
	      "join-failure reason line present in the log.")
	return 0

if __name__ == "__main__":
	sys.exit(main())
