#!/usr/bin/env python3
"""save_continue_e2e — two-phase save+quit -> continue+jobs-resume E2E (cycle 189).

Proves the roadmap check "save, quit, continue, jobs resume" on
content/Agriculture.c4d/Tests.c4f/SaveContinueProof.c4s through the console
engine, without any UI:

  Phase A  --console --smoke-run 700 --smoke-save-at:700:SCProof
            --frame-rate-cap 1000 --parameter "Seed=181" -s <PACKED fixture>
  -> the fixture's fresh-run arm (t35) and pre-save marks (t665) fire, the
     probe flag QuickSaves at t700 (seed 181 pinned, RNG-pinned) and the
     cap quits clean.
  Phase B  --console --smoke-run 2800 --frame-rate-cap 1000 -s <savegame>
  -> NO --parameter overrides: the savegame carries its exact parameter +
     RNG state. The restored effect timer resumes at ~t700 and the ladder
     proves the job loops came back: SCP:resumed at t1260, SaveContinueProof
     PASS at t2380 (GameOver -> exit 0).

Driver step 0 (cycle-189 finding): QuickSave from a DIRECTORY-form scenario
is corrupted by C4Group::Save folder packing, so the fixture is first packed
with the sibling c4group binary into a temp working area and phase A runs
against the PACKED copy (mirrors the Release workflow, which packs content
the same way). The packed copy and the produced savegame are removed on exit.

Engine discipline (rules/engine-behavior-gotchas.md #6): stdin=DEVNULL at
every spawn, cwd = the engine binary's directory (build-dir pack symlinks).
Effect-timer FatalError exits 0 but is caught by grepping the log
(gotchas #3); the oracle is the same as the CTest FAIL regex.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

SLOT = "SCProof"
SCEN_NAME = "SaveContinueProof.c4s"
PHASE_B_CAP = "2800"
PASS_LINE = "SaveContinueProof PASS"
RUN_TIMEOUT = 200  # s, per engine spawn (a hung run must fail, not linger)

# Same oracle the CTest stanza uses: [error]/[critical]/[fatal] + FatalError.
FATAL_RE = re.compile(r"FatalError|\[error\]|\[critical\]|\[fatal\]", re.IGNORECASE)

def fail(msg):
    print("SaveContinueProof E2E FAIL: %s" % msg)
    return 1

def log_tail(log):
    tail = log.strip().splitlines()[-8:]
    return ";\n".join(tail) if tail else "(empty log)"

def run_engine(engine, args):
    """Spawn the console engine once; return (rc, combined_log) or
    (None, msg) on timeout. stdin=DEVNULL mandatory (gotcha #6); cwd is the
    engine binary's directory so the build-dir content-pack symlinks
    resolve."""
    cmd = [engine] + args
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(engine)),
            stdin=subprocess.DEVNULL, timeout=RUN_TIMEOUT,
            encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, "engine run timed out after %d s" % RUN_TIMEOUT
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

def pack_fixture(c4group, fixture, workdir):
    """Pack the fixture directory into a packed .c4s (or copy an already
    packed fixture as-is) inside workdir. Returns the packed path."""
    target = os.path.join(workdir, SCEN_NAME)
    if os.path.isdir(fixture):
        shutil.copytree(fixture, target)
        proc = subprocess.run([c4group, target, "-pack"],
                              capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=120)
        if proc.returncode != 0 or os.path.isdir(target):
            return None, ("c4group pack failed (rc=%s): %s"
                          % (proc.returncode, (proc.stdout or "") + (proc.stderr or "")))
    else:
        shutil.copyfile(fixture, target)
    return target, None

def savegame_core_ok(c4group, savegame, workdir):
    """Extract the savegame's Scenario.txt and verify [Head] SaveGame=1."""
    out = os.path.join(workdir, "core")
    os.mkdir(out)
    proc = subprocess.run([c4group, savegame, "-et", "Scenario.txt", out],
                          capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120)
    if proc.returncode != 0:
        return False, "c4group extract failed (rc=%s): %s" % (
            proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
    try:
        with open(os.path.join(out, "Scenario.txt"), "r",
                  encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        return False, "cannot read extracted Scenario.txt: %s" % exc
    if not re.search(r"(?m)^SaveGame\s*=\s*1", text):
        return False, "savegame core lacks SaveGame=1"
    return True, None

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: save_continue_e2e.py <engine binary> <fixture .c4s>",
              file=sys.stderr)
        return 2
    engine, fixture = os.path.abspath(args[0]), os.path.abspath(args[1])

    if not os.path.isfile(engine):
        return fail("engine not found: %s" % engine)
    if not os.path.exists(fixture):
        return fail("fixture not found: %s" % fixture)

    c4group = os.path.join(os.path.dirname(engine), "c4group")
    if not os.path.isfile(c4group):
        c4group = os.path.join(os.path.dirname(engine), "c4group.exe")
    if not os.path.isfile(c4group):
        return fail("sibling c4group not found next to %s" % engine)

    save_dir = os.path.join(os.path.dirname(engine), "Savegames.c4f")
    savegame = os.path.join(save_dir, "%s.c4s" % SLOT)

    workdir = None
    try:
        workdir = tempfile.mkdtemp(prefix="save_continue_e2e_")

        # --- step 0: pack the fixture first (cycle-189 finding) ------------
        packed, err = pack_fixture(c4group, fixture, workdir)
        if err is not None:
            return fail(err)

        # --- step 1: stale savegame must not masquerade as a new one ------
        if os.path.exists(savegame):
            os.remove(savegame)

        # --- step 2: phase A — save at cap, literal save+quit --------------
        a_args = ["--console", "--smoke-run", "700", "--smoke-save-at:700:%s" % SLOT,
                  "--frame-rate-cap", "1000", "--parameter", "Seed=181",
                  "-s", packed]
        rc, log = run_engine(engine, a_args)
        if rc is None:
            return fail("phase A %s" % log)
        if rc != 0:
            return fail("phase A exit %d (expected 0)%s" % (rc, log_tail(log)))
        if FATAL_RE.search(log):
            return fail("phase A log has a fatal/[error] line%s" % log_tail(log))
        if "SCP:marks" not in log:
            return fail("phase A ladder never recorded the t665 marks%s"
                        % log_tail(log))
        if not os.path.isfile(savegame):
            return fail("phase A produced no %s%s" % (savegame, log_tail(log)))
        ok, err = savegame_core_ok(c4group, savegame, workdir)
        if not ok:
            return fail("phase A savegame invalid: %s" % err)

        # --- step 3: phase B — resume the savegame, jobs resume ------------
        rc, log = run_engine(engine, ["--console", "--smoke-run", PHASE_B_CAP,
                                      "--frame-rate-cap", "1000",
                                      "-s", savegame])
        if rc is None:
            return fail("phase B %s" % log)
        if rc != 0:
            return fail("phase B exit %d (expected 0)%s" % (rc, log_tail(log)))
        if FATAL_RE.search(log):
            return fail("phase B log has a fatal/[error] line%s" % log_tail(log))
        if "SCP:resumed" not in log:
            return fail("phase B ladder never reached the t1260 resume arm%s"
                        % log_tail(log))
        if PASS_LINE not in log:
            return fail("phase B missing '%s'%s" % (PASS_LINE, log_tail(log)))

        print("SaveContinueProof E2E PASS")
        return 0
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
        if os.path.exists(savegame):
            try:
                os.remove(savegame)
            except OSError:
                pass

if __name__ == "__main__":
    sys.exit(main())
