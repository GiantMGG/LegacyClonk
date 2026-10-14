#!/usr/bin/env python3
"""quicksave_directory_roundtrip — directory-source QuickSave round trip (cycle 231).

Permanent gate for the roadmap check "quicksave-directory-fix": quicksaving
a game whose scenario is a DIRECTORY-form .c4s folder must produce a packed
savegame slot that reloads clean. Proves it on
content/Knights.c4f/SiegeOfHighKeep.c4s (a directory-form scenario, run IN
PLACE — QuickSave's copy goes to the slot, the source is never written):

  Phase A  --console --smoke-run 700 --smoke-save-at:200:QuicksaveDirRT
            --frame-rate-cap 1000 -s <scenario-dir>
          -> one QuickSave at t200 into Savegames.c4f; assert rc 0, belt
             clean, and the '--smoke-save-at: saved <slot>' line.
  Check    RED detectors, in order (spec §5): the slot must be a FILE, must
             be >= 1024 bytes (pre-fix bug: a 76-byte 0-entry corpse while
             logging success), and c4group must extract Game.txt and
             Scenario.txt from it.
  Phase B  --console --smoke-run 350 --frame-rate-cap 1000 -s <slot>
          -> fresh process reloads the savegame; the engine logs the -s
             path verbatim ('Scenario: <slot>', IDS_PRC_LOADC4S,
             C4Game.cpp:300) and the belt stays clean to the run cap.

Engine discipline (rules/engine-behavior-gotchas.md #6): stdin=DEVNULL at
every spawn, cwd = the engine binary's directory. Belt note: the [info]-level
'SaveGame: Error saving game title' wart fires on every quicksave (packed
probes included, C4GameSave.cpp:650) — it must NOT match the belt.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

SLOT_NAME = "QuicksaveDirRT"
CAP_A = "700"
SAVE_AT_TICK = "200"
CAP_B = "350"
MIN_SLOT_BYTES = 1024
RUN_TIMEOUT = 200  # s, per engine spawn (a hung run must fail, not linger)
SAVE_LINE = "--smoke-save-at: saved"
SLOT_RE = re.compile(r"--smoke-save-at: saved (\S+)")
E2E_PASS_LINE = "QuicksaveDirectoryRoundtrip E2E PASS"

# Same oracle the CTest stanza uses: [error]/[critical]/[fatal] + FatalError.
FATAL_RE = re.compile(r"FatalError|\[error\]|\[critical\]|\[fatal\]", re.IGNORECASE)
# Known-benign, self-healing savegame-load diagnostics (cycle-231
# adjudication): C4GameObjects' loader normalizes compound sort categories
# and re-links mis-ordered objects in place (C4GameObjects.cpp:827-:871),
# then resumes cleanly. Proven identical on the packed-source path — the
# UNFIXED tree's own PackedABpre slot reloads with the same two [error]
# lines (scratch/231/t2-packedsrc-reload.log). Any other [error] still reds.
OBJECTS_TXT_SORT_WART = re.compile(
    r"Objects\.txt: (Object #\d+ (is missing|has invalid) sorting category"
    r"|Wrong object order of #\d+-#\d+! \((down|up)\))")

def fail(msg):
    print("QuicksaveDirectoryRoundtrip E2E FAIL: %s" % msg)
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

def phase_a(engine, scenario):
    """Phase A: run the directory-form scenario to the cap with one
    QuickSave at SAVE_AT_TICK. Returns (slot_path, None) or (None, err).
    Asserts, in order: clean exit, belt clean, save line, slot path in the
    save line."""
    rc, log = run_engine(engine, [
        "--console", "--smoke-run", CAP_A,
        "--smoke-save-at:%s:%s" % (SAVE_AT_TICK, SLOT_NAME),
        "--frame-rate-cap", "1000",
        "-s", scenario])
    if rc is None:
        return None, "phase A %s" % log
    if rc != 0:
        return None, "phase A exit %d (expected 0)%s" % (rc, log_tail(log))
    if FATAL_RE.search(log):
        return None, "phase A log has a fatal/[error] line%s" % log_tail(log)
    if SAVE_LINE not in log:
        return None, ("phase A missing save line '%s'%s"
                      % (SAVE_LINE, log_tail(log)))
    match = SLOT_RE.search(log)
    if not match:
        return None, "phase A missing slot path in save line%s" % log_tail(log)
    return match.group(1), None

def extract_entry(c4group, slot, entry, workdir):
    """c4group -et <entry> <dir> extraction of the slot (RED detector (c)).
    Returns None on success or the pinned fail message on failure."""
    out = os.path.join(workdir, "extract-" + entry)
    os.mkdir(out)
    proc = subprocess.run([c4group, slot, "-et", entry, out],
                          capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120)
    if proc.returncode != 0 or not os.path.isfile(os.path.join(out, entry)):
        return ("save slot extraction of %s failed (rc=%s): %s"
                % (entry, proc.returncode, (proc.stdout or "") + (proc.stderr or "")))
    return None

def artifact_checks(c4group, slot, workdir):
    """RED detectors (spec §5), in order: (a) the slot is a file, (b) it is
    >= 1024 bytes, (c) Game.txt and Scenario.txt extract from it."""
    if not os.path.isfile(slot):
        return "save slot is not a file: %s" % slot
    size = os.path.getsize(slot)
    if size < MIN_SLOT_BYTES:
        return ("save slot %s too small: %d bytes (< %d; 76-byte corpse)"
                % (slot, size, MIN_SLOT_BYTES))
    for entry in ("Game.txt", "Scenario.txt"):
        err = extract_entry(c4group, slot, entry, workdir)
        if err is not None:
            return err
    return None

def phase_b(engine, slot):
    """Phase B: reload the slot in a fresh process to the cap. The engine
    logs the -s path verbatim via IDS_PRC_LOADC4S ('Scenario: <slot>').
    The belt drops the known Objects.txt sort-validator lines first
    (OBJECTS_TXT_SORT_WART, cycle-231 adjudication)."""
    rc, log = run_engine(engine, ["--console", "--smoke-run", CAP_B,
                                  "--frame-rate-cap", "1000",
                                  "-s", slot])
    if rc is None:
        return "phase B %s" % log
    belt_log = "\n".join(ln for ln in log.splitlines()
                         if not OBJECTS_TXT_SORT_WART.search(ln))
    if rc != 0:
        return "phase B exit %d (expected 0)%s" % (rc, log_tail(log))
    if FATAL_RE.search(belt_log):
        return "phase B log has a fatal/[error] line%s" % log_tail(log)
    if ("Scenario: %s" % slot) not in log:
        return "phase B missing 'Scenario:' line%s" % log_tail(log)
    return None

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: quicksave_directory_roundtrip.py <engine binary> <scenario dir>",
              file=sys.stderr)
        return 2
    engine, scenario = os.path.abspath(args[0]), os.path.abspath(args[1])

    if not os.path.isfile(engine):
        return fail("engine not found: %s" % engine)
    if not os.path.isdir(scenario):
        return fail("scenario is not a directory: %s" % scenario)

    c4group = os.path.join(os.path.dirname(engine), "c4group")
    if not os.path.isfile(c4group):
        c4group = os.path.join(os.path.dirname(engine), "c4group.exe")
    if not os.path.isfile(c4group):
        return fail("sibling c4group not found next to %s" % engine)

    workdir = None
    try:
        workdir = tempfile.mkdtemp(prefix="quicksave_directory_roundtrip_")

        # --- phase A: directory-source quicksave --------------------------
        slot, err = phase_a(engine, scenario)
        if err is not None:
            return fail(err)

        # --- artifact checks: packed file, >= 1024 B, extractable ---------
        err = artifact_checks(c4group, slot, workdir)
        if err is not None:
            return fail(err)

        # --- phase B: reload the slot in a fresh process ------------------
        err = phase_b(engine, slot)
        if err is not None:
            return fail(err)

        print(E2E_PASS_LINE)
        return 0
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
