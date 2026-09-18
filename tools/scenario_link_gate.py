#!/usr/bin/env python3
"""scenario_link_gate — tutorial/world link gate (spec tutorial-guidance-live, cycle 142).

Tiers (all must hold):
  W1 (source pin): kTutorial01Path in src/C4StartupWelcomeDlg.cpp is the forward-slash
      literal "Tutorial.c4f/Tutorial01.c4s" (the backslash form defeats
      RegisterParentFolders; 213 helper calls resolved to `unknown identifier:`).
  W2 (player-path boot): engine spawned with CWD = content root and
      -s Tutorial.c4f/Tutorial01.c4s --smoke-run 350 logs ZERO `unknown identifier:`
      lines AND the instrumented first tutorial message
      ("TutorialMessage: Welcome to the world of Clonk.").
  L  (link sweep): in-place --smoke-run 60 boots of Tutorial02-10 and the 14 clean
      Worlds.c4f scenarios; ZERO `unknown identifier:` per boot.

CaveExplorer.c4s and Stormwatch.c4s are on the printed skip list (known symbol debt;
spec remaining-work). Engine spawns go through tools/run_engine_headless.py
(stdin=DEVNULL, engine-behavior-gotchas #6). Python 3 stdlib only.

Prints one PASS/FAIL line per scenario, the skip list, then one aggregate line
`scenario_link_gate PASS` (the CTest PASS_REGULAR_EXPRESSION target). Exit 0 only
on a full pass.
"""
import argparse
import os
import re
import subprocess
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WELCOME_DLG = os.path.join(REPO_DIR, "src", "C4StartupWelcomeDlg.cpp")
RUN_HEADLESS = os.path.join(REPO_DIR, "tools", "run_engine_headless.py")

KPATH_RE = re.compile(r'kTutorial01Path\s*=\s*"([^"]*)"')
EXPECTED_KPATH = "Tutorial.c4f/Tutorial01.c4s"

UNKNOWN_ID_RE = re.compile(r"unknown identifier:")
FIRST_MESSAGE = "TutorialMessage: Welcome to the world of Clonk."

W2_SCENARIO = "Tutorial.c4f/Tutorial01.c4s"
W2_TICKS = "350"
L_TICKS = "60"
PER_SPAWN_TIMEOUT = 120  # seconds per engine spawn

L_SCENARIOS = (
    ["Tutorial.c4f/Tutorial%02d.c4s" % n for n in range(2, 11)]
    + ["Worlds.c4f/" + name for name in [
        "ArcticOcean.c4s", "Ashlands.c4s", "Chasm.c4s", "ColonyBay.c4s",
        "Desert.c4s", "FoggyCliffs.c4s", "Goldmine.c4s", "Lavacaves.c4s",
        "Mountains.c4s", "Outset.c4s", "SkyAtoll.c4s", "SkyIslands.c4s",
        "Tropical.c4s", "Watercaves.c4s",
    ]]
)

SKIP_LIST = [
    ("Worlds.c4f/CaveExplorer.c4s",
     "known debt: 9 unknown identifiers (StampBand/GetMaterialDensity/COMD_*) + syntax errors"),
    ("Worlds.c4f/Stormwatch.c4s",
     "known debt: 1 unknown identifier (g_Chapters)"),
]

def boot(engine, content_dir, rel_scenario, ticks):
    """Spawn the engine once through run_engine_headless.py; return (rc, log)."""
    cmd = [sys.executable, RUN_HEADLESS, engine,
           "--console", "--smoke-run", ticks, "-s", rel_scenario]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=content_dir,
            stdin=subprocess.DEVNULL, timeout=PER_SPAWN_TIMEOUT,
            encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, ""
    log = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, log

def main():
    parser = argparse.ArgumentParser(description="scenario_link_gate driver")
    parser.add_argument("--engine", required=True, help="path to the clonk binary")
    parser.add_argument("--content-dir", required=True, help="content checkout root")
    args = parser.parse_args()

    engine = os.path.abspath(args.engine)
    content_dir = os.path.abspath(args.content_dir)
    failures = []

    # --- W1: source pin ---
    try:
        with open(WELCOME_DLG, encoding="utf-8") as fh:
            src = fh.read()
    except OSError as exc:
        print("W1 source-pin: FAIL (cannot read %s: %s)" % (WELCOME_DLG, exc))
        failures.append("W1")
    else:
        match = KPATH_RE.search(src)
        if match is None:
            print("W1 source-pin: FAIL (kTutorial01Path not found)")
            failures.append("W1")
        elif match.group(1) != EXPECTED_KPATH:
            print("W1 source-pin: FAIL (kTutorial01Path is %r, expected %r)"
                  % (match.group(1), EXPECTED_KPATH))
            failures.append("W1")
        else:
            print("W1 source-pin: PASS (kTutorial01Path == %r)" % EXPECTED_KPATH)

    # --- W2: player-path boot ---
    rc, log = boot(engine, content_dir, W2_SCENARIO, W2_TICKS)
    unknown = UNKNOWN_ID_RE.findall(log) if log else []
    if rc != 0:
        print("W2 Tutorial01: FAIL (engine exit %s)" % rc)
        failures.append("W2")
    elif unknown:
        print("W2 Tutorial01: FAIL (%d `unknown identifier:` lines)" % len(unknown))
        failures.append("W2")
    elif FIRST_MESSAGE not in log:
        print("W2 Tutorial01: FAIL (first TutorialMessage line missing from log)")
        failures.append("W2")
    else:
        print("W2 Tutorial01: PASS (exit 0, 0 unknown identifier:, first message logged)")

    # --- L: link sweep ---
    for rel in L_SCENARIOS:
        rc, log = boot(engine, content_dir, rel, L_TICKS)
        unknown = UNKNOWN_ID_RE.findall(log) if log else []
        if rc != 0 or unknown:
            print("L %s: FAIL (exit %s, %d `unknown identifier:` lines)"
                  % (rel, rc, len(unknown)))
            failures.append("L %s" % rel)
        else:
            print("L %s: PASS" % rel)

    # --- skip list (printed every run) ---
    print("scenario_link_gate skip list:")
    for rel, reason in SKIP_LIST:
        print("  %s -- %s" % (rel, reason))

    if failures:
        print("scenario_link_gate FAIL (%d failure(s))" % len(failures))
        return 1
    print("scenario_link_gate PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
