# Changelog

All notable changes to LegacyClonk are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [366] - 2026-09-01

### Added

- **tests**: Wire CMakeLists.txt helper to real CTest targets (a530862)

- **ci**: Harden Test step with --no-tests=error and JUnit output (c9c72ed)

- **tests**: Add C4Fixed unit tests (cohorts A/D/E) (f3fdadd)

- **menu**: Generic rule-injection extension point in AddContextFunctions (3aaeafb)

- **tests**: Add C4NetIO wire-format and fragmentation unit tests (f37a811)

- **build**: Modernize toolchain — CMake 4.0 floor, opt-in C++26, CI smoke lane (57542b0)

- **docs**: Add read-only harvest script for C4Script reference (4e9f5d3)

- **Input**: Add string IDs for bindings tab (bb47cff)

- **Input**: Add EN/DE string values for bindings tab (59502e8)

- **Input**: Add key rebinding API to C4KeyboardInput (d184cde)

- **Input**: Add fAnyKey mode to KeySelDialog (a669cd9)

- **Input**: Add BindingsTab UI for key rebinding (4ab2a86)

- **Input**: Add Bindings sheet to Options dialog (1262d6d)

- **Input**: Persist custom key config on SaveConfig (2b9ce25)

- **Input**: Load gamecontrollerdb.txt mapping DB (dcd7509)

- **Input**: Add gamecontrollerdb.txt mapping DB (2d83e01)

- **Weather**: Add C4SEventEntry and C4SEvents to C4Scenario.h (1834874)

- **Weather**: Implement C4SEvents methods and wire [WeatherEvents] block (bf9082b)

- **Weather**: Add weather-event state and method declarations to C4Weather.h (c77b8be)

- **Weather**: Implement weather-event scheduling and lifecycle in C4Weather.cpp (34e3aff)

- **Weather**: Add five new C4Script APIs for weather events (e3bea90)

- **Replay**: Add C4Playback::GetTotalFrames for replay scrub controller (a51fe22)

- **Replay**: Add C4ReplayController state machine for replay scrubbing (48fba94)

- **Replay**: Wire C4ReplayController into C4GameControl and CMake (38cd3e8)

- **Replay**: Add pause/speed hooks to C4Game tick loop (e64e3e3)

- **Replay**: Add ReplaySpeedMultiplier config field (383f808)

- **Replay**: Add C4StartupReplaySelDlg replay browser dialog (8d6c477)

- **Replay**: Add C4ReplayViewerDlg in-game scrub viewer overlay (79fc640)

- **onboarding**: Add welcome-dialog 'Read the 5-minute quickstart' button (b49e464)

- **engine**: Add SmokeRunTicks field + SmokeRunActive() accessor on C4Game (69871d6)

- **engine**: Parse --smoke-run <N> flag in C4Game::ParseCommandLine (d70e3a9)

- **engine**: Add smoke-exit check in C4Game::Execute after GameOverCheck (9e4d817)

- **ci**: Add FreeBSD 14.2 console-only CI lane (bsd.yml) (3aff6a4)

- **ci**: Add OpenBSD 7.9 best-effort lane to bsd.yml (3a79c54)

- **Preservation**: Scaffold import_ccan.py skeleton (8c98028)

- **Preservation**: Manifest loading + verify-manifest subcommand (569b720)

- **Preservation**: CCAN metadata HTML parser (9aa8865)

- **Preservation**: HTTP fetch with rate limit + retry (1b39777)

- **Preservation**: Unpack step with extension dispatch (5f70047)

- **Preservation**: Normalize step (COPYING/ATTRIBUTION.txt/ChangesLE.txt) (e7eb746)

- **Preservation**: Validate step (c4group -l integrity probe) (93af630)

- **Preservation**: Idempotency check + rollback (9da608d)

- **Preservation**: Wire import subcommand end-to-end (faf51d2)

- **Preservation**: List subcommand + --rate-limit arg (c048548)

- **Preservation**: Curated CCAN manifest with canary entry (f0efee9)

- **Preservation**: Vendored sample fixture for offline tests (8a52adb)

- **Rollback**: Scaffold C4Rollback module and test_C4Rollback target (9571a3e)

- **Rollback**: Add Config.Network.RollbackEnabled + tuning knobs (d1c7aa8)

- **Rollback**: Wire C4Rollback member into C4GameControl (df27a7a)

- **Rollback**: Add C4GameSave SaveRuntimeDataToBuffer/LoadRuntimeDataFromBuffer (0cca804)

- **Rollback**: Implement TakeSnapshot/RestoreSnapshot/RollbackToTick (d3b7483)

- **Rollback**: Add divergence check in HandleControl (1dcc979)

- **Rollback**: Implement LoadRuntimeDataFromBuffer in-place restore (e654ed2)

- **Rollback**: Expose RollbackSaveState/RollbackLoadState to C4Script (5eb7781)

- **launcher**: Add cross-platform launcher script (f4ee718)

- **CCAN**: Add SmokeConfig + requires/smoke fields to ManifestEntry (e172627)

- **CCAN**: Parse requires + smoke subtable in load_manifest (ffc8d7b)

- **CCAN**: Add resolve_requires with cycle detection (f640559)

- **CCAN**: Add emit_smoke_artefacts for tier-A marker + tier-B smoke (c8d909e)

- **CCAN**: Wire resolve_requires + emit_smoke_artefacts into _import_one (485fd36)

- **CCAN**: Declare requires + smoke subtable for Hazard 3D entry (8de408a)

- **CCAN**: Add CMake wiring for CCAN smoke gate (tier A + tier B) (eef02ce)

- **Networking**: Add per-tick state-hash comparison to desync smoke (8afa48e)

- **tools**: Add citation freshness linter + unit tests (0c86421)

- **game**: Add --frame-rate-cap N flag to pace headless loop (c04042c)

- **CCAN**: Add Phase 1 raw-mirror tier (mirror_ccan.py + ccan_index.py) (38bd156)

- **CCAN**: Add Phase 2 license-triage discover subcommand (6ca4b60)

- **CCAN**: Add Phase 3 bulk-import + master ATTRIBUTION.toml index (b3ed2dd)

- **CCAN**: Add Phase 4 verify-imports upstream-change detection (be3960c)

- **Networking**: Add /bind-address flag to filter advertised client addresses (93a8315)

- **Networking**: Client-side reconnect initiation (token store, re-dial, PID_Reconn) (c61829c)

- **material**: Add Buoyancy field for rising PXS gases (57693a5)

- **material**: Add React reaction type for two-product pixel reactions (690c33d)

- **script**: Add GetPXSCount() engine function (2b34c90)

- **tools**: Extend citation gate to .md/.txt citations (d5f1a1c)

- **reconnect**: Re-send IPID_Close to dormant clients (QUIC closing state) (3efbf6c)

- **materials**: Add Saltation field and supported-PXS hop branch (3794e2e)

- **docs-gate**: Add citation content expectations ledger (24978c3)

- **game**: Apply --parameter Key=Value overrides after scenario load (1d50bdc)

- **gui**: Add offline pre-game options dialog (deb0267)


### Changed

- **Preservation**: Apply auto_format to new Python files (9850446)

- **Rollback**: Befriend C4GameSave for in-place restore access (7c4c2cd)

- **CCAN**: Normalize new function indentation to 4-space (auto_format) (fdaa413)

- Collapse double blank lines (auto-format dirt pass) (82bf1ec)

- **pxs**: Hoist Saltation map read; fix stale test header comment (baa47e3)

- **docs-gate**: Extract shared orphan_failures helper (review M1) (d9cf1cd)

- Apply auto_format dirt pass (wave 2) (b667bb7)


### Fixed

- Add missing includes to C4Fonts.cpp for PCH-disabled builds (fbd909e)

- Replace std::size_t with uint32_t in C4Aul.cpp for portability (b3e46ab)

- Add missing includes to 8 files for PCH-disabled builds (55c9173)

- **build**: Resolve source bugs blocking console build (DefaultBounds, InitGameSecondPart, SectionGLCtx gating, C4Startup friend) (c27f83c)

- **docs**: Address review findings (H-1/H-2/M-1/M-2/M-3/M-4) (f4ee784)

- **tests**: Address review findings (H-1/M-1/M-2/M-3) (d65914f)

- **Input**: Address review findings (H-1/H-2/M-1) (7f7bc23)

- **Weather**: Address review findings (H-1/M-1/L-1/L-3) (58ab7e3)

