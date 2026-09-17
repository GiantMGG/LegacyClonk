#!/usr/bin/env bash
#
# menu_walk_screenshots.sh — Leg B evidence generator (NOT a battery entry).
#
# Drives the GUI build (LegacyClonk/build3/clonk) through the new-player menu
# walk under Xvfb at 1920x1080 and 1280x720, capturing one PNG per observable
# step into:
#     .opencode/scratch/131/menu-walk/{1080p,720p}/NN-<step>.png
#
# Walk (per spec 2026-09-17-menu-walk-smoke, task T4):
#   player-creation dialog  ->  welcome dialog  ->  Play tutorial (Enter; default
#   focus per C4StartupWelcomeDlg.cpp:83)  ->  tutorial runs  ->  abort (ESC)  ->
#   back on the main menu  ->  Start Game  ->  scenario selection  ->  Worlds
#   folder  ->  Colony Bay loads.
#
# Implements the verified recipe in rules/gui-screenshots.md end-to-end:
#   - private HOME with a copied&patched config (ResolutionX/Y per resolution)
#   - own Xvfb displays (:96 / :97)
#   - the exact LD_PRELOAD / LD_LIBRARY_PATH / LIBGL_ALWAYS_SOFTWARE launch line
#   - `import -window root` per observable step, `identify` sanity below
#   - kill Xvfb and clonk by PID on exit (never pkill -f on a pattern we're in)
#
# Keyboard-first navigation. Best-effort: a step that cannot be reached is
# logged as GAP and the walk continues with what works — a partial walk with
# honest gaps beats a faked full one.
#
# Empirically verified navigation facts (cycle-131, 2026-09-17):
#   * main menu auto-opens the player-creation dialog when no *.c4p exists in
#     build3/ (players live in ExePath, not in HOME).
#   * the welcome dialog's "Play tutorial" is the default focus; Enter launches
#     Tutorial01 (log: "Scenario: Tutorial.c4f\Tutorial01.c4s").
#   * the single-player pre-game clonk chooser is accepted with Down+Return
#     (log: "Player join: WalkPlayer" / "Game started.").
#   * ESC during gameplay opens the abort dialog (Yes has default focus); Enter
#     aborts and returns to the startup frontend. For a game started from the
#     welcome path (eLastDlgID=Main) that is the MAIN MENU, not the scenario
#     selection. Both landings are handled below.
#   * main menu "Start Game" is the default focus; Enter opens the scenario
#     selection (log shows the EnableSurrender pack scan).
#   * root scenario list: folders sorted by Folder.txt Index
#     (ReactionLab[1], Tutorial[1], Worlds[2], ...) -> Worlds is entry 3
#     (2 Down presses from the top).
#   * inside Worlds the scenarios sort by difficulty (Gold Mine D5 first,
#     Colony Bay D40 at position 9; values read from content/Worlds.c4f) ->
#     8 Down presses from Gold Mine select Colony Bay.
#
# Requires (checked at startup): Xvfb, xdotool, import, identify, tesseract,
# gm (GraphicsMagick) — held to the same bar as tesseract: both serve the
# OCR state checks after the engine's small fonts defeat bare tesseract, so a
# missing gm fails preflight loudly instead of silently no-oping every
# ocr_has() and degrading all OCR gates to blind navigation (cycle-131 nits),
# > 8 GiB free memory.
#
# Usage:  bash tools/menu_walk_screenshots.sh
#
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"                        # LegacyClonk
WS="$(dirname "$REPO")"                                # clonk_ws
SEED_CONFIG="$WS/.opencode/scratch/wincond-qa/qa-home/.legacyclonk/config"
LIBFILL="$WS/.opencode/scratch/wincond-qa/libfill"
OUT="$WS/.opencode/scratch/131/menu-walk"
BINARY="$REPO/build3/clonk"
PLAYER_BACKUP="$OUT/players-backup"

# xdotool / import bursts must stay behind the engine frame rate. The smaller
# resolution renders slower under xdotool's software GL, so the cadence is
# raised per leg before run_walk().
KEY_DELAY=0.8
LOG_OFFSET=0

# --- spawned PIDs (killed by PID only; trap + helpers) ------------------------
XVFB_PIDS=()
CLONK_PIDS=()

