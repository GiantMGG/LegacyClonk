#!/bin/bash
# run_repro_matrix.sh — cycle-90 six-symptom repro matrix (spec
# pixel-physics-repro-diagnose). Prints one GREEN/RED line per symptom.
# Usage: LegacyClonk/tools/run_repro_matrix.sh [build-dir]
set -u
LC="$(cd "$(dirname "$0")/.." && pwd)"     # LegacyClonk root
CONTENT="$LC/../content"
BUILD="${1:-$LC/build}"
mkdir -p /tmp/opencode
declare -A REPRO=(
  [PaintGapRepro]="$CONTENT/PixelPhysics.c4d/Tests.c4f/PaintGapRepro.c4s"
  [OilImmobileRepro]="$CONTENT/PixelPhysics.c4d/Tests.c4f/OilImmobileRepro.c4s"
  [LavaWallRepro]="$CONTENT/PixelPhysics.c4d/Tests.c4f/LavaWallRepro.c4s"
  [SandFlowRepro]="$CONTENT/PixelPhysics.c4d/Tests.c4f/SandFlowRepro.c4s"
  [ScorpionStagingRepro]="$CONTENT/Desert.c4d/Tests.c4f/ScorpionStagingRepro.c4s"
  [FeuerstaudammMirrorRepro]="$CONTENT/Missions.c4f/Tests.c4f/FeuerstaudammMirrorRepro.c4s"
)
for name in PaintGapRepro OilImmobileRepro LavaWallRepro SandFlowRepro \
            ScorpionStagingRepro FeuerstaudammMirrorRepro; do
  path="${REPRO[$name]}"
  log="/tmp/opencode/${name}.log"
  (cd "$BUILD" && ./clonk --console --smoke-run 350 -s "$path") > "$log" 2>&1
  if grep -q "${name} PASS" "$log"; then verdict=GREEN
  elif grep -q "FAIL:" "$log"; then verdict=RED
  else verdict="NO-RUN"; fi
  printf '%-26s %s\n' "$name" "$verdict"
done