- **Replay**: Address review findings (H-1/H-2/M-1/M-2/M-3) (33381b1)

- **engine**: Honour fQuitWithError + fatal stack in C4WinMain exit code (e4b9095)

- **port**: Broaden __linux__ engine guards for FreeBSD/OpenBSD (d2bc9be)

- **port**: Link -lexecinfo on FreeBSD for backtrace()/backtrace_symbols_fd() (58e33f8)

- **console**: Stop polling stdin on EOF instead of failing the run loop (cc1eca4)

- **net**: Make IPv6 loopback test portable (H-1) (6cbea5d)

- **test**: Symlink content packs into build dir for smoke runs (H-1) (6e1df27)

- **Preservation**: Align meta.html fixture with expected ATTRIBUTION.txt (8cbe1ff)

- **Preservation**: Address review findings (H-1/M-1/M-2) (ea236c4)

- **Rollback**: Address review findings (3643f7d)

- **StdAdaptors**: Use std::format placeholder in unknown-value-name Warn (ecc403a)

- **Rollback**: Make SaveRuntimeDataToBuffer produce non-empty savegames (a9c4489)

- **Rollback**: Address review findings (d504079)

- **airships**: Address review findings (a6389d9)

- **launcher**: Address review findings (ba4c9e8)

- **C4File**: Clear errno before std::rewind to avoid false failures (56f154b)

- **net-smoke**: Pass player file to peers and wait for ref registration (3656305)

- **net-smoke**: Prevent sudo tc hang by closing stdin (d62ab46)

- **Tutorials**: Address review findings (ad6cd30)

- **content**: Replace stub Graphics.png files with valid 64x64 transparent PNGs (9fa9510)

- **tests**: Discover smoke scenarios at nested depths (66865bb)

- **Save Games**: Re-init landscape after rollback load for second round-trip (1d2863b)

- **tools**: Remove stale file references from auto_format.py (6a60fd5)

- Add missing includes for PCH-off build (unblocks ASan lane) (3f5d6a1)

- **CCAN**: Escape TOML strings in discovered manifest + master index (294ab53)

- **C4NetIO**: Replace misaligned uint32_t stores with std::memcpy (1456eae)

- **C4Record**: Close #pragma pack after C4RecordChunkHead (314e91b)

- **C4GameControl**: Add IsInitComplete getter, guard harness Execute() (213d8ae)

- **tests**: Replace misaligned uint32_t in TstC4NetIO, add alignof guard (e9a0f70)

- **value**: Sign-extend deserialized 32-bit values in CompileFunc (e008b3a)

- **live-smoke**: Raise marker-timeout and grace-sec defaults for the paced reconnect cycle (7e91f3e)

- **fixtures**: Keep NetSyncSmoke alive to the smoke bound with a script observer player (6eeae92)

- **app**: Make --frame-rate-cap actually pace solo and networked smoke loops (a2ce5df)

- **app**: Ignore SIGPIPE so peer-closed sockets return EPIPE instead of killing the engine (4bca88c)

- **Networking**: Complete the reconnect handshake end-to-end (7c91d46)

- **upnp**: Demote port-mapping failure to warning (a8488bc)

- **live-smoke**: Intersection SyncCheck comparison and critical-level fatal markers (386eedf)

- **Networking**: Gate client reconnect on Reconnect.IsEnabled() (1bacf47)

- **live-smoke**: Guard against vacuous SyncCheck intersection pass (9b2970f)

- **game**: Keep playerless smoke scenarios running to the smoke-run cap (0045a3a)

- **material**: Correct React/Incinerate contact-cell semantics (8a2b5a4)

- **buf**: Guard zero-size Compare against null-pointer memcmp (UBSan) (90664ef)

- **C4Aul**: Replace empty-Code clamp in Parse_Function with explicit nullptr path (ff87738)

- **tools**: Make deps-lock.sh awk regex portable across mawk and gawk (1f52f98)

- **src**: Reformat TODO markers to satisfy the lint format (674bc67)

- **todo-lint**: Re-pin 2 allowlist entries shifted by format sweep (eadfabe)

- **math**: Define itofix overflow wrap via unsigned multiply (f930a54)

- **particles**: Wrap smoke color decay in unsigned domain (0d8dbad)

- **playerinfo**: Drop dead force-specialize statement (70b8b72)

- **mapgen**: Close residual signed-add UB window in turbulence LCG (50c7804)

- **game**: NUL-terminate --parameter key substring in AddParameterOverride (5ecacc5)

- **game**: Skip --parameter overrides during replay playback (929b090)

- **ci**: Test-target scan race + GUI-config compile + headless guards (ce6dfa0)

- **ci**: Test-target scan race + GUI-config compile + headless guards (0fafd3c)

- **gui**: Add missing C4GuiDialogs.h includes for non-PCH builds (dec5b41)

- **portability**: Netinet/in.h include + C4ID serialization adaptor (a0880ee)

- **Weather**: Wrap ActiveEventID in mkC4IDAdapt for LLP64/Apple targets (72f37bf)

- **tests**: Windows test-link gaps + missing <bit> include (9b3bc7b)

- **ci**: Mac app bundle + Windows string_view link gap (0c7a5eb)

- **tests**: Initialize Winsock + skip IPv6 loopback tests when unavailable (e9b7bbf)

- **ci**: Guard pxs_perf_gate on scenario existence (contentless CI checkouts) (2acd927)

- **release**: Write git-cliff digest via --output (action has no output input) (0ac67d0)

- **docs**: Replace removed mike set-alias with alias command (mike 2.x) (4b84c2a)

- **release**: Fall back to default token for public content checkout (9bfd757)


### Internal

- **modder-docs**: Add MkDocs Material modder docs site (19e327e)

- Add clonk_engine static library for test linking (bc1943e)

- Add LINK_ENGINE flag to add_test_target and register new tests (2ffe03b)

- Add C4Value coercion matrix unit tests (f8ece2e)

- Add C4Aul parser bytecode generation unit tests (9945cc1)

- **Weather**: Add C4WeatherEvents unit tests and wire into CMake (a26519c)

- **Replay**: Add C4ReplayController Catch2 unit tests (12 cases) (ee503e5)

- **onboarding**: Write 5-minute first-game guide for Colony Bay (ad52a54)

- **onboarding**: Add docs/players/img placeholder directory (b79a3cf)

- **onboarding**: Wire mkdocs.yml for player guide (7857411)

- **onboarding**: Pin mkdocs-glightbox==0.4.0 (97ef602)

- **onboarding**: Add README first-game links (b232f3e)

- **onboarding**: Fix README section ordering (M-1) (8e37e76)

- **smoke**: Add CTest glob harness for *Smoke.c4s scenarios (665b065)

- **smoke**: Add Catch2 state-semantics tests for SmokeRunTicks (1b4a089)

- **port**: Add BSD_PORT.md, wire mkdocs nav, add README BSD note (3c87365)

- **Contributors**: Add engine architecture doc + Contributors nav (924d598)

- **net**: Add IPv6 loopback CI smoke test for C4NetIO (33ab8ba)

- **Preservation**: Pytest unit suite for import_ccan (4b6da99)

- **Preservation**: Offline integration test for import pipeline (1610920)

- **Rollback**: Add case 5 delay-based lockstep baseline (c219f6a)

- **Rollback**: Add Tier 1 cases 1-4 C4Rollback unit tests (357bfae)

- **Rollback**: Add Tier 1 cases 6-8, 9-13 harness skeletons (119f33c)

- **Rollback**: Add fake-fixture cases 6,7,9,10 for ring buffer mechanics (267bb1f)

- **Rollback**: Verify Tier 3 mutation tests all fail as expected (b488044)

- **Rollback**: Convert cases 11-13 to real assertions (65dfba7)

- **Contributors**: Add C4Aul deep dive page (1548b27)

- **Contributors**: Add network lockstep deep dive page (fcc67de)

- **Contributors**: Add rendering pipeline deep dive page (a63da02)

- **Contributors**: Replace reader's-guide sections with summary blocks (16bfde0)

- **nav**: Add three Contributors deep-dive nav entries (1f4a74a)

- Add C4RecordChunk binary round-trip characterization tests (ffc5f39)

- Add NetSyncSmoke.c4s fixture metadata and static map (f65eee7)

- Add NetSyncSmoke Script.c deterministic activity driver (64a0ade)

