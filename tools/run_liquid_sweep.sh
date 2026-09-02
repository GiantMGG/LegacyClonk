#!/bin/bash
# run_liquid_sweep.sh — cycle-92 liquid dig-delay sweep (spec
# 2026-09-02-0258-liquid-flow-hotfix, Phase A). Generates per-cell delay
# variants of the 3 basin repros in-tree (g_fCalibrate=1), runs them under
# --frame-rate-cap 1000, and prints one verdict line per cell.
# Usage: run_liquid_sweep.sh [build-dir] [delay ...]
# Default delays: 35 350 3500. Add 7000 only if D3500 stays GREEN.
# F-1 anomaly: timer FatalError exits 0 — verdicts come from log greps.
set -u
LC="$(cd "$(dirname "$0")/.." && pwd)"
CONTENT="$LC/../content"
TCD="$CONTENT/PixelPhysics.c4d/Tests.c4f"
BUILD="${1:-$LC/build}"
[ $# -gt 0 ] && shift
DELAYS=("$@")
[ ${#DELAYS[@]} -gt 0 ] || DELAYS=(35 350 3500)
OUT="/tmp/opencode"
mkdir -p "$OUT"

GENERATED=()
cleanup() { for d in ${GENERATED[@]+"${GENERATED[@]}"}; do rm -rf "$d"; done; }
trap cleanup EXIT

declare -A REPRO=(
  [Water]=PaintGapSmoke
  [Oil]=OilImmobileSmoke
  [Lava]=LavaWallSmoke
)

printf '%-7s %7s %9s %8s %7s %6s\n' liquid delay smoke_run verdict drain famB
for liquid in Water Oil Lava; do
  base="${REPRO[$liquid]}"
  for delay in "${DELAYS[@]}"; do
    variant="${base}D${delay}"
    vdir="$TCD/${variant}.c4s"
    GENERATED+=("$vdir")
    rm -rf "$vdir"
    cp -r "$TCD/${base}.c4s" "$vdir"
    sed -i "s/static const DigDelay = 35;/static const DigDelay = ${delay};/" "$vdir/Script.c"
    sed -i "s/g_fCalibrate = 0;/g_fCalibrate = 1;/" "$vdir/Script.c"
    sed -i "s/^Title=.*/Title=${variant}/" "$vdir/Scenario.txt"
    sed -i "s/^Origin=.*/Origin=PixelPhysics.c4d\\\\Tests.c4f\\\\${variant}.c4s/" "$vdir/Scenario.txt"
    log="$OUT/${variant}.log"
    smoke_run=$((delay + 400))
    (cd "$BUILD" && ./clonk --console --smoke-run "$smoke_run" \
      --frame-rate-cap 1000 -s "$vdir") > "$log" 2>&1
    last_cal="$(grep '\[CAL\]' "$log" | tail -1)"
    drain="$(sed -n 's/.*drain \(-\?[0-9]*\).*/\1/p' <<<"$last_cal")"
    famb="$(sed -n 's/.*famB \(-\?[0-9]*\).*/\1/p' <<<"$last_cal")"
    if grep -q 'FAIL:' "$log"; then verdict=RED
    elif [ -z "$drain" ]; then verdict=NO-RUN
    elif [ "$drain" -lt 20 ]; then verdict=RED
    else verdict=GREEN
    fi
    printf '%-7s %7d %9d %8s %7s %6s\n' \
      "$liquid" "$delay" "$smoke_run" "$verdict" "${drain:--1}" "${famb:--1}"
  done
done
