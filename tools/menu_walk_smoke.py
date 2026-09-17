#!/usr/bin/env python3
"""menu-walk-smoke — five-leg new-player-walk driver (spec 2026-09-17, cycle 131).

Covers the Epic-1 guarantee: a new player sees the welcome dialog, plays the
tutorial, finds the tutorial world first under "Start Game", and loads the
guide's first scenario (Colony Bay).

Legs:
  A1 guide-URL:    parse kFirstGameGuideURL from src/C4StartupWelcomeDlg.cpp
                   (the constexpr spans two source lines) and HTTP-GET it;
                   red on status >= 400 or on a missing bundled/local target.
  A2 tutorial-load: content/Tutorial.c4f/Tutorial01.c4s loads under
                   --smoke-run 350 (mirrors kTutorial01Path / OnPlayTutorialBtn).
  A3 tutorial-first: Tutorial.c4f holds the UNIQUE nonzero minimum Folder.txt
                   Index across content packs (Index=0 means "unindexed", which
                   sorts last per EntrySortFunc, C4StartupScenSelDlg.cpp).
  A4 locked-refusal: tests/fixtures/MenuWalkLocked.c4s (head MissionAccess) is
                   REFUSED by the engine: exit 1 + "Access to this mission"
                   in the log (C4Game.cpp LogFatal path).
  A5 ColonyBay-load: content/Worlds.c4f/ColonyBay.c4s loads clean (exit 0, no
                   FATAL). Plain [error] DebugLog noise is TOLERATED (ColonyBay
                   logs pre-existing [error] lines at base).

Addendum 1 (binding): A1/A3 ship in KNOWN-RED report mode in the default run —
each prints KNOWN-RED(<slug>): <detail>, the run exits 0, and a loud summary
names the owning roadmap items (quickstart-link-fix, tutorial-first-in-browser).
--strict runs every leg strict (cycle RED evidence). A2/A4/A5 are strict in BOTH
modes. Any UNDECLARED leg failure is a hard FAIL in both modes.

Engine discipline (rules/engine-behavior-gotchas.md #6): stdin=DEVNULL at EVERY
engine spawn, via tools/run_engine_headless.py, with cwd = the engine binary's
directory so the build-dir content-pack symlinks resolve. Python 3 stdlib only.
"""

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Repo root lives two levels up from this file (tools/menu_walk_smoke.py).
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WELCOME_DLG = os.path.join(REPO_DIR, "src", "C4StartupWelcomeDlg.cpp")
LOCKED_FIXTURE = os.path.join(REPO_DIR, "tests", "fixtures", "MenuWalkLocked.c4s")
RUN_HEADLESS = os.path.join(REPO_DIR, "tools", "run_engine_headless.py")

# kFirstGameGuideURL spans lines 46-47 of C4StartupWelcomeDlg.cpp.
GUIDE_URL_RE = re.compile(r'kFirstGameGuideURL\s*=\s*"([^"]+)"', re.DOTALL)
INDEX_RE = re.compile(r"^Index\s*=\s*(\d+)\s*$", re.MULTILINE)

# Roadmap owners of the KNOWN-RED legs (Addendum 1).
KNOWN_RED_OWNERS = {"A1": "quickstart-link-fix", "A3": "tutorial-first-in-browser"}

SMOKE_TICKS = "350"
RUN_TIMEOUT = 60        # seconds, per engine spawn
HTTP_TIMEOUT = 15       # seconds, per urllib attempt
HTTP_RETRIES = 3        # retries on connection errors / 5xx before giving up
RETRY_DELAY = 1         # seconds between network retries

def run_engine(engine, scenario):
    """Spawn the console engine once; return (exit_code, combined_log).

    Every spawn goes through tools/run_engine_headless.py (stdin=DEVNULL,
    gotcha #6); cwd is the engine binary's directory (build-dir pack symlinks).
    """
    cmd = [sys.executable, RUN_HEADLESS, engine,
           "--console", "--smoke-run", SMOKE_TICKS, "-s", scenario]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=os.path.dirname(engine), stdin=subprocess.DEVNULL,
            timeout=RUN_TIMEOUT, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, "engine run timed out after %d s" % RUN_TIMEOUT
    log = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, log

def log_tail(log):
    """Compact diagnostic tail for a failed engine run."""
    tail = log.strip().splitlines()[-6:]
    return ":\n  " + "\n  ".join(tail) if tail else ""

def has_fatal(log):
    """True when the log carries a fatal-class line.

    Covers [critical]/'fatal' lines AND the effect-timer FatalError class
    (engine-behavior-gotchas.md #3): a FatalError inside an effect timer is
    caught as C4AulExecError, logged '[error] User error: <Name> FAIL: ...',
    and the process still exits 0 — so the oracle must match the 'FAIL:'
    marker directly, never rely on the exit code. Plain [error] DebugLog
    lines stay tolerated (ColonyBay's pre-existing noise is [error], never
    FAIL:; verified 0 FAIL: occurrences in current A2/A5/A4 logs).
    """
    return ("[critical]" in log.lower() or "fatal" in log.lower()
            or re.search(r"\bFAIL:", log) is not None)

