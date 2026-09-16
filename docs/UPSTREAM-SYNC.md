# Upstream sync policy

How the GiantMGG fork relates to `legacyclonk/LegacyClonk` upstream: what we
ingest, what we push back, how release numbers coexist, and who reviews what.
Status: adopted policy (cycle 129, 2026-09-16); revisited at every intake.

## Players

Nothing in this policy changes gameplay. It exists so that engine work can
flow between the fork and upstream without losing fork features, breaking
releases, or surprising the itch.io/AUR/forum audience with colliding
version numbers.

## Code ingestion rules (fork ← upstream)

- Upstream PRs of substance (migrations, refactors, platform ports) are
  triaged before merge: a local `--no-commit` merge on a throwaway branch,
  the fork's full battery + ASan subset + harness-surface probes, and a
  validated verdict. Verdict grammar: `MERGE-READY | MERGE-READY-WITH-FIXES
  | MERGE-BLOCKED | TRIAGE-INCOMPLETE`; the SDL drift mapper is
  `tools/sdl_api_drift.py`.
- Cherry-picks and squash-merges carry a provenance trailer, because
  upstream force-pushes `master` and bare SHAs are unstable:

  `Upstream: legacyclonk/LegacyClonk#<PR>, snapshot <sha>`

  Always record the PR-number + snapshot-SHA pair; never cite a bare
  upstream SHA as provenance.
- During intake triage, conflict resolution may only DELETE fork-side code
  or MECHANICALLY rename SDL2 symbols to their SDL3 equivalents. Anything
  requiring real porting work is an intake gap: listed, never invented
  mid-triage.
- Every deletion of fork-side code is a fork-parity-loss candidate (R1 in
  the triage taxonomy) and must appear in the verdict's regression list.

## Upstreaming rules (fork → upstream)

- Fork commits headed upstream go as PRs with clean, focused diffs — no
  fork-only `#ifdef` walls, no drive-by refactors.
- A PR merged upstream from fork work carries the mirror provenance (fork
  commit range in the PR description).
- Content (definition packs, scenarios, planet groups) is NOT synced with
  upstream — our content line has diverged permanently; see below.

## Content divergence

The fork's content repos (`content/`, `content-community/`) evolve
independently of upstream. No content sync, no content provenance
requirements. Content releases ride the fork's own version sequence.

## Numbering-collision protocol

Two `vNNN` namespaces exist: the fork's tags (v358…v369+ on GiantMGG) and
upstream's tags (v358…v365+ on legacyclonk; two upstream releases within 12
days in Aug 2026 made this acute). Protocol:

1. The fork's integer sequence is authoritative and leading (next: v370).
2. Upstream tags are a separate namespace, never adopted, never renumbered.
3. Disambiguation is by repo + date, never by number alone.
4. The engine version number (`C4XVER1..4` + build) is the exchange unit
   between the two lines — bump it in lockstep with fork tags and cite it
   in every cross-repo conversation.

## Sync-review process

An intake cycle produces a drift map, an A/B battery diff, an ASan subset
diff, a harness-surface ledger, and a validated verdict. The merge-gate
reviewer reads the verdict post-L and owns the merge/no-merge call.
Regression classes: R1 fork-parity loss · R2 engine/logic regression ·
R3 input/event regression · R4 video/window regression · R5 audio
regression · R6 harness-surface-only artifact · PRE pre-existing/flake.
Probe results are recorded as `PASS / REGRESSION(class) / ENV-LIMITED` —
never a bare "fine", never silently rounded.

## Divergence ledger (human-maintained; seeded cycle 129)

Known fork-divergence surfaces vs upstream, updated per intake cycle:

- **Audio backend** (`src/C4AudioSystemSdl.cpp`): the fork carries its own
  SDL2_mixer implementation with a linear-resampling hint, an MP3 layer-3
  header guard, and a clipping-safe volume cap. Upstream PR #150 replaces
  the whole backend with SDL3_mixer; parity of these three features is
  intake-gated.
- **gamecontrollerdb** (`src/C4GamePadCon.cpp`): the fork loads
  `gamecontrollerdb.txt` via `SDL_GameControllerAddMappingsFromFile`; the
  SDL3 migration path is `SDL_AddGamepadMappingsFromFile`.
- **Keymap surface** (`src/C4Config.cpp` + keymap arrays): the default
  keyboard tables use SDL2 `SDL_SCANCODE_*` names that must be audited
  against SDL3's scancode set on migration.

## v370 release-notes relationship statement

The v370 release notes will include, verbatim:

> This release continues the LegacyClonk fork line maintained under
> GiantMGG. It shares heritage with the upstream legacyclonk project but
> is developed and released independently; release numbers of the two
> lines are unrelated even when numerically similar. The engine version
> number reported by the binary is the authoritative identifier for
> support and compatibility questions.
