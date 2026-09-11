#!/usr/bin/env python3
"""Run the engine with stdin from /dev/null.

The console engine reads stdin commands; under CI the inherited
stdin (a runner pipe) can block the engine at startup. CTest
cannot redirect stdin, so this wrapper does it for the direct
engine invocations.

--smoke-player-fixture <path> (repeatable): the engine writes player
state back into any .c4p it joins on game over, so player fixtures
must never be passed to it directly. Every value is copied to a fresh
temp file inside a per-run tempdir and the temp paths are appended to
the engine argv (the net_desync_smoke.py fixture-copy pattern,
promoted into the shared wrapper for the two-player melee smokes).
The tempdir is removed once the engine exits.
"""
import os
import shutil
import subprocess
import sys
import tempfile

def main() -> int:
    args = sys.argv[1:]
    player_fixtures = []

    # Pull every --smoke-player-fixture <path> pair out of the argv
    # before anything reaches the engine.
    i = 0
    while i < len(args):
        if args[i] == "--smoke-player-fixture":
            if i + 1 >= len(args):
                print("run_engine_headless: --smoke-player-fixture needs a value", file=sys.stderr)
                return 2
            player_fixtures.append(args[i + 1])
            del args[i:i + 2]
        else:
            i += 1

    tmpdir = None
    rc = 0
    try:
        if player_fixtures:
            tmpdir = tempfile.mkdtemp(prefix="smoke_plr_")
            for i, fixture in enumerate(player_fixtures):
                temp_path = os.path.join(tmpdir, f"SmokePlayer{i}.c4p")
                shutil.copyfile(fixture, temp_path)
                args.append(temp_path)

        rc = subprocess.call(args, stdin=subprocess.DEVNULL)
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # Match the shell's signal-exit convention (128+signo), not Python's
    # 256-signo, so CTest sees the same code the bare engine would give.
    if rc < 0:
        rc = 128 - rc
    return rc

if __name__ == "__main__":
    sys.exit(main())
