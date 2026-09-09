#!/usr/bin/env python3
"""net_abort_smoke.py -- network abort freeze CI smoke orchestrator.

Spawns two headless LegacyClonk engine instances (host + client) on
loopback, with the host's master/league server redirected (via a custom
config passed as /config:) to a local mock league HTTP server. The mock
replies to Start/Update instantly but delays the End reply by
--mock-end-delay seconds (default 5). The orchestrator:

  1. boots host + client (the net_desync_smoke.py pattern),
  2. waits for the "Game started." marker in the host log,
  3. writes "/close" to the host's stdin (the headless equivalent of
     Esc -> abort game), and
  4. asserts the host's game teardown ("Game cleared.") completes within
     --assert-ms (default 4000) of the /close write.

Pre-fix (teardown deadline absent), the teardown blocks on the delayed
mock End reply (~5+ s) and the smoke fails. Post-fix, the teardown
deadline cancels the in-flight End request after ~1 s, so the teardown
completes in time.

Exit codes:
  0 -- test passed (game started, /close teardown under bound, mock
      league saw Start and End requests, no desync/fatal).
  1 -- test failed (teardown over bound, markers missing, desync or
      fatal markers present, or the game never started).
  2 -- infrastructure error (engine binary missing, bad scenario path).
"""

from __future__ import annotations

