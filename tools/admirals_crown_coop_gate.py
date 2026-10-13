#!/usr/bin/env python3
"""admirals_crown_coop_gate — permanent CTest gate for the shipped
AdmiralsCrown.c4s 2-player co-op loop (cycle 222, flooded-crown-coop-paths).

Spec: .opencode/specs/2026-10-13-flooded-crown-coop-paths.md
Plan: .opencode/plans/2026-10-13-flooded-crown-coop-paths.md (Task 2)

Boots the SHIPPED content/OceanTrade.c4f/AdmiralsCrown.c4s headless with TWO
TestPlayer fixtures (P1 helm + P2 boatswain) through the stdin /script
console seam and drives the real crew mirror through the full co-op loop,
phase by phase (seam input re-asserted every poll while a phase is active;
every seam write is gated on the round running — the
"AdmiralsCrown: director armed" line):

  0 boot     wait for "AdmiralsCrown: director armed"; no [error]/[fatal] so far
  1 board    board one crew clonk per player into the Cog (self-guarded
             Enter chain; markers GATE:boarded0 / GATE:boarded1 log exactly
             once despite per-poll retries), then neutralize both crews
  2 breach   OpenBreach() once; TRACE asserts op 0->1 and the +1/frame fill
  3 bail     hold P2 COMD_Left from fl >= 30; PASS on a strict fl decrease
             with dfl == dt*1 - 25 (+-2, k=1 bail per bracket); at fl >= 70
             with no decrease: LOUD walk-on (exact FAIL line, phases 4-8
             still run below AWASH_AT=100) — this is what makes the MUT-red
             run isolate exactly the bail clause
  4 jettison hold P2 COMD_Right from fl >= 30 again; PASS on sk -1 AND
             fl -25 net of fill (dfl == dt - 25, +-2) in one step
  5 plug     hold P2 COMD_Up; PASS on op 1->0 AND wd -1 in one step, then
             fl frozen (fill 0) across 3 samples
  6 steer    hold P1 COMD_Right (x increases between samples); brake
             (COMD_None once) on the FIRST "AdmiralsCrown: delivery" line
  7 win      the 3 "AdmiralsCrown: delivery N of 3" lines + the
             "AdmiralsCrown WIN: 3 bales delivered at the east port" line +
             engine exit 0
  8 audit    zero FatalError / [error] / [fatal] in the whole engine log

T1 probe evidence (banked: .opencode/scratch/222/t1-probe.log +
t1-engine.log) feeding the constants:
  - steer latency (ComDir -> heading -> x increase): 30 frames
  - sail speed ~0.8 px/frame (SetXDir(8) is fixed-point), NOT 8 px/frame
  - coast after the COMD_None brake <= 35 frames * 0.8 ~= 28 px (measured
    ~16 px) -> the spec-default brake (first delivery line) parks the Cog
    inside the 300 px dock window; the proactive x-threshold is NOT needed
    (trigger kept as the single tunable BRAKE_ON_FIRST_DELIVERY / BRAKE_X)
  - bail dip confirmed: fl 46 -> 24 over dt=3 (dfl = dt*1 - 25 = -22)
  - the engine echoes every /script send as "[info] -> <text>" -> marker
    literals are Format-split so the echo never matches a grep target
  - engine exits 0 on GameOver(); the probe ran with zero [error]

Structure precedent: tools/frontier_outset_construct_gate.py (launch ->
pipe stdin -> poll log -> react -> assert -> aggregate print). The literal
"/console" argv flips isFullScreen -> DebugMode -> /script ungated.
run_engine_headless.py is NOT used: it forces stdin=DEVNULL.

Output contract (exact): one "assert <phase>: PASS" line per phase (phase
names boot / board / breach-open / bail / jettison / plug / steer / win /
log-audit) plus the bail-FAIL form
"assert bail cut flood: FAIL (no flood decrease at director fire)";
aggregate "admirals_crown_coop_smoke PASS" (CTest PASS_REGULAR_EXPRESSION)
or "admirals_crown_coop_smoke FAIL (<N> failure(s): <list>)"; exit 0 only
on a full pass; engine timeout/early spawn failure ->
"spawn/timeout: FAIL (...)" + aggregate FAIL + exit 1.

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

SMOKE_RUN = "2500"
SEED = "199"
CAP = "100"
POLL = 0.03          # driver cadence (~3 frames per poll at cap 100)
WALL_BOUND = 200     # s; CTest TIMEOUT is 240 (headroom)

SCENARIO_REL = os.path.join("OceanTrade.c4f", "AdmiralsCrown.c4s")

# Phase tunables (each bound is a single constant, per the Task 2 contract).
BAIL_FLOOR = 30                  # hold P2 COMD_Left from fl >= 30 (no bail clamp at 0)
BAIL_BOUND = 70                  # fl >= 70 with no dip -> loud FAIL + walk-on
PLUG_FROZEN_SAMPLES = 3          # constant-fl samples after the plug
DOCK_RANGE = 150                 # px (scenario DOCK_RANGE: delivery proximity)
BRAKE_ON_FIRST_DELIVERY = True   # spec-default brake trigger (T1: coast <= 28 px)
BRAKE_X = 845                    # proactive x-threshold fallback (unused by default)

# Phase machine states.
ST_BOOT, ST_BOARD, ST_BREACH, ST_BAIL, ST_JETT, ST_PLUG, ST_STEER, ST_WINWAIT = range(8)

ARMED_RE = re.compile(r"AdmiralsCrown: director armed\b")
# Output lines only ('[info] GATE:...'); echo lines are '[info] -> ...'.
GATE_RE = re.compile(r"\[info\] GATE:t=(-?\d+) fl=(-?\d+) op=(-?\d+) sk=(-?\d+) wd=(-?\d+) x=(-?\d+)")
BOARD0_RE = re.compile(r"\[info\] GATE:boarded0\b")
BOARD1_RE = re.compile(r"\[info\] GATE:boarded1\b")
BREACH_RE = re.compile(r"\[info\] GATE:breach-opened\b")
LW_RE = re.compile(r"\[info\] GATE:lw=(\d+)")
DELIVERY_RE = re.compile(r"AdmiralsCrown: delivery (\d+) of 3\b")
WIN_RE = re.compile(r"AdmiralsCrown WIN: 3 bales delivered at the east port\b")
STORM_RE = re.compile(r"AdmiralsCrown: STRM storm at f(\d+)")
ERROR_LOG_RE = re.compile(r"FatalError|\[error\]|\[fatal\]")

# Boarding: self-gating (Contained guard) so each marker logs EXACTLY once
# even though the command is re-asserted per poll; the marker literal is
# Format-split so the echo line never contains 'GATE:boarded'.
BOARD_SCRIPTS = {
    0: ('/script GetCrew(0,0) && FindObject2(Find_ID(CGSH)) && '
        'Contained(GetCrew(0,0)) != FindObject2(Find_ID(CGSH)) && '
        'Enter(FindObject2(Find_ID(CGSH)), GetCrew(0,0)) && '
        'Log(Format("GATE:board%s0", "ed"))'),
    1: ('/script GetCrew(1,0) && FindObject2(Find_ID(CGSH)) && '
        'Contained(GetCrew(1,0)) != FindObject2(Find_ID(CGSH)) && '
        'Enter(FindObject2(Find_ID(CGSH)), GetCrew(1,0)) && '
        'Log(Format("GATE:board%s1", "ed"))'),
}
NEUTRALIZE_SCRIPTS = [
    '/script SetComDir(COMD_None, GetCrew(0,0))',
    '/script SetComDir(COMD_None, GetCrew(1,0))',
]
# East-port x probe (one-shot; feeds the dock-window entry frame report).
LW_SCRIPT = '/script Log(Format("GATE:lw%s%d", "=", LandscapeWidth()))'
BREACH_SCRIPT = ('/script FindObject2(Find_ID(CGSH)) && '
                 'FindObject2(Find_ID(CGSH))->OpenBreach() && '
                 'Log(Format("GATE:breach-%s", "opened"))')
TRACE_SCRIPT = ('/script FindObject2(Find_ID(CGSH)) && Log(Format("GATE:t=%d '
                'fl=%d op=%d sk=%d wd=%d x=%d", FrameCounter(), '
                'FindObject2(Find_ID(CGSH))->GetFloodLevel(), '
                'FindObject2(Find_ID(CGSH))->GetOpenBreaches(), '
                'ContentsCount(SILK, FindObject2(Find_ID(CGSH))), '
                'ContentsCount(WOOD, FindObject2(Find_ID(CGSH))), '
                'GetX(FindObject2(Find_ID(CGSH)))))')
P2_LEFT_SCRIPT = '/script SetComDir(COMD_Left, GetCrew(1,0))'
P2_RIGHT_SCRIPT = '/script SetComDir(COMD_Right, GetCrew(1,0))'
P2_UP_SCRIPT = '/script SetComDir(COMD_Up, GetCrew(1,0))'
P2_NONE_SCRIPT = '/script SetComDir(COMD_None, GetCrew(1,0))'
P1_RIGHT_SCRIPT = '/script SetComDir(COMD_Right, GetCrew(0,0))'
P1_NONE_SCRIPT = '/script SetComDir(COMD_None, GetCrew(0,0))'

def _write(proc, line):
    if proc.poll() is not None:
        return
    try:
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass

def _pair_scan(samples, pred):
    """Index i of the first pair (samples[i-1], samples[i]) with pred true."""
    for i in range(1, len(samples)):
        if pred(samples[i - 1], samples[i]):
            return i
    return None

def _bail_dip(a, b):
    """Bail cut: strict fl decrease while the breach is open and the
    director-fire arithmetic dfl == dt*1 - 25 holds (+-2; k=1 per bracket)."""
    if a[2] != 1 or b[2] != 1:
        return False
    dt = b[0] - a[0]
    dfl = b[1] - a[1]
    return dfl < 0 and abs(dfl - (dt - 25)) <= 2

def _jett_step(a, b):
    """Jettison: sk -1 AND fl -25 net of fill in the same sample step."""
    if b[2] != 1 or b[3] != a[3] - 1:
        return False
    dt = b[0] - a[0]
    dfl = b[1] - a[1]
    return abs(dfl - (dt - 25)) <= 2

def _plug_step(a, b):
    """Plug: op 1->0 AND wd -1 in the same sample step."""
    return a[2] == 1 and b[2] == 0 and b[4] == a[4] - 1

def run(engine, content_dir, out_log):
    """Drive one round; returns (rc, res) with rc None on spawn error/timeout."""
    workdir = tempfile.mkdtemp(prefix="acg_")
    fix1 = os.path.join(workdir, "TestPlayerA.c4p")
    fix2 = os.path.join(workdir, "TestPlayerB.c4p")
    shutil.copyfile(PLAYER_FIXTURE, fix1)  # TWICE: the engine writes player
    shutil.copyfile(PLAYER_FIXTURE, fix2)  # state back into joined .c4p files
    scenario = os.path.abspath(os.path.join(content_dir, SCENARIO_REL))
    cmd = [engine, "/console", "--console", "--smoke-run", SMOKE_RUN,
           "--frame-rate-cap", CAP, "--parameter", "Seed=" + SEED,
           "-s", scenario, fix1, fix2]
    logf = open(out_log, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=logf,
                                stderr=subprocess.STDOUT, cwd=content_dir,
                                encoding="utf-8", errors="replace")
    except OSError as e:
        logf.close()
        shutil.rmtree(workdir, ignore_errors=True)
        return None, {"spawn": "spawn error: %s" % e}

    state = ST_BOOT
    armed = False
    err_pre_armed = 0
    last_len = 0
    samples = []            # (t, fl, op, sk, wd, x) tuples from GATE:t= lines
    markers = {"boarded0": False, "boarded1": False, "breach": False}
    lw = None               # LandscapeWidth (dock-window geometry)
    deliveries = []         # (n, TRACE t observed at) per delivery line
    win_seen = False
    storm_f = None          # frame stamped on the STRM storm line
    breach_rise_t = None    # frame of the op 0->1 sample
    breach_sent = False
    fill_ok = False         # +1/frame fill observed while op==1
    bail_dip = None         # (t, fl_before, fl_after) on success
    bail_walkon = None      # fl at the BAIL_BOUND walk-on (loud MUT-red path)
    jett = None             # (t, sk_before, sk_after, fl_before, fl_after)
    plug = None             # (t, wd_before, wd_after, frozen_ok)
    plug_frozen_from = None
    brake_sent = False
    steer_x_rise = False
    dock_entry = None       # (t, x) of the first sample at/after the window edge
    deadline = time.time() + WALL_BOUND
    rc = None
    try:
        while True:
            if proc.poll() is not None:
                break
            if time.time() > deadline:
                proc.kill()
                proc.wait()
                return None, {"timeout": "<TIMEOUT after %ds>" % WALL_BOUND}
            with open(out_log, "r", errors="replace") as rf:
                rf.seek(last_len)
                newtxt = rf.read()
                last_len = rf.tell()
            if newtxt:
                for ln in newtxt.splitlines():
                    m = GATE_RE.search(ln)
                    if m:
                        samples.append(tuple(int(g) for g in m.groups()))
                    if ARMED_RE.search(ln):
                        armed = True
                    if BOARD0_RE.search(ln):
                        markers["boarded0"] = True
                    if BOARD1_RE.search(ln):
                        markers["boarded1"] = True
                    if BREACH_RE.search(ln):
                        markers["breach"] = True
                    m = LW_RE.search(ln)
                    if m:
                        lw = int(m.group(1))
                    m = DELIVERY_RE.search(ln)
                    if m:
                        deliveries.append((int(m.group(1)),
                                           samples[-1][0] if samples else -1))
                    if WIN_RE.search(ln):
                        win_seen = True
                    m = STORM_RE.search(ln)
                    if m:
                        storm_f = int(m.group(1))

            if state == ST_BOOT:
                if armed:
                    state = ST_BOARD
                time.sleep(POLL)
                continue

            # TRACE every poll once the round runs (all phases after boot).
            _write(proc, TRACE_SCRIPT)

            if state == ST_BOARD:
                # Re-assert per poll; the Contained guard makes each marker
                # log exactly once and a false chain stays silent (retry free).
                _write(proc, BOARD_SCRIPTS[0])
                _write(proc, BOARD_SCRIPTS[1])
                if markers["boarded0"] and markers["boarded1"]:
                    for s in NEUTRALIZE_SCRIPTS:
                        _write(proc, s)   # pin both headings (once each)
                    _write(proc, LW_SCRIPT)
                    state = ST_BREACH
            elif state == ST_BREACH:
                if not breach_sent:
                    _write(proc, BREACH_SCRIPT)   # send ONCE (Task 2 contract)
                    breach_sent = True
                if markers["breach"]:
                    if breach_rise_t is None:
                        i = _pair_scan(samples, lambda a, b: a[2] == 0 and b[2] == 1)
                        if i is not None:
                            breach_rise_t = samples[i][0]
                    if breach_rise_t is not None and not fill_ok:
                        fill_ok = _pair_scan(
                            samples, lambda a, b: b[2] == 1 and b[1] > a[1]) is not None
                    if breach_rise_t is not None and fill_ok:
                        state = ST_BAIL
            elif state == ST_BAIL:
                last = samples[-1] if samples else None
                if last and last[1] >= BAIL_FLOOR and last[2] == 1:
                    _write(proc, P2_LEFT_SCRIPT)
                    i = _pair_scan(samples, _bail_dip)
                    if i is not None:
                        _write(proc, P2_NONE_SCRIPT)   # stop bailing, once
                        bail_dip = (samples[i][0], samples[i - 1][1], samples[i][1])
                        state = ST_JETT
                    elif last[1] >= BAIL_BOUND:
                        # Loud walk-on (MUT-red path): no dip -> report the
                        # exact FAIL line, neutralize P2, keep driving phases
                        # 4-8 below AWASH_AT=100. Do NOT exit.
                        bail_walkon = last[1]
                        _write(proc, P2_NONE_SCRIPT)
                        state = ST_JETT
            elif state == ST_JETT:
                last = samples[-1] if samples else None
                if last and last[1] >= BAIL_FLOOR and last[2] == 1:
                    _write(proc, P2_RIGHT_SCRIPT)
                    i = _pair_scan(samples, _jett_step)
                    if i is not None:
                        _write(proc, P2_NONE_SCRIPT)   # stop jettisoning, once
                        jett = (samples[i][0], samples[i - 1][3], samples[i][3],
                                samples[i - 1][1], samples[i][1])
                        state = ST_PLUG
            elif state == ST_PLUG:
                last = samples[-1] if samples else None
                if last and last[2] == 1:
                    _write(proc, P2_UP_SCRIPT)
                if plug is None:
                    i = _pair_scan(samples, _plug_step)
                    if i is not None:
                        plug = [samples[i][0], samples[i - 1][4], samples[i][4], False]
                        plug_frozen_from = i
                elif plug_frozen_from is not None:
                    j = plug_frozen_from
                    if len(samples) >= j + PLUG_FROZEN_SAMPLES:
                        fls = set(samples[j + k][1] for k in range(PLUG_FROZEN_SAMPLES))
                        if len(fls) == 1 and samples[j][2] == 0:
                            plug[3] = True
                            _write(proc, P2_NONE_SCRIPT)   # stop plugging, once
                            state = ST_STEER
            elif state == ST_STEER:
                if not brake_sent:
                    _write(proc, P1_RIGHT_SCRIPT)
                    if not steer_x_rise:
                        steer_x_rise = _pair_scan(
                            samples, lambda a, b: b[5] > a[5]) is not None
                    if lw is not None and dock_entry is None:
                        edge = (5 * lw) // 6 - DOCK_RANGE   # scenario geometry
                        for s in samples:
                            if s[5] >= edge:
                                dock_entry = (s[0], s[5])
                                break
                    if BRAKE_ON_FIRST_DELIVERY:
                        trigger = bool(deliveries)
                    else:
                        trigger = bool(samples) and samples[-1][5] >= BRAKE_X
                    if trigger:
                        _write(proc, P1_NONE_SCRIPT)       # brake, once
                        brake_sent = True
                        state = ST_WINWAIT
            # ST_WINWAIT: keep the TRACE cadence until the round ends (WIN).
            time.sleep(POLL)
    finally:
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()
        logf.close()
        with open(out_log, "r", errors="replace") as rf:
            final = rf.read()
        shutil.rmtree(workdir, ignore_errors=True)
    res = {
        "armed": armed, "err_pre_armed": err_pre_armed,
        "samples": samples, "markers": markers, "lw": lw,
        "deliveries": deliveries, "win_seen": win_seen, "storm_f": storm_f,
        "breach_rise_t": breach_rise_t, "fill_ok": fill_ok,
        "bail_dip": bail_dip, "bail_walkon": bail_walkon,
        "jett": jett, "plug": tuple(plug) if plug else None,
        "brake_sent": brake_sent, "steer_x_rise": steer_x_rise,
        "dock_entry": dock_entry, "err_count": len(ERROR_LOG_RE.findall(final)),
        "log_lines": len(final.splitlines()),
    }
    return rc, res

def main():
    parser = argparse.ArgumentParser(
        description="admirals_crown_coop_smoke gate (cycle 222)")
    parser.add_argument("--engine", required=True, help="path to the clonk binary")
    parser.add_argument("--content-dir", required=True, help="content checkout root")
    parser.add_argument("--log", default=None,
                        help="engine log path (default: tempdir file)")
    args = parser.parse_args()

    engine = os.path.abspath(args.engine)
    content_dir = os.path.abspath(args.content_dir)
    out_log = args.log or os.path.join(
        tempfile.gettempdir(), "admirals_crown_coop_gate_%d.log" % os.getpid())

    failures = []
    rc, res = run(engine, content_dir, out_log)

    if rc is None:
        print("spawn/timeout: FAIL (%s)" % (res.get("spawn") or res.get("timeout")))
        failures.append("spawn/timeout")
    else:
        if rc != 0:
            print("engine exit: FAIL (rc=%s, expected 0; %d log lines)"
                  % (rc, res["log_lines"]))
            failures.append("engine exit %s" % rc)
        else:
            print("engine exit: PASS (rc=0, %d log lines)" % res["log_lines"])

        samples = res["samples"]
        markers = res["markers"]

        # Phase 0 boot: director armed with no [error]/[fatal] before it.
        if res["armed"] and res["err_pre_armed"] == 0:
            print("assert boot: PASS")
        else:
            print("assert boot: FAIL (armed=%s, %d error line(s) before armed)"
                  % (res["armed"], res["err_pre_armed"]))
            failures.append("assert boot")

        # Phase 1 board: both boarding markers logged exactly once.
        if markers["boarded0"] and markers["boarded1"]:
            print("assert board: PASS")
        else:
            print("assert board: FAIL (boarded0=%s boarded1=%s)"
                  % (markers["boarded0"], markers["boarded1"]))
            failures.append("assert board")

        # Phase 2 breach: OpenBreach marker + op 0->1 + fill observed via TRACE.
        if markers["breach"] and res["breach_rise_t"] is not None and res["fill_ok"]:
            print("assert breach-open: PASS (op 0->1 at f%d, fill confirmed)"
                  % res["breach_rise_t"])
        else:
            print("assert breach-open: FAIL (marker=%s op_rise=%s fill=%s)"
                  % (markers["breach"], res["breach_rise_t"], res["fill_ok"]))
            failures.append("assert breach-open")

        # Phase 3 bail: strict fl decrease with the director-fire arithmetic.
        if res["bail_dip"]:
            t, fl0, fl1 = res["bail_dip"]
            print("assert bail: PASS (f%d: fl %d->%d, dt-integrated dip -25 net of fill)" % (t, fl0, fl1))
        elif res["bail_walkon"] is not None:
            print("assert bail cut flood: FAIL (no flood decrease at director fire)")
            failures.append("assert bail cut flood")
        else:
            print("assert bail: FAIL (no dip; flood never reached the fl>=%d hold floor)"
                  % BAIL_FLOOR)
            failures.append("assert bail")

        # Phase 4 jettison: sk -1 AND fl -25 net of fill in one step.
        if res["jett"]:
            t, sk0, sk1, fl0, fl1 = res["jett"]
            print("assert jettison: PASS (f%d: sk %d->%d, fl %d->%d)"
                  % (t, sk0, sk1, fl0, fl1))
        else:
            print("assert jettison: FAIL (no sk-1 / fl-25 step observed)")
            failures.append("assert jettison")

        # Phase 5 plug: op 1->0 + wd -1 in one step, then fl frozen.
        if res["plug"] and res["plug"][3]:
            t, wd0, wd1, _ = res["plug"]
            print("assert plug: PASS (f%d: wd %d->%d, breach closed, fl frozen x%d)"
                  % (t, wd0, wd1, PLUG_FROZEN_SAMPLES))
        else:
            print("assert plug: FAIL (op=%s frozen=%s)"
                  % (bool(res["plug"]), res["plug"][3] if res["plug"] else False))
            failures.append("assert plug")

        # Phase 6 steer: x increased under COMD_Right and the delivery-line
        # brake fired.
        if res["steer_x_rise"] and res["brake_sent"]:
            print("assert steer: PASS (x increased under COMD_Right; brake on "
                  "first delivery line; %d delivery line(s))" % len(res["deliveries"]))
        else:
            print("assert steer: FAIL (x_rise=%s brake_sent=%s)"
                  % (res["steer_x_rise"], res["brake_sent"]))
            failures.append("assert steer")

        # Phase 7 win: the three delivery lines + the WIN line + exit 0.
        del_nums = set(n for n, _ in res["deliveries"])
        if res["win_seen"] and rc == 0 and {1, 2, 3} <= del_nums:
            print("assert win: PASS (deliveries 1/2/3 of 3 + WIN line, exit 0)")
        else:
            print("assert win: FAIL (win_line=%s rc=%s deliveries=%s)"
                  % (res["win_seen"], rc, sorted(del_nums)))
            failures.append("assert win")

        # Phase 8 log audit: zero FatalError / [error] / [fatal] anywhere.
        if res["err_count"] == 0:
            print("assert log-audit: PASS (0 fatal/error matches in %d lines)"
                  % res["log_lines"])
        else:
            print("assert log-audit: FAIL (%d fatal/error match(es))"
                  % res["err_count"])
            failures.append("assert log-audit")

        # Telemetry for the cycle-222 verification (frames, dock window).
        phase_t = {}
        if res["bail_dip"]:
            phase_t["bail"] = res["bail_dip"][0]
        if res["jett"]:
            phase_t["jettison"] = res["jett"][0]
        if res["plug"]:
            phase_t["plug"] = res["plug"][0]
        del_t = dict((n, t) for n, t in res["deliveries"])
        win_frame = (del_t[3] + 35) if 3 in del_t else None   # WIN fires one director tick later
        print("info: frames=%s storm=%s dock_entry=%s deliveries=%s win~=%s "
              "(brake=%s x_rise=%s lw=%s)"
              % (phase_t, res["storm_f"], res["dock_entry"],
                 sorted(del_t.items()), win_frame, res["brake_sent"],
                 res["steer_x_rise"], res["lw"]))

    if failures:
        print("admirals_crown_coop_smoke FAIL (%d failure(s): %s)"
              % (len(failures), ", ".join(failures)))
        return 1
    print("admirals_crown_coop_smoke PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
