#!/usr/bin/env bash
#
# devmode_boot_drive.sh — cycle 227, slice 1 of the Epic 7 world-editor chain.
#
# Proves the engine's EXISTING GTK developer console (WITH_DEVELOPER_MODE=ON)
# boots under Xvfb, opens a shipped scenario, and enters Edit mode — with zero
# [error] lines. This is the boot drive for the world-editor chain; later
# items (paint-pin, save-roundtrip) extend it.
#
# Drive shape (modelled on tools/real_playtest_walk.sh):
#   launch the GUI developer build (build3/clonk: USE_CONSOLE=OFF +
#   WITH_DEVELOPER_MODE=ON — the only build with the GTK dev console; plain
#   build/ is USE_CONSOLE=On and renders no window, rules/gui-screenshots.md)
#   with /console <abs ColonyBay.c4s> on Xvfb :98 with the brew LD_LIBRARY_PATH
#   recipe + LIBGL_ALWAYS_SOFTWARE=1 (setsid env form),
#   wait for the GTK console window + the "Scenario: " log line + the
#   calibrated game-open marker ("Game started."), screenshot the boot, then
#   click the btnModeEdit toolbar toggle (4th of 5 pixbuf-only GtkToggleButtons
#   in the top_hbox; no OCR text, so the click is calibrated on the live frame
#   from the dark icon-pixel column clusters — walk F3 pattern), screenshot
#   again, and byte-compare the toolbar strip.
#
# Outputs:
#   .opencode/scratch/227/01-console-booted.png
#   .opencode/scratch/227/02-toolbar-before.png   (toolbar strip crop)
#   .opencode/scratch/227/03-toolbar-after.png    (toolbar strip crop)
#   .opencode/scratch/227/04-edit-mode.png
#   .opencode/scratch/227/run.log                 (engine stdout/stderr)
#   .opencode/scratch/227/boot-verdict.txt        (gates + final verdict line)
#
# Gates (all must hold for PASS):
#   * run log has "[info] Scenario: ...ColonyBay..." and "Game started.";
#   * the GTK console window is mapped (xdotool search non-empty);
#   * the toolbar strip pair (02 vs 03) differs in bytes (toggle flipped);
#   * zero [error] lines in the run log;
#   * all four shots exist non-empty;
#   * verdict ends "DEVMODE-BOOT-DRIVE: PASS".
#
# The drive is idempotent: it clears its own outputs at start (fresh scratch
# state per run) and kills only its own PIDs (PID-only cleanup).
#
# Usage: bash tools/devmode_boot_drive.sh
#
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"                        # LegacyClonk
WS="$(dirname "$REPO")"                                # clonk_ws
EVID="$WS/.opencode/scratch/227"
BINARY="${DRIVE_BINARY:-$REPO/build3/clonk}"
SCEN="$WS/content/Worlds.c4f/ColonyBay.c4s"
SEED_CONFIG="$WS/.opencode/scratch/wincond-qa/qa-home/.legacyclonk/config"
LIBFILL="$WS/.opencode/scratch/wincond-qa/libfill"
RUNLOG="$EVID/run.log"
VERDICT="$EVID/boot-verdict.txt"
TMP="$EVID/tmp"
PRIVATE_HOME="$EVID/home"
XVFB_LOG="$EVID/xvfb.log"

# display :98 (the walk owns :96/:97; :99 has other windows). Overridable for
# a local reproduction on a free display.
DISP="${DRIVE_DISPLAY:-:98}"
SCR_W=1280
SCR_H=1024

SHOTS=(01-console-booted 02-toolbar-before 03-toolbar-after 04-edit-mode)

# toolbar strip crop, window-relative: the top_hbox buttons sit ~44px above the
# window bottom (status frame below them); 52px tall excludes the status bar so
# the byte-compare sees the toggle change, not the ticking frame counter.
STRIP_TOP_OFF=70
STRIP_H=52