- Add net_desync_smoke.py network desync CI smoke orchestrator (36cd9a6)

- Register net_desync_smoke CTest entry (ec48ebe)

- Add rich GlowStone.c4d skeleton for modder tutorial (936d140)

- Declare g_initialized local in GlowStone skeleton Script.c (658ab66)

- Add modder quickstart tutorial + c4d-anatomy reference (a108b56)

- **Contributors**: Add contributing.md skeleton (67e4ba1)

- **Contributors**: Fill Phase 1+2 (source/deps, build) (ee82a46)

- **Contributors**: Fill Phase 3+4 (test suite, new Catch2 test) (75222df)

- **Contributors**: Fill Phase 5 + appendices (PR flow, CI, style, AGENTS.md) (900d41d)

- **Contributors**: Wire contributing.md into nav + cross-links (a93d910)

- Add launcher unit test gate (9541340)

- **Players**: Add controls reference page (8537064)

- **Players**: Wire controls reference into nav (f52c27f)

- **Players**: Cross-link controls reference from first-game guide (0c9dff8)

- **changelog**: Add git-cliff changelog generator with highlights fragment (da54a1c)

- **tools**: Seed citation-freshness allowlist (2adf577)

- **docs**: Add citation-freshness gate + pre-commit hook (b3f9464)

- Add cmake/Sanitizer.cmake with USE_SANITIZER option (ed049a8)

- Wire Sanitizer.cmake into CMakeLists.txt; gate LTO/PCH off under USE_SANITIZER (7859bb7)

- Add standalone asan.yml workflow (asan-pr + asan-nightly) and document USE_SANITIZER (b21761e)

- **Networking**: Add C4PacketReconn wire round-trip + reassociation log marker (fc71481)

- **Networking**: Add live_reconnect_smoke two-engine orchestrator (b345cd5)

- **Networking**: Make live_reconnect_smoke skip gracefully on environment limitations (80a2a9b)

- Add scenario authoring guide and worked-example skeleton (b6d595b)

- Fix scenario tutorial run command + SWORD→FLNT identifier (6102a13)

- **Contributors**: Add troubleshooting FAQ page (210ad12)

- **Contributors**: Fix README citation line in troubleshooting FAQ (69b5e4d)

- **repro**: Add SKIP exit code and configure-args passthrough to verify-repro.sh (ff9bf2a)

- **repro**: Rewrite repro-check workflow with record-baseline job and skip/mismatch mapping (9a9df6d)

- **deps**: Refresh [baseline.binaries] comment for record-baseline flow (1af76b1)

- **repro**: Grant actions read for diffoscope diagnostics and fix dispatch gating (9653808)

- **live-network**: Nightly + manual live network smoke lane (5247a03)

- **reference**: Document React per-event semantics and TargetSpec=All hazard (031740b)

- **docs**: Run the citation gate's own test suite in docs-harvest-tests (5e49e7a)

- **release**: Add cross-platform portable archives with SHA256SUMS manifest (ab972c3)

- **live-smoke**: Document the SIGSTOP fallback close-loss pathology (2cadaf1)

- **bsd**: Fix OpenBSD pkg_add list against the 7.9 package index (ed81c32)

- **bsd**: Build cmake 4 from source for FreeBSD (no cmake 4 package) (5aefa32)

- **format-lint**: Add auto_format dirt gate (2c4ec96)

- **blame**: Ignore auto-format sweep commits (2e81291)

- **options**: Add parameter_override_smoke over OptionsOverride.c4s (280ef4c)

- **version**: Bump content version to 4.9.11.3 for v366 (ed15d16)

- **release**: First fork release cut (v366) (943ec31)

- **options**: Apply RandomTeamCount before TeamDist in override test (f4602dd)

- **bsd**: Mark FreeBSD lane continue-on-error (base libc++ jthread gap) (1e1094a)

- **smoke**: Wire pxs_perf_gate CTest entry + ASan guard (cycle 88) (51484f2)

- **changelog**: Update for v366 [skip ci] (98f61c0)


### Other

- Make CPattern movable (9ebc496)

- Add C4LinkedListIterator (af3914a)

- Split C4Game into C4Section (9f80c07)

- Remove the concept of a main section (7f3f8e0)

- :GetSectionByIndex: Fix out of bounds read (cfd1cc4)

- Update ViewSection (8103974)

- Don't draw object messages in every section (860a7aa)

- Remove mainSection (2f51245)

- Also check the scenario file for materials (ba03391)

- Fix clearing the wrong object list in ClearPointers (1fef4cb)

- Fix section assignment on object creation (8f212a0)

- Add FnCreateScenarioSection (7a70882)

- Add FnMoveObjectToSection (852fe62)

- Add FnGetScenarioSectionCount, FnGetScenarioSectionByName, FnGetSection (7b4396a)

- Add sections to script contexts and make global effects section-local (aaa636e)

- Include forward declarations (db46493)

- Fix leftover references to Landscape (5bca917)

- Rename, fix and add section script functions (48a7b20)

- Don't do debug checks in all sections since some may have already been destroyed during game clearing (986ac8a)

- Refactor section initialization sequence, make FnCreateSection be able to create a section with an empty landscape from a map providing C4SLandscape initialization data (b0afb4f)

- Fix DEBUGREC build (871b040)

- Move GetViewSection out of the Win32-only block (5fb76d1)

- Fix GTK developer mode build (1aad48a)

- Use section numbers to uniquely identify sections and add FnRemoveSection (881dd77)

- Remove Section member (032e416)

- Use std::list for sections so that iterators aren't invalidated on script calls to CreateSection / RemoveSection (e344a21)

- Fix uninitialized usage of Relights (5409575)

- Pass a const reference instead of a pointer to a const object to EMMoveObject since the parameter is never nullptr anyway (6151a49)

- Fix desync due to uninitialized member variable (817db11)

- Make the FoW reducer / generator checks section aware (47be412)

- Fix Linux build errors (d2d388f)

- Use Empty{} as name for empty sections (b3877d9)

- Rework C4Texture and GroupReadSurface8 to use std::unique_ptr and std::vector (6d5ffeb)

- Add missing include (5466851)

- :Load: Remove unused parameter (44bff73)

- :LoadTextures: Remove unused parameter (e8275d3)

- Fix crash with an invalid map structure (39885ac)

- Reference the main section's materials and textures if the section doesn't have its own Material.c4g to improve memory usage and loading times (17478be)

- Remove unused dead code (4dc7e00)

- Allow C4SVal = 100 as a shorthand for C4SVal = [100, 0, 100, 100] (416fb33)

- Don't load savegame files for empty sections (5f1f4db)

- Store First and Last in C4Landscape instead of static variables (a905a56)

- Add section parameter to audibility calculations (a1801ec)

- Return the old section number or nil on error (2b1226e)

- Fix resorting being broken due to the wrong flag being used (502c16e)

- Don't execute section object list checks if Section==nullptr during a loading failure (a4340c7)

- Add nowarn option for #include C4ID (29f01f4)

- Add C4Thread::CreateJ (af3aa92)

- Load section in separate thread (83d7a7f)

- Rework script section context handling

- Rename `SwitchToSection` to `SetSectionContext`
- Rename `GetSection` to `GetSectionContext`
- Rename `MoveToSection` to `SetSection`
- Add `GetSection` which gets the section an object is in
- Section contexts cannot be set when called with an object context
- Add `SetObjectContext` to set the object context to an object of the same definition (or nil) (84ea4c2)

- CPattern: Use `std::shared_ptr` for the cached pattern so it may be shared
between patterns that are copied from another pattern (63d9d4e)

- C4Section: Don't load the material enumeration and reinitialize the texture map
if the materials and textures were copied from another section

This allows `CPattern` to reuse the cached patterns, massively cutting down
on RAM costs - with 2000 20x20 sections, 10 GB of RAM were previously used
just for cached patterns. (17cfc90)

- Fix logic for determining objects created by script (32c6b23)

- Remove minimum size requirements for landscape width / height (7a198c3)

- Throw an error for now (2795661)

- First draft for child sections (392edf3)

- Add missing includes (d28a6d6)

- :DrawSection: Remove crashing assertion as observers don't have players (f4e24d5)

- Add the ability to search in multiple sections with FindObject and the likes and
introduce the concept of objects that can be found in all sections for compatibility
with old scripts searching for goal / rule objects (d8c9cce)

- Add script functions for the section info parameters (1bdf897)

