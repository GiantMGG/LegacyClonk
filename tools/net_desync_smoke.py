#!/usr/bin/env python3
"""net_desync_smoke.py -- network desync CI smoke test orchestrator.

Spawns two headless LegacyClonk engine instances on localhost (host + client),
optionally applies tc netem impairment to loopback, and asserts no desync
fatal errors occur over N ticks.

See spec network-desync-ci-smoke.

Exit codes:
  0 -- test passed (both peers exited 0, no desync marker in logs).
  1 -- test failed (desync detected, non-zero peer exit, or timeout).
  2 -- infrastructure error (engine binary missing, bad scenario path).
"""

from __future__ import annotations

import argparse
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The desync fatal log line emitted by C4ControlSyncCheck::Execute()
# (src/C4Control.cpp:524). Presence in either peer's log => desync.
DESYNC_MARKER = "Network: Synchronization loss!"

# C4NetStdPortRefServer (src/C4Network2.h:52). The host runs a reference
# server on this port; the client queries it. Both use the default.
REF_SERVER_PORT = 11111


def pick_free_port() -> int:
    """Bind a temporary TCP socket to port 0 and return the assigned port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def wait_for_port(host: str, port: int, timeout: float, interval: float = 0.1) -> bool:
    """Poll a TCP connect until it succeeds or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=interval):
                return True
        except OSError:
            time.sleep(interval)
    return False


def run_tc(tc_program: str, args: list[str], use_sudo: bool) -> subprocess.CompletedProcess:
    """Run a tc subcommand, optionally via sudo."""
    cmd: list[str] = []
    if use_sudo:
        cmd.append("sudo")
    cmd.append(tc_program)
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def apply_impairment(tc_program: str, delay: int, jitter: int, loss: int,
                     use_sudo: bool) -> bool:
    """Apply tc netem impairment to loopback. Returns True on success."""
    # Defensive: clear any leftover qdisc from a crashed previous run.
    run_tc(tc_program, ["qdisc", "del", "dev", "lo", "root"], use_sudo)
    result = run_tc(tc_program,
                    ["qdisc", "add", "dev", "lo", "root", "netem",
                     "delay", f"{delay}ms", f"{jitter}ms",
                     "loss", f"{loss}%"],
                    use_sudo)
    if result.returncode != 0:
        print(f"WARNING: tc qdisc add failed (exit {result.returncode}): "
              f"{result.stderr.strip()}")
        print("WARNING: running without impairment")
        return False
    print(f"Impairment applied: delay {delay}ms jitter {jitter}ms loss {loss}%")
    return True


def cleanup_impairment(tc_program: str, use_sudo: bool) -> None:
    """Remove tc netem qdisc from loopback."""
    result = run_tc(tc_program, ["qdisc", "del", "dev", "lo", "root"], use_sudo)
    if result.returncode != 0:
        print(f"WARNING: tc qdisc del failed (exit {result.returncode}): "
              f"{result.stderr.strip()}")


def build_engine_args(engine: str, scenario: Path, ticks: int, role: str,
                      tcp_port: int, udp_port: int) -> list[str]:
    """Build the command-line args for a host or client engine instance."""
    args = [engine, "--console", "--smoke-run", str(ticks)]
    if role == "host":
        args.extend(["/host", "/lobby:10",
                     f"/tcpport:{tcp_port}", f"/udpport:{udp_port}",
                     "-s", str(scenario)])
    elif role == "client":
        args.extend(["/client:0",
                     f"/tcpport:{tcp_port}", f"/udpport:{udp_port}"])
    else:
        raise ValueError(f"unknown role: {role}")
    return args