# xdotool lives at the brew path and is not always on PATH (rules/gui-screenshots.md)
XDTOOL="$(command -v xdotool 2>/dev/null || true)"
if [ -z "$XDTOOL" ] || [ ! -x "$XDTOOL" ]; then
	XDTOOL="/home/linuxbrew/.linuxbrew/bin/xdotool"
fi

XVFB_PIDS=()
CLONK_PIDS=()
CONSOLE_WID=""

VERDICT_LINES=()

log() { printf '[devmode_boot_drive] %s\n' "$*" >&2; }

# --- PID-only cleanup -----------------------------------------------------------
cleanup()
{
	log "cleanup: killing engine + Xvfb by PID"
	kill_clonk
	local p
	for p in "${XVFB_PIDS[@]:-}"; do
		kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null
	done
	local i any
	for i in 1 2 3 4 5; do
		any=0
		for p in "${CLONK_PIDS[@]:-}" "${XVFB_PIDS[@]:-}"; do
			kill -0 "$p" 2>/dev/null && any=1
		done
		[ "$any" = 0 ] && break
		sleep 1
	done
	for p in "${CLONK_PIDS[@]:-}" "${XVFB_PIDS[@]:-}"; do
		kill -0 "$p" 2>/dev/null && kill -9 "$p" 2>/dev/null
	done
	log "cleanup done"
}
trap cleanup EXIT INT TERM

kill_clonk()
{
	# kill ONLY drive-spawned engines (CLONK_PIDS); a foreign clonk (a
	# concurrent smoke/battery engine) must never be touched.
	local p i any
	for p in "${CLONK_PIDS[@]:-}"; do
		log "killing clonk pid $p"
		kill "$p" 2>/dev/null
	done
	for i in 1 2 3 4 5; do
		any=0
		for p in "${CLONK_PIDS[@]:-}"; do
			kill -0 "$p" 2>/dev/null && any=1
		done
		[ "$any" = 0 ] && break
		sleep 1
	done
	for p in "${CLONK_PIDS[@]:-}"; do
		kill -0 "$p" 2>/dev/null && kill -9 "$p" 2>/dev/null
	done
	CLONK_PIDS=()
}

# --- capture helpers -------------------------------------------------------------
shot()
{
	local name="$1" path="$EVID/$1.png" imginfo
	DISPLAY="$DISP" timeout 30 import -window root "$path" 2>/dev/null
	imginfo="$(identify -format '%wx%h/%k colors' "$path" 2>/dev/null)"
	if [ -s "$path" ] && [ -n "$imginfo" ]; then
		log "shot $name ($imginfo)"
		return 0
	fi
	rm -f "$path"
	log "GAP shot $name failed (no image)"
	return 1
}

# crop_shot NAME SRC TOP HEIGHT X WIDTH — toolbar strip crop from a root shot
crop_shot()
{
	local name="$1" src="$2" top="$3" height="$4" x="$5" width="$6" imginfo
	convert "$src" -crop "${width}x${height}+${x}+${top}" +repage "$EVID/$name.png" 2>/dev/null
	imginfo="$(identify -format '%wx%h/%k colors' "$EVID/$name.png" 2>/dev/null)"
	if [ -s "$EVID/$name.png" ] && [ -n "$imginfo" ]; then
		log "shot $name ($imginfo)"
		return 0
	fi
	rm -f "$EVID/$name.png"
	log "GAP shot $name failed (no image)"
	return 1
}

# --- window / log waits ----------------------------------------------------------
# console_window: echo the wid of the GTK console window (the LegacyClonk window
# that is not a full-screen render surface, i.e. width <= 500). Logs all matches.
find_console_wid()
{
	local wid name geom w
	for wid in $(DISPLAY="$DISP" "$XDTOOL" search --class LegacyClonk 2>/dev/null); do
		name="$(DISPLAY="$DISP" "$XDTOOL" getwindowname "$wid" 2>/dev/null)"
		geom="$(DISPLAY="$DISP" "$XDTOOL" getwindowgeometry --shell "$wid" 2>/dev/null)"
		w="$(sed -n 's/^WIDTH=//p' <<<"$geom")"
		log "window $wid name='$name' width='${w:-?}'"
		if [ -n "$w" ] && [ "$w" -le 500 ] 2>/dev/null; then
			printf '%s\n' "$wid"
			return 0
		fi
	done
	return 1
}