- Don't use std::from_range as libstdc++ doesn't support it yet (0f45cf9)

- :MultipleObjectListsWithMarker: Fix comparator returning utterly wrong values (75aa509)

- :Enter: Move the object to the container's section (c6216ab)

- Fix missing PktHandlingData for CID_SectionLoaded and CID_SectionLoadFinished (89f05e8)

- Disable smooth scrolling for switching between sections (2b407cf)

- C4Game: Use a separate GL context for each section load to fix off-thread section
loading resulting in incomplete textures (98d1524)

- :Clear: Don't reset section back to nullptr as this breaks close commands (476b2ac)

- Remove incorrect duplicate call to C4Weather::Init (7afa9be)

- Make section loading use dedicated random generators based on the current random value
on starting the loading (1a07d2b)

- Fix section denumeration & enumeration only occuring in the first effect (8520d18)

- Assume the section as the first section if no section number was deserialized (a79519e)

- Use std::unique_ptr (2c76608)

- Initial draft of savegames

Sections save their runtime state into a SaveSect-<x>-<y>.c4g subgroup; x
denotes an ascending counter for sorting purposes, y the section number.
The exception to this is the first section, which saves into the main group
as well as Game.txt for compatibility. (7bd0875)

- Fix 'global' script sounds not being constrained to a section and differentiate between section-local and global sounds (5bcd5c1)

- Make C4EditCursor and C4ToolsDlg work with sections (a22f451)

- Fix sounds without an object target being audible in every section (5b09921)

- Fix one source of desync caused by CID_SectionLoaded and CID_SectionLoadFinished being send as CDT_Sync instead of CDT_Decide (720b0eb)

- Change view offset to a per section value (f74ac3f)

- Disallow script execution in sections as they are loaded in a separate thread (9e45c44)

- Always renumber all objects loaded from Objects.txt during non-savegame section creation
to avoid conflicts and only use the section's objects for denumeration (22ed480)

- Readd accidentally deleted call to InitValueOverloads and setting PreloadingStatus (9b57f49)

- Fix FixedRandom not resetting the random count (68366ec)

- Fix sounds with custom falloff distance being audible in other sections (7820393)

- Make saving as scenario work again (c23a6c1)

- Fix empty landscape sections loading Objects.txt from the main group (72395f6)

- Add missing include (108c344)

- Rework section deletion and use status to keep track of sections that should be deleted (26ff866)

- Add Inactive status and SetSectionStatus() (914d26c)

- Add C4SoundSystem::ClearSectionPointers and extract the clearing of section pointers into C4Game::ClearSectionPointers (a00663c)

- :LoadScenarioSection: Remove handling of C4S_KEEP_EFFECTS (44a9053)

- Mark exception throwing helper methods as [[noreturn]] (5075259)

- Remove most special-casing of the main section

- It is now saved like any other section.
- `CreateSection("main")` is now possible. (99336e1)

- Add missing C4Section forward declaration (cd3b8e9)

- Load materials and textures globally and use them as a fallback for sections
instead of the first section (bda6658)

- :AddDataRef: Let the wild object pointer check also search in inactive and deleted sections (e6cba05)

- Remove special treatment for section 0 in script functions (777e0a2)

- Ensure the last active section is never deleted or set inactive (719ed8c)

- C4Section::ExecObjects: Abort object execution if processing the current object
caused the section to be deleted (cafacef)

- Add C4Value callback parameter (8d3e0fd)

- Fix capitalization (88d2d18)

- Remove LoadScenarioSection (c0971b1)

- :MenuCommand: Fix rebase error (ef49a43)

- Add FnDrawLandscape (d850ff6)

- Return old object context (6e39fda)

- Add section-local variables (declared with section_local) (5a594b3)

- Fix autobuild (3027dbc)

- Fix undefined behavior in console mode if the viewport size is greater than the section landscape size (1b3ac65)

- Add OnSectionMoved callback on section move (f22c571)

- Merge branch 'master' into multiple_sections (cc83bd5)

- Merge branch 'master' into multiple_sections (9aadf04)

- Start section numbers at 1 instead of 0 to avoid nil/0 ambiguities (d889d9b)

- Rename emptyLandscape to createdByScript and allow specifying a Landscape.txt map script for script sections (1e6e778)

- Merge branch 'master' into multiple_sections (d9f688b)

- Rename C4S member to GameC4S to catch accidental future usage from merges from other branches (7babe79)

- Refactor relative position handling into helper functions (37c1227)

- Use helper type to fallback to context object for C4Object* arguments (617655b)

- Use helper type to provide default arguments for integral script function arguments (b4b7677)

- Use helper type to provide automatic nil/nullptr checks on script function arguments and return a failure value (2d5e98a)

- FnSimFlight: Remove unnecessary nullptr checks. Type checks already ensure non-nullptr values (0a222b1)

- CreateObject: Use caller-owner or NO_OWNER if owner is specified as nil (ff444f4)

- Fix pathfinder transfer zone waypoints using the wrong update interval due to an unused variable (efa9f28)

- :Broadcast: Fix success condition (20908a4)

- Deduplicate Sin + Cos / ArcSin + ArcCos (bf24608)

- :Grab, Get, Put: Finish command immediately on success, instead of on next execution (1f55b27)

- Fix rare edge case failure of AdjustMoveToTarget

Under certain circumstances this made the anvil unusable. (5fef4d3)

- Replace C4Network2Res::Ref with std::shared_ptr (4df88b2)

- Replace C headers with their C++ equivalents and use std::foo instead of foo for some functions (9ffbbb0)

- Add and use RequiredNonZero (e79d92d)

- C4AulEngineFunc: Make C4AulContext * argument optional and remove it from all Fn* where it is unused (633825b)

- Replace Required<Foo *> arguments with Foo & (d87bae5)

- Add automatic conversion from C4Value to C4Player */& and simplify functions where possible (6b8a150)

- Adapt function wrappers to allow exposing member variable and function pointers as script functions (eb5d753)

- Add function wrappers to allow exposing member variables and function pointers of global instances (de5375e)

- Directly expose trivially wrapped functions (8361770)

- Replace some constant-like functions with a generic constant template function (7a7882a)

- Add and use conversion from player ID to C4PlayerInfo * (ec10826)

- Add automatic conversion from C4Value to C4Def */& and simplify FnDefinitionCall (eb7f7fb)

- Simplify Required’s implicit conversion functions (44f9dd8)

- Add explicit string_view interoperability (3d85ac5)

- Modernize C4AulError classes (3ad1fcd)

- Avoid incorrect line numbers in stack traces with utility function C4AulExec::ThrowExecError (80ad206)

- Use std::vector for loop stack and loop controls (0d79c19)

- Replace Code and related members with std::vector (b31210e)

- Move helpers from C4Script.cpp to separate headers (33537dc)

- Use span for parameters (ab63a69)

- Simplify usage of CreateCriterionsFromPars (01547c6)

- Modernize C4FindObject and C4SortObject with vector and unique_ptr (c29ef8e)

- New feature custom hud bars

This implements unified hud bars logic, with new features:
  - hud bar graphics can be scaled
  - arbitrary amount of custom hud bars
  - hud bars can mimick the traditional hud bars or replace them
  - hud bars can be arranged in arbitrary user defined order
  - hud bars can be grouped to be rendered above another for a "shield effect"
  - hud bar rendering can be based on physicals and HideHUDBars
  - or controlled manually with script functions

New Script Functions:
FnDefineHudBars
FnSetHudBarValue
FnSetHudBarVisibility

New Script Constants:
EBP_None
EBP_Energy
EBP_Magic
EBP_Breath
EBH_Never
EBH_Empty
EBH_Full
EBH_HideHUDBars (9f3689b)

- Make code compile again (6e46134)

-  C4HudBarsUniquifier::DefineHudBars: Remove unnecessary move that prevents copy elision (c47f9a5)

- First round of style fixes (0bdac73)

- :CompileFunc: Don't copy gfxs (5a10ade)

- Replace magic number 1000000 with constexpr variable (01af812)

- Refactor C4HudBar into a struct (d395358)

- Remove unnecessary copies of std::shared_ptr and std::string (a8686bf)

- Another round of style fixes (419adf8)

- :CompileFunc: Move uniqueDef into Instantiate() (5ebfb09)

- Don't drag C4AulContext into HUD bar classes (a8a1f1c)

- Add const to function parameters (96fa92a)

- Use range check for physical enum (252ed42)