log() { printf '[menu_walk] %s\n' "$*"; }

cleanup()
{
	log "cleanup: killing engine + Xvfb by PID"
	kill_clonk
	for p in "${XVFB_PIDS[@]}"; do
		kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null
	done
	local i any p
	for i in 1 2 3 4 5; do
		any=0
		for p in "${CLONK_PIDS[@]}" "${XVFB_PIDS[@]}"; do kill -0 "$p" 2>/dev/null && any=1; done
		[ "$any" = 0 ] && break
		sleep 1
	done
	for p in "${CLONK_PIDS[@]}" "${XVFB_PIDS[@]}"; do
		kill -0 "$p" 2>/dev/null && kill -9 "$p" 2>/dev/null
	done
	restore_players
	log "cleanup done"
}
trap cleanup EXIT INT TERM

kill_clonk()
{
	local p i any
	for p in $(pgrep -x clonk 2>/dev/null); do
		log "killing clonk pid $p"
		kill "$p" 2>/dev/null
	done
	for i in 1 2 3 4 5; do
		pgrep -x clonk >/dev/null 2>&1 || break
		sleep 1
	done
	any="$(pgrep -x clonk 2>/dev/null | wc -l)"
	[ "$any" -gt 0 ] && { for p in $(pgrep -x clonk 2>/dev/null); do kill -9 "$p" 2>/dev/null; done; }
	CLONK_PIDS=()
}

# --- player file handling ----------------------------------------------------
# Players are looked up in ExePath (= build3/) with PlayerPath "", NOT in HOME.
# A leftover *.c4p (e.g. Neuling.c4p) suppresses the first-run player-creation
# dialog, so existing players are parked for the walk and restored at exit.
# BACKUP_RAN gates every destructive player-file operation: a preflight exit
# (missing tool, engine already running, display busy) happens BEFORE
# backup_players(), so without the gate restore_players() would treat every
# build3/*.c4p as walk-created (is_walk_player with an empty list returns 0
# for everything) and delete all player profiles (cycle-131 BLOCKING #1).
PRECREATED_PLAYERS=()
BACKUP_RAN=0