def tail(text: str, n: int = 20) -> str:
    """Return the last n lines of text."""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def kill_proc(proc: subprocess.Popen | None) -> None:
    """Terminate then SIGKILL a process if still running."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Network desync CI smoke orchestrator "
                    "(spec network-desync-ci-smoke).")
    parser.add_argument("--engine", required=True,
                        help="Path to the clonk binary.")
    parser.add_argument("--scenario", required=True,
                        help="Path to the .c4s scenario directory.")
    parser.add_argument("--ticks", type=int, default=2000,
                        help="smoke-run tick count (default: 2000).")
    parser.add_argument("--timeout", type=int, default=120,
                        help="max wall-clock seconds for both peers (default: 120).")
    parser.add_argument("--delay", type=int, default=50,
                        help="tc netem delay in ms (default: 50).")
    parser.add_argument("--jitter", type=int, default=10,
                        help="tc netem jitter in ms (default: 10).")
    parser.add_argument("--loss", type=int, default=2,
                        help="tc netem packet loss percentage (default: 2).")
    parser.add_argument("--tc-program", default=None,
                        help="Path to the tc binary (omit to skip impairment).")
    parser.add_argument("--sudo", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Use sudo for tc commands (default: true).")
    args = parser.parse_args(argv)

    # --- Validate inputs -------------------------------------------------
    engine_path = Path(args.engine)
    if not engine_path.is_file():
        print(f"ERROR: engine binary not found: {engine_path}", file=sys.stderr)
        return 2
    scenario_path = Path(args.scenario)
    if not scenario_path.is_dir():
        print(f"ERROR: scenario directory not found: {scenario_path}",
              file=sys.stderr)
        return 2

    # --- Port selection --------------------------------------------------
    base = pick_free_port()
    host_tcp, host_udp = base, base + 1
    client_tcp, client_udp = base + 2, base + 3
    print(f"Ports: host tcp={host_tcp} udp={host_udp}  "
          f"client tcp={client_tcp} udp={client_udp}  "
          f"refserver={REF_SERVER_PORT}")

    # --- Impairment (optional) -------------------------------------------
    impairment_active = False
    if args.tc_program:
        tc_path = Path(args.tc_program)
        if tc_path.is_file():
            impairment_active = apply_impairment(
                args.tc_program, args.delay, args.jitter, args.loss, args.sudo)
        else:
            print(f"WARNING: tc not available at {args.tc_program} -- "
                  f"running without impairment")
    else:
        print("NOTE: --tc-program not provided -- running without impairment")

    host_proc: subprocess.Popen | None = None
    client_proc: subprocess.Popen | None = None
    host_log_file: tempfile.NamedTemporaryFile | None = None
    client_log_file: tempfile.NamedTemporaryFile | None = None

    try:
        # --- Spawn host --------------------------------------------------
        host_log_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_net_desync_host.log")
        host_cmd = build_engine_args(
            args.engine, scenario_path, args.ticks, "host", host_tcp, host_udp)
        print(f"Host: {shlex.join(host_cmd)}")
        host_proc = subprocess.Popen(
            host_cmd, stdout=host_log_file, stderr=subprocess.STDOUT,
            text=True)

        # --- Wait for reference server ----------------------------------
        if not wait_for_port("127.0.0.1", REF_SERVER_PORT, timeout=15.0):
            # Host may have exited early or be hung; kill it if still
            # running, then read its log for diagnostics.
            kill_proc(host_proc)
            host_exit = host_proc.wait(timeout=5)
            host_out = Path(host_log_file.name).read_text(errors="replace")
            print(f"FAIL: host reference server did not come up on port "
                  f"{REF_SERVER_PORT} within 15s")
            print(f"Host exit code: {host_exit}")
            print(f"--- Host log (last 20 lines) ---\n{tail(host_out)}")
            return 1

        # --- Spawn client ------------------------------------------------
        client_log_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_net_desync_client.log")
        client_cmd = build_engine_args(
            args.engine, scenario_path, args.ticks, "client",
            client_tcp, client_udp)
        print(f"Client: {shlex.join(client_cmd)}")
        client_proc = subprocess.Popen(
            client_cmd, stdout=client_log_file, stderr=subprocess.STDOUT,
            text=True)

        # --- Wait for both to exit (bounded by --timeout) ----------------
        deadline = time.monotonic() + args.timeout
        host_exit: int | None = None
        client_exit: int | None = None

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

        # --- Timeout handling: kill stragglers ---------------------------
        if host_exit is None or client_exit is None:
            print(f"TIMEOUT: one or both peers did not exit within "
                  f"{args.timeout} seconds.")
            kill_proc(host_proc)
            kill_proc(client_proc)
            host_exit = host_exit if host_exit is not None else -1
            client_exit = client_exit if client_exit is not None else -1

        # --- Read logs ---------------------------------------------------
        host_out = Path(host_log_file.name).read_text(errors="replace")
        client_out = Path(client_log_file.name).read_text(errors="replace")

        # --- Assert results ---------------------------------------------
        desync_in_host = DESYNC_MARKER in host_out
        desync_in_client = DESYNC_MARKER in client_out
        desync_detected = desync_in_host or desync_in_client

        if desync_detected:
            print('DESYNC DETECTED: log contains "Network: Synchronization '
                  'loss!"')
        print(f"Host exit code: {host_exit}")
        print(f"Client exit code: {client_exit}")

        if desync_detected or host_exit != 0 or client_exit != 0:
            print("--- Host log (last 20 lines) ---")
            print(tail(host_out))
            print("--- Client log (last 20 lines) ---")
            print(tail(client_out))
            return 1

        print("PASS: both peers exited 0 with no desync.")
        return 0

    finally:
        # --- Cleanup impairment (always) --------------------------------
        if impairment_active and args.tc_program:
            cleanup_impairment(args.tc_program, args.sudo)
        # --- Kill any surviving processes --------------------------------
        kill_proc(host_proc)
        kill_proc(client_proc)
        # --- Unlink temp log files ---------------------------------------
        for f in [host_log_file, client_log_file]:
            if f is not None:
                try:
                    f.close()
                except OSError:
                    pass
                try:
                    os.unlink(f.name)
                except OSError:
                    pass


if __name__ == "__main__":
    sys.exit(main())