- Make StdBitfieldAdapt work with scoped enums (d12ad4d)

- Use scoped enums (c8b5726)

- Use uppercase properties for HUD bar definitions (9730bdb)

- Add C4TransparentHash (12e7b4c)

- Add HashArguments (4f9a76f)

- Add HashCombineArguments (76658e5)

- :ProcessHudBar: Fix valid physical check being inverted (9a51cc1)

- Refactor default HUD bar loading and use transparent comparators (5971258)

- Revert misconception about what group set the Graphics.c4g folders are stored in (2156952)

- Don't close gfx groups (23e8f5e)

- :GetFacet: Remove leftover debug logs (407b6c2)

- :Hide: Rename HideHUDBars to AsDef (1e9eca4)

- Use default member initializers instead of initializing the members in the default constructor (7e8c1aa)

- :Maximum: Use thousands separator for better readability (4ee40b0)

- Rename Maximum to DefaultMaximum (3cfc871)

- Fix spelling of Uniqueify to Uniquify (42b04db)

- :UniquifyDefinition: Remove const from return value to prevent it from being copied (d2ee361)

- Merge UniquifyDefinition and Instantiate into RegisterAndCreateInstance (b32083d)

- Remove redudant mention of HUD bars from function names (bd339fe)

- :BarVal: Remove unused functionName parameter (2b86aaf)

- C4Object. Replace HUD bar setters function with direct access to the already public HudBars element (8966c99)

- :Gfx: Capitalize public members and remove unnecessary constructors and operator== implementation (4468906)

- Remove unnecessary operator== implementation (0558203)

- Use std::hash specializations for C4HudBarDef and C4HudBarsDef instead of GetHash member function (bf6fcea)

- Add C4PosixSpawn (4620704)

- Use posix_spawn for Linux and Mac (38fc19f)

- Remove C4Include.h (861a4a7)

- Cache Fx*Context (a55fb75)

- :GetCallbackScript: Return reference as it can never be null and eliminate unnecessary usage in C4ObjectMenu (6cb570b)

- Put helper functions in anonymous namespace (712835e)

- Bump version to 366 and update System.c4g c4u parts (3fb8224)

- CreateObject: Use caller-owner or NO_OWNER if owner is specified as nil (fd1aec7)

- Fix pathfinder transfer zone waypoints using the wrong update interval due to an unused variable (2431e7b)

- Deduplicate Sin + Cos / ArcSin + ArcCos (4f41f05)

- :Grab, Get, Put: Finish command immediately on success, instead of on next execution (29c5677)

- Fix rare edge case failure of AdjustMoveToTarget

Under certain circumstances this made the anvil unusable. (f6c567f)

- Replace C4Network2Res::Ref with std::shared_ptr (1b74390)

- Replace C headers with their C++ equivalents and use std::foo instead of foo for some functions (db62c42)

- Add explicit string_view interoperability (17cc60f)

- Modernize C4AulError classes (7884aa0)

- Avoid incorrect line numbers in stack traces with utility function C4AulExec::ThrowExecError (ba243c7)

- Use std::vector for loop stack and loop controls (0032b81)

- Replace Code and related members with std::vector (24889ee)

- Revert "C4Strings: Workaround libc++ bug (#128)"

This reverts commit cafb0ce9b3c4f5c8848bbbd74902bb238a3bf6da. (6926d85)

- Merge remote-tracking branch 'origin/cleanup_ready' (402496c)

- Introduce C4EnumInfo for unified serialization and script constant registration (e93efcb)

- Merge remote-tracking branch 'origin/enums' (08ced56)

- Add a game option to enable / disable voting for host actions instead of having it locked behind the league (ba5ee2a)

- Only vote on pause in league as pause / unpause is a workaround against network games freezing up (090069a)

- Merge remote-tracking branch 'origin/voting' (13bf6a6)

- Merge remote-tracking branch 'origin/master' into posix_spawn (c51c0e1)

- Merge remote-tracking branch 'origin/posix_spawn' (d5285bc)

- Implement C4ValueConstexpr and use it for some script functions (1de70f6)

- Merge origin/master into c4valueconstexpr (7b7152c)

- Merge remote-tracking branch 'origin/c4valueconstexpr' (d4910dc)

- Add C4File (4e7c04a)

- Replace non-compressed CStdFile usage with C4File (c0a6bf5)

- Move C4File to its own files (f252fba)

- Add C4File::Rewind (0b3b7c5)

- Add C4File::GetHandle (a583d6c)

- Replace fopen() with C4File (577b591)

- Remove CStdFile::AccessedEntrySize (21c3ac4)

- Rename Read/Write to ReadExact/WriteExact and ReadPartial to Read (2b334c2)

- Add ReadAt and AtEnd and return success status in Rewind (8fd776b)

- C4Group: Replace OpenMother and OpenChild hacks with GrabMother and OpenAsChild
and make C4Group noncopyable.

The functions were only used in C4Language and use copy constructor hacks. (07e0f8d)

- Fix SeekMode not being public (f45e6b2)

- :LoadContents: Use ptr, size overload of ReadExact (ff0c993)

- Move std::span overloads into a separate base class (e85a013)

- :LogSink: Use C4File (49e8bee)

- Fix usage of C4File::Read (664c782)

- Use C4File (3d3a583)

- Fix usage of C4File::WriteStringLine (72c5e1b)

- Use C4File (170ec70)

- Remove ReadAt and WriteAt (a77b874)

- Add missing include (87c0e80)

- Fix Seek declaration (0d0c1c8)

- Fix memory leak if OpenAsChild fails (c164603)

- Reduce redundancy (af4bb9c)

- Refactor read and write methods and move implementations into C4File.cpp (77f2cdd)

- C4File: Use std::optional and std::expected and add [[nodiscard]]
to functions returning whether they succeeded or not (80402a1)

- Handle or explicitely ignore results of C4File operations (561c30f)

- Use std::error_code instead of std::errc (e314267)

- Fix rewind error message (2a36346)

- Replace std::string overloads with std::filesystem::path overloads (f22a535)

- Add missing whitespace (567e962)

- Replace LoadContents with LoadContentsAsString (4d70d23)

- :Open: Replace StdStringEncodingConverter with ranges as it is not available in the c4group target and mode characters are all ASCII anyway (7ab6ad0)

- Add missing include (d5c34b8)

- Merge remote-tracking branch 'origin/master' into HEAD

# Conflicts:
#	src/C4Config.cpp
#	src/CStdFile.cpp (0061681)

- Merge remote-tracking branch 'origin/c4file' (ff9026c)

- Merge remote-tracking branch 'origin/master' into custom_energy_bars

# Conflicts:
#	src/C4Object.cpp
#	src/C4Value.cpp
#	src/StdAdaptors.h
#	src/StdHelpers.h (0ee7559)

- Port C4HudBars to C4EnumInfo API and fix StdAdaptors for enum class

After merging master (which includes the c4valueconstexpr and enums
refactors), C4HudBars.cpp still used the old StdEnumEntry/StdBitfieldEntry/
mkEnumAdaptT API. Port it to the new mkEnumAdapt/mkBitfieldAdapt API by
adding C4EnumInfo specializations for C4HudBarDef::Physical and
C4HudBarDef::Hide.

Also fix C4EnumAdaptWithInfo and C4BitfieldAdaptWithInfo in StdAdaptors.h
to work with enum class types by casting to the underlying type for
comparisons and assignments. (d650c1b)

- Merge remote-tracking branch 'origin/custom_energy_bars' (2a104a4)

- Merge remote-tracking branch 'origin/master' into HEAD

# Conflicts:
#	src/C4AulExec.cpp
#	src/C4Command.cpp
#	src/C4FindObject.cpp
#	src/C4FindObject.h
#	src/C4Network2Res.cpp
#	src/C4Network2ResDlg.cpp
#	src/C4Script.cpp
#	src/C4Value.h
#	src/CStdFile.cpp
#	src/StdBuf.cpp
#	src/StdCompiler.cpp (407b55d)

- Fix compile errors after cleanup/master merge

- C4FindObject: reorder initializer list to match member declaration order
- C4Network2ResDlg: add parens around assignment in while condition
- C4Script: add AddEnum function template definition (lost in merge)
- StdBuf: add parens around assignment in while condition (96352a4)

- Merge remote-tracking branch 'origin/cleanup' (66c1674)

- Merge origin/master into multiple_sections