def http_status(url):
    """GET url, retrying HTTP_RETRIES times on connection errors / 5xx.

    Returns the final HTTP status int (>=400 -> red), or None when the host is
    persistently unreachable (-> SKIP per Addendum 1).
    """
    status = None
    for attempt in range(HTTP_RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            if 500 <= status < 600 and attempt < HTTP_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return status
        except (urllib.error.URLError, OSError, TimeoutError):
            status = None
            if attempt < HTTP_RETRIES:
                time.sleep(RETRY_DELAY)
    return status

# --- Legs -------------------------------------------------------------------

def leg_a1(strict):
    """A1 guide-URL: parse kFirstGameGuideURL; red on HTTP >= 400 or missing
    bundled target. Regex parse failure is a hard FAIL in both modes."""
    try:
        src = open(WELCOME_DLG, "r", encoding="utf-8", errors="replace").read()
    except OSError as exc:
        return "FAIL", "cannot read %s: %s" % (WELCOME_DLG, exc)
    match = GUIDE_URL_RE.search(src)
    if not match:
        return "FAIL", "kFirstGameGuideURL not found via regex in src/C4StartupWelcomeDlg.cpp"
    raw = match.group(1).strip()
    lower = raw.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        status = http_status(raw)
        if status is None:
            return "SKIP", "A1 network unavailable (persistent connection failure)"
        if status >= 400:
            detail = "guide URL %s -> HTTP %d" % (raw, status)
            return ("FAIL" if strict else "RED_K"), detail
        return "PASS", "guide URL %s -> HTTP %d" % (raw, status)
    # Bundled/local doc target (quickstart-link-fix may take either shape).
    # Resolve relative to the repo docs root, tolerating a leading "./", a
    # stray "/" or "../" from a doc-relative reference (the old lstrip()
    # chain mangled './docs/x' into '/docs/x' and joined it as absolute).
    # An empty constant is a malformed config: hard FAIL in both modes.
    rel = raw.replace("\\", "/")
    if not rel or not rel.removeprefix("./").lstrip("/"):
        return "FAIL", "kFirstGameGuideURL is empty (no bundled target to check)"
    rel = rel.removeprefix("./").lstrip("/")
    target = os.path.normpath(os.path.join(REPO_DIR, rel))
    if os.path.exists(target):
        return "PASS", "bundled guide target %s exists" % target
    detail = "bundled guide target %s missing (resolved %s)" % (raw, target)
    return ("FAIL" if strict else "RED_K"), detail

def leg_a2(engine, content_dir):
    """A2 tutorial-load: Tutorial01.c4s must reach the end of --smoke-run 350
    with exit 0 and no fatal line."""
    scenario = os.path.join(content_dir, "Tutorial.c4f", "Tutorial01.c4s")
    rc, log = run_engine(engine, scenario)
    if rc is None:
        return "FAIL", "Tutorial01.c4s: %s" % log
    if rc != 0:
        return "FAIL", "Tutorial01.c4s exit %d%s" % (rc, log_tail(log))
    if has_fatal(log):
        return "FAIL", "Tutorial01.c4s log has a [critical]/fatal/FAIL: line%s" % log_tail(log)
    return "PASS", "Tutorial01.c4s loads (exit 0, no fatal)"

def scan_packs(content_dir):
    """Parse Index= from every <content>/*/Folder.txt. Returns {pack: index};
    a pack without an Index= line counts as 0 (unindexed)."""
    packs = {}
    try:
        names = sorted(os.listdir(content_dir))
    except OSError as exc:
        return None, "cannot list content dir %s: %s" % (content_dir, exc)
    for name in names:
        pack_dir = os.path.join(content_dir, name)
        folder_txt = os.path.join(pack_dir, "Folder.txt")
        if not os.path.isdir(pack_dir) or not os.path.exists(folder_txt):
            continue
        try:
            text = open(folder_txt, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        match = INDEX_RE.search(text)
        packs[name] = int(match.group(1)) if match else 0
    return packs, None

def leg_a3(content_dir, strict):
    """A3 tutorial-first: Tutorial.c4f must hold the UNIQUE NONZERO minimum
    Folder.txt Index (Index=0 = unindexed, sorts last)."""
    packs, err = scan_packs(content_dir)
    if err is not None:
        return "FAIL", err
    if not packs:
        return "FAIL", "no Folder.txt packs found in %s" % content_dir
    if "Tutorial.c4f" not in packs:
        return "FAIL", "Tutorial.c4f pack not found in %s" % content_dir
    nonzero = {name: index for name, index in packs.items() if index != 0}
    if not nonzero:
        return "FAIL", ("no nonzero Folder.txt Index in %s "
                        "(Tutorial.c4f Index=%d)" % (content_dir, packs["Tutorial.c4f"]))
    min_index = min(nonzero.values())
    holders = sorted(name for name, index in nonzero.items() if index == min_index)
    tutorial_index = packs["Tutorial.c4f"]

    if tutorial_index == 0:
        detail = "Tutorial.c4f unindexed (Index=0) sorts last, not first"
    elif len(holders) > 1:
        colliders = [h for h in holders if h != "Tutorial.c4f"]
        detail = ("Folder.txt Index=%d tie: %s collides with Tutorial.c4f "
                  "(unique nonzero minimum required)" % (min_index, ", ".join(colliders)))
    elif min_index != tutorial_index:
        detail = ("minimum Folder.txt Index=%d held by %s, not Tutorial.c4f "
                  "(Index=%d)" % (min_index, holders[0], tutorial_index))
    else:
        return "PASS", ("Tutorial.c4f holds the unique nonzero minimum "
                        "Folder.txt Index=%d" % min_index)
    return ("FAIL" if strict else "RED_K"), detail

def leg_a4(engine):
    """A4 locked-refusal: the MenuWalkLocked fixture must be refused (exit 1 +
    "Access to this mission"); exit 0 means the locked class loaded -> FAIL."""
    rc, log = run_engine(engine, LOCKED_FIXTURE)
    if rc is None:
        return "FAIL", "locked fixture: %s" % log
    if rc == 0:
        return "FAIL", "locked fixture loaded (exit 0)"
    if rc != 1:
        return "FAIL", "locked fixture exit %d (expected 1)%s" % (rc, log_tail(log))
    if "Access to this mission" not in log:
        return "FAIL", "'Access to this mission' missing from log%s" % log_tail(log)
    return "PASS", "locked fixture refused (exit 1, 'Access to this mission')"

def leg_a5(engine, content_dir):
    """A5 ColonyBay-load: World.c4f/ColonyBay.c4s loads clean (exit 0, no
    FATAL-class line). Do NOT assert absence of [error] — ColonyBay logs
    pre-existing [error] DebugLog lines at base (spec premise 4)."""
    scenario = os.path.join(content_dir, "Worlds.c4f", "ColonyBay.c4s")
    rc, log = run_engine(engine, scenario)
    if rc is None:
        return "FAIL", "ColonyBay.c4s: %s" % log
    if rc != 0:
        return "FAIL", "ColonyBay.c4s exit %d%s" % (rc, log_tail(log))
    if has_fatal(log):
        return "FAIL", "ColonyBay.c4s log has a [critical]/fatal/FAIL: line%s" % log_tail(log)
    return "PASS", "ColonyBay.c4s loads (exit 0, no FATAL)"

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="menu_walk_smoke.py",
        description="Five-leg new-player-walk smoke (spec 2026-09-17).")
    ap.add_argument("--engine", required=True, metavar="PATH",
                    help="path to the clonk console binary (build/clonk)")
    ap.add_argument("--content-dir", required=True, metavar="PATH",
                    help="path to the content directory (workspace content/)")
    ap.add_argument("--strict", action="store_true",
                    help="run every leg strict (A1/A3 FAIL on today's red state)")
    args = ap.parse_args(argv)

    engine = os.path.abspath(args.engine)
    if not os.path.isfile(engine):
        print("menu_walk_smoke FAIL: engine not found: %s" % engine)
        return 1
    content_dir = os.path.abspath(args.content_dir)
    if not os.path.isdir(content_dir):
        print("menu_walk_smoke FAIL: content dir not found: %s" % content_dir)
        return 1

    results = [
        ("A1", leg_a1(args.strict)),
        ("A2", leg_a2(engine, content_dir)),
        ("A3", leg_a3(content_dir, args.strict)),
        ("A4", leg_a4(engine)),
        ("A5", leg_a5(engine, content_dir)),
    ]
    failed = []

    for leg_id, (status, detail) in results:
        if status == "PASS":
            flip = ""
            if args.strict and leg_id in KNOWN_RED_OWNERS:
                flip = " FLIP CANDIDATE (remove marker)"
            print("%s: PASS: %s%s" % (leg_id, detail, flip))
        elif status == "SKIP":
            print("%s: SKIP: %s" % (leg_id, detail))
        elif status == "FAIL":
            print("%s: FAIL: %s" % (leg_id, detail))
            failed.append(leg_id)
        elif status == "RED_K":
            print("%s: KNOWN-RED(%s): %s" % (leg_id, KNOWN_RED_OWNERS[leg_id], detail))

    if args.strict:
        if failed:
            print("menu_walk_smoke FAIL (%s)" % ", ".join(failed))
            return 1
        print("menu_walk_smoke PASS")
        return 0

    # Default (report) mode.
    if failed:
        print("menu_walk_smoke FAIL (%s)" % ", ".join(failed))
        return 1
    red_owners = ", ".join("%s (%s)" % (leg_id, KNOWN_RED_OWNERS[leg_id])
                           for leg_id, widget in results if widget[0] == "RED_K")
    if red_owners:
        print("KNOWN-RED roadmap items: %s" % red_owners)
    print("menu_walk_smoke PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
