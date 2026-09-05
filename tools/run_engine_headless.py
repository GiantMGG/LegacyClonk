#!/usr/bin/env python3
"""Run the engine with stdin from /dev/null.

The console engine reads stdin commands; under CI the inherited
stdin (a runner pipe) can block the engine at startup. CTest
cannot redirect stdin, so this wrapper does it for the direct
engine invocations."""
import subprocess
import sys

sys.exit(subprocess.call(sys.argv[1:], stdin=subprocess.DEVNULL))
