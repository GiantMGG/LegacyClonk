#!/bin/bash
# run_repro_matrix.sh — Epic-9 pin matrix (cycle 94: the 7 promotions).
# The matrix now drives the promoted smokes at --smoke-run 350, same
# as the CTest glob (the local-loop twin of the 7 smoke_* entries).
# Prints one GREEN/RED line per scenario.
set -u
LC="$(cd "$(dirname "$0")/.." && pwd)"     # LegacyClonk root
CONTENT="$LC/../content"
BUILD="${1:-$LC/build}"
mkdir -p /tmp/opencode
declare -A REPRO=(
  [PaintGapSmoke]="$CONTENT/PixelPhysics.c4d/Tests.c4f/PaintGapSmoke.c4s"
  [OilImmobileSmoke]="$CONTENT/PixelPhysics.c4d/Tests.c4f/OilImmobileSmoke.c4s"
  [LavaWallSmoke]="$CONTENT/PixelPhysics.c4d/Tests.c4f/LavaWallSmoke.c4s"
  [SandFlowSmoke]="$CONTENT/PixelPhysics.c4d/Tests.c4f/SandFlowSmoke.c4s"
  [LateralChannelSmoke]="$CONTENT/PixelPhysics.c4d/Tests.c4f/LateralChannelSmoke.c4s"
  [ScorpionStagingSmoke]="$CONTENT/Desert.c4d/Tests.c4f/ScorpionStagingSmoke.c4s"
  [FeuerstaudammMirrorSmoke]="$CONTENT/Missions.c4f/Tests.c4f/FeuerstaudammMirrorSmoke.c4s"
)
for name in PaintGapSmoke OilImmobileSmoke LavaWallSmoke SandFlowSmoke \
            LateralChannelSmoke ScorpionStagingSmoke FeuerstaudammMirrorSmoke; do
  path="${REPRO[$name]}"
  log="/tmp/opencode/${name}.log"
  (cd "$BUILD" && ./clonk --console --smoke-run 350 -s "$path") > "$log" 2>&1
  if grep -q "${name} PASS" "$log"; then verdict=GREEN
  elif grep -q "FAIL:" "$log"; then verdict=RED
  else verdict="NO-RUN"; fi
  printf '%-26s %s\n' "$name" "$verdict"
done
