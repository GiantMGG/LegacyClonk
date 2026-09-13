#!/usr/bin/env python3
"""Hermetic selftest for the vision-judge lock (cycle 121, spec
vision-judge-serialization s5).

No GPU, no ollama, no engine, no content checkout: a fake-ollama stub
(ThreadingHTTPServer on 127.0.0.1, ephemeral port — the net_* smoke
precedent) serves /api/tags and /api/chat, recording per-request
(start, end) time.monotonic() pairs and the peak in-flight count.
Two tools/vision_qa.py child batteries run against it sharing a private
VQ_LOCK_PATH; the test asserts the second battery WAITS, not overlaps:

  1. both children exit 0 and print GATE PASS (the lock breaks nothing)
  2. stub peak in-flight /api/chat == 1
  3. the recorded intervals, sorted, strictly non-overlap (every start
     >= previous end — all timestamps from one process, no clock skew)
  4. exactly one child output contains WAITING FOR JUDGE LOCK

Anti-vacuity control (s5): the same pair rerun with VQ_LOCK_DISABLE=1
MUST show peak in-flight >= 2 — proving the instrument detects
concurrent judge use, so a green run of 1-3 cannot be vacuous (this is
the safety net for the flock fd/GC silent-release trap, s4.3).

Child staggering is event-driven: child B spawns only after child A's
first /api/chat is in flight at the stub (A is then provably inside its
judge region, holding the lock) — no python-startup jitter can flip
which child waits.

Exit code: 0 = all assertions hold; 1 = any FAIL line was printed
(infra failures print ASSERT FAIL lines).
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from vision_qa import (FLAT_H, FLAT_RGB, FLAT_W, FIXTURE_JPG, PAIR_GAP, Q1,
                       Q2, Q3, Q4, Q5, render_b64)

CHILD = os.path.join(SCRIPT_DIR, "vision_qa.py")
CHAT_DELAY_S = 0.4  # stub service time (sleep OUTSIDE the mutex)
SCALE = 8           # children run --scale 8; the oracle renders with it
SPAWN_DEADLINE_S = 30.0
CHILD_TIMEOUT_S = 90  # 15x headroom over the ~13s serialized worst case

# Default battery answers on the synthetic target (the stub never looks
# at pixels): Q4 "eight legs" >= 4 and Q5 yes-first make the feature
# gate pass; Q2's default contains no tail/arch/tip word (the same
# discipline the flat-block oracle control demands).
DEFAULT_ANSWERS = {
    Q1: "a small dark figure",
    Q2: "a uniform solid-color rectangle",
    Q3: "no",
    Q4: "eight legs",
    Q5: "yes, the two frames show the same figure walking",
}

def canned_oracle_answers():
    """(prompt, image_b64) -> answer, keyed on the exact oracle fixtures:
    the photo JPG bytes and the flat block / stacked pair rendered at the
    children's --scale (deterministic via vision_qa's own constants)."""
    with open(FIXTURE_JPG, "rb") as f:
        photo_b64 = base64.b64encode(f.read()).decode()
    block = [[(*FLAT_RGB, 255)] * FLAT_W for _ in range(FLAT_H)]
    block_b64 = render_b64(block, SCALE)
    stacked = (block + [[(255, 255, 255, 255)] * FLAT_W
                        for _ in range(PAIR_GAP)] + block)
    return {
        # control 1: photo positive — must read "scorpion"
        (Q1, photo_b64): "a scorpion, viewed from above",
        # control 2: flat block — no scorpion/mammal word; Q2 fails
        # tail+arch+tip AND tail+arch; Q3 not yes-first; Q4 count None
        (Q1, block_b64): "a plain solid-color block",
        (Q2, block_b64): "a uniform rectangle of one color",
        (Q3, block_b64): "no",
        (Q4, block_b64): "zero",
        # control 3: stacked flat pair — Q5 must not be yes-first
        (Q5, render_b64(stacked, SCALE)): "no",
    }

class StubState(object):
    def __init__(self):
        self.mutex = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0
        self.chat_count = 0
        self.intervals = []  # (start, end) time.monotonic() pairs

def make_handler(state, canned):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence per-request stderr; verdicts are asserted below

        def _reply(self, obj, code=200):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/api/tags":
                self._reply({"models": [{"name": "stub-qwen"}]})
            else:
                self._reply({"error": "no such path " + self.path}, 404)

        def do_POST(self):
            if self.path != "/api/chat":
                self._reply({"error": "no such path " + self.path}, 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            start = time.monotonic()
            with state.mutex:
                state.in_flight += 1
                state.chat_count += 1
                state.max_in_flight = max(state.max_in_flight,
                                          state.in_flight)
            # The delay is OUTSIDE the mutex on purpose: a server-side
            # sleep under the lock would serialize requests HERE and mask
            # client-side overlap — the exact vacuity this test polices.
            time.sleep(CHAT_DELAY_S)
            msg = (body.get("messages") or [{}])[0]
            prompt = msg.get("content", "")
            image = (msg.get("images") or [""])[0]
            answer = canned.get((prompt, image))
            if answer is None:
                answer = DEFAULT_ANSWERS.get(prompt, "")
            end = time.monotonic()
            with state.mutex:
                state.in_flight -= 1
                state.intervals.append((start, end))
            self._reply({"model": body.get("model", "stub-qwen"),
                         "message": {"role": "assistant", "content": answer},
                         "done": True})

    return Handler

class StubJudge(object):
    """Fake ollama on an ephemeral loopback port; `with` starts/stops it."""

    def __init__(self):
        self.state = StubState()
        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.state, canned_oracle_answers()))
        self.httpd.daemon_threads = True
        self._thread = threading.Thread(target=self.httpd.serve_forever,
                                        daemon=True)

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def chats_seen(self):
        with self.state.mutex:
            return self.state.chat_count

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

def child_env(lock_path, disable_lock=False):
    env = dict(os.environ)
    env["VQ_ALLOW_DAYTIME"] = "1"  # window rule orthogonal to the lock
    # Private lockfile: the selftest never contends with a real battery.
    env["VQ_LOCK_PATH"] = lock_path
    # Anti-vacuity control ONLY (spec s4.9) — never bypass contention.
    if disable_lock:
        env["VQ_LOCK_DISABLE"] = "1"
    return env

def spawn_child(url, image, lock_path, disable_lock=False):
    cmd = [sys.executable, CHILD, "--host", url, "--model", "stub-qwen",
           "--image", image, "--facet", "0,0,8,6", "--phases", "2",
           "--runs", "1", "--scale", "8", "--gate-mode", "feature"]
    return subprocess.Popen(cmd, env=child_env(lock_path, disable_lock),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)

def run_pair(stub, image, lock_path, disable_lock=False):
    """(ok, rc_a, rc_b, out_a, out_b). Child B spawns only after child
    A's first /api/chat is in flight — A then holds the lock for sure,
    so the wait-line assertion carries no startup-jitter race."""
    a = spawn_child(stub.url, image, lock_path, disable_lock)
    seen = False
    deadline = time.monotonic() + SPAWN_DEADLINE_S
    while time.monotonic() < deadline:
        if stub.chats_seen() >= 1:
            seen = True
            break
        if a.poll() is not None:
            out_a = a.stdout.read()
            print(f"ASSERT FAIL: child A exited before judge contact "
                  f"(rc={a.returncode}):\n{out_a}", flush=True)
            return False, a.returncode, None, out_a, ""
        time.sleep(0.05)
    if not seen:
        a.kill()
        out_a = a.stdout.read()
        print(f"ASSERT FAIL: child A made no judge contact within "
              f"{SPAWN_DEADLINE_S}s", flush=True)
        return False, None, None, out_a, ""
    b = spawn_child(stub.url, image, lock_path, disable_lock)
    try:
        out_a = a.communicate(timeout=CHILD_TIMEOUT_S)[0]
        out_b = b.communicate(timeout=CHILD_TIMEOUT_S)[0]
    except subprocess.TimeoutExpired:
        a.kill()
        b.kill()
        print(f"ASSERT FAIL: child exceeded {CHILD_TIMEOUT_S}s runtime",
              flush=True)
        return False, None, None, "", ""
    return True, a.returncode, b.returncode, out_a, out_b

def main():
    failures = []

    def check(ok, label):
        print(("PASS: " if ok else "FAIL: ") + label, flush=True)
        if not ok:
            failures.append(label)

    tmp = tempfile.mkdtemp(prefix="vqlock-selftest-")
    try:
        # Synthetic two-phase 16x6 target PNG (facet 0,0,8,6); the stub
        # answers do not depend on target pixels.
        grid = [[(90, 58, 31, 255)] * 8 + [(60, 90, 40, 255)] * 8
                for _ in range(6)]
        image = os.path.join(tmp, "target.png")
        with open(image, "wb") as f:
            f.write(base64.b64decode(render_b64(grid, SCALE)))

        # -- phase 1: the locked pair must serialize ----------------------
        # 15 judge calls per child (6 oracle + 8 phase probes + 1 pair)
        # -> 30 intervals when both complete.
        with StubJudge() as stub:
            ok, rc_a, rc_b, out_a, out_b = run_pair(
                stub, image, os.path.join(tmp, "judge.lock"))
            if not ok:
                return 1
            check(rc_a == 0 and "GATE PASS" in out_a,
                  "child A exit 0 + GATE PASS")
            check(rc_b == 0 and "GATE PASS" in out_b,
                  "child B exit 0 + GATE PASS")
            check(stub.state.max_in_flight == 1,
                  "peak in-flight /api/chat == 1 (got "
                  + str(stub.state.max_in_flight) + ")")
            ints = sorted(stub.state.intervals)
            overlap = any(ints[i + 1][0] < ints[i][1]
                          for i in range(len(ints) - 1))
            check(len(ints) == 30 and not overlap,
                  f"strict timestamp non-overlap over {len(ints)} "
                  "intervals")
            waits = (("WAITING FOR JUDGE LOCK" in out_a)
                     + ("WAITING FOR JUDGE LOCK" in out_b))
            check(waits == 1,
                  "exactly one WAITING FOR JUDGE LOCK line (got "
                  + str(waits) + ")")

        # -- phase 2: anti-vacuity — the disabled lock MUST overlap -------
        with StubJudge() as stub:
            ok, rc_a, rc_b, out_a, out_b = run_pair(
                stub, image, os.path.join(tmp, "judge-disabled.lock"),
                disable_lock=True)
            if not ok:
                return 1
            check(rc_a == 0 and rc_b == 0, "control pair both exit 0")
            check(stub.state.max_in_flight >= 2,
                  "anti-vacuity: VQ_LOCK_DISABLE=1 overlaps (peak "
                  "in-flight " + str(stub.state.max_in_flight) + " >= 2)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"SELFTEST FAIL: {len(failures)} assertion(s): "
              + "; ".join(failures), flush=True)
        return 1
    print("SELFTEST PASS: judge lock serializes; instrument not vacuous",
          flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