backup_players()
{
	local p
	PRECREATED_PLAYERS=()
	mkdir -p "$PLAYER_BACKUP"
	for p in "$REPO"/build3/*.c4p; do
		[ -e "$p" ] || continue
		PRECREATED_PLAYERS+=("$(basename "$p")")
		mv "$p" "$PLAYER_BACKUP/"
	done
	[ "${#PRECREATED_PLAYERS[@]}" -gt 0 ] && log "parked pre-existing players: ${PRECREATED_PLAYERS[*]}"
	BACKUP_RAN=1
}

is_walk_player()
{
	# $1 = basename; returns 0 if the player was created by the walk
	local b="$1" pre
	for pre in "${PRECREATED_PLAYERS[@]:-}"; do
		[ "$b" = "$pre" ] && return 1
	done
	return 0
}

restore_players()
{
	local p b
	# Never touch build3/ player files unless the walk actually backed them up
	# first. On a preflight exit (missing tool, engine already running, display
	# busy) no walk ever started, so no *.c4p can be walk-created and deleting
	# any of them would wipe pre-existing profiles (cycle-131 BLOCKING #1).
	if [ "$BACKUP_RAN" != 1 ]; then
		log "skipping player restore (walk never backed up players)"
		return 0
	fi
	for p in "$REPO"/build3/*.c4p; do
		[ -e "$p" ] || continue
		b="$(basename "$p")"
		if is_walk_player "$b"; then
			log "removing walk-created player: $b"
			rm -f "$p"
		fi
	done
	for b in "${PRECREATED_PLAYERS[@]:-}"; do
		if [ -e "$PLAYER_BACKUP/$b" ] && [ ! -e "$REPO/build3/$b" ]; then
			log "restoring player: $b"
			mv "$PLAYER_BACKUP/$b" "$REPO/build3/"
		fi
	done
}

# between resolutions the next run must see the player-creation dialog again
drop_walk_players()
{
	local p b
	if [ "$BACKUP_RAN" != 1 ]; then
		log "skipping drop (walk never backed up players)"
		return 0
	fi
	for p in "$REPO"/build3/*.c4p; do
		[ -e "$p" ] || continue
		b="$(basename "$p")"
		if is_walk_player "$b"; then
			rm -f "$p"
			log "dropped walk-created player $b for next resolution"
		fi
	done
}

# --- capture / screen helpers -------------------------------------------------
shot()
{
	local name="$1" path="$CUR_DIR/$1" imginfo
	# import can hang for minutes under heavy llvmpipe load; timeout keeps the walk moving
	DISPLAY="$CUR_DISP" timeout 30 import -window root "$path" 2>/dev/null
	imginfo="$(identify -format '%wx%h/%k colors' "$path" 2>/dev/null)"
	if [ -s "$path" ] && [ -n "$imginfo" ]; then
		log "shot $name ($imginfo)"
	else
		# a `timeout`-killed import can leave a truncated PNG that [ -s ]
		# accepts; only a successful identify counts as a real shot
		# (cycle-131 flash nit 7), so the partial file is dropped as GAP
		rm -f "$path"
		log "GAP shot $name failed (no image)"
	fi
}

frame_colors()
{
	DISPLAY="$CUR_DISP" timeout 30 import -window root /tmp/menu_walk_frame.png 2>/dev/null
	identify -format '%k' /tmp/menu_walk_frame.png 2>/dev/null || echo 0
}

# wait until the frame shows >= MIN distinct colors (real UI, not a black screen)
wait_colors()
{
	local min="$1" secs="$2" i c
	for ((i=0;i<secs;i++)); do
		c="$(frame_colors)"
		if [ "$c" -ge "$min" ] 2>/dev/null; then return 0; fi
		sleep 1
	done
	return 1
}

wait_log()
{
	local pattern="$1" secs="$2" i
	for ((i=0;i<secs;i++)); do
		[ -f "$CUR_LOG" ] && grep -q "$pattern" "$CUR_LOG" && return 0
		sleep 2
	done
	return 1
}

# mark + wait for a pattern that must appear in the log AFTER mark_log()
wait_log_new()
{
	local pattern="$1" secs="$2" i
	for ((i=0;i<secs;i++)); do
		[ -f "$CUR_LOG" ] && [ -n "$LOG_OFFSET" ] && tail -c +"$LOG_OFFSET" "$CUR_LOG" | grep -q "$pattern" && return 0
		sleep 2
	done
	return 1
}

mark_log()
{
	LOG_OFFSET="$(wc -c < "$CUR_LOG" 2>/dev/null || echo 0)"
}

ocr_has()
{
	DISPLAY="$CUR_DISP" timeout 30 import -window root /tmp/menu_walk_ocr.png 2>/dev/null
	# upscale 2x: the engine's fonts are hard for tesseract at 1280x720
	gm convert /tmp/menu_walk_ocr.png -resize 200% /tmp/menu_walk_ocr2x.png 2>/dev/null
	tesseract /tmp/menu_walk_ocr2x.png stdout 2>/dev/null | grep -qiE "$1"
}

wait_ocr()
{
	local pattern="$1" secs="$2" i
	for ((i=0;i<secs;i++)); do
		ocr_has "$pattern" && return 0
		sleep 2
	done
	return 1
}

xkey()
{
	sleep "$KEY_DELAY"
	DISPLAY="$CUR_DISP" xdotool key "$@"
	sleep "$KEY_DELAY"
}

xtype()
{
	sleep "$KEY_DELAY"
	DISPLAY="$CUR_DISP" xdotool type --delay 50 "$1"
	sleep "$KEY_DELAY"
}

focus_window()
{
	local wid
	wid="$(DISPLAY="$CUR_DISP" xdotool search --class LegacyClonk 2>/dev/null | tail -1)"
	[ -n "$wid" ] && DISPLAY="$CUR_DISP" xdotool windowfocus "$wid" 2>/dev/null
	true
}

check_tools()
{
	local t
	for t in Xvfb xdotool import identify tesseract gm setsid; do
		command -v "$t" >/dev/null 2>&1 || { echo "missing tool: $t"; return 1; }
	done
	[ -x "$BINARY" ] || { echo "GUI build not found: $BINARY"; return 1; }
	[ -f "$SEED_CONFIG" ] || { echo "seed config missing: $SEED_CONFIG"; return 1; }
	[ -d "$LIBFILL" ] || { echo "libfill missing: $LIBFILL"; return 1; }
	local avail availGiB
	avail="$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
	availGiB=$((avail / 1024 / 1024))
	[ "$availGiB" -ge 8 ] || { echo "free memory too low: ${availGiB} GiB (< 8 GiB)"; return 1; }
	return 0
}

# --- engine lifecycle -----------------------------------------------------------
start_xvfb()
{
	local wdt="$1" hgt="$2" disp="$3" label="$4"
	Xvfb "$disp" -screen 0 "${wdt}x${hgt}x24" >"$OUT/xvfb-$label.log" 2>&1 &
	XVFB_PIDS+=($!)
	local i
	for i in 1 2 3 4 5; do
		DISPLAY="$disp" xdotool getdisplaygeometry >/dev/null 2>&1 && break
		sleep 1
	done
	if ! DISPLAY="$disp" xdotool getdisplaygeometry >/dev/null 2>&1; then
		log "GAP Xvfb $disp failed to start (see $OUT/xvfb-$label.log)"
		return 1
	fi
	return 0
}

launch_engine()
{
	# recipe line from rules/gui-screenshots.md (modified per task: resolution from config)
	log "launching engine"
	HOME="$PRIVATE_HOME" LD_PRELOAD=libGLX_mesa.so.0 \
	LD_LIBRARY_PATH="/home/linuxbrew/.linuxbrew/Cellar/glibc/2.39_1/lib:/home/linuxbrew/.linuxbrew/lib/gcc/current:/home/linuxbrew/.linuxbrew/lib:$LIBFILL:/usr/lib/x86_64-linux-gnu" \
	DISPLAY="$CUR_DISP" LIBGL_ALWAYS_SOFTWARE=1 setsid "$BINARY" >>"$CUR_LOG" 2>&1 &
	local engine_pid=$! i p
	for i in 1 2 3 4 5; do
		p="$(pgrep -x clonk 2>/dev/null | tail -1)"
		[ -n "$p" ] && break
		sleep 1
	done
	p="$(pgrep -x clonk 2>/dev/null | tail -1)"
	if [ -z "$p" ]; then
		log "GAP engine did not spawn clonk (launcher pid $engine_pid); logs at $CUR_LOG"
		return 1
	fi
	CLONK_PIDS+=("$p")
	log "engine pid $p"
	return 0
}

# Wait for the frontend main menu. Deals with a re-shown welcome dialog by
# dismissing it with Escape (dialog-level escape closes a modal without side
# effects). Returns 0 when the main menu (Replays button) is OCR-detected.
# Wait for the frontend main menu (relaunch path). Handles a re-shown welcome
# dialog (config not saved on SIGTERM -> FirstStart may still be true) by
# dismissing it with Escape, then waits for the menu chrome (version text).
wait_mainmenu()
{
	local i
	for i in $(seq 1 45); do
		if ocr_has "welcome"; then
			log "dismissing re-shown welcome dialog"
			xkey Escape
			sleep 2
			continue
		fi
		if ocr_has "4.9|replays|players|about"; then return 0; fi
		sleep 2
	done
	return 1
}

# --- per-resolution walk ---------------------------------------------------------
run_walk()
{
	local label="$1" wdt="$2" hgt="$3" disp="$4" home="$5"
	CUR_DIR="$OUT/$label"
	CUR_DISP="$disp"
	CUR_LOG="$OUT/run-$label.log"
	PRIVATE_HOME="$home"
	mkdir -p "$CUR_DIR" "$home/.legacyclonk"
	: > "$CUR_LOG"
	rm -f "$CUR_DIR"/*.png

	log "==== $label ($wdt x $hgt on $disp) ===="

	# private HOME with copied + resolution-patched config
	if ! cp "$SEED_CONFIG" "$home/.legacyclonk/config"; then
		log "GAP cannot copy seed config; continuing with defaults"
	fi
	sed -i "s/^ResolutionX=.*/ResolutionX=$wdt/; s/^ResolutionY=.*/ResolutionY=$hgt/" "$home/.legacyclonk/config" 2>/dev/null
	# Starting any single-player scenario requires at least one participating
	# player (CanOpen: "0 of 1 players" otherwise). The walk's creation dialog
	# always produces the deterministic player file build3/WalkPlayer.c4p, so
	# seed the participant list with its absolute path — this survives the
	# abort->relaunch (config is not saved on SIGTERM). Format: plain string.
	local plrpath="$REPO/build3/WalkPlayer.c4p"
	if grep -q '^Participants=' "$home/.legacyclonk/config" 2>/dev/null; then
		sed -i "s|^Participants=.*|Participants=\"$plrpath\"|" "$home/.legacyclonk/config"
	else
		sed -i "/^\[General\]/a Participants=\"$plrpath\"" "$home/.legacyclonk/config"
	fi

	start_xvfb "$wdt" "$hgt" "$disp" "$label" || return 1

	launch_engine || return 1
	# readiness: real rendering once (cold start can take a while), then settle
	if ! wait_colors 20000 180; then
		log "GAP no rendered frame after 180s; capturing anyway"
	fi
	sleep 3
	focus_window

	# 01 - player-creation dialog (auto-opened: no player files present)
	if wait_ocr "jump" 60; then log "player-creation dialog detected"; else log "note: creation-dialog OCR marker not found"; fi
	shot 01-player-creation.png

	# 02 - create player (name edit has default focus) -> welcome dialog
	xtype "WalkPlayer"
	xkey Return
	if wait_ocr "welcome" 30; then log "welcome dialog detected"; else log "note: 'welcome' not OCR-detected"; fi
	sleep 2
	shot 02-welcome.png

	# 03 - Play tutorial (Enter on the default-focused button), then join as player
	mark_log
	xkey Return
	if wait_log_new "materials loaded" 120; then log "tutorial scenario loaded"; else log "GAP tutorial did not reach 'materials loaded'"; fi
	sleep 3
	xkey Down
	xkey Return
	mark_log
	if wait_log_new "Player join" 30; then log "joined tutorial as player (gameplay started)"; else log "note: 'Player join' not seen; abort may hit the pre-game phase instead"; fi
	sleep 8
	shot 03-tutorial-running.png

	# 04 - abort the game (ESC -> abort dialog with Yes focused -> Enter)
	xkey Escape
	sleep 2
	shot 04-abort-dialog.png
	mark_log
	xkey Return
	# 05 - back on the main menu. A gameplay abort re-enters the startup
	#      frontend, which logs "Music: Frontend.ogg" — a deterministic signal
	#      (the OCR marker routine is a secondary check).
	local state=""
	if wait_log_new "Frontend.ogg" 60; then
		log "frontend re-entered after abort (log signal)"
		sleep 2
		state=main
	else
		log "GAP no 'Frontend.ogg' after abort"
		if wait_ocr "reaction lab" 15; then state=scensel; fi
	fi
	case "$state" in
		scensel)
			log "abort landed in scenario selection; going to the main menu"
			shot 05-scen-sel-after-abort.png
			xkey Left
			if wait_ocr "4.9|replays|players|about" 15; then log "main menu reached"; else sleep 2; fi
			;;
		main)
			true
			;;
		*)
			log "GAP abort landing not determined; relaunching to a clean main menu"
			shot 05-undetermined.png
			kill_clonk
			CLONK_PIDS=()
			launch_engine || log "GAP relaunch of engine failed"
			if ! wait_colors 20000 60; then log "GAP no frame after relaunch"; fi
			sleep 3
			focus_window
			wait_mainmenu || log "GAP main menu not confirmed after relaunch"
			;;
	esac
	shot 05-main-menu.png

	# if the OCR guard misjudged and we are actually in the scenario selection,
	# back out to the main menu first (Left is safe only there, not on the menu)
	if ocr_has "reaction lab"; then
		log "note: actually in scenario selection; backing out to the main menu"
		xkey Left
		sleep 2
	fi

	# 06 - Start Game (default focus on the main menu) -> scenario selection
	xkey Return
	if wait_ocr "reaction lab" 45; then log "scenario selection reached via Start Game"; sleep 1; else log "note: scenario selection not OCR-confirmed"; fi
	shot 06-scenario-select.png

	# 07 - Worlds: root folders are sorted by Folder.txt Index
	#      (ReactionLab[1], Tutorial[1], Worlds[2], ...) => entry 3, 2 Downs.
	#      Home resets to the first entry each attempt, making the sequence
	#      self-correcting even if a keystroke gets dropped.
	local attempt ok=1
	ok=1
	for attempt in 1 2 3 4 5; do
		xkey Home
		sleep 1
		xkey Down
		xkey Down
		if wait_ocr "settlement" 10; then log "Worlds folder selected (attempt $attempt)"; ok=0; break; fi
	done
	if [ "$ok" = 1 ]; then log "note: Worlds selection not OCR-verified (blind-committing after 5 attempts)"; fi
	shot 07-worlds-selected.png

	# 08 - open Worlds
	xkey Return
	if wait_ocr "colony" 20; then log "Worlds folder opened"; else log "note: Worlds folder content not OCR-verified"; fi
	shot 08-worlds-folder.png

	# 09 - Colony Bay: inside Worlds the scenarios sort by difficulty, Gold Mine
	#      first, Colony Bay at position 9 => 8 Downs. Home-reset retry loop.
	ok=1
	for attempt in 1 2 3 4 5; do
		xkey Home
		sleep 1
		local d
		for d in 1 2 3 4 5 6 7 8; do
			xkey Down
		done
		if wait_ocr "shipwrecked" 10; then log "Colony Bay selected (attempt $attempt)"; ok=0; break; fi
	done
	if [ "$ok" = 1 ]; then log "note: Colony Bay selection not OCR-verified (blind-committing after 5 attempts)"; fi
	shot 09-colony-bay-selected.png

	# 10 - start Colony Bay; the pre-game clonk chooser appears
	mark_log
	xkey Return
	if wait_log_new "ColonyBay" 90; then log "ColonyBay.c4s found in engine log"; else log "GAP ColonyBay not seen in engine log"; fi
	if wait_log_new "materials loaded" 90; then log "Colony Bay scenario loaded"; else log "GAP Colony Bay did not reach 'materials loaded'"; fi
	sleep 4
	shot 10-colony-bay-starting.png

	# 11 - accept the default clonk; the world view should appear
	xkey Down
	xkey Return
	mark_log
	if wait_log_new "Player join" 30; then log "joined Colony Bay as player"; else log "note: 'Player join' not seen"; fi
	sleep 12
	shot 11-colony-bay-loaded.png

	log "==== $label walk finished ===="
	# park the engine so only one engine runs at a time (next leg spawns its own)
	kill_clonk
	for p in "${XVFB_PIDS[@]}"; do kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null; done
	XVFB_PIDS=()
}

