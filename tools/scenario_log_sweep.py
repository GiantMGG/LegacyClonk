#!/usr/bin/env python3
"""scenario_log_sweep — shipped-scenario zero-script-error gate (cycle 173).

Boots a roster of shipped scenarios headless and fails on ANY `[error]`
line in the engine log (the 2026-09-26 recon found 34 of 122 shipped
scenarios logging script errors; tasks A-C fixed every non-excluded one).

Roster modes:
  (default) the FIXED roster: every recon-affected scenario minus the
      documented exclusions — the fixtures a scenario boot exercises at
      runtime (see FIXED_ROSTER below).
  --full    every shipped content/**/*.c4s (scenario dirs + loose files,
      Tests.c4f pruned) minus the same exclusions, which are skipped by
      path pattern and REPORTED so the nightly/full run can be green
      while the excluded packs own their debt.

EXCLUSIONS (documented, never silently dropped — printed every full run;
the fixed roster simply does not contain them):
  * Hazard.c4f/ (13 scenarios) — owner directive 2026-09-18 ("not
    interested in the eke and hazard stuff"); Stripe gfx/overlay mismatch
    and friends.
  * content/SiegeRange.c4s (root stray) — content-cleanup's territory;
    owns the whole FindObject int-arg x26 cluster.
  * Tutorial.c4f/Tutorial03.c4s + Tutorial04.c4s — ancient pre-#strict
    scripts (eq"" / goto()) needing full rewrites; deferred follow-up.

Engine spawns go through tools/run_engine_headless.py (stdin=DEVNULL;
engine-behavior-gotchas #6) with --frame-rate-cap 1000 (playtest_sweep
precedent: 13x wall-clock speedup, frame-count semantics unchanged). The
engine runs with CWD = the engine's own directory (the game folder —
planet files + content symlinks live there). Scenario paths are ABSOLUTE:
relative -s paths are fatal, the console engine resolves them against
the program dir, not the content root.

Concurrency: at most 4 engine procs (playtest_sweep MAX_JOBS precedent);
each boot is ~1 s so the default 21-scenario set finishes in well under
a minute.

Prints one PASS/FAIL line per scenario, the exclusion list (--full),
then the aggregate `scenario_log_sweep PASS` line (the CTest
PASS_REGULAR_EXPRESSION target). Exit 0 iff every rostered scenario
boots with zero `[error]` lines. Exit 2 on usage/infrastructure errors.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_HEADLESS = os.path.join(REPO_DIR, "tools", "run_engine_headless.py")
FRAME_RATE_CAP = "1000"  # playtest_sweep precedent (13x wall speedup)

MAX_JOBS = 4  # resource-hygiene: at most 4 concurrent engine procs
PER_SPAWN_TIMEOUT = 60  # seconds per engine spawn (a boot is ~1 s)

DEFAULT_TICKS = 70

# Default tick per scenario, bumped for runtime-exercising classes that
# need frames to reach their error site (Siege FindObject storm ~frame 44,
# CrisisDirector ~70, Tutorial02 "Object call: target is zero!" ~frame 10).
TICK_OVERRIDES = {
    "Knights.c4f/SiegeOfHighKeep.c4s": 350,
    "Worlds.c4f/Stormwatch.c4s": 350,
    "Tutorial.c4f/Tutorial02.c4s": 350,
    "Tutorial.c4f/Tutorial06.c4s": 350,
    "Tutorial.c4f/Tutorial07.c4s": 350,
}

# Every scenario that logged [error] on the 2026-09-26 recon, minus the
# exclusions above (see module docstring). Content-root-relative paths.
FIXED_ROSTER = (
    "Fantasy.c4f/Alchemy.c4s",
    "Fantasy.c4f/Crystalvalley.c4s",
    "Fantasy.c4f/Drachenfels.c4s",
    "Fantasy.c4f/SkiesOfFire.c4s",
    "FarWorlds.c4f/DeepAbyss.c4s",
    "FarWorlds.c4f/Deep.c4s",
    "FarWorlds.c4f/Arctic.c4s",
    "FarWorlds.c4f/Jungle.c4s",
    "Knights.c4f/Paxhill.c4s",
    "Knights.c4f/CoFuT.c4s",
    "Knights.c4f/SiegeOfHighKeep.c4s",
    "Races.c4f/GlowingPeak.c4s",
    "Races.c4f/MonsterRescue.c4s",
    "Races.c4f/Tritonpath.c4s",
    "SilkRoad.c4f/SilkRoad.c4s",
    "Tutorial.c4f/Tutorial01.c4s",
    "Tutorial.c4f/Tutorial02.c4s",
    "Tutorial.c4f/Tutorial06.c4s",
    "Tutorial.c4f/Tutorial07.c4s",
    "Worlds.c4f/CaveExplorer.c4s",
    "Worlds.c4f/Stormwatch.c4s",
)

# --full skip patterns (why, see module docstring):
#   Hazard.c4f/ .. owner directive 2026-09-18
#   SiegeRange.c4s .. root stray, content-cleanup's item
#   Tutorial03/04 .. deferred ancient-syntax rewrites
FULL_SKIP_DIRS = ("Hazard.c4f",)
FULL_SKIP_PATHS = (
    "SiegeRange.c4s",
    "Tutorial.c4f/Tutorial03.c4s",
    "Tutorial.c4f/Tutorial04.c4s",
)

ERROR_RE = re.compile(r"\[error\]")

def die(msg):
    print("ERROR: %s" % msg, file=sys.stderr)
    sys.exit(2)

def find_engine(repo_dir):
    """Default --engine: the build dir binary (build/clonk preferred)."""
    for build_dir in ("build", "build2", "build3", "build4", "build5"):
        for exe in ("clonk", "clonk.exe"):
            cand = os.path.join(repo_dir, build_dir, exe)
            if os.path.isfile(cand):
                return cand
    return None

def enumerate_full(content_dir):
    """Every shipped content/**/*.c4s (scenario dirs + loose files),
    Tests.c4f pruned, exclusions skipped."""
    roster = []
    for root, dirs, files in os.walk(content_dir):
        dirs[:] = [d for d in dirs if d != "Tests.c4f"]
        for name in sorted(dirs) + sorted(files):
            if not name.endswith(".c4s"):
                continue
            rel = os.path.relpath(os.path.join(root, name), content_dir)
            rel = rel.replace(os.sep, "/")
            if rel.startswith(FULL_SKIP_DIRS):
                continue
            if rel in FULL_SKIP_PATHS:
                continue
            roster.append(rel)
    return sorted(roster)

def boot(engine, content_dir, rel, ticks):
    """Spawn the engine once through run_engine_headless.py; return
    (rc, errors, samples) — errors = count of `[error]` lines in stdout,
    samples = first few matching lines for failure diagnosis."""
    scenario = os.path.join(content_dir, rel)
    cmd = [sys.executable, RUN_HEADLESS, engine,
           "--console", "--smoke-run", str(ticks),
           "--frame-rate-cap", FRAME_RATE_CAP, "-s", scenario]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=os.path.dirname(engine),
                              stdin=subprocess.DEVNULL,
                              timeout=PER_SPAWN_TIMEOUT,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, -1, []
    log = (proc.stdout or "") + (proc.stderr or "")
    matches = ERROR_RE.findall(log)
    samples = [ln for ln in log.splitlines() if ERROR_RE.search(ln)][:3]
    return proc.returncode, len(matches), samples

def run_roster(engine, content_dir, roster, default_ticks, jobs):
    results = {}

    def one(rel):
        ticks = TICK_OVERRIDES.get(rel, default_ticks)
        rc, errors, samples = boot(engine, content_dir, rel, ticks)
        results[rel] = (rc, errors, samples)
        return rel, rc, errors

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(one, roster))

    fail = []
    for rel in roster:
        rc, errors, samples = results[rel]
        if rc is None:
            print("TIMEOUT %s (killed after %ds)" % (rel, PER_SPAWN_TIMEOUT))
            fail.append(rel)
        elif errors:
            print("FAIL %s errors=%d" % (rel, errors))
            for ln in samples:
                print("    %s" % ln.strip()[:120])
            fail.append(rel)
        else:
            print("PASS %s errors=0" % rel)
    return fail

def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", default=None,
        help="clonk binary (default: <repo>/build/clonk)")
    ap.add_argument("--content", default=None,
        help="content checkout root (default: <repo>/../content)")
    ap.add_argument("--full", action="store_true",
        help="sweep every shipped content/**/*.c4s minus exclusions "
             "(default: the fixed recon-affected roster)")
    ap.add_argument("--tick", type=int, default=DEFAULT_TICKS,
        help="default smoke-run ticks (default: %(default)d; per-scenario "
             "overrides in TICK_OVERRIDES still apply)")
    ap.add_argument("--jobs", type=int, default=MAX_JOBS,
        help="concurrent engine procs, 1..4 (default: %(default)d)")
    args = ap.parse_args()

    if not 1 <= args.jobs <= MAX_JOBS:
        die("--jobs must be in 1..%d" % MAX_JOBS)

    engine = os.path.abspath(args.engine) if args.engine else find_engine(REPO_DIR)
    if not engine or not os.path.isfile(engine):
        die("engine binary not found (pass --engine; default looks in "
            "<repo>/build{2..5}/clonk)")
    content_dir = os.path.abspath(args.content) if args.content else \
        os.path.join(REPO_DIR, os.pardir, "content")
    if not os.path.isdir(content_dir):
        die("content dir not found: %s (pass --content)" % content_dir)

    roster = enumerate_full(content_dir) if args.full else list(FIXED_ROSTER)
    if args.full:
        for rel in roster:
            if not os.path.exists(os.path.join(content_dir, rel)):
                die("full-sweep scenario missing from content: %s" % rel)
    else:
        for rel in roster:
            if not os.path.exists(os.path.join(content_dir, rel)):
                die("fixed-roster scenario missing from content: %s" % rel)

    start = time.monotonic()
    failed = run_roster(engine, content_dir, roster, args.tick, args.jobs)
    wall = time.monotonic() - start

    skipped = 0
    if args.full:
        excluded = _excluded_enumerate(content_dir)
        skipped = len(excluded)
        print("scenario_log_sweep exclusions (--full):")
        for rel in excluded:
            print("  SKIP %s" % rel)
        print("  (Hazard.c4f = owner directive 2026-09-18; SiegeRange = "
              "content-cleanup; Tutorial03/04 = deferred ancient-syntax "
              "rewrite)")

    npass = len(roster) - len(failed)
    print("scenario_log_sweep: %d scenarios, pass=%d fail=%d skip=%d "
          "(%d concurrent, %.1fs)" % (len(roster), npass, len(failed),
          skipped, args.jobs, wall))
    if failed:
        print("scenario_log_sweep FAIL (%d failure(s))" % len(failed))
        return 1
    print("scenario_log_sweep PASS")
    return 0

def _excluded_enumerate(content_dir):
    """The --full exclusion members, expanded for the skip report."""
    out = []
    for root, dirs, files in os.walk(content_dir):
        dirs[:] = [d for d in dirs if d != "Tests.c4f"]
        for name in sorted(dirs) + sorted(files):
            if not name.endswith(".c4s"):
                continue
            rel = os.path.relpath(os.path.join(root, name), content_dir)
            rel = rel.replace(os.sep, "/")
            full_skip = rel.startswith(FULL_SKIP_DIRS)
            if full_skip or rel in FULL_SKIP_PATHS:
                out.append(rel)
    return sorted(out)

if __name__ == "__main__":
    sys.exit(main())