wait_window()
{
	local secs="$1" wid
	local deadline=$((SECONDS + secs))
	while [ $SECONDS -lt $deadline ]; do
		wid="$(find_console_wid | tail -1)"
		if [ -n "$wid" ]; then printf '%s\n' "$wid"; return 0; fi
		sleep 2
	done
	return 1
}

wait_log()
{
	local pattern="$1" secs="$2"
	local deadline=$((SECONDS + secs))
	while [ $SECONDS -lt $deadline ]; do
		[ -f "$RUNLOG" ] && grep -qE "$pattern" "$RUNLOG" && return 0
		sleep 2
	done
	return 1
}

# --- engine lifecycle ------------------------------------------------------------
check_tools()
{
	local t
	for t in Xvfb import identify convert tesseract gm setsid awk sed; do
		command -v "$t" >/dev/null 2>&1 || { echo "missing tool: $t"; return 1; }
	done
	[ -x "$XDTOOL" ] || { echo "xdotool not found (PATH + $XDTOOL)"; return 1; }
	[ -x "$BINARY" ] || { echo "GUI build not found: $BINARY"; return 1; }
	[ -e "$SCEN" ] || { echo "scenario missing: $SCEN"; return 1; }
	[ -f "$SEED_CONFIG" ] || { echo "seed config missing: $SEED_CONFIG"; return 1; }
	[ -d "$LIBFILL" ] || { echo "libfill missing: $LIBFILL"; return 1; }
	local availGiB
	availGiB=$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 0) / 1024 / 1024 ))
	[ "$availGiB" -ge 4 ] || { echo "free memory too low: ${availGiB} GiB (< 4 GiB)"; return 1; }
	return 0
}

start_xvfb()
{
	# refuse a warm display we do not own (a stale server makes the driver
	# connect to a foreign window tree)
	if DISPLAY="$DISP" "$XDTOOL" getdisplaygeometry >/dev/null 2>&1; then
		log "FATAL: display $DISP is already in use; refusing to continue"
		return 1
	fi
	Xvfb "$DISP" -screen 0 "${SCR_W}x${SCR_H}x24" >"$XVFB_LOG" 2>&1 &
	local xpid=$!
	XVFB_PIDS+=("$xpid")
	local i
	for i in 1 2 3 4 5; do
		kill -0 "$xpid" 2>/dev/null || break
		DISPLAY="$DISP" "$XDTOOL" getdisplaygeometry >/dev/null 2>&1 && break
		sleep 1
	done
	if ! kill -0 "$xpid" 2>/dev/null || ! DISPLAY="$DISP" "$XDTOOL" getdisplaygeometry >/dev/null 2>&1; then
		log "GAP Xvfb $DISP failed to start (see $XVFB_LOG)"
		return 1
	fi
	sleep 2
	return 0
}

# find our engine by DISPLAY match (never by a global pgrep that could grab a
# concurrent smoke engine)
find_our_clonk()
{
	local p
	for p in $(pgrep -x clonk 2>/dev/null); do
		if tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -qx "DISPLAY=$DISP"; then
			printf '%s\n' "$p"
			return 0
		fi
	done
	return 1
}

launch_engine()
{
	# setsid env ... form per rules/gui-screenshots.md: the plain
	# LD_LIBRARY_PATH prefix poisons setsid itself (brew glibc)
	log "launching engine: $BINARY /console $SCEN"
	HOME="$PRIVATE_HOME" DISPLAY="$DISP" \
	setsid env LD_PRELOAD=libGLX_mesa.so.0 \
	LD_LIBRARY_PATH="/home/linuxbrew/.linuxbrew/Cellar/glibc/2.39_1/lib:/home/linuxbrew/.linuxbrew/lib/gcc/current:/home/linuxbrew/.linuxbrew/lib:$LIBFILL:/usr/lib/x86_64-linux-gnu" \
	LIBGL_ALWAYS_SOFTWARE=1 "$BINARY" /console "$SCEN" >>"$RUNLOG" 2>&1 &
	local i p
	for i in 1 2 3 4 5; do
		p="$(find_our_clonk | tail -1)"
		[ -n "$p" ] && break
		sleep 1
	done
	p="$(find_our_clonk | tail -1)"
	if [ -z "$p" ]; then
		log "GAP engine did not spawn a clonk on $DISP; logs at $RUNLOG"
		return 1
	fi
	CLONK_PIDS+=("$p")
	log "engine pid $p"
	return 0
}