# --- main -----------------------------------------------------------------------
main()
{
	check_tools || { log "prerequisite check failed"; exit 2; }

	# one engine + one Xvfb at a time: refuse to stomp on leftovers
	if pgrep -x clonk >/dev/null 2>&1; then
		log "FATAL: clonk already running ($(pgrep -x clonk | tr '\n' ' ')); refusing to continue"
		exit 2
	fi
	local xp
	for xp in $(pgrep -x Xvfb 2>/dev/null); do
		if tr '\0' ' ' < "/proc/$xp/cmdline" 2>/dev/null | grep -qE '(:96|:97)( |$)'; then
			log "FATAL: Xvfb pid $xp already owns :96/:97; refusing to continue"
			exit 2
		fi
	done

	mkdir -p "$OUT"
	backup_players

	# slower key cadence for the smaller (software-rendered) resolution
	KEY_DELAY=0.8
	run_walk 1080p 1920 1080 :96 "$OUT/home-1080"
	# park created players so the next resolution sees the creation dialog again
	drop_walk_players

	KEY_DELAY=1.6
	run_walk 720p 1280 720 :97 "$OUT/home-720"

	log "==== verifying outputs ===="
	local res set n ok=1
	for res in 1080p 720p; do
		set="$OUT/$res"
		n=$(ls "$set"/*.png 2>/dev/null | wc -l)
		log "$res: $n screenshots"
		[ "$n" -ge 4 ] || ok=0
	done
	if [ "$ok" = 1 ]; then
		log "RESULT: screenshot sets present at both resolutions"
	else
		log "RESULT: incomplete screenshot sets (see GAP lines above)"
	fi
}

main "$@"
