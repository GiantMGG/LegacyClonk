#!/usr/bin/env python3
"""net_settings_sync_smoke.py -- host->client settings sync CI smoke.

Spawns two headless LegacyClonk engine instances on loopback: a host with
explicit --parameter overrides (Seed, Amplitude, Rules, Goals) and a
client joining via reference-server discovery (/client:0). Asserts:

  (a) both peers exit 0 within timeout
  (b) no "Network: Synchronization loss!" in either log
  (c) host and client log the SAME "LandscapeFP:" value
  (d) both peers log "RulesObjects: 1" / "GoalsObjects: 1"
  (e) a second pass with Seed ONLY (no Amplitude=) logs a DIFFERENT
      host "LandscapeFP:" -- the cross-pass diff proves the Amplitude
      override is live end-to-end
  (f) in the second pass, host and client again log the SAME
      "LandscapeFP:" value

See spec net-preround-settings-fix.

Exit codes:
  0 -- test passed
  1 -- test failed (sync loss, fingerprint divergence, non-zero exit)
  2 -- infrastructure error (engine binary missing, bad scenario path)
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DESYNC_MARKER = "Network: Synchronization loss!"
REF_SERVER_PORT = 11111

DEFAULT_PLAYER_FILE = (
    Path(__file__).resolve().parent.parent
    / "tests" / "fixtures" / "TestPlayer.c4p"
)

FP_RE = re.compile(r"LandscapeFP: (-?\d+)")
RULES_RE = re.compile(r"RulesObjects: (\d+)")
GOALS_RE = re.compile(r"GoalsObjects: (\d+)")

# Pass 1: full host --parameter set (seed + amplitude + rules + goals).
HOST_PARAMS_FULL = [
    "--parameter", "Seed=3373",
    "--parameter", "Amplitude=45",
    "--parameter", "Rules=ENRG=1",
    "--parameter", "Goals=MELE=1",
]
# Pass 2: seed only -- the cross-pass Amplitude sensitivity check.
HOST_PARAMS_SEED_ONLY = [
    "--parameter", "Seed=3373",
]


def pick_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def wait_for_port(host: str, port: int, timeout: float,
                  interval: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=interval):
                return True
        except OSError:
            time.sleep(interval)
    return False


def kill_proc(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def tail(text: str, n: int = 20) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def build_engine_args(engine: str, ticks: int, role: str,
                      tcp_port: int, udp_port: int, scenario: Path,
                      player_file: Path, host_params: list[str]) -> list[str]:
    """Build the command-line args for a host or client engine instance."""
    args = [str(engine), "--console", "--smoke-run", str(ticks),
            "--bind-address", "127.0.0.1"]
    if role == "host":
        args.extend(["/host", "/lobby:10",
                     f"/tcpport:{tcp_port}", f"/udpport:{udp_port}",
                     "-s", str(scenario)])
        args.extend(host_params)
    elif role == "client":
        args.extend(["/client:0",
                     f"/tcpport:{tcp_port}", f"/udpport:{udp_port}"])
    else:
        raise ValueError(f"unknown role: {role}")
    if player_file is not None:
        args.append(str(player_file))
    return args


def run_pair(engine: str, scenario: Path, ticks: int, timeout: int,
             host_params: list[str], host_player: Path,
             client_player: Path, log_suffix: str) -> dict | None:
    """Run one host+client pass. Returns parsed per-peer results, or
    None on infrastructure error (engine exit before assertions)."""
    base = pick_free_port()
    host_tcp, host_udp = base, base + 1
    client_tcp, client_udp = base + 2, base + 3

    host_cmd = build_engine_args(engine, ticks, "host", host_tcp, host_udp,
                                 scenario, host_player, host_params)
    client_cmd = build_engine_args(engine, ticks, "client", client_tcp,
                                   client_udp, scenario, client_player, [])

    host_log_file = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=f"_{log_suffix}_host.log")
    client_log_file = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=f"_{log_suffix}_client.log")

    host_proc: subprocess.Popen | None = None
    client_proc: subprocess.Popen | None = None

    try:
        print(f"Host:   {shlex.join(host_cmd)}")
        host_proc = subprocess.Popen(
            host_cmd, stdout=host_log_file, stderr=subprocess.STDOUT,
            text=True, stdin=subprocess.DEVNULL)

        if not wait_for_port("127.0.0.1", REF_SERVER_PORT, timeout=15.0):
            print(f"FAIL: host reference server did not come up within 15s")
            kill_proc(host_proc)
            host_out = Path(host_log_file.name).read_text(errors="replace")
            print(f"Host exit code: {host_proc.poll()}")
            print(f"--- Host log (last 20 lines) ---\n{tail(host_out)}")
            return None

        # grace period so the client does not race the reference registration
        time.sleep(5.0)

        print(f"Client: {shlex.join(client_cmd)}")
        client_proc = subprocess.Popen(
            client_cmd, stdout=client_log_file, stderr=subprocess.STDOUT,
            text=True, stdin=subprocess.DEVNULL)

        deadline = time.monotonic() + timeout
        host_exit = client_exit = None
        try:
            host_exit = host_proc.wait(
                timeout=max(1.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
        try:
            client_exit = client_proc.wait(
                timeout=max(1.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
        if host_exit is None or client_exit is None:
            print(f"TIMEOUT: peers did not exit within {timeout}s")
        kill_proc(host_proc)
        kill_proc(client_proc)

        host_out = Path(host_log_file.name).read_text(errors="replace")
        client_out = Path(client_log_file.name).read_text(errors="replace")

        def grab(pattern: re.Pattern[str], text: str) -> int | None:
            m = pattern.search(text)
            return int(m.group(1)) if m else None

        return {
            "host_exit": host_exit,
            "client_exit": client_exit,
            "host_fp": grab(FP_RE, host_out),
            "client_fp": grab(FP_RE, client_out),
            "host_rules": grab(RULES_RE, host_out),
            "client_rules": grab(RULES_RE, client_out),
            "host_goals": grab(GOALS_RE, host_out),
            "client_goals": grab(GOALS_RE, client_out),
            "host_desync": DESYNC_MARKER in host_out,
            "client_desync": DESYNC_MARKER in client_out,
            "host_out": host_out,
            "client_out": client_out,
        }
    finally:
        kill_proc(host_proc)
        kill_proc(client_proc)
        for f in (host_log_file, client_log_file):
            try:
                f.close()
            except OSError:
                pass
            try:
                os.unlink(f.name)
            except OSError:
                pass


def make_player_copies(player_file: Path) -> tuple[Path, Path, Path]:
    """The engine writes player state back into the .c4p on game over;
    copy the fixture to a fresh temp dir so the original stays pristine
    (the net_desync_smoke.py pattern). Returns (tmp_dir, host_player,
    client_player); the caller owns tmp_dir and must remove it."""
    tmp_dir = tempfile.mkdtemp(prefix="net_settings_plr_")
    host_player = Path(tmp_dir) / "HostPlayer.c4p"
    client_player = Path(tmp_dir) / "ClientPlayer.c4p"
    shutil.copyfile(player_file, host_player)
    shutil.copyfile(player_file, client_player)
    return tmp_dir, host_player, client_player


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Network settings-sync CI smoke orchestrator "
                    "(spec net-preround-settings-fix).")
    parser.add_argument("--engine", required=True,
                        help="Path to the clonk binary.")
    parser.add_argument("--scenario", required=True,
                        help="Path to the .c4s scenario directory.")
    parser.add_argument("--ticks", type=int, default=2000,
                        help="smoke-run tick count (default: 2000).")
    parser.add_argument("--timeout", type=int, default=100,
                        help="max wall-clock seconds per pass (default: 100).")
    parser.add_argument("--player-file", default=str(DEFAULT_PLAYER_FILE),
                        help="Path to a .c4p player file passed to both "
                             "peers (default: tests/fixtures/TestPlayer.c4p).")
    args = parser.parse_args(argv)

    engine_path = Path(args.engine)
    if not engine_path.is_file():
        print(f"ERROR: engine binary not found: {engine_path}",
              file=sys.stderr)
        return 2
    scenario_path = Path(args.scenario)
    if not scenario_path.is_dir():
        print(f"ERROR: scenario directory not found: {scenario_path}",
              file=sys.stderr)
        return 2
    player_path = Path(args.player_file)
    if not player_path.exists():
        print(f"ERROR: player file not found: {player_path}", file=sys.stderr)
        return 2

    # --- Pass 1: full host --parameter set --------------------------------
    # Fresh player copies per pass -- the engine writes player state back
    # into the .c4p on game over, so pass 2 must not reuse pass-1's files.
    player_dir, host_player, client_player = make_player_copies(player_path)
    try:
        r1 = run_pair(engine_path, scenario_path, args.ticks, args.timeout,
                      HOST_PARAMS_FULL, host_player, client_player, "pass1")
    finally:
        shutil.rmtree(player_dir, ignore_errors=True)
    if r1 is None:
        return 1

    failures: list[str] = []

    # (a) both peers exit 0
    if r1["host_exit"] != 0 or r1["client_exit"] != 0:
        failures.append(
            f"(a) non-zero exit: host={r1['host_exit']} "
            f"client={r1['client_exit']}")
    # (b) no desync marker in either log
    if r1["host_desync"] or r1["client_desync"]:
        failures.append("(b) desync marker present in a peer log")
    # (c) host/client LandscapeFP equality
    if r1["host_fp"] is None or r1["client_fp"] is None:
        failures.append("(c) missing LandscapeFP line in a peer log")
    elif r1["host_fp"] != r1["client_fp"]:
        failures.append(
            f"(c) LandscapeFP divergence: host={r1['host_fp']} "
            f"client={r1['client_fp']}")
    # (d) rules/goals object counts
    for key in ("host_rules", "client_rules", "host_goals", "client_goals"):
        if r1[key] != 1:
            failures.append(f"(d) {key} expected 1, got {r1[key]}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print("--- Host log (last 20 lines) ---")
        print(tail(r1["host_out"]))
        print("--- Client log (last 20 lines) ---")
        print(tail(r1["client_out"]))
        return 1

    # --- Pass 2: Seed ONLY (Amplitude sensitivity) ------------------------
    player_dir, host_player, client_player = make_player_copies(player_path)
    try:
        r2 = run_pair(engine_path, scenario_path, args.ticks, args.timeout,
                      HOST_PARAMS_SEED_ONLY, host_player, client_player,
                      "pass2")
    finally:
        shutil.rmtree(player_dir, ignore_errors=True)
    if r2 is None:
        return 1

    # (e) cross-pass host LandscapeFP diff (same seed, different Amplitude)
    if r2["host_fp"] is None:
        failures.append("(e) missing pass-2 host LandscapeFP line")
    elif r2["host_fp"] == r1["host_fp"]:
        failures.append(
            f"(e) Amplitude override not live: pass1 host_fp="
            f"{r1['host_fp']} == pass2 host_fp={r2['host_fp']}")
    # (f) pass-2 host/client LandscapeFP equality
    if r2["host_fp"] is None or r2["client_fp"] is None:
        failures.append("(f) missing pass-2 LandscapeFP line in a peer log")
    elif r2["host_fp"] != r2["client_fp"]:
        failures.append(
            f"(f) pass-2 LandscapeFP divergence: host={r2['host_fp']} "
            f"client={r2['client_fp']}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print("--- Host log (last 20 lines) ---")
        print(tail(r2["host_out"]))
        print("--- Client log (last 20 lines) ---")
        print(tail(r2["client_out"]))
        return 1

    # Fingerprint evidence for the determinism gate (G3): print the values
    # so three consecutive runs can be compared by eye.
    print(f"pass1: host_fp={r1['host_fp']} client_fp={r1['client_fp']} "
          f"rules={r1['host_rules']}/{r1['client_rules']} "
          f"goals={r1['host_goals']}/{r1['client_goals']}")
    print(f"pass2: host_fp={r2['host_fp']} client_fp={r2['client_fp']} "
          f"rules={r2['host_rules']}/{r2['client_rules']} "
          f"goals={r2['host_goals']}/{r2['client_goals']}")

    print("net_settings_sync_smoke PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