import argparse
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Host log markers (English string table entries, planet/System.c4g:
# IDS_PRC_START "Game started.", logged at src/C4Game.cpp:761 when the
# game goes active; IDS_CNS_GAMECLOSED "Game cleared.", logged at
# src/C4Game.cpp:889 at the end of C4Game::Clear()).
GAME_STARTED_MARKER = "Game started."
GAME_CLEARED_MARKER = "Game cleared."
DESYNC_MARKER = "Network: Synchronization loss!"
FATAL_MARKERS = ("FatalError", "[critical]")

# The smoke prints every "net teardown: ..." line from the host log as
# D1 evidence (drives the spec §5 D4 conditional decision in Task 4).
TEARDOWN_TOTAL_RE = re.compile(
	r"net teardown: total took (\d+) ms")
# Unanchored on purpose: engine log lines carry a "[timestamp] [level] "
# prefix (C4Log.cpp:297), so a "^net teardown:" line-start anchor can
# never match (dual-review F1 — the D1-evidence echo was dead code).
TEARDOWN_LINE_RE = re.compile(
	r"net teardown: .*$", re.MULTILINE)

# C4NetStdPortRefServer (src/C4Network2.h:54). The host runs a reference
# server on this port; the client queries it (/client:0).
REF_SERVER_PORT = 11111

DEFAULT_PLAYER_FILE = (
	Path(__file__).resolve().parent.parent
	/ "tests" / "fixtures" / "TestPlayer.c4p"
)

# --- Mock league replies (INI bodies parsed by C4League*.CompileFunc) ---
# A [Response] section with Status/CSID/Message; GetStartReply
# (src/C4League.cpp:283-314) additionally requires a non-empty CSID.
START_REPLY = (
	"[Response]\n"
	"Status=Success\n"
	"CSID=smoke-csid-1\n"
	"Message=mock league start reply\n"
	"League=SmokeLeague\n"
)
END_REPLY = (
	"[Response]\n"
	"Status=Success\n"
	"Message=mock league end reply\n"
)
UPDATE_REPLY = (
	"[Response]\n"
	"Status=Success\n"
	"Message=mock league update reply\n"
	"League=SmokeLeague\n"
)
AUTH_REPLY = (
	"[Response]\n"
	"Status=Success\n"
	"Message=mock league auth reply\n"
	"Account=SmokeAccount\n"
	"AUID=smoke-auid-1\n"
	"FBID=smoke-fbid-1\n"
)
GENERIC_SUCCESS_REPLY = END_REPLY

ACTION_RE = re.compile(r"^Action=(\w+)", re.MULTILINE)

class MockLeagueServer:
	"""Threaded HTTP server impersonating a league/master server.

	Replies are instant except Action=End, which sleeps mock_end_delay
	seconds first -- reproducing the slow-league abort freeze. Counts
	requests per action so the smoke can assert the league path was live.
	"""

	def __init__(self, mock_end_delay: float) -> None:
		self.counts: dict[str, int] = {}
		self.mock_end_delay = mock_end_delay
		self.lock = threading.Lock()
		outer = self

		class Handler(BaseHTTPRequestHandler):
			protocol_version = "HTTP/1.1"

			def log_message(self, format: str, *args) -> None:  # noqa: A002
				pass  # keep the mock quiet

			def do_POST(self) -> None:
				length = int(self.headers.get("Content-Length", 0))
				body = self.rfile.read(length).decode(
					"utf-8", errors="replace")
				match = ACTION_RE.search(body)
				action = match.group(1) if match else "Unknown"
				with outer.lock:
					outer.counts[action] = outer.counts.get(action, 0) + 1
				delay = outer.mock_end_delay if action == "End" else 0.0
				if delay:
					time.sleep(delay)
				data = outer.reply_for(action).encode("utf-8")
				self.send_response(200)
				self.send_header("Content-Type", "text/plain")
				self.send_header("Content-Length", str(len(data)))
				self.end_headers()
				self.wfile.write(data)

			def do_GET(self) -> None:
				# Reference queries arrive as GETs with no body; answer
				# generically so an unexpected query cannot wedge the run.
				data = GENERIC_SUCCESS_REPLY.encode("utf-8")
				self.send_response(200)
				self.send_header("Content-Type", "text/plain")
				self.send_header("Content-Length", str(len(data)))
				self.end_headers()
				self.wfile.write(data)

		self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
		self.httpd.daemon_threads = True
		self.thread = threading.Thread(
			target=self.httpd.serve_forever, daemon=True)

	def reply_for(self, action: str) -> str:
		if action == "Start":
			return START_REPLY
		if action == "Update":
			return UPDATE_REPLY
		if action == "Auth":
			return AUTH_REPLY
		return GENERIC_SUCCESS_REPLY

	@property
	def port(self) -> int:
		return self.httpd.server_address[1]

	@property
	def url(self) -> str:
		return f"http://127.0.0.1:{self.port}/mock-league.php"

	def start(self) -> None:
		self.thread.start()

	def stop(self) -> None:
		self.httpd.shutdown()
		self.httpd.server_close()

def pick_free_port() -> int:
	"""Bind a temporary TCP socket to port 0 and return the assigned port."""
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		sock.bind(("127.0.0.1", 0))
		return sock.getsockname()[1]
	finally:
		sock.close()

def wait_for_port(host: str, port: int, timeout: float,
                  interval: float = 0.1) -> bool:
	"""Poll a TCP connect until it succeeds or timeout expires."""
	deadline = time.monotonic() + timeout
	while time.monotonic() < deadline:
		try:
			with socket.create_connection((host, port), timeout=interval):
				return True
		except OSError:
			time.sleep(interval)
	return False

def wait_for_marker(log_path: Path, marker: str,
                    timeout: float, interval: float = 0.1):
	"""Poll a log file until `marker` appears. Returns elapsed
	seconds since the call started, or None on timeout."""
	deadline = time.monotonic() + timeout
	while time.monotonic() < deadline:
		text = log_path.read_text(errors="replace")
		if marker in text:
			return time.monotonic() - (deadline - timeout)
	return None

def kill_proc(proc: subprocess.Popen | None) -> None:
	"""Terminate then SIGKILL a process if still running."""
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

def build_host_args(engine: str, ticks: int, tcp_port: int, udp_port: int,
                    config_ini: Path, scenario: Path,
                    player_file: Path | None) -> list[str]:
	args = [str(engine), "--console", "--smoke-run", str(ticks),
	        "--bind-address", "127.0.0.1",
	        f"/config:{config_ini}",
	        "/host", "/signup", "/lobby:10",
	        f"/tcpport:{tcp_port}", f"/udpport:{udp_port}",
	        "-s", str(scenario)]
	if player_file is not None:
		args.append(str(player_file))
	return args

def build_client_args(engine: str, ticks: int, tcp_port: int,
                      udp_port: int, player_file: Path | None) -> list[str]:
	args = [str(engine), "--console", "--smoke-run", str(ticks),
	        "--bind-address", "127.0.0.1",
	        "/client:0",
	        f"/tcpport:{tcp_port}", f"/udpport:{udp_port}"]
	if player_file is not None:
		args.append(str(player_file))
	return args

def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		description="Network abort freeze CI smoke orchestrator "
		            "(spec net-abort-freeze-fix).")
	parser.add_argument("--engine", required=True,
	                    help="Path to the clonk binary.")
	parser.add_argument("--scenario", required=True,
	                    help="Path to the .c4s scenario directory.")
	parser.add_argument("--ticks", type=int, default=10000,
	                    help="smoke-run tick count; must exceed the ticks "
	                         "elapsed before /close (default: 10000).")
	parser.add_argument("--player-file", default=str(DEFAULT_PLAYER_FILE),
	                    help="Path to a .c4p player file passed to both peers.")
	parser.add_argument("--mock-end-delay", type=float, default=5.0,
	                    help="Seconds the mock league delays its End reply "
	                         "(default: 5.0).")
	parser.add_argument("--assert-ms", type=int, default=4000,
	                    help="Teardown wall-clock bound (default: 4000 ms).")
	parser.add_argument("--start-timeout", type=float, default=90.0,
	                    help="Seconds to wait for the host's "
	                         '"Game started." marker (default: 90).')
	args = parser.parse_args(argv)

	# Resolve to absolute paths: the engine chdir()s into its binary
	# directory at startup, so RELATIVE paths break engine-side
	# resolution (the Task-1 relative-scenario failure).
	engine_path = Path(args.engine).resolve()
	if not engine_path.is_file():
		print(f"ERROR: engine binary not found: {engine_path}",
		      file=sys.stderr)
		return 2
	scenario_path = Path(args.scenario).resolve()
	if not scenario_path.is_dir():
		print(f"ERROR: scenario directory not found: {scenario_path}",
		      file=sys.stderr)
		return 2
	player_path = Path(args.player_file).resolve()
	if not player_path.exists():
		print(f"ERROR: player file not found: {player_path}",
		      file=sys.stderr)
		return 2

	failures: list[str] = []
	run_dir = Path(tempfile.mkdtemp(prefix="net_abort_smoke_"))
	mock = MockLeagueServer(args.mock_end_delay)
	mock.start()

	host_log = run_dir / "host.log"
	client_log = run_dir / "client.log"
	config_ini = run_dir / "host_config.ini"
	config_ini.write_text(
		"[Network]\n"
		f'ServerAddress="{mock.url}"\n',
		encoding="utf-8")

	base = pick_free_port()
	host_tcp, host_udp = base, base + 1
	client_tcp, client_udp = base + 2, base + 3

	# The engine saves player state back into the .c4p; copy the fixture
	# so the original stays pristine (net_desync_smoke.py pattern).
	player_tmp = Path(tempfile.mkdtemp(prefix="net_abort_plr_"))
	host_player = player_tmp / "HostPlayer.c4p"
	client_player = player_tmp / "ClientPlayer.c4p"
	shutil.copyfile(player_path, host_player)
	shutil.copyfile(player_path, client_player)

	host_cmd = build_host_args(
		str(engine_path), args.ticks, host_tcp, host_udp,
		config_ini, scenario_path, host_player)
	client_cmd = build_client_args(
		str(engine_path), args.ticks, client_tcp, client_udp, client_player)

	print(f"Host:   {shlex.join(host_cmd)}")
	print(f"Client: {shlex.join(client_cmd)}")

	host_proc: subprocess.Popen | None = None
	client_proc: subprocess.Popen | None = None
	try:
		host_proc = subprocess.Popen(
			host_cmd, stdout=open(host_log, "w"),
			stderr=subprocess.STDOUT, text=True,
			stdin=subprocess.PIPE, bufsize=1)
		if not wait_for_port("127.0.0.1", REF_SERVER_PORT, timeout=15.0):
			failures.append(
				f"host reference server did not come up on port "
				f"{REF_SERVER_PORT} within 15s")
		else:
			# Grace period so the client does not race the reference
			# registration (net_desync_smoke.py ref-wait pattern).
			time.sleep(5.0)
			client_proc = subprocess.Popen(
				client_cmd, stdout=open(client_log, "w"),
				stderr=subprocess.STDOUT, text=True,
				stdin=subprocess.DEVNULL)

		# --- Wait for the game to start ------------------------------
		if not failures:
			started = wait_for_marker(
				host_log, GAME_STARTED_MARKER, args.start_timeout)
			if started is None:
				failures.append(
					f'"{GAME_STARTED_MARKER}" not found in host log '
					f"within {args.start_timeout:.0f}s")
			else:
				print(f"Game started after {started:.1f}s")

		# --- Abort: /close on host stdin ------------------------------
		if not failures:
			time.sleep(2.0)  # let the game run a little
			assert host_proc is not None and host_proc.stdin is not None
			t_close = time.monotonic()  # absolute /close send time
			host_proc.stdin.write("/close\n")
			host_proc.stdin.flush()

			t_wait = time.monotonic()  # marker-wait start (absolute)
			cleared = wait_for_marker(
				host_log, GAME_CLEARED_MARKER,
			    args.assert_ms / 1000.0)
			if cleared is None:
				failures.append(
					f'"{GAME_CLEARED_MARKER}" not found in host log '
					f"within {args.assert_ms} ms of /close -- teardown "
					f"took longer than the bound")
			else:
				# wait_for_marker returns elapsed since ITS call start;
				# anchor to the absolute /close send time for the
				# wall-clock (domain-mixing = the -1.6e9 ms bug).
				elapsed_ms = (t_wait - t_close + cleared) * 1000.0
				print(f"Teardown wall-clock: {elapsed_ms:.0f} ms "
				      f"(bound {args.assert_ms} ms)")
				if elapsed_ms > args.assert_ms:
					failures.append(
						f"teardown wall-clock {elapsed_ms:.0f} ms "
						f"exceeds bound {args.assert_ms} ms")

		# --- Wind down: /quit host, wait client, kill stragglers -----
		if host_proc is not None and host_proc.poll() is None \
		        and host_proc.stdin is not None:
			host_proc.stdin.write("/quit\n")
			host_proc.stdin.flush()
		if host_proc is not None:
			try:
				host_proc.wait(timeout=10.0)
			except subprocess.TimeoutExpired:
				kill_proc(host_proc)
		if client_proc is not None:
			try:
				client_proc.wait(timeout=10.0)
			except subprocess.TimeoutExpired:
				kill_proc(client_proc)

		# --- Assertions ----------------------------------------------
		host_out = host_log.read_text(errors="replace") \
			if host_log.exists() else ""
		client_out = client_log.read_text(errors="replace") \
			if client_log.exists() else ""

		if DESYNC_MARKER in host_out or DESYNC_MARKER in client_out:
			failures.append("desync marker present in a peer log")
		for marker in FATAL_MARKERS:
			if marker in host_out or marker in client_out:
				failures.append(f"fatal marker '{marker}' present in a log")

		with mock.lock:
			counts = dict(mock.counts)
		if counts.get("Start", 0) < 1:
			failures.append("mock league saw no Start request -- "
			                "host never signed up at the mock")
		if counts.get("End", 0) < 1:
			failures.append("mock league saw no End request -- "
			                "teardown never reported to the league")

		total_match = TEARDOWN_TOTAL_RE.search(host_out)
		if total_match:
			print(f"Instrumented teardown total: {total_match.group(1)} ms")
		else:
			failures.append(
				'"net teardown: total took N ms" instrumentation marker '
				"missing from host log")

		# D1 evidence for the spec §5 D4 conditional (Task 4):
		# print every "net teardown: ..." line from the host log.
		for line in TEARDOWN_LINE_RE.findall(host_out):
			print(f"[teardown] {line}")

		if failures:
			for f in failures:
				print(f"FAIL: {f}")
			print("--- Host log (last 20 lines) ---")
			print(tail(host_out))
			print("--- Client log (last 20 lines) ---")
			print(tail(client_out))
			return 1

		print("net_abort_smoke PASS: teardown under bound, league path "
		      "live, no desync/fatal markers.")
		return 0

	finally:
		kill_proc(host_proc)
		kill_proc(client_proc)
		mock.stop()
		shutil.rmtree(player_tmp, ignore_errors=True)
		shutil.rmtree(run_dir, ignore_errors=True)

if __name__ == "__main__":
	sys.exit(main())