Resolve conflicts per branch strategy:
- Prefer multiple_sections' section-aware changes
- Take master's include cleanup, HUD bars, hash helpers
- Use GameC4S consistently for C4Game::C4S rename
- Port master's CachedPattern deep-copy fix (c3fcb40)

- Address TODO/FIXME markers after master merge

- Replace throw std::runtime_error{"TODO"} with proper error logging
- Document FIXME markers using first active section pattern
- Remove transitional FIXMEs by explaining the design choice (c508418)

- Fix compile errors after master merge

- C4Script.cpp: Take HEAD version (section-aware), update to new
  C4FindObject/C4SortObject unique_ptr API
- C4FindObject.h: Remove duplicate C4SortObject class definition
- C4AulExec.cpp: Use Obj instead of cObj after master's rename
- C4Game.cpp: Remove undefined 'section' variable from InitGame
- C4MapCreatorS2.cpp: Close anonymous namespace before AlgoScript
  to resolve ambiguity with forward declaration
- C4ObjectMenu.cpp: Add missing section parameter to Exec call
- StdDDraw2.cpp: Fix CachedPattern deep copy for shared_ptr
- StdHelpers.h: Fix missing closing brace in end() function (6efd0c4)

- Merge remote-tracking branch 'origin/multiple_sections' (376c910)

- **Tutorials**: Add first-run welcome dialog (c625064)

- **cleanup**: Triage all TODO/FIXME markers, add lint + CI policy (4641f04)

- **Preservation**: Add reproducible build pinning (6c8950e)

- Unlock /host and /client:N flags in release builds for CI smoke tests (cd65029)

- Add session-token reconnect handshake (Milestone A) + rollback-ring snapshot source (Milestone B)

- New C4Reconnect module: game-scoped 128-bit token, NCS_Dormant grace
  window, snapshot-source policy (rollback ring preferred, fresh
  SaveRuntimeDataToBuffer fallback).
- New C4PacketReconn (PID_Reconn = 0x18) carrying
  {token, originalClientID, lastConfirmedCtrlTick}.
- C4PacketJoinData gains reconnectToken + inline reconnectSnapshot +
  reconnectSnapshotTick; client-side HandleReconnectJoinData restores
  via LoadRuntimeDataFromBuffer and chases.
- OnClientDisconnect dormancy branch + Execute dormancy tick; grace
  expiry calls CtrlRemove directly (no double league notify).
- C4Rollback::GetSnapshotForTick accessor (Milestone B plumbing).
- Config.Network.ReconnectEnabled / ReconnectGraceSec (default off ->
  byte-for-byte identical to pre-reconnect engine).
- 17 Catch2 cases in test_C4Reconnect (LINK_ENGINE).

Spec: .opencode/specs/2026-08-29-1000-connection-migration-reconnect.md (cf8c883)

- Expose C4IdText as a script function (3f5900e)

- Fix/ci-red-workflows — deps-lock awk portability, TODO lint format, BSD pkg lists, FreeBSD cmake-from-source (d8c191d)

- Merge branch 'feat/pregame-options-parity' (deb7479)

- Merge branch 'feat/pregame-options-parity' (CI fix round 2) (b9b6ee1)

- Merge branch 'feat/pregame-options-parity' (CI fix round 3) (3e98bb1)

- Merge branch 'feat/pregame-options-parity' (CI fix round 4) (7bc8967)

- Merge branch 'feat/pregame-options-parity' (CI fix round 5) (6d7504a)

- Merge branch 'feat/pregame-options-parity' (CI fix round 6) (302f8d7)

- Revert "chore(changelog): update for v366" (splice re-applied on re-tag) (0d13552)

## [367] - 2026-09-08

### Added

- **tools**: Add gen_scorpion_gfx.py deterministic scorpion art generator (cycle 93) (5453fe7)

- **tools**: Add lint_placeholder_gfx.py + seeded allowlist (cycle 93) (f2e1092)

- **tools**: Add oracle-validated vision_qa.py battery harness (cycle 98) (59282af)

- **tools**: Clonkgfx shared sprite library + selftest (cycle 99) (d749635)

- **tools**: Vision_qa --gate-mode {full,feature,advisory} (strictly additive) (22c853f)

- **tools**: Gen_camel_gfx - multi-action camel sheet (first clonkgfx customer) (21b5266)

- **lint**: De-allowlist camel + wire clonkgfx selftest and gfx --check CTest gates (328c338)

- **tools**: Gen_desert_gfx - batch desert generator (7 defs, per-def subcommands) (5cfbae1)

- **lint**: FLAT_PICTURE check for actionless flat Picture rects; de-allowlist DatePalm, grandfather Heal (d63471d)

- **controls**: Console-safe preset registry + table pins (G1/G2/G4) (d203387)

- **controls**: Two-layer ApplyPreset + SetKeyboardControlKey + persistence pins (P1–P5, seeded G3, G5) (bccca0a)

- **controls**: Old-editor live rebind + player-properties preset picker (9274aed)

- **controls**: Options → Keyboard preset dropdown (5bd6ff0)

- **controls**: Fresh-default flip to Two-Hand WASD+Mouse + linkage pins + docs (0863267)

- **options**: Make the ControlRate row network-only (Network.isEnabled gate) (9469f33)

- **overrides**: Rules=/Goals= --parameter ID-list overrides + Catch2 C1-C6 (02df52e)

- **pregame**: Two-pane offline dialog shell + ScenDesc-style briefing (972a3ba)

- **pregame**: Objectives/rules picker rows with write-through to Parameters (8b9abc0)

- **overrides**: Seed=/landscape-param --parameter overrides + Catch2 C7-C11 (20a9d9b)

- **landscape**: C4Landscape::CreatePreviewMap — seeded preview render helper (6ce67c3)

- **pregame**: Landscape panel — seed line + reroll with write-through (a0ab651)

- **pregame**: Live landscape preview — on-demand seeded render + palette colorize (9d6f5b3)

- **pregame**: Classic-generator landscape parameter steppers with dual write-through (f0c5dc8)

- **gfx**: Art-pipeline-v2 HiRes authoring + box-downscale + quantize (9060dcc)

- **tools**: Vision judge at ollama think=high (2nd-highest effort) (8d931a8)

- **gfx**: Scorpion 36x26 generator v2 on clonkgfx (cycle 105) (d1918ef)


### Changed

- **tools**: Fix auto_format dirt in cycle-93 gfx tools (cycle 93) (8c0cdfa)

- **tools**: Auto_format vision_qa.py (Format Lint fix, cycle 98) (e3d612c)

- **tools**: Auto_format clonkgfx + selftest (Format Lint fix, cycle 99) (5d51a51)

- **smoke**: Auto_format landscape_seed_smoke driver (Format Lint red) (8de2930)


### Fixed

- **release**: Use github.event.inputs to avoid invalid inputs context (677d3d4)

- **release**: Replace env context in job-level if with github event expression (57ba1dd)

- **release**: Skip changelog splice on nightly dry-runs (cycle 95) (ae6f25d)

- **ci**: Ship 12 missing content packs + release-content lint (cycle 96) (16e1337)

- **effect**: Drop null-section effects in C4Effect::Execute (cycle 97) (787b861)

- **net-smokes**: Stdin=DEVNULL on engine procs + sweep failure-log retention (c0dbb9d)

- **net-desync-smoke**: Bind both peers to 127.0.0.1 (live_reconnect pattern) (07e70cf)

- **smokes**: Wrap direct engine test invocations with stdin=/dev/null (f514ee6)

- **wrapper**: Remap engine signal exits to shell convention (128+signo) (eb2b0b3)

- **tools**: Vision_qa gate-soundness fixes from cycle-98 review (7293fdd)

- **controls**: Include C4GuiComboBox.h in C4StartupPlrSelDlg (PCH-masked missing include) (626961c)

- **lint**: Refresh stale todo-allowlist lines after picker insertion (aaf1a20)

- **controls**: Kbd3 slot-12 VK collision on non-German Windows (186 → 0xDB base) (5364d57)

- **game**: Move offline pre-game dialog post-def-load; offline-only via !Network.isEnabled() (5f2a0f7)

- **smoke**: Landscape_seed_smoke relative-determinism driver (CI-red: absolute pin is machine-dependent) (bc42980)

- **gfx**: Scorpion maps 4px claw-band drift + 2400s vision timeout (e8ea4f4)

- **ci**: Resolve update-group parts fork-first with upstream fallback (1323c26)


