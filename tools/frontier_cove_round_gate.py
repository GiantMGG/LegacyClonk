#!/usr/bin/env python3
"""frontier_cove_round_gate — permanent two-leg CTest gate for the REAL
Breaker Cove round (cycle 217, roadmap frontier-cove).

Leg 1 (unattended LOSE): nothing is driven — the TestPlayer fixture crew
spawns over the open sea (seed-199 map: waterline ~wy=160, the crew falls
in and drowns at ~t=220-255) and never carries WOOD, so the stamped
tower stays dark through the fog window; the round must resolve lost and
print FRMT:outcome=LOSE.

Leg 2 (driven WON): on seeing FRMT:c1_darkstart=1 the driver sends ONE
/script expression that spawns a wood-carrying CLNK at the stamped tower
(FindObject(LHGT)-anchored, self-locating, seed-insensitive). The Cove's
scenario-side BCKindleCheck fires on the next director tick and relights
the beacon; the round must resolve won and print FRMT:outcome=WIN.

Timing (measured, seed-199 / this engine, cycle-217 T3 findings):
  - The fixture crew drowns ~8-11ms wall after FRMT:c1_darkstart=1 and
    the stdin /script channel closes with the player elimination
    (C4ControlScript::Execute resolves the eliminated player's section
    to nothing and drops the command silently -- no console echo).
  - A console command sent at the marker takes ~65-110 ticks to dispatch
    (control queue), so it must be SENT within ~100-180 ticks of the
    marker. A 30ms poll cadence lands in that window only ~1 run in 4;
    a 0.5ms cadence is inside it on any realistic machine (even at 4x
    the early-game tick rate the 1ms send lag is ~80 ticks < 190).
  - The kindle itself is content-side (director tick), so once the drive
    has EXECUTED the relight happens even across the later elimination.
  - run_engine_headless.py is NOT used (it forces stdin=DEVNULL); the
    engine spawn REQUIRES the literal argv "/console" before --console
    (flips isFullScreen -> DebugMode -> /script ungated; construct-gate
    findings). Console scripts are expression-only &&-guard chains.

Asserts per leg (Leg 1: darkstart + fog + resolved=lost + outcome=LOSE;
Leg 2: darkstart + drive marker + relit + fog + resolved=won + WIN):
both legs must also exit 0 and log zero FatalError/[error]/[fatal]
lines. The driver owns fail detection: one line per assertion plus the
aggregate `frontier_cove_round_gate PASS` line that CTest's
PASS_REGULAR_EXPRESSION targets, and exits 0 only on a full pass.

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

SMOKE_RUN = "7000"        # verdict+GameOver at 6300; 700 headroom
SEED = "199"              # pinned round seed (deterministic stamps)
POLL = 0.0005             # driver cadence: the marker->elimination window
                          # is only ~8-11ms; 30ms cadence won ~1 run in 4.
LEG_TIMEOUT = 300         # CTest TIMEOUT is 600; two legs share it

COVE_REL = os.path.join("Worlds.c4f", "BreakerCove.c4s")

ERROR_LOG_RE = re.compile(r"FatalError|\[error\]|\[fatal\]")

# The kindle drive (expression-only; guarded &&-chain). Self-locating:
# anchored on the stamped LHGT, clonk offset ~32 px inside the Cove's
# BC_RELIGHT_RADIUS=45, carrying one WOOD (CreateContents(id, obj) with
# the default count 1 — FnCreateContents C4Script.cpp:2037). The clonk
# may sit in the shallows (the tower IS at the shoreline) but the
# scenario-side kindle check fires on the next director tick.
COVE_DRIVE = ('/script FindObject(LHGT) && CreateContents(WOOD, '
              'CreateObject(CLNK, GetX(FindObject(LHGT)) - 30, '
              'GetY(FindObject(LHGT)) + 10, NO_OWNER)) && '
              'Log("COVEDRV:kindle_spawn")')

DARKSTART_RE = re.compile(r"FRMT:c1_darkstart=1\b")
FOG_BEGINS_RE = re.compile(r"FRMT:fog_begins\b")
RESOLVED_LOST_RE = re.compile(r"FRMT:c1_resolved=lost\b")
RESOLVED_WON_RE = re.compile(r"FRMT:c1_resolved=won\b")
OUTCOME_LOSE_RE = re.compile(r"FRMT:outcome=LOSE\b")
OUTCOME_WIN_RE = re.compile(r"FRMT:outcome=WIN\b")
DRIVE_MARKER_RE = re.compile(r"COVEDRV:kindle_spawn\b")
RELIT_RE = re.compile(r"FRMT:c1_relit=1\b")

LEG1_ASSERTS = [
    ("darkstart", DARKSTART_RE),
    ("fog begins", FOG_BEGINS_RE),
    ("resolved lost", RESOLVED_LOST_RE),
    ("outcome LOSE", OUTCOME_LOSE_RE),
]
LEG2_ASSERTS = [
    ("darkstart", DARKSTART_RE),
    ("drive marker", DRIVE_MARKER_RE),
    ("relit", RELIT_RE),
    ("fog begins", FOG_BEGINS_RE),
    ("resolved won", RESOLVED_WON_RE),
    ("outcome WIN", OUTCOME_WIN_RE),
]

def run_leg(engine, content_dir, out_log, drive):
    """Run one Cove round; return (rc, log) or (None, msg) on timeout.

    drive=False: passive watch (the unattended leg). drive=True: send the
    kindle drive once, right after the tower's dark-start telemetry."""
    workdir = tempfile.mkdtemp(prefix="fcrg_")
    fixture = os.path.join(workdir, "TestPlayer.c4p")
    shutil.copyfile(PLAYER_FIXTURE, fixture)
    scenario = os.path.join(content_dir, COVE_REL)
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
                return None, "<TIMEOUT after %ds>" % LEG_TIMEOUT
            # Whole-file read per poll (NOT seek-incremental): a seek-based
            # reader can split a line across poll boundaries -- the marker's
            # "FRMT:" prefix is consumed by one read and the rest by the
            # next, so the guarded substring never matches and the drive is
            # silently never sent (cycle-217 T3 finding). The log is
            # ~10-20 KB over <=300 polls, so re-reading is free.
            with open(out_log, "r", errors="replace") as rf:
                txt = rf.read()
            if drive and not sent_drive and DARKSTART_RE.search(txt):
                _write(proc, COVE_DRIVE)
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
        print("%s fatal/error lines: FAIL (%d matches, e.g. %r)"
              % (name, len(errs), errs[:3]))
        failures.append("%s error lines" % name)
    else:
        print("%s fatal/error lines: PASS (0 matches)" % name)
    return failures

