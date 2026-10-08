#!/usr/bin/env python3
"""frontier_outset_longboot_gate — permanent CTest gate for the v378 Outset flood
(cycle 208, chore frontier-outset-boot-gate).

Boots the REAL content/Worlds.c4f/Outset.c4s (the Free Game pin) for the full
16000-tick run with one TestPlayer fixture and asserts the FRMT flood telemetry
the shipped Outset logs on stdout:

  FRMT:flood_geom base_wy=210 wet_span=238   (onset geometry card, Script.c:240)
  FRMT:wy_peak=<WY>                          (highest water surface, Script.c:192)
  FRMT:wy_end=210                            (recede back to base, Script.c:204)
  FRMT:c3_verdict=...                        (drought verdict card, Script.c:343)
  FRMT:outcome=...                           (win/loss card, Script.c:369)

Value pins come from the v378-recorded baseline (scratch/205/t2c/long-boot.log,
natural pace, 432 s wall, wy_peak=170, wy_end=210, c3_verdict=lost banked=0,
outcome=LOSE, exit 0). D1 (cycle-208 measurement) confirmed the FRMT lines are
identical at --frame-rate-cap 1000, so the gate runs at the capped pace: wall
time drops from ~432 s to ~20 s and the CTest budget shrinks (TIMEOUT 600).

Engine spawns go through tools/run_engine_headless.py (stdin=DEVNULL + player
fixture copied to a per-run tempdir; engine-behavior-gotchas #6). The driver
owns fail detection (menu_walk_smoke / scenario_link_gate precedent): it prints
one line per assertion, then the aggregate `frontier_outset_longboot PASS` line
that CTest's PASS_REGULAR_EXPRESSION targets. Exit 0 only on a full pass.
CTest also carries a FAIL_REGULAR_EXPRESSION as defense-in-depth (the
baseline log is clean of those markers).

Python 3 stdlib only.
"""
import argparse
import os
import re
import subprocess
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_HEADLESS = os.path.join(REPO_DIR, "tools", "run_engine_headless.py")
PLAYER_FIXTURE = os.path.join(REPO_DIR, "tests", "fixtures", "TestPlayer.c4p")

SMOKE_RUN = "16000"
SEED = "199"

# Per-spawn subprocess budget (seconds). CTest TIMEOUT is 600; the spawn
# budget keeps 10% headroom so a stalled engine is reported as FAIL by the
# driver instead of being SIGKILLed by CTest (scenario_link_gate precedent).
SPAWN_TIMEOUT = 540

OUTSET_REL = os.path.join("Worlds.c4f", "Outset.c4s")

# (name, regex) — every pattern must be found in the captured engine log.
ASSERTS = [
    ("flood_geom card",       re.compile(r"FRMT:flood_geom base_wy=210\b")),
    ("wy_peak pin",           re.compile(r"FRMT:wy_peak=170\b")),
    ("wy_end pin",            re.compile(r"FRMT:wy_end=210\b")),
    ("c3_verdict card",       re.compile(r"FRMT:c3_verdict=")),
    ("outcome card",          re.compile(r"FRMT:outcome=")),
]
ERROR_LOG_RE = re.compile(r"FatalError|\[error\]|\[fatal\]")


def boot(engine, content_dir):
    """Spawn the engine once; return (rc, log) or (None, msg) on timeout."""
    cmd = [
        sys.executable, RUN_HEADLESS, engine,
        "--console", "--smoke-run", SMOKE_RUN,
        "--parameter", "Seed=" + SEED,
        "--frame-rate-cap", "1000",
        "--smoke-player-fixture", PLAYER_FIXTURE,
        "-s", os.path.join(content_dir, OUTSET_REL),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=content_dir,
            stdin=subprocess.DEVNULL, timeout=SPAWN_TIMEOUT,
            encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, "<TIMEOUT after %ds>" % SPAWN_TIMEOUT
    log = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, log


def main():
    parser = argparse.ArgumentParser(description="frontier_outset_longboot gate driver")
    parser.add_argument("--engine", required=True, help="path to the clonk binary")
    parser.add_argument("--content-dir", required=True, help="content checkout root")
    args = parser.parse_args()

    engine = os.path.abspath(args.engine)
    content_dir = os.path.abspath(args.content_dir)
    failures = []

    rc, log = boot(engine, content_dir)
    if rc is None:
        print("long-boot spawn: FAIL (%s)" % log)
        failures.append("spawn timeout")
    else:
        lines = len(log.splitlines())
        if rc != 0:
            print("long-boot exit: FAIL (rc=%s, expected 0; %d log lines)" % (rc, lines))
            failures.append("engine exit %s" % rc)
        else:
            print("long-boot exit: PASS (rc=0, %d log lines)" % lines)
        for name, pattern in ASSERTS:
            if pattern.search(log):
                print("assert %s: PASS" % name)
            else:
                print("assert %s: FAIL (pattern %r not found in log)"
                      % (name, pattern.pattern))
                failures.append("assert %s" % name)
        err_lines = ERROR_LOG_RE.findall(log)
        if err_lines:
            print("fatal/error lines: FAIL (%d matches, e.g. %r)"
                  % (len(err_lines), err_lines[:3]))
            failures.append("fatal/error log lines")
        else:
            print("fatal/error lines: PASS (0 matches)")

    if failures:
        print("frontier_outset_longboot FAIL (%d failure(s): %s)"
              % (len(failures), ", ".join(failures)))
        return 1
    print("frontier_outset_longboot PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
