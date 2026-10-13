#!/usr/bin/env python3
"""saltroad04_round_gate — permanent two-leg CTest gate for the REAL
SaltRoad04.c4s round (cycle 226, desert-campaign Act IV "The Salt Run").

frontier_cove_round_gate.py shape: each leg spawns the engine with the
literal "/console" argv (REQUIRED for the stdin /script seam — it flips
isFullScreen -> DebugMode -> /script ungated; construct-gate findings),
a fresh TestPlayer fixture copy per leg (writeback isolation), pinned
Seed=226 and --smoke-run 9000.

  Leg LOSE — on the intro marker the driver sends ONE /script
  expression removing both camels (engine globals only: FindObject +
  RemoveObject chain). The director's defeat watch must fire next tick:
  message, Log("Salt Road Act IV: the caravan is lost."), GameOver().

  Leg WON — on the intro marker the driver sends ONE /script expression
  calling the scenario-global gate hook SaltRoad04_LoadCargo(3) (3 SALT
  into each of the two camels = 6 riding). The director's own departure
  check must fire Depart() -- the gate exercises the REAL departure
  trigger, not a puppet shortcut -- the caravan crosses the ambush
  thresholds, and the win re-check must resolve the round won:
  Log("Salt Road Act IV: N SALT delivered at the market.", N >= 6).

Asserts per leg (LOSE: drive marker + defeat line + exit 0 + zero
FatalError/[error]/[fatal] lines; WON: drive marker + departure line +
victory line with a >= 6 delivered count + exit 0 + zero error lines).
The driver owns fail detection: one line per assertion plus the
aggregate `saltroad04_round_gate PASS` line that CTest's
PASS_REGULAR_EXPRESSION targets, and exits 0 only on a full pass.

Timing: the /script drive takes ~65-110 ticks to dispatch (control
queue, cycle-217 T3 findings), so it is sent within ticks of the intro
marker; the director ticks every 35 frames, so the watches resolve
within ~35-70 frames of the drive executing. The 9000-frame budget
covers the ~1180 px crossing with ambushes (the wprobe precedent,
pinned to observed-arrival + headroom after the first green run).

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

SMOKE_RUN = "9000"       # crossing budget: depart -> ambushes -> market
SEED = "226"             # pinned act seed (deterministic generated map)
POLL = 0.0005            # driver cadence (marker -> drive-send window)
LEG_TIMEOUT = 240        # per-leg wall bound; CTest TIMEOUT is 600

SCEN_REL = os.path.join("SaltRoad.c4f", "SaltRoad04.c4s")

ERROR_LOG_RE = re.compile(r"FatalError|\[error\]|\[fatal\]")

# The intro marker: the scenario's first Log line (Initialize).
INTRO_RE = re.compile(r"Salt Road Act IV: the salt run begins\.")

# The drives (expression-only; guarded &&-chains). Engine-globals-only
# for LOSE; WON calls the scenario-global gate hook (the /script seam
# executes in the Game.Script host, so scenario globals resolve).
LOSE_DRIVE = ('/script RemoveObject(FindObject(CAML)) && '
              'RemoveObject(FindObject(CAML)) && '
              'Log("SALTGATE:camels_removed")')
WIN_DRIVE = ('/script SaltRoad04_LoadCargo(3) && '
             'Log("SALTGATE:cargo_loaded")')

DRIVE_MARKER_RE = re.compile(r"SALTGATE:(?:camels_removed|cargo_loaded)\b")
DEPARTURE_RE = re.compile(r"Salt Road Act IV: the caravan rides east\.")
DEFEAT_RE = re.compile(r"Salt Road Act IV: the caravan is lost\.")
# Victory line with a delivered count of at least 6: single digits 6-9
# or any multi-digit count (SALTROAD4_DELIVERY is the win threshold).
VICTORY_RE = re.compile(
    r"Salt Road Act IV: (?:[6-9]|[1-9][0-9]+) SALT delivered at the market\.")

LEG1_ASSERTS = [
    ("camels removed", DRIVE_MARKER_RE),
    ("defeat line", DEFEAT_RE),
]
LEG2_ASSERTS = [
    ("cargo loaded", DRIVE_MARKER_RE),
    ("departure line", DEPARTURE_RE),
    ("victory line", VICTORY_RE),
]


def run_leg(engine, content_dir, out_log, drive, asserts):
    """Run one SaltRoad04 round; return (rc, log) or (None, msg).

    drive: the /script expression to send once the intro marker appears.
    The TestPlayer fixture is copied to a fresh temp file first: the
    engine writes player state back into any .c4p it joins on game over
    (run_engine_headless fixture-copy pattern).
    """
    workdir = tempfile.mkdtemp(prefix="saltroad04_round_")
    fixture = os.path.join(workdir, "TestPlayer.c4p")
    shutil.copyfile(PLAYER_FIXTURE, fixture)
    scenario = os.path.join(content_dir, SCEN_REL)
    cmd = [engine, "/console", "--console", "--smoke-run", SMOKE_RUN,
           "--frame-rate-cap", "1000", "--parameter", "Seed=" + SEED,
           "-s", scenario, fixture]
    logf = open(out_log, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=logf,
                                stderr=subprocess.STDOUT, cwd=content_dir,
                                encoding="utf-8", errors="replace")
    except OSError as e:
        logf.close()
        shutil.rmtree(workdir, ignore_errors=True)
        return None, "spawn error: %s" % e

    sent_drive = False
    deadline = time.time() + LEG_TIMEOUT
    try:
        while True:
            if proc.poll() is not None:
                break
            if time.time() > deadline:
                proc.kill()
                proc.wait()
                logf.close()
                shutil.rmtree(workdir, ignore_errors=True)
                return None, "<TIMEOUT after %ds>" % LEG_TIMEOUT
            # Whole-file read per poll (NOT seek-incremental): a
            # seek-based reader can split a line across poll boundaries
            # -- the marker's prefix is consumed by one read and the
            # rest by the next, so the guarded substring never matches
            # and the drive is silently never sent (cycle-217 T3
            # finding). The log is small, so re-reading is free.
            with open(out_log, "r", errors="replace") as rf:
                txt = rf.read()
            if drive and not sent_drive and INTRO_RE.search(txt):
                _write(proc, drive)
                sent_drive = True
            time.sleep(POLL)
    finally:
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()
        logf.close()
        with open(out_log, "r", errors="replace") as rf:
            log = rf.read()
        shutil.rmtree(workdir, ignore_errors=True)
    return rc, log


def _write(proc, line):
    if proc.poll() is not None:
        return
    try:
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass


def check_leg(name, rc, log, asserts):
    """Print one line per assertion; return the failure list."""
    failures = []
    if rc is None:
        print("%s spawn: FAIL (%s)" % (name, log))
        return ["%s spawn/timeout" % name]
    if rc != 0:
        print("%s exit: FAIL (rc=%s, expected 0)" % (name, rc))
        failures.append("%s exit %s" % (name, rc))
    else:
        print("%s exit: PASS (rc=0, %d log lines)" % (name, len(log.splitlines())))
    for aname, pat in asserts:
        if pat.search(log):
            print("assert %s: PASS" % aname)
        else:
            print("assert %s: FAIL (%r not found)" % (aname, pat.pattern))
            failures.append("assert %s" % aname)
    errs = ERROR_LOG_RE.findall(log)
    if errs:
        print("%s fatal/error lines: FAIL (%d matches, e.g. %r)" % (name, len(errs), errs[:3]))
        failures.append("%s error lines" % name)
    else:
        print("%s fatal/error lines: PASS (0 matches)" % name)
    return failures


def main():
    parser = argparse.ArgumentParser(description="SaltRoad04 round gate")
    parser.add_argument("--engine", required=True, help="path to the clonk binary")
    parser.add_argument("--content-dir", required=True, help="content checkout root")
    args = parser.parse_args()

    engine = os.path.abspath(args.engine)
    content_dir = os.path.abspath(args.content_dir)
    tmpdir = tempfile.gettempdir()

    failures = []

    # Leg 1: driven LOSE (both camels removed on the intro marker).
    out1 = os.path.join(tmpdir, "saltroad04_round_gate_leg1_%d.log" % os.getpid())
    rc1, log1 = run_leg(engine, content_dir, out1, LOSE_DRIVE, LEG1_ASSERTS)
    failures += check_leg("leg1 LOSE", rc1, log1, LEG1_ASSERTS)

    # Leg 2: driven WON (the LoadCargo gate hook; the director's own
    # departure check fires Depart()).
    out2 = os.path.join(tmpdir, "saltroad04_round_gate_leg2_%d.log" % os.getpid())
    rc2, log2 = run_leg(engine, content_dir, out2, WIN_DRIVE, LEG2_ASSERTS)
    failures += check_leg("leg2 WON", rc2, log2, LEG2_ASSERTS)

    if failures:
        print("saltroad04_round_gate FAIL (%d failure(s): %s)" % (len(failures), ", ".join(failures)))
        return 1
    print("saltroad04_round_gate PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
