#!/usr/bin/env python3
"""Relative-determinism driver for the LandscapeSeed smoke scenario.

WHY relative and not a pinned absolute checksum:

The classic map creator chain contains double-precision floating point
(e.g. the Julia overlay at src/C4MapCreatorS2.cpp:1442-1446, the AlgoSin
script binding at :1594), so the generated landscape - and therefore any
checksum over it - is build/machine-dependent. The failure that motivated
this redesign: the Playtest CI lane computed 94780 for Seed=3373 while a
local build computed 464412 (stable across 3+ engine invocations), with
identical texture/material tables and a zero-initialized surface. The map
generator output being machine-dependent is engine-inherent and tolerated
by the netcode (the host generates the map and syncs it; peers do not
regenerate their own copy), so no absolute baked checksum can be shipped.

This driver pins the machine-independent contract instead:

  A == B  two runs with the SAME seed produce the SAME checksum
          (per-machine determinism of the --parameter Seed plumbing)
  C != A  a DIFFERENT seed produces a DIFFERENT checksum
          (seed-sensitivity, non-vacuity)
  D != A  same seed, different Amplitude= override produces a DIFFERENT
          checksum (Amplitude-override end-to-end non-vacuity)

The scenario's FxRunTestTimer is log-only (it prints "LandscapeSeed
checksum: %d" and "LandscapeSeed PASS", then GameOver); the driver parses
the checksum and enforces the three assertions above.

Each engine run goes through tools/run_engine_headless.py (the stdin=DEVNULL
wrapper), with the engine's working directory set to the clonk binary's
directory so the build-dir content-pack symlinks resolve. --smoke-run 70
suffices: the effect fires once at tick 35 and GameOver()s.
"""
import os
import re
import subprocess
import sys

CHECKSUM_RE = re.compile(r"LandscapeSeed checksum: (\d+)")
PASS_LINE = "LandscapeSeed PASS"
RUN_TIMEOUT = 60  # seconds, per engine invocation
RUN_TICKS = "70"

# Run id -> --parameter overrides. A and B are identical runs that must yield
# identical checksums; C varies the seed, D varies the amplitude.
RUNS = [
    ("A", ["--parameter", "Seed=3373", "--parameter", "Amplitude=45"]),
    ("B", ["--parameter", "Seed=3373", "--parameter", "Amplitude=45"]),
    ("C", ["--parameter", "Seed=3374", "--parameter", "Amplitude=45"]),
    ("D", ["--parameter", "Seed=3373", "--parameter", "Amplitude=60"]),
]

def run_engine(wrapper, clonk, scenario, overrides, engine_cwd):
    """Run the engine once; return (checksum, pass_seen, diagnostic_tail)."""
    cmd = ([sys.executable, wrapper, clonk, "--console", "--smoke-run", RUN_TICKS]
           + overrides + ["-s", scenario])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=engine_cwd, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, False, "engine run timed out after %d s" % RUN_TIMEOUT
    stdout = proc.stdout or ""
    match = CHECKSUM_RE.search(stdout)
    checksum = int(match.group(1)) if match else None
    passed = PASS_LINE in stdout
    if checksum is None or not passed:
        return None, False, "checksum/PASS line missing; output tail:\n" + stdout[-800:]
    return checksum, True, ""

def main(argv):
    if len(argv) != 3:
        print("usage: %s <clonk-binary> <scenario.c4s>" % os.path.basename(argv[0]),
              file=sys.stderr)
        return 2
    _, clonk, scenario = argv
    wrapper = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "run_engine_headless.py")
    clonk = os.path.abspath(clonk)
    scenario = os.path.abspath(scenario)
    engine_cwd = os.path.dirname(clonk)

    checksums = {}
    for run_id, overrides in RUNS:
        checksum, passed, diagnostic = run_engine(wrapper, clonk, scenario,
                                                  overrides, engine_cwd)
        if not passed:
            print("landscape_seed_smoke FAIL: run %s (%s) failed: %s"
                  % (run_id, " ".join(overrides), diagnostic))
            return 1
        checksums[run_id] = checksum

    a, b, c, d = checksums["A"], checksums["B"], checksums["C"], checksums["D"]
    failures = []
    if a != b:
        failures.append("A == B (same-seed determinism)")
    if c == a:
        failures.append("C != A (seed sensitivity)")
    if d == a:
        failures.append("D != A (Amplitude sensitivity)")
    if failures:
        print("landscape_seed_smoke FAIL: %s" % "; ".join(failures))
        print("  A(Seed=3373,Amplitude=45)=%s  B(Seed=3373,Amplitude=45)=%s  "
              "C(Seed=3374,Amplitude=45)=%s  D(Seed=3373,Amplitude=60)=%s"
              % (a, b, c, d))
        return 1

    print("landscape_seed_smoke PASS (same-seed deterministic, seed- and amplitude-sensitive)")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