# --- live toolbar calibration ----------------------------------------------------
# The five GtkToggleButtons in the top_hbox are pixbufs with no OCR text, so
# locate them by the dark ink of their icons: crop the window's toolbar band
# (above the status frame), find contiguous column clusters of dark pixels, and
# take the 4th cluster (mode_hbox = [btnModePlay btnModeEdit btnModeDraw], so
# btnModeEdit is the 4th of five). Echoes "abs_x abs_y" for the cluster centre.
calibrate_mode_edit()
{
	local wid="$1" wx="$2" wy="$3" ww="$4" wh="$5"
	# the toolbar row sits ~45px above the window bottom; the crop stops above
	# the status frame so the ticking frame counter is not read as an icon
	local top=$(( wh - 72 ))
	DISPLAY="$DISP" timeout 30 import -window "$wid" "$TMP/win.png" 2>/dev/null || return 1
	convert "$TMP/win.png" -crop "${ww}x48+0+${top}" +repage txt:- 2>/dev/null \
	| awk -F'[(),]' -v W="$ww" -v top="$top" '
		NR > 1 {
			x = $1 + 0; y = $2 + 0; r = $3 + 0; g = $4 + 0; b = $5 + 0
			if (r < 120 && g < 120 && b < 120) { cnt[x]++; sy[x] += y }
		}
		END {
			n = 0; inrun = 0; rs = 0; re = 0; rsy = 0; rn = 0
			for (x = 0; x < W; x++) {
				if (cnt[x] > 0) {
					if (!inrun) { inrun = 1; rs = x; rsy = 0; rn = 0 }
					else if (x - re > 6) {
						printf "%d %d\n", int((rs + re) / 2), int(rsy / rn) + top
						rs = x; rsy = 0; rn = 0
					}
					re = x; rsy += sy[x]; rn += cnt[x]
				}
			}
			if (inrun) printf "%d %d\n", int((rs + re) / 2), int(rsy / rn) + top
		}' > "$TMP/clusters.txt"
	local ncluster line cx cy
	ncluster="$(wc -l < "$TMP/clusters.txt" 2>/dev/null || echo 0)"
	log "toolbar ink clusters: $ncluster"
	line="$(sed -n '4p' "$TMP/clusters.txt")"
	if [ -z "$line" ]; then
		log "GAP calibration: fewer than 4 toolbar icon clusters (see $TMP/clusters.txt)"
		return 1
	fi
	read -r cx cy <<<"$line"
	printf '%d %d\n' $(( wx + cx )) $(( wy + cy ))
}

xclick()
{
	DISPLAY="$DISP" "$XDTOOL" mousemove "$1" "$2"
	sleep 0.3
	DISPLAY="$DISP" "$XDTOOL" click 1
	sleep 0.5
}

park_mouse()
{
	DISPLAY="$DISP" "$XDTOOL" mousemove 8 8
	sleep 0.3
}

# --- verdict ---------------------------------------------------------------------
vgate()
{
	# vgate NAME STATUS DETAIL
	VERDICT_LINES+=("$1: $2 — $3")
	log "GATE $1: $2 — $3"
}

