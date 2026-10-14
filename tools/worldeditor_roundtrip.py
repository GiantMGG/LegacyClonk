#!/usr/bin/env python3
"""worldeditor_roundtrip — paint -> SaveGame(false) -> reload -> pixels persist (cycle 230).

Proves the roadmap check "worldeditor save round trip" on
content/SavegameTests.c4d/Tests.c4f/WorldEditorRoundtrip.c4s through the
console engine, without any UI:

  Phase A  --console --smoke-run 350 --smoke-scenario-save-at:210
            --frame-rate-cap 1000 -s <PACKED fixture>
          -> the fixture's pristine arm paints Rock at MARK1 (200,100) and
             Gold-Rough at MARK2 (700,100) by t105 (TexMap pair 45; a
             dynamic Gold-Gold AddEntry fails Init - no Gold texture png),
             probes the unpainted Earth interior NEG (400,200), then idles;
             the engine flag fires one C4Console::SaveGame(false) at t210 -
             the pinned world-editor scenario save - writing the painted
             landscape back into the packed scenario group (in-place).
  Check    extract Map.bmp from the saved packed .c4s, sha256-diff against
           the pristine fixture's Map.bmp: must DIFFER (proof the paint
           landed in the saved FILE, localizing a landscape-write MUT to
           phase A).
  Phase B  --console --smoke-run 350 --frame-rate-cap 1000 -s <same packed>
          -> fresh process reopens the saved group; the fixture's
             Initialize probe (GetMaterial(200,100)==Rock) flips it to the
             reload arm, which asserts MARK1/MARK2/NEG in-engine and logs
             WorldEditorRoundtrip PASS before any restored effect ticks.

Engine discipline (rules/engine-behavior-gotchas.md #6): stdin=DEVNULL at
every spawn, cwd = the engine binary's directory. Effect-timer FatalError
exits 0 with an empty fatal stack (gotchas #3), so the FAIL marker is
grepped in addition to the rc/[error] belt.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCEN_NAME = "WorldEditorRoundtrip.c4s"
PHASE_A_CAP = "350"
SAVE_AT_TICK = "210"
RUN_TIMEOUT = 200  # s, per engine spawn (a hung run must fail, not linger)
PASS_LINE = "WorldEditorRoundtrip PASS"
E2E_PASS_LINE = "WorldEditorRoundtrip E2E PASS"
SAVE_LINE = "--smoke-scenario-save-at: saved"

# Same oracle the CTest stanza uses: [error]/[critical]/[fatal] + FatalError.
FATAL_RE = re.compile(r"FatalError|\[error\]|\[critical\]|\[fatal\]", re.IGNORECASE)
# Cycle-90 belt: an effect-timer FatalError exits 0 with an empty fatal
# stack, so the scenario's own FAIL marker is grepped as a second layer.
FAIL_MARKER = "WorldEditorRoundtrip FAIL:"

def fail(msg):
    print("WorldEditorRoundtrip E2E FAIL: %s" % msg)
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

def extract_map(c4group, packed, workdir):
    """Extract the saved scenario's Map.bmp; return (sha256, None) or
    (None, err). c4group -et <entry> <dir> extraction (savegame_core_ok
    precedent)."""
    out = os.path.join(workdir, "saved-map")
    os.mkdir(out)
    proc = subprocess.run([c4group, packed, "-et", "Map.bmp", out],
                          capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120)
    if proc.returncode != 0:
        return None, ("c4group extract failed (rc=%s): %s"
                      % (proc.returncode, (proc.stdout or "") + (proc.stderr or "")))
    path = os.path.join(out, "Map.bmp")
    if not os.path.isfile(path):
        return None, "saved scenario has no Map.bmp entry"
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest(), None
    except OSError as exc:
        return None, "cannot read extracted Map.bmp: %s" % exc

def file_sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

def phase_a(engine, c4group, packed, pristine_map_hash):
    """Phase A: paint ladder + pinned scenario save. Returns error msg or
    None. Asserts, in order: clean exit, no fatal/[error] line, no FAIL
    marker (cycle-90 belt), the save line, the three ladder markers."""
    rc, log = run_engine(engine, ["--console", "--smoke-run", PHASE_A_CAP,
                                  "--smoke-scenario-save-at:" + SAVE_AT_TICK,
                                  "--frame-rate-cap", "1000",
                                  "-s", packed])
    if rc is None:
        return "phase A %s" % log
    if rc != 0:
        return "phase A exit %d (expected 0)%s" % (rc, log_tail(log))
    if FATAL_RE.search(log):
        return "phase A log has a fatal/[error] line%s" % log_tail(log)
    if FAIL_MARKER in log:
        return "phase A has FAIL marker%s" % log_tail(log)
    if SAVE_LINE not in log:
        return ("phase A missing save line '%s'%s"
                % (SAVE_LINE, log_tail(log)))
    for step in ("1", "2", "3"):
        if ("WorldEditorRoundtrip step %s" % step) not in log:
            return ("phase A missing ladder marker "
                    "'WorldEditorRoundtrip step %s'%s" % (step, log_tail(log)))
    return None

def phase_b(engine, packed):
    """Phase B: reopen the saved scenario in a fresh process; the fixture's
    Initialize probe (GetMaterial(200,100)==Rock) flips it to the reload
    arm, which asserts MARK1/MARK2/NEG in-engine and logs the PASS line
    before any restored effect can tick. Returns error msg or None."""
    rc, log = run_engine(engine, ["--console", "--smoke-run", PHASE_A_CAP,
                                  "--frame-rate-cap", "1000",
                                  "-s", packed])
    if rc is None:
        return "phase B %s" % log
    if rc != 0:
        return "phase B exit %d (expected 0)%s" % (rc, log_tail(log))
    if FATAL_RE.search(log):
        return "phase B log has a fatal/[error] line%s" % log_tail(log)
    if FAIL_MARKER in log:
        return "phase B has FAIL marker%s" % log_tail(log)
    if PASS_LINE not in log:
        return "phase B missing '%s'%s" % (PASS_LINE, log_tail(log))
    return None

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: worldeditor_roundtrip.py <engine binary> <fixture dir>",
              file=sys.stderr)
        return 2
    engine, fixture = os.path.abspath(args[0]), os.path.abspath(args[1])

    if not os.path.isfile(engine):
        return fail("engine not found: %s" % engine)
    if not os.path.isdir(fixture):
        return fail("fixture directory not found: %s" % fixture)

    c4group = os.path.join(os.path.dirname(engine), "c4group")
    if not os.path.isfile(c4group):
        c4group = os.path.join(os.path.dirname(engine), "c4group.exe")
    if not os.path.isfile(c4group):
        return fail("sibling c4group not found next to %s" % engine)

    pristine_map = os.path.join(fixture, "Map.bmp")
    if not os.path.isfile(pristine_map):
        return fail("pristine fixture Map.bmp not found: %s" % pristine_map)
    pristine_map_hash = file_sha256(pristine_map)

    workdir = None
    try:
        workdir = tempfile.mkdtemp(prefix="worldeditor_roundtrip_")

        # --- step 0: pack the fixture (mutable copy; repo content safe) ----
        packed, err = pack_fixture(c4group, fixture, workdir)
        if err is not None:
            return fail(err)

        # --- phase A: paint ladder + pinned scenario save ------------------
        err = phase_a(engine, c4group, packed, pristine_map_hash)
        if err is not None:
            return fail(err)

        # --- post-save file check: the paint round-tripped into the file ---
        saved_hash, err = extract_map(c4group, packed, workdir)
        if err is not None:
            return fail(err)
        if saved_hash == pristine_map_hash:
            return fail("post-save Map.bmp identical to pristine fixture "
                        "(paint not saved)")

        # --- phase B: reopen + assert (fresh process) ----------------------
        err = phase_b(engine, packed)
        if err is not None:
            return fail(err)

        print(E2E_PASS_LINE)
        return 0
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