### Internal

- **release**: Add dry-run rehearsal + nightly schedule (30c4f02)

- **release**: Skip changelog splice commit in dry-run mode (5c64924)

- **changelog**: Update for v366 [skip ci] (88d3972)

- **macos**: Drop Intel x86_64 lane (Homebrew/GitHub deprecation) (953bafb)

- **tools**: Add run_repro_matrix.sh six-symptom driver (cycle 90) (fefaf16)

- **tools**: Add run_liquid_sweep.sh dig-delay sweep driver (cycle 92) (e8ff666)

- **cmake**: Wire content_gfx_lint CTest entry (cycle 93) (65dda77)

- **cmake**: Wire lava_wall_long_gate + promote-aware repro drivers (cycle 94) (1c585fb)

- **playtest**: Add shipped-scenario playtest sweep + CI lane (cycle 97) (1df7f81)

- **playtest**: Raise lane timeout to 120 min (first-run hit 60-min cap mid-test) (26998fb)

- **playtest**: Trigger on tools/ changes (smoke drivers live there) (4d6783d)

- **playtest**: Publish failed-test list to step summary (auth-free diagnosis) (a9a8ce6)

- Wire 7 desert gfx --check byte gates (gfx_check_*) (412abf5)

- **playtest**: Exclude flaky network smokes from per-push sweep (e63cfc7)

- **overrides**: Rules_goals_override_smoke — Rules=/Goals= override end-to-end (b72f20b)

- **overrides**: Landscape_seed_smoke — Seed= determinism end-to-end pin (9760468)

- **gfx**: Vision_qa_scorpion CTest gate + 36x26 DEFAULT_FACET (cycle 105) (c278d65)

- **version**: Bump content version to 4.9.11.4 for v367 (4b37197)

- **changelog**: Update for v367 [skip ci] (a525044)


### Other

- Revert "chore(changelog): update for v367" (5ba68d8)

- Merge master: absorb v367 changelog splice revert (re-cut) (9e42d6a)

## [368] - 2026-09-11

### Added

- **net**: C4LandscapeOverrides block in C4PacketJoinData (W1/W2) (deaf9ce)

- **net**: Host fill + client stage/apply of JoinData landscape overrides (C12/C13) (d248936)

- **net**: Pre-lobby net-host settings stage + InitGameFirstPart guard fix (5ea57cd)

- **engine**: --screenshot-at/--shot-size parse + shot state + fire site (f1c5d2f)

- **engine**: CSceneShot CPU frame composer + SceneTruth sidecar (P1/P2/P5 findings) (3358899)

- **vision**: Qwen3.8 window guard — SKIP-exit-0 08:00-21:00 unless VQ_ALLOW_DAYTIME=1 (0607ee7)

- **tools**: Gen_agriculture_gfx - batch agriculture generator (9 defs, per-def subcommands) (948ab70)

- Slider-contract descriptor table + pinning test (cycle 112 gate) (dc10689)

- Rework world-generator settings screen (two-stage flow, hero preview, generated slider rows) (3a79f29)

- Generalize --parameter dispatch to the descriptor table (six new keys) (9211cdf)

- Grow JoinData landscape-override block 5 -> 11 slots (order-stable, old-format gate preserved) (aa02fcb)

- **wincond**: Descriptor tables + shared codec, pinned by the SliderContract gate (cycle 114) (162afa3)

- **wincond**: Four --parameter parity keys (Mode/Elimination/CooperativeGoal/ValueGain) via the shared codec (1a1e0f1)

- **wincond**: Count sliders on the picker rows (MaxUserSelect eligibility, live refresh) (54bd489)

- **wincond**: The Winning Conditions panel (mode/elimination/goal combos + settlement slider, live cross-refresh) (30a2484)


### Changed

- **net**: Auto_format condense empty lines in net_settings_sync_smoke (256f67f)

- **auto_format**: Cycle-114 format gate (7dd9edd)


### Fixed

- **vision**: Dual-review nits — R1 fallback arg, R2 missed-tick log, F2 fallback bound, F5 phase clamp (563ba56)

- **ci**: CSceneShot self-include (PCH-off ASan/debugrec compile fix) + IPv6 loopback UDP port-probe hardening (f97ce33)

- **Networking**: Deadline-bound the teardown league end (abort freeze) (32bad62)

- **Networking**: Unanchor net_abort_smoke teardown-line regex (dual-review F1) (6182f09)

- **tools**: Align dead-lobster invariants window to Amendment 2 (95,160) (dual-review F1) (6ac9af4)

- **dialog**: Add missing #pragma once include guard (1619f13)

- **tests**: Swap std::string_view for std::string in Catch2 macros (MSVC deps lib lacks the StringMaker specialization) (5a29b44)

- **viewport**: Pass view section to X11 edit-cursor calls (1ab9550)

- **release**: Publish release body from every publish leg (9ae10ab)


### Internal

- **net**: Net_settings_sync_smoke two-engine settings-sync pin (W3) (ad1880e)

- **net**: Fresh player copies per smoke pass + pass-2 fp cross-assert (review nits) (91bec18)

- **vision**: Playtest_vision.py scene-capture + oracle + sidecar cross-check harness (a6dee48)

- **vision**: Register playtest_vision CTest entry (advisory, SKIP-exit-0 without ollama) (ee5e008)

- **lint**: De-allowlist the 9 reworked Agriculture defs (cycle 110) (7149463)

- Wire 9 agriculture gfx --check byte gates + lobster vision battery (cycle 110) (c424c3a)

- Wire SliderContract pinning test (RED: descriptor table pending) (4c81626)

- **gui**: Add compile-only GUI X11 lane (d2c74fd)

- **wincond**: Wincond_override_smoke + wincond_mode_smoke ctest entries (36fd0a3)

- **changelog**: Update for v367 [skip ci] (fabe6a6)

- **version**: Bump content version to 4.9.11.5 for v368 (51cd790)

- **smoke**: Pin DuneBurialSmoke RNG seed (Playtest lane flake) (cc7aef7)


### Other

- Merge master: absorb v367 changelog splice (e9d3d44)

## [369] - 2026-09-14

### Added

- **CCAN**: Add Phase-0 population crawl + offline stats tooling (76dfaef)

- **CCAN**: Publish Phase-0 population thresholds (tools/ccan_thresholds.toml) (e6802e1)

- **Replay**: Add replay-browser resource strings (ca386e2)

- **Input**: Bind Ctrl+R replay-viewer toggle, auto-show on replay start (10b85e7)

- **startup**: Finish replay browser list, metadata, and launch (df6a0a4)

- **startup**: Register replay browser in the startup tree (ee825a4)

- **Replay**: Log saved replay path on record stop (d0da8cb)

- **vision**: Machine-global judge_lock serializes qwen3.8 consumers (cycle 121) (764a0ea)

- **Networking**: Enable ReconnectEnabled by default (6d0ee62)

- **pregame**: Add [PlayerN] start-list descriptor table + SliderContract pins (1535df2)

- **pregame**: Generate [PlayerN] picker sections in the offline options dialog (dec06e7)

- **pregame**: Add Knowledge/HomeBaseMaterial/HomeBaseProduction parameter keys (17b6a0b)

- **material**: FlowRate + JetFall .c4m knobs with legacy defaults (cycle 124) (8d5952b)

- **massmover**: FlowRate multi-hop transfer per Execute (cycle 124) (a951975)

- **massmover**: JetFall ballistic-PXS handoff with budgeted create-or-deposit caster (cycle 124) (19f9106)

- **script**: GetMassMoverCount() getter - cycle-118 instrument gap (cycle 124) (6aadc3f)

- **gfx**: Scorpion generator v3 - 24x14 five-band sheet (cycle 125) (58fb93f)


### Changed

- **auto_format**: Cycle-117 format gate (a2d268d)

- **gfx**: Auto_format pass on gen_scorpion_gfx.py - collapse double blank lines (cycle 125) (2c59340)


### Fixed

- **Input**: Tolerate quoted KeyConfig.txt code tokens on load (a41501a)

- **ccan-index**: Parse live 5/11-column listing layouts + correct footer totals (eef14b2)

- **ccan-index**: Footer total from live <td>-wrapped footer + commit ground-truth fixture (L7/L8) (aa2beff)

- **CCAN**: Recover entry_type from IMG evidence + ISO-normalize uploaded (914465d)