write_verdict()
{
	local overall="$1"
	{
		echo "# devmode-boot-drive verdict (cycle 227, worldeditor-devmode-boot)"
		echo "# gates: Scenario marker + Game-started marker; console window mapped;"
		echo "# toolbar strip 02 vs 03 differs; zero [error] lines; all shots non-empty"
		local line
		for line in "${VERDICT_LINES[@]:-}"; do
			[ -n "$line" ] && echo "$line"
		done
		echo "DEVMODE-BOOT-DRIVE: $overall"
	} > "$VERDICT"
	log "verdict written: $VERDICT"
	log "DEVMODE-BOOT-DRIVE: $overall"
}

# --- main ------------------------------------------------------------------------
main()
{
	check_tools || { log "prerequisite check failed"; exit 2; }

	mkdir -p "$EVID" "$TMP"
	# fresh scratch state per run: clear only our own outputs
	rm -f "$EVID/01-console-booted.png" "$EVID/02-toolbar-before.png" \
		"$EVID/03-toolbar-after.png" "$EVID/04-edit-mode.png" \
		"$VERDICT" "$RUNLOG" "$XVFB_LOG"
	rm -rf "$TMP" "$PRIVATE_HOME"
	mkdir -p "$TMP" "$PRIVATE_HOME/.legacyclonk"
	: > "$RUNLOG"

	if ! start_xvfb; then
		vgate xvfb FAIL "display $DISP would not start (see $XVFB_LOG)"
		write_verdict FAIL
		exit 1
	fi

	# private HOME with a copied config (keeps resolution changes local)
	cp "$SEED_CONFIG" "$PRIVATE_HOME/.legacyclonk/config" 2>/dev/null \
		|| log "note: cannot copy seed config; continuing with defaults"

	# launch with a small retry loop: the brew-env swrast launch is flaky
	# (rules/gui-screenshots.md "Hard-won launch lessons")
	local attempt launched=0
	for attempt in 1 2 3; do
		log "launch attempt $attempt"
		if ! launch_engine; then
			log "engine did not spawn on attempt $attempt"
			continue
		fi
		CONSOLE_WID="$(wait_window 90 | tail -1)"
		if [ -z "$CONSOLE_WID" ]; then
			log "no GTK console window after attempt $attempt; relaunching"
			kill_clonk
			continue
		fi
		if ! wait_log '\[info\] Scenario: .*ColonyBay' 120; then
			log "no ColonyBay Scenario: line after attempt $attempt; relaunching"
			kill_clonk
			CONSOLE_WID=""
			continue
		fi
		launched=1
		break
	done

	if [ "$launched" != 1 ]; then
		vgate console-window FAIL "no GTK console window / Scenario line after 3 attempts (see $RUNLOG)"
		write_verdict FAIL
		exit 1
	fi

	# wait for the calibrated game-open marker on the console path
	local gameopen_ok=0
	if wait_log '\[info\] Game started\.' 120; then
		gameopen_ok=1
	fi
	sleep 2
	park_mouse

	# --- 01: console booted ---
	shot 01-console-booted

	# window geometry + toolbar before
	local geom wx wy ww wh
	geom="$(DISPLAY="$DISP" "$XDTOOL" getwindowgeometry --shell "$CONSOLE_WID" 2>/dev/null)"
	wx="$(sed -n 's/^X=//p' <<<"$geom")"
	wy="$(sed -n 's/^Y=//p' <<<"$geom")"
	ww="$(sed -n 's/^WIDTH=//p' <<<"$geom")"
	wh="$(sed -n 's/^HEIGHT=//p' <<<"$geom")"
	log "console window $CONSOLE_WID at $wx,$wy ${ww}x${wh}"

	local strip_top=$(( wy + wh - STRIP_TOP_OFF ))
	crop_shot 02-toolbar-before "$EVID/01-console-booted.png" "$strip_top" "$STRIP_H" "$wx" "$ww"

	# --- click btnModeEdit (calibrated on the live frame) ---
	local xy cx cy
	xy="$(calibrate_mode_edit "$CONSOLE_WID" "$wx" "$wy" "$ww" "$wh")"
	if [ -n "$xy" ]; then
		read -r cx cy <<<"$xy"
		log "clicking btnModeEdit at $cx,$cy"
		xclick "$cx" "$cy"
	else
		log "GAP calibration failed; falling back to source-derived geometry"
		# InitGUI: mode_hbox is right-aligned; btnModeEdit centre is ~66px in
		# from the window's right edge, ~45px above the bottom edge (320x320)
		cx=$(( wx + ww - 66 ))
		cy=$(( wy + wh - 45 ))
		log "clicking btnModeEdit at $cx,$cy (fallback)"
		xclick "$cx" "$cy"
	fi
	sleep 2
	park_mouse

	# --- 03 + 04: post-click frame ---
	DISPLAY="$DISP" timeout 30 import -window root "$TMP/root-after.png" 2>/dev/null
	crop_shot 03-toolbar-after "$TMP/root-after.png" "$strip_top" "$STRIP_H" "$wx" "$ww" || true
	if [ -s "$TMP/root-after.png" ]; then
		cp -f "$TMP/root-after.png" "$EVID/04-edit-mode.png"
		log "shot 04-edit-mode ($(identify -format '%wx%h/%k colors' "$EVID/04-edit-mode.png" 2>/dev/null))"
	else
		log "GAP shot 04-edit-mode failed (no image)"
	fi

	# --- gates ---
	local scen_ok=0 gameopen_line="" errs=0 shots_ok=0 diff_ok=0 s
	local scen_line
	scen_line="$(grep -m1 -E '\[info\] Scenario: ' "$RUNLOG" 2>/dev/null || true)"
	[ -n "$scen_line" ] && grep -q 'ColonyBay' <<<"$scen_line" && scen_ok=1
	vgate scenario "$([ "$scen_ok" = 1 ] && echo PASS || echo FAIL)" "${scen_line:-no Scenario: line}"

	gameopen_line="$(grep -m1 -E '\[info\] Game started\.' "$RUNLOG" 2>/dev/null || true)"
	[ "$gameopen_ok" = 1 ] && [ -n "$gameopen_line" ] \
		&& vgate game-open PASS "$gameopen_line" \
		|| vgate game-open FAIL "${gameopen_line:-no 'Game started.' line}"

	if [ -n "$CONSOLE_WID" ] && DISPLAY="$DISP" "$XDTOOL" getwindowgeometry --shell "$CONSOLE_WID" >/dev/null 2>&1; then
		vgate console-window PASS "wid $CONSOLE_WID mapped"
	else
		vgate console-window FAIL "no mapped GTK console window"
	fi

	if [ -s "$EVID/02-toolbar-before.png" ] && [ -s "$EVID/03-toolbar-after.png" ] \
		&& ! cmp -s "$EVID/02-toolbar-before.png" "$EVID/03-toolbar-after.png"; then
		diff_ok=1
		vgate toolbar-toggle PASS "02 vs 03 differ in bytes"
	else
		vgate toolbar-toggle FAIL "toolbar strip pair byte-identical or missing"
	fi

	errs="$(grep -c '\[error\]' "$RUNLOG" 2>/dev/null || true)"
	[ -z "$errs" ] && errs=0
	[ "$errs" = 0 ] \
		&& vgate no-errors PASS "0 [error] lines in run log" \
		|| vgate no-errors FAIL "$errs [error] lines in run log"

	for s in "${SHOTS[@]}"; do
		[ -s "$EVID/$s.png" ] && shots_ok=$((shots_ok + 1))
	done
	[ "$shots_ok" = "${#SHOTS[@]}" ] \
		&& vgate shots PASS "$shots_ok/${#SHOTS[@]} non-empty" \
		|| vgate shots FAIL "$shots_ok/${#SHOTS[@]} non-empty"

	if [ "$scen_ok" = 1 ] && [ "$gameopen_ok" = 1 ] && [ -n "$CONSOLE_WID" ] \
		&& [ "$diff_ok" = 1 ] && [ "$errs" = 0 ] && [ "$shots_ok" = "${#SHOTS[@]}" ]; then
		write_verdict PASS
		exit 0
	fi
	write_verdict FAIL
	exit 1
}

main "$@"
