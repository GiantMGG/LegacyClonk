#!/usr/bin/env bash
#
# real_playtest_walk.sh — cycle 216 real-playtest walk (T1; NOT a battery entry).
#
# Drives the GUI build (LegacyClonk/build3/clonk) through the owner's real-player
# path end-to-end at 1920x1080 and 1280x720 under Xvfb:
#
#   player-creation dialog -> welcome dialog (Escape) -> main menu -> Start Game
#   -> scenario selection -> Worlds folder -> Colony Bay -> C4OfflineOptionsDlg
#   landing stage -- CLICK [World Settings] (NEVER Enter on the landing stage:
#   Enter = Quick Start and skips the settings stage, C4OfflineOptionsDlg.cpp:1399)
#   -> settings stage, Round tab -> Store tab with a shared count-editor refill
#   -> [Start Game] -> in-game.
#
# Outputs:
#   .opencode/playtests/2026-10-12-real-playtest-walk/{1080p,720p}/NN-<stage>.png
#     01-main-menu 02-scenario-selection 03-landing 04-round-tab
#     05-store-before 06-store-after 07-in-game
#   .opencode/scratch/216/run-{1080p,720p}.log     (engine run logs)
#   .opencode/scratch/216/walk-verdict.txt         (gates + final verdict line)
#
# Per-resolution PASS gates (all must hold):
#   * all seven stage shots exist non-empty;
#   * engine log does NOT contain "PreGame: skipping options dialog";
#   * engine log contains "Player join: " and "Game started." after Start;
#   * the Store refill before/after PNG pair differs in bytes (cmp);
#   * zero [error] lines from scenario scripts in the engine log.
#
# FAIL = a stage unreachable at that resolution, or the refill pair stays
# byte-identical at 1080p (at 720p an identical pair is a reportable GAP when
# 1080p proved the refill). GAP (honest, non-fatal) = team picker absent on the
# Round tab (Colony Bay offers none) — recorded, never synthesized.
#
# Every UI click is derived from a LIVE tesseract-TSV scan of the current frame
# at the current resolution (rules/gui-screenshots.md) — no coordinates are
# reused across resolutions. OCR navigates and sanity-checks but never concludes;
# the log markers gate. Keyboard-first where the cycle-131 facts are verified
# (main-menu Start Game default focus, Worlds 1 Down, Colony Bay 8 Downs).
#
# The engine draws its cursor sprite into every frame, so the mouse is parked at
# the same neutral spot (12,12) before the Store before/after pair — the cmp
# gate must not see cursor-position deltas, only real UI change.
#
# Usage: bash tools/real_playtest_walk.sh
#
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"                        # LegacyClonk
WS="$(dirname "$REPO")"                                # clonk_ws
EVID="$WS/.opencode/scratch/216"
PLAYTEST="$WS/.opencode/playtests/2026-10-12-real-playtest-walk"
SEED_CONFIG="$WS/.opencode/scratch/wincond-qa/qa-home/.legacyclonk/config"
LIBFILL="$WS/.opencode/scratch/wincond-qa/libfill"
BINARY="$REPO/build3/clonk"
PLAYER_BACKUP="$EVID/players-backup"
VERDICT="$EVID/walk-verdict.txt"

# xdotool lives at the brew path and is not on PATH in loop shells
# (rules/gui-screenshots.md:51) — resolve it once, use it everywhere.
XDTOOL="$(command -v xdotool 2>/dev/null || true)"
if [ -z "$XDTOOL" ] || [ ! -x "$XDTOOL" ]; then
	XDTOOL="/home/linuxbrew/.linuxbrew/bin/xdotool"
fi

# key cadence: the smaller (software-rendered) resolution needs a slower one
KEY_DELAY=0.8
LOG_OFFSET=0

# per-leg state
CUR_LABEL=""
CUR_DIR=""
CUR_DISP=""
CUR_LOG=""
CUR_W=0
CUR_H=0
PRIVATE_HOME=""