- **startup**: Repair replay browser list population (Clear UAF + doubled path) (c7933cc)

- **Input**: Dock replay viewer at screen bottom via DoPlacement (ShowDialog was re-centering the overlay) (ab5df35)

- **Input**: Translate timeline bar by dialog bounds (bar drew at screen origin, missing docked overlay) (f2f3721)

- **Input**: Draw replay timeline in the dialog element pass (facet-relative coords) (7c777e8)

- **pregame**: Make Start a visible right-anchored primary on the settings stage (b566982)

- **lobby**: Tooltip on the host Start button (OC parity) (38f9523)


### Internal

- **changelog**: Update for v368 [skip ci] (f33148f)

- **Input**: Pin the KeyConfig round-trip (R2-R4) + retire stale NOTES (82a67bb)

- **perf**: Declare MinSpec-A reference machine + gate-constant re-derivation (5d5a616)

- **perf**: Wire mobilization_perf_gate CTest twin (cycle 118) (5f1cc95)

- **perf**: Transcribe cycle-118 mobilization baselines + [HEADROOM] projection (6a259da)

- **tools**: Add hermetic vision-judge lock selftest (RED on unlocked tree) (3b95ac6)

- **vision**: Qwen_judge RESOURCE_LOCK + vision labels + vision_lock_selftest entry (cycle 121) (c3a331b)

- **Networking**: Add default-config live reconnect smoke variant (f39626a)

- **smoke**: Pin DammbruchSmoke seed via SMOKE_SEED_PIN (cycle 124) (9ef6953)

- **perf**: Re-baseline [CAL] medians + FlowRate dwell point at Water FlowRate=4 (cycle 124) (f8a2188)

- **vision**: Vision_qa_scorpion re-pin - facet 24x14, phases 6, TIMEOUT 5400 (cycle 125) (cfb2f3b)

- **version**: Bump content version to 4.9.11.6 for v369 (8f850f7)


### Other

- **lobby**: Drop duplicate btnRun tooltip (38f9523d) — line already present at base 7c777e86:296-297; review finding F1 (Flash), false-premise fix (09b9c09)

## [370] - 2026-09-18

### Added

- **CCAN**: Quarantine record + subcommand + outreach templates (seepack FAIL branch) (5dec24b)

- **tools**: Gen_rtap_gfx - RTAP standpipe sprite generator (clonk-gfx) (5e4ca99)

- **tools**: Sdl_api_drift.py - SDL2->SDL3 API drift mapper (cycle 129) (44ab54b)

- **tools**: Add menu_walk_smoke.py five-leg driver with --strict (Addendum 1) (9e5b5d9)

- **tools**: Add menu_walk_screenshots.sh Leg B Xvfb driver (4473039)

- **scenario**: Skip pre-game options dialog for authored scenarios (04e4d00)

- **dialog**: Tabletize welcome + pre-game option strings (5808cfa)

- **pregame**: String-table keys for the store tab (d55c2ab)

- **pregame**: ComputeStoreWrap helper + SliderContract fit pins (5619da8)

- **pregame**: Store tab with dense grid + shared count editor (85c95fa)

- **pregame**: String-table keys for free game menu entry (5302fbf)

- **startup**: Free Game main-menu entry opening world settings (8e5a854)


### Changed

- **tools**: Auto_format pass - condense double blank lines in ccan tools (cycle 128) (913d973)


### Fixed

- **CCAN**: Triage default 'ok'->'unknown' - B6 quarantine tier machine-enforced (d17e10f)

- **CCAN**: Quarantine record -> durable hold path; DE template typo (43b27fa)

- **gui**: Keep pre-game settings buttons on screen, drop empty options box (072ad49)

- **tools**: Menu_walk_smoke fatal oracle catches effect-timer FAIL + A1 path robustness (a6a33e3)

- **tools**: Menu_walk_screenshots preflight player-delete trap + gm check (9672513)

- **tools**: Capture join-log offset before join keystrokes (critic fix-now) (a48a29d)

- **ui**: Point quickstart link at the bundled first-game guide on GitHub (881b12c)

- **docs**: Replace remaining dead docs-site links with bundled blob URLs (c103daa)

- **tools**: A3 strict flip, A6 browser-purity leg, walk nav for new browser order (024f13c)

- **pregame**: Retune store wrap cells to 170px for measured 1080p fit (4945b01)

- **pregame**: Pending count preview so unchecked store cells commit drags (cd7091a)

- **pregame**: Rename Zoom factor to Map scale + Latin-1 unit glyph (7b9f12f)

- **startup**: KTutorial01Path backslash breaks parent-pack registration (b4b7e30)


### Internal

- **changelog**: Update for v369 [skip ci] (a170cff)

- **smoke**: Pin FirstLightSmoke RNG seed 721 (cycle 127) (021c28f)

- **smoke**: Pin ReactionLabSmoke RNG seed + register ReactionLab.c4f content group (01062a9)

- **upstream**: Add fork<->upstream sync policy (cycle 129) (ad1b4c0)

- **smoke**: Add MenuWalkLocked mission-access refusal fixture (c3fe67f)

- **smoke**: Register menu_walk_smoke CTest entry (bfa94ad)

- **smoke**: Raise menu_walk_smoke CTest TIMEOUT to 240 (1b07dd1)

- **Players**: Rewrite first-game guide to match the real game (c688c86)

- **Players**: Fix chemical-factory claim and where-next links (e10fa19)

- **Players**: Apply critic fixes to first-game guide (a0590b9)

- **Players**: Quote the actual unlock toast text (a4160e2)

- **cmake**: Six-leg menu walk comment (b111b86)

- **language-tables**: Add translate-new-dialogs regression gate (b26f188)

- **language-tables**: Wrap GetEntry views in std::string for MSVC link (c2ca970)

- **blueprints**: Register blueprint_live_smoke (a67a000)

- **gate**: Scenario_link_gate W1/W2/L link tiers (eff5d90)

- **version**: Bump content version to 4.9.11.7 for v370 (49df3d1)

- **changelog**: Scope v370 highlights to resolvable claims (audit fix) (a8b39c2)

## [371] - 2026-09-19

### Added

- **tools**: Classicart v3 raster pipeline + selftest (ac91eb3)

- **tools**: Gen_windmill_gfx + gfx_check_windmill; allowlist -2 (553f2d2)

- **tools**: Gen_cog_gfx + gfx_check_cog; allowlist -1 (cea08ca)

- **gfx**: Scorpion walk v4 - six-phase gait cycle (fdd1655)

- **gfx**: Add escape-rooms helper sprite batch generator (EGAT/ERLV/ERKY) (cycle 147) (40ed4b8)

- **gamepad**: Xbox-style default binding table + CompileFunc INI defaults (cycle 148) (0c9b69e)

- **gamepad**: Migrate SDL event layer to SDL_GameController + dpad alias (cycle 148) (47e9c28)


### Changed

- Auto_format pass over classicart v3 tooling (blank-line condense) (dd21066)


### Fixed

- **tools**: Gen_cog_gfx draw mast over sail + billow shading (judge critique: sail read as blank panel, mast invisible) (4ee5b79)

- **gfx**: Scorpion walk P2 leg cluster right-shift (judge leg-count merge claw+leg1) (e955850)

- **gamepad**: Migrate legacy -1 button entries to registry defaults (cycle 148) (fefaa2a)

- **lint**: Re-pin gamepad TODO allowlist after SDL_GC rewrite (cycle 148) (cce7555)


### Internal

- **playtest**: Install Pillow for classicart_selftest PIL oracle (runner python3 lacks it; Playtest was the only ctest lane registering the test — CI-red fix) (83ea99c)

- **content**: Register SaltRoad.c4f in release content groups (cycle 146) (13e377f)

- **smoke**: Pin SaltRoadStorySmoke RNG seed 146 (cycle 146) (32a852f)

- **content**: Register EscapeRooms.c4f + folder-local closure in release-content lint (cycle 147) (652fbe6)

- **smoke**: Pin escape-room smoke RNG seeds (cycle 147) (1f6f94a)

- **Players**: Document default gamepad bindings and OOTB behavior (cycle 148) (4483a6e)

- **changelog**: Update for v370 [skip ci] (2db1331)

- **version**: Bump content version to 4.9.11.8 for v371 (344ac68)


### Other

- Merge branch 'master' into development (pre-v371: bring v370 changelog splice into the release line) (de63f6c)

<!-- git-cliff prepends new release sections above this line. -->
