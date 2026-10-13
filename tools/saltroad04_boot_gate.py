#!/usr/bin/env python3
"""saltroad04_boot_gate — permanent x3 boot-clean CTest gate for the REAL
SaltRoad04.c4s (cycle 226, desert-campaign Act IV "The Salt Run").

Boots the scenario headless three times (the boots-clean bar: min 3
zero-error boots) and asserts per boot:
  - engine exit code 0
  - zero FatalError/[error]/[fatal] log lines
  - zero "(placement defect)" lines (the scenario's permanent pan and
    quarry placement pins -- both log through the same wording)
  - the scenario intro line ("Salt Road Act IV: the salt run begins.")

Each boot joins one TestPlayer fixture; the engine writes player state
back into any .c4p it joins on game over, so the fixture is copied to a
fresh temp file per boot before it is passed (writeback isolation, the
run_engine_headless fixture-copy pattern).

Passive gate: unlike the round gate it never drives the engine's stdin
(/script seam), so the argv does NOT carry the literal "/console" toggle
that flips the engine into DebugMode — it is the plain smoke-entry argv
shape plus the frame-rate cap, with the pinned Seed=226 keeping the
generated map deterministic per binary.

The driver owns fail detection: one PASS/FAIL line per assertion plus
the aggregate `saltroad04_boot_gate PASS` line that CTest's
PASS_REGULAR_EXPRESSION targets, exiting 0 only on a full pass.

Python 3 stdlib only.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYER_FIXTURE = os.path.join(REPO_DIR, "tests", "fixtures", "TestPlayer.c4p")

SMOKE_RUN = "350"      # smoke-entry budget: the skeleton completes long before
SEED = "226"           # pinned act seed (deterministic generated map)
BOOTS = 3              # the boots-clean bar: min 3 zero-error boots
BOOT_TIMEOUT = 90      # per-boot wall bound (350 ticks @ cap 1000 is seconds)

SCEN_REL = os.path.join("SaltRoad.c4f", "SaltRoad04.c4s")

ERROR_LOG_RE = re.compile(r"FatalError|\[error\]|\[fatal\]")

PLACEMENT_DEFECT_RE = re.compile(r"\(placement defect\)")

INTRO_RE = re.compile(r"Salt Road Act IV: the salt run begins\.")


def run_boot(engine, content_dir, out_log):
    """Run one SaltRoad04 boot; return (rc, log) or (None, msg) on error.

    The TestPlayer fixture is copied to a fresh temp file per boot: the
    engine writes player state back into any .c4p it joins on game over
    (run_engine_headless.py docstring), so the pristine fixture must
    never be passed directly.
    """
    workdir = tempfile.mkdtemp(prefix="saltroad04_boot_")
    fixture = os.path.join(workdir, "TestPlayer.c4p")
    shutil.copyfile(PLAYER_FIXTURE, fixture)
    scenario = os.path.join(content_dir, SCEN_REL)
    cmd = [engine, "--console", "--smoke-run", SMOKE_RUN,
           "--frame-rate-cap", "1000", "--parameter", "Seed=" + SEED,
           "-s", scenario, fixture]
    logf = open(out_log, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=logf,
                                stderr=subprocess.STDOUT, cwd=content_dir)
    except OSError as e:
        logf.close()
        shutil.rmtree(workdir, ignore_errors=True)
        return None, "spawn error: %s" % e
    timed_out = False
    try:
        try:
            rc = proc.wait(timeout=BOOT_TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            rc = proc.wait()
    finally:
        logf.close()
        with open(out_log, "r", errors="replace") as rf:
            log = rf.read()
        shutil.rmtree(workdir, ignore_errors=True)
    if timed_out:
        return None, "<TIMEOUT after %ds>" % BOOT_TIMEOUT
    return rc, log


def check_boot(boot, rc, log):
    """Print one line per assertion; return the failure list."""
    failures = []
    if rc is None:
        print("boot %d: FAIL (%s)" % (boot, log))
        return ["boot %d timeout" % boot]
    if rc != 0:
        print("boot %d exit: FAIL (rc=%s, expected 0)" % (boot, rc))
        failures.append("boot %d exit %s" % (boot, rc))
    else:
        print("boot %d exit: PASS (rc=0, %d log lines)"
              % (boot, len(log.splitlines())))
    if INTRO_RE.search(log):
        print("boot %d intro line: PASS" % boot)
    else:
        print("boot %d intro line: FAIL (intro line not found)" % boot)
        failures.append("boot %d intro line" % boot)
    errs = ERROR_LOG_RE.findall(log)
    if errs:
        print("boot %d fatal/error lines: FAIL (%d matches, e.g. %r)"
              % (boot, len(errs), errs[:3]))
        failures.append("boot %d error lines" % boot)
    else:
        print("boot %d fatal/error lines: PASS (0 matches)" % boot)
    defects = PLACEMENT_DEFECT_RE.findall(log)
    if defects:
        print("boot %d placement-defect lines: FAIL (%d matches, e.g. %r)"
              % (boot, len(defects), defects[:3]))
        failures.append("boot %d placement defects" % boot)
    else:
        print("boot %d placement-defect lines: PASS (0 matches)" % boot)
    return failures


def main():
    parser = argparse.ArgumentParser(description="SaltRoad04 x3 boot-clean gate")
    parser.add_argument("--engine", required=True, help="path to the clonk binary")
    parser.add_argument("--content-dir", required=True, help="content checkout root")
    args = parser.parse_args()

    engine = os.path.abspath(args.engine)
    content_dir = os.path.abspath(args.content_dir)
    tmpdir = tempfile.gettempdir()

    failures = []
    for boot in range(1, BOOTS + 1):
        out_log = os.path.join(tmpdir, "saltroad04_boot_gate_%d_%d.log"
                               % (os.getpid(), boot))
        rc, log = run_boot(engine, content_dir, out_log)
        failures += check_boot(boot, rc, log)

    if failures:
        print("saltroad04_boot_gate FAIL (%d failure(s): %s)"
              % (len(failures), ", ".join(failures)))
        return 1
    print("saltroad04_boot_gate PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