# verdict accumulation
VERDICT_LINES=()
declare -A RES_STATUS RES_REFILL_OK

log() { printf '[real_playtest_walk] %s\n' "$*"; }

# --- spawned PIDs (killed by PID only; trap + helpers) ------------------------
XVFB_PIDS=()
CLONK_PIDS=()

cleanup()
{
	log "cleanup: killing engine + Xvfb by PID"
	kill_clonk
	local p
	for p in "${XVFB_PIDS[@]}"; do
		kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null
	done
	local i any
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
	local p i
	for p in $(pgrep -x clonk 2>/dev/null); do
		log "killing clonk pid $p"
		kill "$p" 2>/dev/null
	done
	for i in 1 2 3 4 5; do
		pgrep -x clonk >/dev/null 2>&1 || break
		sleep 1
	done
	local any
	any="$(pgrep -x clonk 2>/dev/null | wc -l)"
	if [ "$any" -gt 0 ]; then
		for p in $(pgrep -x clonk 2>/dev/null); do kill -9 "$p" 2>/dev/null; done
	fi
	CLONK_PIDS=()
}

# --- player file handling ------------------------------------------------------
# Players are looked up in ExePath (= build3/), NOT in HOME. A leftover *.c4p
# suppresses the first-run player-creation dialog, so pre-existing players are
# parked in PLAYER_BACKUP and restored at exit. BACKUP_RAN gates every
# destructive player-file operation: a preflight exit must never treat foreign
# *.c4p files as walk-created (cycle-131 BLOCKING #1).
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

# between resolutions the next leg must see the creation dialog again
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

# --- capture / screen helpers ---------------------------------------------------
shot()
{
	local name="$1" path="$CUR_DIR/$1" imginfo
	# import can hang for minutes under heavy llvmpipe load; timeout keeps the walk moving
	DISPLAY="$CUR_DISP" timeout 30 import -window root "$path" 2>/dev/null
	imginfo="$(identify -format '%wx%h/%k colors' "$path" 2>/dev/null)"
	if [ -s "$path" ] && [ -n "$imginfo" ]; then
		log "shot $name ($imginfo)"
	else
		# a timeout-killed import can leave a truncated PNG that [ -s ] accepts;
		# only a successful identify counts as a real shot (cycle-131 flash nit)
		rm -f "$path"
		log "GAP shot $name failed (no image)"
	fi
}

