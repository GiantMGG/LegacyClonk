# Simulation perf-budget charter

Status: ACTIVE since cycle 118 (`sim-performance-budget`, 2026-09-12).
Scope: every LegacyClonk simulation perf gate (`pxs_perf_gate`,
`mobilization_perf_gate`) and the headroom analyses the Epic-10 L cycles
(`liquid-body-dynamics` ~121, then `dirty-chunk-tracking`,
`instability-driven-mobilization`, `per-cell-state`) inherit.

## 1. MinSpec-A — the declared reference machine

Declared BEFORE any new measurement (Epic-10 council blind spot 5;
roadmap item `sim-performance-budget`, staked cycle 118):

> **MinSpec-A** = a single-thread x86-64 performance class ≈ *Intel
> Skylake-class 2C/4T, ~2.5 GHz sustained, Passmark single-thread ≈
> 2000–2200* (exemplars: i5-6300U, i3-6100).

Why this class:

1. It is the 90th-percentile "potato" CPU of the plausible audience —
   slower machines exist but are not the design target.
2. Its ST class ≈ the slowest GitHub-hosted runner generation observed
   (EPYC 7763, Passmark-ST p50 ≈ 2269; Runs-on data, Sep 2026), so CI
   numbers are a fair stand-in for MinSpec-A ± 25%.
3. It is falsifiable — anyone with a MinSpec-A-class CPU can run
   `ctest -R "pxs_perf_gate|mobilization_perf_gate"` and compare the
   `[CAL]` lines against §3 of this charter.

**Hosted runners are measurement vehicles, not reference machines.**
GitHub-hosted `ubuntu-24.04 x64` spans Passmark-ST p50 ≈ 2269–3382
across Azure generations, and identical-commit A/B ratios wander
0.51–1.36 (std 0.05) over a 16-day window (Quansight study). A
hosted-runner number is interpreted against MinSpec-A through §2's
slack, never taken as the reference itself.

**Calibration machine** (the de facto secondary reference): the
maintainer workstation that produced the cycle-88 `GATE_WINDOW_MS =
1500` calibration and this charter's §3 baselines. `[CAL]` comparisons
against it are exact; against MinSpec-A they carry the ± 25% band above.

## 2. Gate-constant re-derivation

- Tick budget: 28 ms/tick (`defaultIngameGameTickDelay = 28`,
  `src/C4Game.cpp:188`).
- Window: 35 ticks/window (the frozen-constants contract, cycle 88).
- CI slack: 1.53 — derived from the runner-variance data in §1, not
  guessed: the hosted-runner worst observed identical-commit A/B ratio
  is ≈ 1.36; the slack covers it plus the 2-strike absorption margin.

  **GATE_WINDOW_MS = 35 × 28 × 1.53 ≈ 1500 ms/window**
  (allows ≈ 42.9 ms/tick sustained before the 2-strike fires).

- Pacing: `--frame-rate-cap 1000` lifts the 28 ms/tick pace
  (`ResetTimer(1000/FrameRateCap)`, `src/C4Game.cpp:2963-2965`), so
  per-window wall-clock reflects simulation cost (cycle-64 option).
  Under the cap the pacing contributes ~35 ms of the 1500 ms budget —
  absorbed by the slack.
- 2-strike: a single-window breach is absorbed; a SECOND consecutive
  breach window fails. Observed transient magnitude (std 0.05,
  Quansight) sits inside this envelope.

## 3. Measured baselines (calibration machine)

Populated by the cycle-118 calibration (Task 3 of the cycle-118 plan):
per-window `[CAL] mob win` / `[CAL] mob static` transcriptions from the
three calibration runs and the ×2-churn negative-mutation run (the cost
model's second dwell level), plus the PXSPerfSmoke cross-reference.
This is the per-path regression baseline the L cycle inherits.

## 4. Cost-slope model and [HEADROOM] projection

Populated together with §3 (two dwell levels: baseline + ×2-churn
mutation). Stated as a **bound, not a prophecy**: the gates (not this
projection) are the enforcement; the L recomputes before trusting.

## 5. Dirty-chunk conclusion

Today's 10k PXS + 10k mass-mover caps sit AT the amortized scan floor:

- PXS: all 20 × 500 = 10 000 slots are walked every tick
  (`C4PXSSystem::Execute`, `src/C4PXS.cpp:243-269`; empty chunks freed).
- Mass movers: the whole 10 000-entry set is walked TWICE per tick
  regardless of mover count (`C4MassMoverSet::Execute`,
  `src/C4MassMover.cpp:50-65` — the `for (speed = 2; speed > 0; ...)`
  two-speed loop).

Cap inflation therefore buys nothing: the full-array scans ARE the
floor, and doubling the caps doubles the floor. L-scope physics must
ride the **dirty-chunk lever** (Noita's model: cost ∝ dirty cells,
bounded by chunk skips — GDC "Falling Everything", Purho 2019), not cap
inflation. This is the architectural conclusion the
`dirty-chunk-tracking` cycle lands.

## 6. Instrument gap (the L's missing instrument)

No `MassMover.Count` script getter exists (verified cycle 118: grep
`GetMassMoverCount` → no matches; `C4MassMoverSet::Count` is
engine-internal, `src/C4MassMover.cpp:53`). Until the L adds it, mover
activity is inferred via `GetMaterialCount` static-count deltas (the
`[CAL] mob static W=… S=…` lines) and the per-window churn counters.
