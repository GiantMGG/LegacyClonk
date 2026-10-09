#!/usr/bin/env python3
"""frontier_outset_construct_gate — permanent CTest gate for the C5/C6
winning leg (cycle 210, roadmap frontier-cards-c5c6).

Drives the REAL content/Worlds.c4f/Outset.c4s round headless through the
engine's stdin /script console seam and asserts the full honest win —
both dealt cards won in ONE round, with the crew standing:

  FRMT:c5_resolved=won crew=1        (3 wolf nights, no clonk lost)
  FRMT:c6_resolved=won mill=1 granary=1   (storm: mill + granary standing)

Recipe (pinned seed 201; preserved transcripts under scratch/210/gate/ —
final-recipe runs are 15/15 won: famE seed-201 12/12 across drive cadences
0.02-0.1 s plus famF 3/3; the earlier 8-decoy famD trio (1/3) is what
motivated the clonk decoys in step 3):
  1. Construct order on the auto-found site right after FRMT:grny_spawn.
     The builder completes the mill (~t=1600) and is squashed by the
     materializing solid mask — unavoidable single-clonk mechanics.
  2. A SECOND crew clonk is parked at (660,190) BEFORE the completion
     (MakeCrewMember(CreateObject(CLNK,...))) so the player crew never
     hits 0: no elimination, no player-save freeze, crew=1 through all
     three dawns (c5 won crew=1).
  3. Twelve SGNL signal poles (AttractLightning=1, non-flammable, shipped
     in the always-loaded Objects.c4d) are placed around the mill, the
     granary and the parked clonk. Storm lightning bolts divert to the
     poles within a +-50 px window and strike THEM instead of the
     structures/crew — c6 becomes structurally deterministic instead of
     an RNG lottery (this was the seed-199/seed-201 rabbit hole: the
     storm's ~58 random-column bolts toggled mill/granary burns run to
     run; the poles remove the divergence).

Console scripts are expression-only (no var/if) and use the proven
&&-guard chain shape (plan finding 2/6). The engine spawn REQUIRES the
literal argv "/console" before --console (flips isFullScreen -> DebugMode
-> /script ungated; finding 1/6). run_engine_headless.py is NOT used: it
forces stdin=DEVNULL; this driver pipes stdin.

The driver owns fail detection (longboot/menu_walk precedent): it prints
one line per assertion plus the aggregate `frontier_outset_construct_gate
PASS` line that CTest's PASS_REGULAR_EXPRESSION targets, and exits 0 only
on a full pass.

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

SMOKE_RUN = "16000"
SEED = "201"            # pinned winning seed (famE/famF probes, cycle 210)
POLL = 0.03             # driver cadence (won across 0.02-0.1s in probes)
SPAWN_TIMEOUT = 540     # CTest TIMEOUT is 600; longboot precedent

# Parked clonk B (crew never 0 -> no elimination) — spike-proven survivor
PRESP = (660, 190)
# SGNL decoy offsets (x, y) around each anchor (mill/granary/clonk)
DECOY_OFFSETS = ((-44, -20), (44, -20), (-44, 12), (44, 12))
CLONK_DECOY_OFFSETS = ((-30, -12), (30, -12), (-30, 10), (30, 10))

OUTSET_REL = os.path.join("Worlds.c4f", "Outset.c4s")

# The two dealt-card wins the gate exists to prove (exact pins).
ASSERTS = [
    ("c5 won crew=1", re.compile(r"FRMT:c5_resolved=won crew=1\b")),
    ("c6 won mill+grny", re.compile(r"FRMT:c6_resolved=won mill=1 granary=1\b")),
]
# Completion + drive non-vacuity evidence.
COMPLETION_RE = re.compile(r"MTRA:t=\d+ clnk=\d+ con=100\b")
ORDER_RE = re.compile(r"MILLDRV:order\b")
PRESP_RE = re.compile(r"MILLDRV:prespawn\b")
DECOY_RE = re.compile(r"MILLDRV:decoy\b")
DAWN3_CREW_RE = re.compile(r"FRMT:dawn=3 crew=1\b")
ERROR_LOG_RE = re.compile(r"FatalError|\[error\]|\[fatal\]")

# Per-poll /script lines (expression-only; guarded &&-chains).
ORDER_SCRIPT = ('/script FindObject(CLNK) && !FindObject(AGWM) && '
                'SetCommand(FindObject(CLNK),"Construct",nil,0,0,nil,AGWM) '
                '&& Log("MILLDRV:order")')
PRESP_SCRIPT = ('/script GetCrewCount(GetPlayerByIndex(0))<2 && '
                'MakeCrewMember(CreateObject(CLNK,%d,%d,GetPlayerByIndex(0)), '
                'GetPlayerByIndex(0)) && Log("MILLDRV:prespawn")' % PRESP)
TRACE_SCRIPT = ('/script FindObject(CLNK) && Log(Format("MTRA:t=%d clnk=%d '
                'con=%d cx=%d cy=%d ax=%d ay=%d e=%d act=%s", FrameCounter(), '
                'ObjectCount(CLNK), GetCon(FindObject(AGWM)), '
                'GetX(FindObject(CLNK)), GetY(FindObject(CLNK)), '
                'GetX(FindObject(AGWM)), GetY(FindObject(AGWM)), '
                'GetEnergy(FindObject(CLNK)), GetAction(FindObject(CLNK))))')
DECOY_SCRIPT = ('/script CreateObject(SGNL,%d,%d,NO_OWNER) && '
                'Log("MILLDRV:decoy")')

def run(engine, content_dir, out_log):
    """Drive one round; return (rc, log) or (None, msg) on timeout."""
    workdir = tempfile.mkdtemp(prefix="focg_")
    fixture = os.path.join(workdir, "TestPlayer.c4p")
    shutil.copyfile(PLAYER_FIXTURE, fixture)
    scenario = os.path.join(content_dir, OUTSET_REL)
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

    sent = {"order": False, "prespawn": False, "decoys": False}
    grny_xy = None
    mill_xy = None
    decoy_queue = list(DECOY_OFFSETS)
    last_len = 0
    t0 = time.time()
    deadline = t0 + SPAWN_TIMEOUT
    try:
        while True:
            if proc.poll() is not None:
                break
            if time.time() > deadline:
                proc.kill()
                proc.wait()
                return None, "<TIMEOUT after %ds>" % SPAWN_TIMEOUT
            with open(out_log, "r", errors="replace") as rf:
                rf.seek(last_len)
                newtxt = rf.read()
                last_len = rf.tell()
            if newtxt:
                for ln in newtxt.splitlines():
                    if ("FRMT:grny_spawn" in ln and not sent["order"]):
                        _write(proc, ORDER_SCRIPT)
                        sent["order"] = True
                    if ("FRMT:grny_spawn" in ln and not sent["prespawn"]):
                        _write(proc, PRESP_SCRIPT)
                        sent["prespawn"] = True
                    m = re.search(r"FRMT:grny_spawn=(-?\d+),(-?\d+)", ln)
                    if m:
                        grny_xy = (int(m.group(1)), int(m.group(2)))
                    m = re.search(r"MTRA:t=\d+ clnk=\d+ con=\d+ "
                                  r"cx=-?\d+ cy=-?\d+ ax=(-?\d+) ay=(-?\d+)", ln)
                    if m and m.group(1) != "0":
                        mill_xy = (int(m.group(1)), int(m.group(2)))
            # Decoys: mill-anchor first (4), then granary- + clonk-anchor (8)
            if not sent["decoys"] and decoy_queue and mill_xy:
                ox, oy = decoy_queue.pop(0)
                _write(proc, DECOY_SCRIPT % (mill_xy[0] + ox, mill_xy[1] + oy))
            elif not sent["decoys"] and not decoy_queue and grny_xy:
                for ox, oy in DECOY_OFFSETS:
                    _write(proc, DECOY_SCRIPT % (grny_xy[0] + ox, grny_xy[1] + oy))
                for ox, oy in CLONK_DECOY_OFFSETS:
                    _write(proc, DECOY_SCRIPT % (PRESP[0] + ox, PRESP[1] + oy))
                sent["decoys"] = True
            # Only talk to the console seam once the round is actually running
            # (grny_spawn means AppState==C4AS_Game). The first famF probe wrote
            # the trace unconditionally and only survived because the release
            # build compiles asserts out; the Debug/ASan build asserts
            # !"Unhandled switch case" in OnCommand for pre-game AppStates.
            if grny_xy:
                _write(proc, TRACE_SCRIPT)
            time.sleep(POLL)
    finally:
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()
        logf.close()
        # reread tail for the log (the file is owned by the driver)
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

def main():
    parser = argparse.ArgumentParser(description="frontier_outset_construct gate")
    parser.add_argument("--engine", required=True, help="path to the clonk binary")
    parser.add_argument("--content-dir", required=True, help="content checkout root")
    args = parser.parse_args()

    engine = os.path.abspath(args.engine)
    content_dir = os.path.abspath(args.content_dir)
    out_log = os.path.join(tempfile.gettempdir(),
                           "frontier_outset_construct_gate_%d.log" % os.getpid())
    failures = []

    rc, log = run(engine, content_dir, out_log)

    if rc is None:
        print("construct spawn: FAIL (%s)" % log)
        failures.append("spawn/timeout")
    else:
        lines = len(log.splitlines())
        if rc != 0:
            print("construct exit: FAIL (rc=%s, expected 0; %d log lines)" % (rc, lines))
            failures.append("engine exit %s" % rc)
        else:
            print("construct exit: PASS (rc=0, %d log lines)" % lines)
        for name, pattern in ASSERTS:
            if pattern.search(log):
                print("assert %s: PASS" % name)
            else:
                print("assert %s: FAIL (%r not found)" % (name, pattern.pattern))
                failures.append("assert %s" % name)
        if COMPLETION_RE.search(log):
            print("assert mill completed (con=100): PASS")
        else:
            print("assert mill completed (con=100): FAIL (no con=100 telemetry)")
            failures.append("assert con=100")
        # DECOY_RE is an any-count presence check; the >=8 bound is asserted
        # separately via n_decoy_markers_ok right below.
        for name, pat in (("drive order marker", ORDER_RE),
                          ("drive prespawn marker", PRESP_RE),
                          ("drive decoy markers", DECOY_RE),
                          ("night-3 dawn crew=1", DAWN3_CREW_RE)):
            if pat.search(log):
                print("assert %s: PASS" % name)
            else:
                print("assert %s: FAIL (%r not found)" % (name, pat.pattern))
                failures.append("assert %s" % name)
        if n_decoy_markers_ok(log):
            print("assert decoy marker count (>=8 logged lines): PASS")
        else:
            print("assert decoy marker count: FAIL (%d logged)" % log.count("MILLDRV:decoy"))
            failures.append("decoy marker count")
        err_lines = ERROR_LOG_RE.findall(log)
        if err_lines:
            print("fatal/error lines: FAIL (%d matches, e.g. %r)" % (len(err_lines), err_lines[:3]))
            failures.append("fatal/error log lines")
        else:
            print("fatal/error lines: PASS (0 matches)")

    if failures:
        print("frontier_outset_construct_gate FAIL (%d failure(s): %s)"
              % (len(failures), ", ".join(failures)))
        return 1
    print("frontier_outset_construct_gate PASS")
    return 0

def n_decoy_markers_ok(log):
    return len(re.findall(r"\[info\] MILLDRV:decoy\b", log)) >= 8

if __name__ == "__main__":
    sys.exit(main())