frame_colors()
{
	DISPLAY="$CUR_DISP" timeout 30 import -window root "$EVID/tmp/frame-$CUR_LABEL.png" 2>/dev/null
	identify -format '%k' "$EVID/tmp/frame-$CUR_LABEL.png" 2>/dev/null || echo 0
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

# wait for a pattern that must appear in the log AFTER mark_log()
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
	DISPLAY="$CUR_DISP" timeout 30 import -window root "$EVID/tmp/ocr-has-$CUR_LABEL.png" 2>/dev/null
	# upscale 2x: the engine's fonts are hard for tesseract at 1280x720
	gm convert "$EVID/tmp/ocr-has-$CUR_LABEL.png" -resize 200% "$EVID/tmp/ocr-has2x-$CUR_LABEL.png" 2>/dev/null
	tesseract "$EVID/tmp/ocr-has2x-$CUR_LABEL.png" stdout 2>/dev/null | grep -qiE "$1"
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

# --- input helpers ---------------------------------------------------------------
xkey()
{
	sleep "$KEY_DELAY"
	DISPLAY="$CUR_DISP" "$XDTOOL" key "$@"
	sleep "$KEY_DELAY"
}

xtype()
{
	sleep "$KEY_DELAY"
	DISPLAY="$CUR_DISP" "$XDTOOL" type --delay 50 "$1"
	sleep "$KEY_DELAY"
}

xclick()
{
	sleep "$KEY_DELAY"
	DISPLAY="$CUR_DISP" "$XDTOOL" mousemove "$1" "$2" click 1
	sleep "$KEY_DELAY"
}

# park the OS pointer at the neutral spot so the engine-drawn cursor sprite is
# at identical pixels in shots that get byte-compared (CMouse::Draw, C4Gui.cpp)
park_mouse()
{
	DISPLAY="$CUR_DISP" "$XDTOOL" mousemove 12 12
	sleep 0.3
}

focus_window()
{
	local wid
	wid="$(DISPLAY="$CUR_DISP" "$XDTOOL" search --class LegacyClonk 2>/dev/null | tail -1)"
	[ -n "$wid" ] && DISPLAY="$CUR_DISP" "$XDTOOL" windowfocus "$wid" 2>/dev/null
	true
}

# --- live OCR-TSV click locator ----------------------------------------------------
# All clicks derive from a LIVE tesseract-TSV scan of the CURRENT frame at the
# CURRENT resolution (rules/gui-screenshots.md: never reuse a coordinate across
# resolutions). The frame is upscaled 2x for tesseract; token bboxes are halved
# back to screen coordinates.

# ocr_locate REGEX [ymin ymax] -> "cx cy" of the first matching level-5 token
# (screen coords, reading order). Empty output = no match. ymin/ymax clamp the
# token's center y (screen px) so e.g. the Start button can be pinned to the
# bottom strip.
ocr_locate()
{
	local regex="$1" ymin="${2:-0}" ymax="${3:-99999}"
	local frame="$EVID/tmp/ocr-frame-$CUR_LABEL.png" frame2x="$EVID/tmp/ocr-frame2x-$CUR_LABEL.png"
	DISPLAY="$CUR_DISP" timeout 30 import -window root "$frame" 2>/dev/null || return 1
	gm convert "$frame" -resize 200% "$frame2x" 2>/dev/null || return 1
	tesseract "$frame2x" stdout tsv 2>/dev/null | awk -v re="$regex" -v ymin="$ymin" -v ymax="$ymax" '
		$1 == 5 && tolower($12) ~ re {
			cx = ($7 + $9 / 2) / 2
			cy = ($8 + $10 / 2) / 2
			if (cy >= ymin && cy <= ymax) { printf "%d %d\n", cx, cy; exit }
		}'
}

# ocr_locate_geom REGEX -> "l t w h" of the first matching token (screen coords)
ocr_locate_geom()
{
	local regex="$1"
	local frame="$EVID/tmp/ocr-frame-$CUR_LABEL.png" frame2x="$EVID/tmp/ocr-frame2x-$CUR_LABEL.png"
	DISPLAY="$CUR_DISP" timeout 30 import -window root "$frame" 2>/dev/null || return 1
	gm convert "$frame" -resize 200% "$frame2x" 2>/dev/null || return 1
	tesseract "$frame2x" stdout tsv 2>/dev/null | awk -v re="$regex" '
		$1 == 5 && tolower($12) ~ re { printf "%d %d %d %d\n", $7 / 2, $8 / 2, $9 / 2, $10 / 2; exit }'
}

# click_ocr "pat1 pat2 ..." TRIES [ymin ymax] — try each pattern per attempt,
# click the first live-located token center. Returns 1 when nothing matched.
click_ocr()
{
	local pats="$1" tries="$2" ymin="${3:-0}" ymax="${4:-99999}"
	local i pat xy
	for ((i=0; i<tries; i++)); do
		for pat in $pats; do
			xy="$(ocr_locate "$pat" "$ymin" "$ymax")"
			if [ -n "$xy" ]; then
				log "click_ocr: '$pat' at ($xy)"
				xclick $xy
				return 0
			fi
		done
		sleep 2
	done
	log "click_ocr: no live match for '$pats' after $tries tries"
	return 1
}

# --- engine lifecycle ---------------------------------------------------------------
check_tools()
{
	local t
	for t in Xvfb import identify tesseract gm setsid awk; do
		command -v "$t" >/dev/null 2>&1 || { echo "missing tool: $t"; return 1; }
	done
	[ -x "$XDTOOL" ] || { echo "xdotool not found (PATH + $XDTOOL)"; return 1; }
	[ -x "$BINARY" ] || { echo "GUI build not found: $BINARY"; return 1; }
	[ -f "$SEED_CONFIG" ] || { echo "seed config missing: $SEED_CONFIG"; return 1; }
	[ -d "$LIBFILL" ] || { echo "libfill missing: $LIBFILL"; return 1; }
	local avail availGiB
	avail="$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
	availGiB=$((avail / 1024 / 1024))
	[ "$availGiB" -ge 8 ] || { echo "free memory too low: ${availGiB} GiB (< 8 GiB)"; return 1; }
	return 0
}

start_xvfb()
{
	local wdt="$1" hgt="$2" disp="$3" label="$4"
	Xvfb "$disp" -screen 0 "${wdt}x${hgt}x24" >"$EVID/xvfb-$label.log" 2>&1 &
	XVFB_PIDS+=($!)
	local i
	for i in 1 2 3 4 5; do
		DISPLAY="$disp" "$XDTOOL" getdisplaygeometry >/dev/null 2>&1 && break
		sleep 1
	done
	if ! DISPLAY="$disp" "$XDTOOL" getdisplaygeometry >/dev/null 2>&1; then
		log "GAP Xvfb $disp failed to start (see $EVID/xvfb-$label.log)"
		return 1
	fi
	return 0
}

launch_engine()
{
	# setsid env ... form per rules/gui-screenshots.md:36-38 — the plain
	# LD_LIBRARY_PATH prefix poisons setsid itself (brew glibc)
	log "launching engine"
	HOME="$PRIVATE_HOME" DISPLAY="$CUR_DISP" \
	setsid env LD_PRELOAD=libGLX_mesa.so.0 \
	LD_LIBRARY_PATH="/home/linuxbrew/.linuxbrew/Cellar/glibc/2.39_1/lib:/home/linuxbrew/.linuxbrew/lib/gcc/current:/home/linuxbrew/.linuxbrew/lib:$LIBFILL:/usr/lib/x86_64-linux-gnu" \
	LIBGL_ALWAYS_SOFTWARE=1 "$BINARY" >>"$CUR_LOG" 2>&1 &
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

# --- verdict helpers ------------------------------------------------------------------
vgap()
{
	local line="$CUR_LABEL GAP: $1"
	VERDICT_LINES+=("$line")
	log "GAP $CUR_LABEL: $1"
}

# --- Store refill interaction -----------------------------------------------------------
# The Store sheet's shared count-editor strip is laid out
#   [Count: 64px][selected-def name spanning][slider track][readout: 44px]
# (C4OfflineOptionsDlg.cpp CreateStoreSheet). The slider is a horizontal
# callback ScrollBar: a click on the track jumps the thumb to the clicked
# fraction and fires OnStoreCountSliderChange -> the bound cell's count changes.
# The Count caption token is located live via OCR TSV; the track click x is
# derived from its bbox (y = the token's center line, which is inside the
# ScrollBar's accepted input band).
store_slider_click()
{
	local frac="$1"
	local geom l t w h sx1 sx2 cx cy
	geom="$(ocr_locate_geom 'count|anzahl')" || { log "note: Count caption not OCR-located"; return 1; }
	read -r l t w h <<<"$geom"
	# slider span: from just right of the Count caption to ~60px off the right
	# screen edge (44px readout + margin); click at frac% of that span
	sx1=$(( l + w + 12 ))
	sx2=$(( CUR_W - 60 ))
	cx=$(( sx1 + (sx2 - sx1) * frac / 100 ))
	cy=$(( t + h / 2 ))
	log "store slider click at $cx,$cy (track ${frac}%)"
	xclick "$cx" "$cy"
	return 0
}

# --- per-resolution walk ------------------------------------------------------------------
run_res()
{
	local label="$1" wdt="$2" hgt="$3" disp="$4"
	CUR_LABEL="$label"; CUR_W="$wdt"; CUR_H="$hgt"
	CUR_DIR="$PLAYTEST/$label"; CUR_DISP="$disp"
	CUR_LOG="$EVID/run-$label.log"
	PRIVATE_HOME="$EVID/home-$label"
	mkdir -p "$CUR_DIR" "$PRIVATE_HOME/.legacyclonk" "$EVID/tmp"
	rm -f "$CUR_DIR"/*.png
	: > "$CUR_LOG"

	log "==== $label ($wdt x $hgt on $disp) ===="

	# private HOME with copied + resolution-patched config
	if ! cp "$SEED_CONFIG" "$PRIVATE_HOME/.legacyclonk/config"; then
		log "GAP cannot copy seed config; continuing with defaults"
	fi
	sed -i "s/^ResolutionX=.*/ResolutionX=$wdt/; s/^ResolutionY=.*/ResolutionY=$hgt/" "$PRIVATE_HOME/.legacyclonk/config" 2>/dev/null
	# Starting any single-player scenario requires at least one participating
	# player. The creation dialog deterministically produces
	# build3/WalkPlayer.c4p, so seed the participant list with its absolute
	# path — this survives the abort->relaunch (config is not saved on
	# SIGTERM). Format: plain string (menu_walk:403-408 idiom).
	local plrpath="$REPO/build3/WalkPlayer.c4p"
	if grep -q '^Participants=' "$PRIVATE_HOME/.legacyclonk/config" 2>/dev/null; then
		sed -i "s|^Participants=.*|Participants=\"$plrpath\"|" "$PRIVATE_HOME/.legacyclonk/config"
	else
		sed -i "/^\[General\]/a Participants=\"$plrpath\"" "$PRIVATE_HOME/.legacyclonk/config"
	fi

	if ! start_xvfb "$wdt" "$hgt" "$disp" "$label"; then
		RES_STATUS[$label]="FAIL"
		RES_REFILL_OK[$label]=1
		VERDICT_LINES+=("$label: FAIL — Xvfb would not start; no gates could run")
		return 1
	fi

	if ! launch_engine; then
		RES_STATUS[$label]="FAIL"
		RES_REFILL_OK[$label]=1
		VERDICT_LINES+=("$label: FAIL — engine did not spawn; see $CUR_LOG")
		local p
		for p in "${XVFB_PIDS[@]}"; do kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null; done
		XVFB_PIDS=()
		return 1
	fi

	# readiness: real rendering once (cold start can take a while)
	if ! wait_colors 20000 180; then
		log "GAP no rendered frame after 180s; one relaunch attempt"
		kill_clonk
		if ! launch_engine; then
			RES_STATUS[$label]="FAIL"
			RES_REFILL_OK[$label]=1
			VERDICT_LINES+=("$label: FAIL — no rendered frame and relaunch failed")
			return 1
		fi
		if ! wait_colors 20000 120; then
			RES_STATUS[$label]="FAIL"
			RES_REFILL_OK[$label]=1
			VERDICT_LINES+=("$label: FAIL — no rendered frame after relaunch")
			return 1
		fi
	fi
	sleep 3
	focus_window

	# --- 01: player-creation dialog -> welcome -> main menu --------------------
	if wait_ocr "jump" 60; then log "player-creation dialog detected"; else log "note: creation-dialog OCR marker not found"; fi
	xtype "WalkPlayer"
	xkey Return
	if wait_ocr "welcome" 30; then log "welcome dialog detected"; else log "note: welcome dialog not OCR-detected"; fi
	xkey Escape
	if ! wait_ocr "4\.9|replays|players|about" 60; then
		log "GAP main menu not OCR-confirmed after welcome dismiss; one more Escape"
		xkey Escape
		wait_ocr "4\.9|replays|players|about" 30 || log "GAP main menu still not OCR-confirmed (continuing blind)"
	fi
	park_mouse
	shot 01-main-menu.png

	# --- 02: Start Game -> scenario selection -----------------------------------
	mark_log
	xkey Return
	if wait_ocr "reaction lab" 45; then log "scenario selection reached via Start Game"; sleep 1; else log "GAP scenario selection not OCR-confirmed"; fi
	park_mouse
	shot 02-scenario-selection.png

	# --- Worlds folder: root folders sort by Folder.txt Index (Tutorial[1],
	#     Worlds[2]) -> 1 Down from the top. Home-reset retry loop.
	local attempt ok=1 d
	for attempt in 1 2 3 4 5; do
		xkey Home
		sleep 1
		xkey Down
		if wait_ocr "settlement" 10; then log "Worlds folder selected (attempt $attempt)"; ok=0; break; fi
	done
	[ "$ok" = 1 ] && log "note: Worlds selection not OCR-verified (blind-committing after 5 attempts)"
	xkey Return
	if wait_ocr "colony" 20; then log "Worlds folder opened"; else log "note: Worlds content not OCR-verified"; fi

	# --- Colony Bay: scenarios sort by difficulty (Gold Mine D5 first, Colony
	#     Bay D40 at position 9) -> 8 Downs. Home-reset retry loop.
	ok=1
	for attempt in 1 2 3 4 5; do
		xkey Home
		sleep 1
		for d in 1 2 3 4 5 6 7 8; do xkey Down; done
		if wait_ocr "shipwrecked" 10; then log "Colony Bay selected (attempt $attempt)"; ok=0; break; fi
	done
	[ "$ok" = 1 ] && log "note: Colony Bay selection not OCR-verified (blind-committing after 5 attempts)"

	# --- open Colony Bay; the pre-game load follows ------------------------------
	mark_log
	xkey Return
	if wait_log_new "ColonyBay" 90; then log "ColonyBay.c4s found in engine log"; else log "GAP ColonyBay not seen in engine log"; fi
	if wait_log_new "materials loaded" 90; then log "Colony Bay scenario loaded"; else log "GAP Colony Bay did not reach 'materials loaded'"; fi
	sleep 3

	# --- 03: options-dialog landing stage ----------------------------------------
	# The C4OfflineOptionsDlg shows for Colony Bay (no SkipPregameOptions, no
	# header MissionAccess; C4Game.cpp:2380 gate). Landing stage: title +
	# [World Settings][Quick Start] + Abort. NEVER press Enter here — Enter on
	# the landing stage is Quick Start and skips the settings stage.
	if wait_ocr "quick|settings" 45; then log "landing stage detected"; else log "GAP landing stage not OCR-confirmed"; fi
	park_mouse
	shot 03-landing.png

	local reached_settings=0 reached_store=0 ingame=0
	if click_ocr "settings sett" 8; then
		reached_settings=1
		log "[World Settings] clicked; settings stage expected (Round tab is the active sheet)"

		# --- 04: settings stage, Round tab --------------------------------------
		if wait_ocr "round|store|start" 30; then log "settings stage reached"; else log "GAP settings stage not OCR-confirmed"; fi
		park_mouse
		shot 04-round-tab.png
		# team picker: Colony Bay offers none — record honestly, never synthesize
		if ocr_has "team"; then
			log "note: team-picker text present on Round tab"
		else
			vgap "team picker absent on Round tab (scenario offers none)"
		fi

		# --- Store tab ----------------------------------------------------------
		if click_ocr "store lager" 8; then
			reached_store=1
			if wait_ocr "wood|metal|loam|lorry|flag|clonk" 30; then log "store grid content detected"; else log "GAP store grid content not OCR-confirmed"; fi
			park_mouse
			shot 05-store-before.png

			# bind the shared count editor to a populated cell: click the cell's
			# def-name caption (the little checkbox BOX toggles membership; the
			# caption area does not — CheckBox::MouseInput box-area check)
			click_ocr "wood metal loam concrete lorry flag clonk" 8 || log "GAP no store cell located via OCR"

			# refill: operate the shared count-editor strip's slider; the pair
			# must differ in bytes. Retry at different track fractions.
			local frac=55 refill_differs=1 rcat
			for attempt in 1 2 3; do
				store_slider_click "$frac"
				park_mouse
				shot 06-store-after.png
				rcat=0; store_pair_differs || rcat=$?
				if [ "$rcat" = 0 ]; then refill_differs=0; break; fi
				log "note: refill pair still identical after attempt $attempt"
				frac=$((frac + 15))
			done
			if [ "$refill_differs" = 0 ]; then
				log "refill pair differs in bytes — refill proven"
				RES_REFILL_OK[$label]=0
			else
				log "GAP/FAIL: refill pair byte-identical after 3 slider attempts"
				RES_REFILL_OK[$label]=1
			fi
		else
			log "GAP Store tab not located via OCR"
			RES_REFILL_OK[$label]=1
		fi

		# --- Start: click [Start Game] (Enter also works — settings-stage Enter
		#     routes through TryStart and the stage's default focus IS the Start
		#     button — but a click avoids all focus ambiguity) --------------------
		mark_log
		if click_ocr "start" 8 $((CUR_H * 3 / 4)) "$CUR_H"; then
			log "[Start Game] clicked"
		else
			log "note: [Start Game] not OCR-located; falling back to Enter (settings-stage Enter = Start)"
			xkey Return
		fi
		# a remaining pre-game prompt (cycle-131 clonk chooser) is accepted with
		# Down+Return — only if the game did not start on its own
		if ! wait_log_new "Game started" 45; then
			log "no 'Game started.' yet; accepting possible pre-game prompt (Down+Return)"
			xkey Down
			xkey Return
			wait_log_new "Game started" 30 || log "GAP 'Game started.' not seen after prompt accept"
		fi
		wait_log_new "Player join: " 30 || log "GAP 'Player join: ' not seen"
		if wait_log_new "Player join: " 1; then ingame=1; fi
		sleep 10
		park_mouse
		shot 07-in-game.png
	else
		log "FAIL: [World Settings] not clickable — settings stage unreachable"
		RES_REFILL_OK[$label]=1
	fi

	# --- per-resolution gates ------------------------------------------------------
	local shots=0 s no_skip=1 join_ok=0 started_ok=0 errs=0
	for s in 01-main-menu 02-scenario-selection 03-landing 04-round-tab 05-store-before 06-store-after 07-in-game; do
		[ -s "$CUR_DIR/$s.png" ] && shots=$((shots+1))
	done
	grep -q "PreGame: skipping options dialog" "$CUR_LOG" 2>/dev/null && no_skip=0
	grep -q "Player join: " "$CUR_LOG" 2>/dev/null && join_ok=1
	grep -q "Game started\." "$CUR_LOG" 2>/dev/null && started_ok=1
	errs="$(grep -cE '\[error\].*(Script\.c|C4Aul|AulExec)' "$CUR_LOG" 2>/dev/null)"
	[ -z "$errs" ] && errs=0

	local res_fail=0 reasons=""
	[ "$shots" = 7 ] || { res_fail=1; reasons="${reasons}shots ${shots}/7; "; }
	[ "$no_skip" = 1 ] || { res_fail=1; reasons="${reasons}PreGame-skip present; "; }
	[ "$join_ok" = 1 ] || { res_fail=1; reasons="${reasons}no 'Player join: '; "; }
	[ "$started_ok" = 1 ] || { res_fail=1; reasons="${reasons}no 'Game started.'; "; }
	[ "$errs" = 0 ] || { res_fail=1; reasons="${reasons}${errs} scenario-script [error]s; "; }
	[ "$reached_settings" = 1 ] || { res_fail=1; reasons="${reasons}settings stage unreachable; "; }
	[ "$reached_store" = 1 ] || { res_fail=1; reasons="${reasons}Store tab unreachable; "; }
	[ "$ingame" = 1 ] || { res_fail=1; reasons="${reasons}not in-game; "; }
	if [ "${RES_REFILL_OK[$label]:-1}" = 0 ]; then
		reasons="${reasons}refill pair differs; "
	else
		# 1080p must prove the refill (plan: "refill must succeed at 1080p");
		# a 720p shortfall becomes a GAP in the overall verdict
		if [ "$label" = 1080p ]; then
			res_fail=1
			reasons="${reasons}refill pair byte-identical; "
		else
			reasons="${reasons}refill pair byte-identical (GAP candidate); "
		fi
	fi

	if [ "$res_fail" = 1 ]; then
		RES_STATUS[$label]="FAIL"
		VERDICT_LINES+=("$label: FAIL — ${reasons%; }")
	else
		RES_STATUS[$label]="PASS"
		VERDICT_LINES+=("$label: PASS — ${reasons%; }")
	fi

	log "==== $label walk finished ===="
	# park the engine so only one engine runs at a time (next leg spawns its own)
	kill_clonk
	local p
	for p in "${XVFB_PIDS[@]}"; do kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null; done
	XVFB_PIDS=()
	return 0
}

# cmp gate for the Store before/after pair.
# returns: 0 = pair differs; 1 = identical; 2 = a shot is missing
store_pair_differs()
{
	local before="$CUR_DIR/05-store-before.png" after="$CUR_DIR/06-store-after.png"
	[ -s "$before" ] && [ -s "$after" ] || return 2
	if cmp -s "$before" "$after"; then
		return 1
	fi
	return 0
}

# --- verdict ---------------------------------------------------------------------------
write_verdict()
{
	local overall="" line
	local anyfail=0 anygap=0

	# 720p refill nuance: a byte-identical 720p pair is a reportable GAP when
	# 1080p proved the refill; if 1080p also failed, the walk FAILs.
	if [ "${RES_REFILL_OK[720p]:-1}" = 1 ] && [ "${RES_REFILL_OK[1080p]:-1}" = 0 ]; then
		VERDICT_LINES+=("720p GAP: refill pair byte-identical; 1080p proved the refill")
	fi
	if [ "${RES_REFILL_OK[1080p]:-1}" = 1 ]; then
		anyfail=1
	fi
	if [ "${RES_STATUS[1080p]:-FAIL}" = "FAIL" ] || [ "${RES_STATUS[720p]:-FAIL}" = "FAIL" ]; then
		anyfail=1
	fi

	for line in "${VERDICT_LINES[@]:-}"; do
		case "$line" in
			*" GAP: "*) anygap=1 ;;
		esac
	done

	if [ "$anyfail" = 1 ]; then
		overall="FAIL"
	elif [ "$anygap" = 1 ]; then
		overall="PASS-WITH-GAPS"
	else
		overall="PASS"
	fi

	{
		echo "# real-playtest-walk verdict (cycle 216)"
		echo "# gates per resolution: 7 stage shots; no 'PreGame: skipping options dialog';"
		echo "# 'Player join: ' + 'Game started.' after Start; Store refill pair differs; zero scenario-script [error]s"
		for line in "${VERDICT_LINES[@]:-}"; do
			[ -n "$line" ] && echo "$line"
		done
		echo "REAL-PLAYTEST-WALK: $overall"
	} > "$VERDICT"

	log "verdict written: $VERDICT"
	log "REAL-PLAYTEST-WALK: $overall"
	[ "$overall" = "FAIL" ] && return 1
	return 0
}

# --- main ---------------------------------------------------------------------------------
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

	mkdir -p "$EVID" "$EVID/tmp" "$PLAYTEST"
	rm -f "$VERDICT"
	backup_players

	KEY_DELAY=0.8
	run_res 1080p 1920 1080 :96
	drop_walk_players

	KEY_DELAY=1.6
	run_res 720p 1280 720 :97

	write_verdict || exit 1
	exit 0
}

main "$@"