def main():
    parser = argparse.ArgumentParser(description="frontier_cove round gate")
    parser.add_argument("--engine", required=True, help="path to the clonk binary")
    parser.add_argument("--content-dir", required=True, help="content checkout root")
    args = parser.parse_args()

    engine = os.path.abspath(args.engine)
    content_dir = os.path.abspath(args.content_dir)
    tmpdir = tempfile.gettempdir()

    failures = []

    # Leg 1: unattended LOSE (fixture crew spawns over the sea and drowns;
    # nothing relights the stamped tower).
    out1 = os.path.join(tmpdir, "frontier_cove_round_gate_leg1_%d.log" % os.getpid())
    rc1, log1 = run_leg(engine, content_dir, out1, drive=False)
    failures += check_leg("leg1 unattended", rc1, log1, LEG1_ASSERTS)

    # Leg 2: driven WON (one /script kindle drive on the dark-start marker).
    out2 = os.path.join(tmpdir, "frontier_cove_round_gate_leg2_%d.log" % os.getpid())
    rc2, log2 = run_leg(engine, content_dir, out2, drive=True)
    failures += check_leg("leg2 driven", rc2, log2, LEG2_ASSERTS)

    if failures:
        print("frontier_cove_round_gate FAIL (%d failure(s): %s)"
              % (len(failures), ", ".join(failures)))
        return 1
    print("frontier_cove_round_gate PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
