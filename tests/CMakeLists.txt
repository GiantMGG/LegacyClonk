# LegacyClonk
#
# Copyright (c) 2023, The LegacyClonk Team and contributors
#
# Distributed under the terms of the ISC license; see accompanying file
# "COPYING" for details.
#
# "Clonk" is a registered trademark of Matthes Bender, used with permission.
# See accompanying file "TRADEMARK" for details.
#
# To redistribute this file separately, substitute the full license texts
# for the above references.

function (add_test_target TEST_NAME)
	set(TARGET "test_${TEST_NAME}")
	cmake_parse_arguments(PARSE_ARGV 1 "ADD_TEST" "LINK_ENGINE" "" "SOURCES;INCLUDE_DIRS;LIBRARIES;DEFINITIONS")

	add_executable("${TARGET}" ${ADD_TEST_SOURCES})
	target_include_directories("${TARGET}" PRIVATE "${CMAKE_SOURCE_DIR}/src" ${ADD_TEST_INCLUDE_DIRS})
	target_compile_definitions("${TARGET}" PRIVATE C4ENGINE)
	if (ADD_TEST_DEFINITIONS)
		target_compile_definitions("${TARGET}" PRIVATE ${ADD_TEST_DEFINITIONS})
	endif ()
	if (USE_CONSOLE)
		target_compile_definitions("${TARGET}" PRIVATE USE_CONSOLE=1)
	endif ()
	target_link_libraries("${TARGET}" PRIVATE Catch2::Catch2WithMain standard ${ADD_TEST_LIBRARIES})

	# GUI configs compile every test target with USE_SDL_FOR_GAMEPAD=1 (macro
	# block in CMakeLists.txt), so any test TU whose include chain reaches
	# StdSdlSubSystem.h needs the SDL2 headers. LINK_ENGINE tests inherit them
	# via clonk_engine's PUBLIC SDL2::SDL2; standalone tests don't — link the
	# imported target so the include dir (and lib) flows. Console/Windows
	# configs never set USE_SDL_FOR_GAMEPAD and stay untouched.
	if (USE_SDL_FOR_GAMEPAD AND TARGET SDL2::SDL2)
		target_link_libraries("${TARGET}" PRIVATE SDL2::SDL2)
	endif ()

	if (WIN32)
		# Match clonk_engine's cppwinrt include path: TstEngineGlobals.cpp.obj
		# (and any test TU pulling in WinRT headers) must embed the same
		# C++/WinRT version and source-location mode as the clonk_engine PCH
		# objects, or the MSVC linker fails with LNK2038/LNK1319.
		target_include_directories("${TARGET}" PRIVATE "${CMAKE_BINARY_DIR}/generated/cppwinrt")
	endif ()

	if (ADD_TEST_LINK_ENGINE)
		target_link_libraries("${TARGET}" PRIVATE clonk_engine)
		# Provide the Game/Application/Console/FullScreen/Config globals that
		# C4WinMain.cpp would normally define. C4WinMain.cpp is excluded from
		# clonk_engine (it also defines main(), which would clash with
		# Catch2's main() on macOS and Windows), so test binaries link this
		# test-only TU instead.
		target_sources("${TARGET}" PRIVATE "${CMAKE_SOURCE_DIR}/tests/TstEngineGlobals.cpp")
	endif ()

	add_test(NAME "${TEST_NAME}" COMMAND "${TARGET}" WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
endfunction ()

add_test_target(C4Math SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4Math.cpp")
add_test_target(StdBuf SOURCES "${CMAKE_SOURCE_DIR}/tests/TstStdBuf.cpp")
add_test_target(C4Fixed SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4Fixed.cpp" "${CMAKE_SOURCE_DIR}/src/Fixed.cpp")

# The standalone C4NetIO test targets compile src/C4NetIO.cpp directly, so on
# Windows they need the Winsock/IPHelper/system libs that clonk links
# (CMakeLists.txt "Link C++/WinRT" / win32 block); on Unix the socket calls
# live in libc and no extra libs are needed.
if (WIN32)
	set(C4NETIO_WIN_LIBS ws2_32 iphlpapi winmm)
else ()
	set(C4NETIO_WIN_LIBS "")
endif ()

add_test_target(C4NetIO
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4NetIO.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4NetIO.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4Network2Address.cpp"
		"${CMAKE_SOURCE_DIR}/src/StdSync.cpp"
	LIBRARIES ${C4NETIO_WIN_LIBS}
)

add_test_target(C4NetIOIPv6Loopback
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4NetIOIPv6Loopback.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4NetIO.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4Network2Address.cpp"
		"${CMAKE_SOURCE_DIR}/src/StdSync.cpp"
	LIBRARIES ${C4NETIO_WIN_LIBS}
)
# "SKIPPED:" is deliberately unanchored: the Catch2 v3 banner is path-prefixed
# ("<file>:155: SKIPPED:"), so an anchored "^SKIP: " would never match it.
set_tests_properties(C4NetIOIPv6Loopback PROPERTIES TIMEOUT 30 SKIP_REGULAR_EXPRESSION "SKIPPED:")

# The standalone C4NetIO test targets compile src/C4NetIO.cpp, whose include
# chain reaches C4ResStrTable.h -> the generated string-table header. Without
# an explicit dependency, their C++ module dependency scans (.ddi) race the
# generation custom command on a fresh build dir (GCC 16 + CMake 4.x).
add_dependencies(test_C4NetIO res_str_table)
add_dependencies(test_C4NetIOIPv6Loopback res_str_table)

add_test_target(C4ValueCoercion
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4ValueCoercion.cpp"
	LINK_ENGINE
)
add_test_target(C4AulParse
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4AulParse.cpp"
	LINK_ENGINE
)

add_test_target(C4IdText
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4IdText.cpp"
	        "${CMAKE_SOURCE_DIR}/src/C4Id.cpp"
)

add_test_target(StdAdaptorsWarn
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstStdAdaptorsWarn.cpp"
	LINK_ENGINE
)

add_test_target(C4WeatherEvents
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4WeatherEvents.cpp"
	LINK_ENGINE
)
add_test_target(C4ReplayController
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4ReplayController.cpp"
	LINK_ENGINE
)

add_test_target(C4Rollback
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4Rollback.cpp"
		"${CMAKE_SOURCE_DIR}/tests/C4RollbackHarness.hpp"
	LINK_ENGINE
)

add_test_target(C4Reconnect
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4Reconnect.cpp"
		"${CMAKE_SOURCE_DIR}/tests/C4ReconnectHarness.hpp"
	LINK_ENGINE
)

add_test_target(C4ConfigMigration
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4ConfigMigration.cpp"
	LINK_ENGINE
)

add_test_target(C4RecordRoundtrip
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4RecordRoundtrip.cpp"
	LINK_ENGINE
)

add_test_target(C4PacketReconn
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4PacketReconn.cpp"
		"${CMAKE_SOURCE_DIR}/tests/C4ReconnectHarness.hpp"
	LINK_ENGINE
)

add_test_target(JoinDataWire
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4PacketJoinData.cpp"
	LINK_ENGINE
)

add_test_target(C4MaterialReactions
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4MaterialReactions.cpp"
	LINK_ENGINE
)

add_test_target(C4ControlPresets
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4ControlPresets.cpp"
	LINK_ENGINE
)

add_test_target(C4GamepadDefaults
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4GamepadDefaults.cpp"
	LINK_ENGINE
)

# --- Free Game multi-root content resolution (spec freegame-real-player-states)
add_test_target(FreeGameEntry
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstFreeGameEntry.cpp"
	LINK_ENGINE
)

# --- Newest-savegame finder (spec save-continue)
add_test_target(SaveContinue
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstSaveContinue.cpp"
	LINK_ENGINE
)

# --- Offline pre-game options (spec pregame-options-parity) ----------------
add_test_target(OptionsOverride
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4GameOptions.cpp"
	LINK_ENGINE
)

# --- Slider-contract pinning test (spec world-generator-ux-rework) ---------
add_test_target(SliderContract
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstSliderContract.cpp"
	LINK_ENGINE
)

# --- Char-input-routing pin (seed-typed-entry defect, cycle 159) ----------
# Pure-capacity contract behind C4GUI::SpinBox::MaxTextLengthForRange: typed
# characters into a spinbox value field must never be silently clamped away
# because the value string fills the whole InsertText budget. Exercises the
# template's static sizing arithmetic without needing the GUI resource
# system (no Edit/Screen construction, no fonts).
add_test_target(CharInputRouting
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstCharInputRouting.cpp"
)

# --- Language-table regression test (spec translate-new-dialogs) -----------
add_test_target(LanguageTables
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstLanguageTables.cpp"
	LINK_ENGINE
	DEFINITIONS "LANG_SRC_DIR=\"${CMAKE_SOURCE_DIR}\""
)

# Python 3 for the smoke-test engine wrapper (tools/run_engine_headless.py)
# and the net-smoke drivers below. Hoisted above the first use: on a fresh
# configure ${PYTHON3} would still be unset at the add_test() calls.
find_program(PYTHON3 python3)

# The scenario lives in the content repo (sibling checkout); only register
# the smoke test when that file is actually present.
if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/OptionsOverride.c4s")
	add_test(NAME parameter_override_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 350
			--parameter TeamDist=Random --parameter RandomTeamCount=2
			--parameter TeamColors=1
			-s "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/OptionsOverride.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(parameter_override_smoke PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "OptionsOverride PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Rules=/Goals= --parameter override smoke (spec pregame-options-parity-2).
# Same EXISTS-guard + explicit-flags pattern as parameter_override_smoke above.
# NO Smoke suffix in the scenario name: the glob must not double-register it.
if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/RulesGoalsOverride.c4s")
	add_test(NAME rules_goals_override_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 350
			--parameter Rules=NMTT=1 --parameter Goals=MONE=1
			-s "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/RulesGoalsOverride.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(rules_goals_override_smoke PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "RulesGoalsOverride PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Winning-condition --parameter override smokes (spec
# adjustable-winning-conditions, cycle 114). Same EXISTS-guard +
# explicit-flags pattern as rules_goals_override_smoke above; NO Smoke
# suffix in the scenario names (the glob must not double-register them).
if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/WinCondOverride.c4s")
	add_test(NAME wincond_override_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 350
			--parameter CooperativeGoal=ValueGain --parameter ValueGain=2500
			--parameter Elimination=KillTheCaptain
			-s "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/WinCondOverride.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(wincond_override_smoke PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "WinCondOverride PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/WinCondMode.c4s")
	# Two-player melee smoke (plan correction 3): the Melee.c4d goal
	# self-destructs with fewer than 2 players (its IsFulfilled), so the
	# scenario runs with MaxPlayer=2 and joins TWO TestPlayer fixtures.
	# The wrapper copies each fixture to a temp .c4p (the engine writes
	# player state back on game over — never feed it the pristine file).
	add_test(NAME wincond_mode_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 350
			--parameter Mode=Melee
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			-s "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/WinCondMode.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(wincond_mode_smoke PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "WinCondMode PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- PlrStart Knowledge --parameter override smoke (roadmap
# blueprints-live-round): the override replaces the scenario's base
# [Player1] knowledge list (FLNT=1) with Knowledge=WMIL=1, and the smoke
# asserts the LIVE-round player knows WMIL and can build it. Same
# EXISTS-guard + explicit-flags pattern as wincond_mode_smoke above; NO
# Smoke suffix in the scenario name (the glob must not double-register it).
if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/BlueprintLive.c4s")
	add_test(NAME blueprint_live_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 350
			--parameter Knowledge=WMIL=1
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			-s "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/BlueprintLive.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(blueprint_live_smoke PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "BlueprintLive PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Jump-and-run climb release smoke (roadmap climb-drop-fix) -------------
# Pins the AutoStopDirectCom fix: a DFA_SCALE clonk holding a flint that
# receives COM_Dig lets go without dropping the item (no C4CMD_Drop
# fall-through) and no spurious delayed dig fires (LastCom clear on the
# let-go). NO Smoke suffix in the scenario name (the glob must not
# double-register it); the fixture-joined variant is registered explicitly.
if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/ClimbDigRelease.c4s")
	add_test(NAME climb_dig_release_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 350
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			-s "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/ClimbDigRelease.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(climb_dig_release_smoke PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "ClimbDigRelease PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Seed=/Amplitude= --parameter override smoke (spec landscape-generator-research).
# Relative-determinism driver: the map generator's output is machine/build-
# dependent (FP in the creator chain), so the pin is same-seed-equality across
# two runs + seed/amplitude sensitivity — never an absolute baked checksum.
if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/LandscapeSeed.c4s")
	add_test(NAME landscape_seed_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/landscape_seed_smoke.py"
			"$<TARGET_FILE:clonk>" "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/LandscapeSeed.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(landscape_seed_smoke PROPERTIES
		TIMEOUT 120
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "landscape_seed_smoke PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Headless scenario smoke harness -------------------------------------
# Discovers content/**/Tests.c4f/*Smoke.c4s scenarios and registers one
# CTest entry per scenario. See spec headless-scenario-smoke-harness.
#
# The glob is anchored at the workspace content/ directory (sibling of
# LegacyClonk/). New content packs add Tests.c4f/*Smoke.c4s scenarios and
# the glob picks them up at configure time — no edits to this file needed.

set(LEGACYCLONK_CONTENT_DIR "${CMAKE_SOURCE_DIR}/../content")

file(GLOB SMOKE_SCENARIOS
  "${LEGACYCLONK_CONTENT_DIR}/*/Tests.c4f/*Smoke.c4s"
  "${LEGACYCLONK_CONTENT_DIR}/*/*/Tests.c4f/*Smoke.c4s"
  "${LEGACYCLONK_CONTENT_DIR}/*/*/*/Tests.c4f/*Smoke.c4s"
  "${LEGACYCLONK_CONTENT_DIR}/*/*/*/*/Tests.c4f/*Smoke.c4s")

# Per-scenario pinned RNG seeds. Smoke scenarios whose assertions are
# sensitive to the game RNG (probabilistic physics like saltation hops)
# must run with a pinned Parameters.RandomSeed: the engine defaults an
# unpinned scenario's seed to time(nullptr) (C4GameParameters.cpp:424),
# so an unpinned smoke's pass/fail varies per run — DuneBurialSmoke
# flaked exactly this way on the Playtest lane (run 42, 2026-09-11:
# "no saltation embeds downwind (2 <= 2)"). The pinned seed makes the
# smoke deterministic per binary: a CI failure becomes locally
# reproducible, and a local pass predicts the CI outcome.
set(SMOKE_SEED_PIN_DuneBurialSmoke 368)
set(SMOKE_SEED_PIN_FirstLightSmoke 721)
set(SMOKE_SEED_PIN_FirstLightSoundSmoke 721)
set(SMOKE_SEED_PIN_DammbruchSmoke 124)
set(SMOKE_SEED_PIN_ReactionLabSmoke 1000)
set(SMOKE_SEED_PIN_SaltRoadStorySmoke 146)
set(SMOKE_SEED_PIN_EscapeSiphonSmoke 1471)
set(SMOKE_SEED_PIN_EscapeFurnaceSmoke 1472)
set(SMOKE_SEED_PIN_EscapeUndertowSmoke 1473)
set(SMOKE_SEED_PIN_SturmfrontSmoke 175)
set(SMOKE_SEED_PIN_AutoTasksSmoke 180)
set(SMOKE_SEED_PIN_FrontierSmoke 199)
set(SMOKE_SEED_PIN_WolfNightsSmoke 199)
set(SMOKE_SEED_PIN_StormMillSmoke 199)

foreach(scenario ${SMOKE_SCENARIOS})
  get_filename_component(scenario_name "${scenario}" NAME_WE)  # e.g. EventSmoke
  set(seed_pin_args "")
  if(DEFINED SMOKE_SEED_PIN_${scenario_name})
    set(seed_pin_args --parameter "Seed=${SMOKE_SEED_PIN_${scenario_name}}")
  endif()
  add_test(NAME "smoke_${scenario_name}"
    COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
            "$<TARGET_FILE:clonk>"
            --console --smoke-run 350 ${seed_pin_args}
            -s "${scenario}"
    WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
  set_tests_properties("smoke_${scenario_name}" PROPERTIES
    TIMEOUT 60
    LABELS "smoke"
    PASS_REGULAR_EXPRESSION "${scenario_name} PASS"
    FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endforeach()

# --- Frontier Outset boot gate (cycle 199, roadmap frontier-mvp) -----------
# Boots the REAL Outset.c4s (the Free Game pin) under --smoke-run 350 with
# one TestPlayer fixture and PASSes only when the dealt-card objective
# lines appear. The glob-registered smoke_FrontierSmoke covers the
# compressed mechanic proofs; this entry is the "start Frontier from the
# menu" leg (explicit-entry precedent: parameter_override_smoke).
if(EXISTS "${LEGACYCLONK_CONTENT_DIR}/Worlds.c4f/Outset.c4s/Script.c")
	add_test(NAME frontier_outset_boot
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 350
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			-s "${LEGACYCLONK_CONTENT_DIR}/Worlds.c4f/Outset.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(frontier_outset_boot PROPERTIES
		TIMEOUT 90
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "CURRENT GOAL"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Frontier Outset long-boot gate (cycle 208, v378 audit M2) -----------
# Permanent gate for the v378-shipped Outset flood (40-px rise, C3 verdict,
# recede): boots the real Outset.c4s for the full 16000-tick run and asserts
# the FRMT flood telemetry so the next release cites a gate, not the
# scratch/205/t2c/long-boot.log recording. Value pins from that recording
# (natural pace 432 s: wy_peak=170, wy_end=210, verdict lost, outcome LOSE,
# exit 0). D1 (cycle 208): FRMT lines identical at --frame-rate-cap 1000
# (16 s vs 431 s wall; pxs_perf_gate precedent), so the gate runs capped.
# Driver owns launch/capture/assertions (menu_walk_smoke, scenario_link_gate
# precedent); CTest PASS/FAIL regexes are defense-in-depth.
if(EXISTS "${LEGACYCLONK_CONTENT_DIR}/Worlds.c4f/Outset.c4s/Script.c")
	add_test(NAME frontier_outset_longboot
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/frontier_outset_longboot_gate.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--content-dir" "${LEGACYCLONK_CONTENT_DIR}"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(frontier_outset_longboot PROPERTIES
		TIMEOUT 600
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "frontier_outset_longboot PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Frontier Outset construct gate (cycle 210, frontier-cards-c5c6) ------
# Permanent gate for the C5/C6 winning leg: drives the REAL Outset.c4s
# round headless through the engine's stdin /script seam (one TestPlayer
# plus a parked second crew clonk plus SGNL lightning-decoy poles) and
# PASSes only when BOTH dealt cards resolve won in ONE round:
#   FRMT:c5_resolved=won crew=1  AND  FRMT:c6_resolved=won mill=1 granary=1
# Pinned seed 201 (cycle-210 probes: 19/19 across drive cadences; the
# decoys remove the storm-lightning RNG lottery that flips mill/granary
# burns run to run). Driver owns launch/capture/assertions (longboot
# precedent); CTest PASS/FAIL regexes are defense-in-depth.
if(EXISTS "${LEGACYCLONK_CONTENT_DIR}/Worlds.c4f/Outset.c4s/Script.c")
	add_test(NAME frontier_outset_construct_gate
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/frontier_outset_construct_gate.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--content-dir" "${LEGACYCLONK_CONTENT_DIR}"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(frontier_outset_construct_gate PROPERTIES
		TIMEOUT 600
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "frontier_outset_construct_gate PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Menu-walk smoke (spec 2026-09-17-menu-walk-smoke, cycle 131) -----------
# Six-leg new-player-walk driver (tools/menu_walk_smoke.py). Console builds
# only (headless engine spawns). Deliberately NO FAIL_REGULAR_EXPRESSION:
# ColonyBay logs pre-existing [error] DebugLog lines (verified at base); the
# driver owns fail detection + exit codes. Content EXISTS guard mirrors
# parameter_override_smoke: the Autobuild CI has no content checkout, and the
# A2/A3/A5/A6 legs need the content tree.
if(PYTHON3 AND USE_CONSOLE
   AND EXISTS "${CMAKE_SOURCE_DIR}/tools/menu_walk_smoke.py"
   AND EXISTS "${LEGACYCLONK_CONTENT_DIR}")
	add_test(NAME menu_walk_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/menu_walk_smoke.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--content-dir" "${LEGACYCLONK_CONTENT_DIR}"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(menu_walk_smoke PROPERTIES
		# Worst-case driver runtime ~240 s: A1 up to 4x15 s HTTP + 3 engine
		# spawns x 60 s RUN_TIMEOUT (GLM review finding 2). Typical runtime is
		# ~20 s; the headroom only matters on loaded CI runners.
		TIMEOUT 240
		LABELS "smoke;menuwalk"
		PASS_REGULAR_EXPRESSION "menu_walk_smoke PASS")
endif()

# --- scenario_link_gate (spec tutorial-guidance-live, cycle 142) -----------
# Three-tier link gate: W1 pins kTutorial01Path (src/C4StartupWelcomeDlg.cpp),
# W2 boots Tutorial01 exactly as the welcome dialog will (post-fix), L sweeps
# Tutorial02-10 + the 14 clean Worlds.c4f scenarios (CaveExplorer/Stormwatch
# on the driver's printed skip list). The driver owns fail detection and
# prints the aggregate `scenario_link_gate PASS` line.
if(PYTHON3 AND USE_CONSOLE
   AND EXISTS "${CMAKE_SOURCE_DIR}/tools/scenario_link_gate.py"
   AND EXISTS "${LEGACYCLONK_CONTENT_DIR}")
	add_test(NAME scenario_link_gate
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/scenario_link_gate.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--content-dir" "${LEGACYCLONK_CONTENT_DIR}"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(scenario_link_gate PROPERTIES
		TIMEOUT 600
		LABELS "smoke;link"
		PASS_REGULAR_EXPRESSION "scenario_link_gate PASS")
endif()

# --- PXS perf gate (spec pxs-particle-budget-benchmark) --------------------
# Raw-throughput companion to smoke_PXSPerfSmoke: --frame-rate-cap 1000
# lifts the 28 ms/tick pace so per-window wall-clock reflects simulation
# cost (spec frame-rate-cap-engine-option, cycle 64).
# EXISTS guard: the Autobuild CI has no content checkout — without it the
# entry would point at a missing scenario and fail on every leg.
if(NOT USE_SANITIZER AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/PXSPerfSmoke.c4s")
	add_test(NAME pxs_perf_gate
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>"
			--console --smoke-run 350 --frame-rate-cap 1000
			-s "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/PXSPerfSmoke.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(pxs_perf_gate PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "PXSPerfSmoke PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Mobilization perf gate (spec sim-performance-budget, cycle 118) ----
# Raw-throughput companion to smoke_MobilizationSmoke: --frame-rate-cap
# 1000 lifts the 28 ms/tick pace so per-window wall-clock reflects the
# mobilization paths (breach/blast/deposit churn + mover transport).
if(NOT USE_SANITIZER AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/MobilizationSmoke.c4s")
	add_test(NAME mobilization_perf_gate
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>"
			--console --smoke-run 350 --frame-rate-cap 1000
			-s "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/MobilizationSmoke.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(mobilization_perf_gate PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "MobilizationSmoke PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- LavaWallLong D3500 dig-delay pin (spec pixel-physics-regression-pin) --
# The only Ashes-Instable discriminator (cycle-92 MUT-3). 3900 ticks exceeds
# the glob's hardcoded --smoke-run 350, so an explicit entry is required
# (pxs_perf_gate precedent). The scenario name has NO Smoke suffix
# (parameter_override_smoke precedent): a *Smoke.c4s name would be
# double-registered by the glob at 350 ticks — permanently RED.
if(NOT USE_SANITIZER AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/LavaWallLong.c4s")
	add_test(NAME lava_wall_long_gate
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>"
			--console --smoke-run 3900 --frame-rate-cap 1000
			-s "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/LavaWallLong.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(lava_wall_long_gate PROPERTIES
		TIMEOUT 90
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "LavaWallLong PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# ASan/UBSan inflate wall-clock 2-5x — a wall-clock gate would flake.
# The glob still registers smoke_PXSPerfSmoke before this point, so
# `if(TEST ...)` resolves; disable it under sanitizers.
if(USE_SANITIZER)
	if(TEST smoke_PXSPerfSmoke)
		set_tests_properties(smoke_PXSPerfSmoke PROPERTIES DISABLED TRUE)
	endif()
	if(TEST smoke_MobilizationSmoke)
		set_tests_properties(smoke_MobilizationSmoke PROPERTIES DISABLED TRUE)
	endif()
endif()

# Symlink content packs into the build directory so the engine (CWD=build/
# after chdir) can resolve bare definition names like "WeatherEvents.c4d"
# during smoke runs.
file(GLOB CONTENT_PACKS
  "${LEGACYCLONK_CONTENT_DIR}/*.c4d"
  "${LEGACYCLONK_CONTENT_DIR}/*.c4f"
  "${LEGACYCLONK_CONTENT_DIR}/*.c4g")
foreach(pack ${CONTENT_PACKS})
  get_filename_component(pack_name "${pack}" NAME)
  set(link_target "${CMAKE_BINARY_DIR}/${pack_name}")
  if(NOT EXISTS "${link_target}")
    file(CREATE_LINK "${pack}" "${link_target}" SYMBOLIC)
  endif()
endforeach()

# --- CCAN smoke gate -------------------------------------------------------
# Two-tier gate for curated CCAN packs (see spec ccan-smoke-gate).
# Tier A: structural probe via `c4group <pack> -l` (sub-second).
# Tier B: engine-load smoke via `clonk --smoke-run 350` (seconds).

# Resolve c4group: $C4GROUP env, then ${CMAKE_BINARY_DIR}/c4group.
set(_c4group_candidate "$ENV{C4GROUP}")
if(NOT _c4group_candidate OR NOT EXISTS "${_c4group_candidate}")
  set(_c4group_candidate "${CMAKE_BINARY_DIR}/c4group")
endif()

if(EXISTS "${_c4group_candidate}")
  set(CCAN_C4GROUP "${_c4group_candidate}")
else()
  message(WARNING "c4group not found; skipping tier-A (ccan_struct_*) registration. Build c4group via `cmake --build build` before running tier A.")
  set(CCAN_C4GROUP "")
endif()

# Tier A — structural probe (c4group -l)
file(GLOB CCAN_STRUCT_MARKERS
  "${CMAKE_SOURCE_DIR}/../content-community/*/Tests.c4f/*Struct.txt")
foreach(marker ${CCAN_STRUCT_MARKERS})
  file(READ "${marker}" _pack_path)
  string(STRIP "${_pack_path}" _pack_path)
  get_filename_component(_struct_name "${marker}" NAME_WE)
  string(REPLACE "Struct" "" _pack_name "${_struct_name}")
  if(CCAN_C4GROUP)
    add_test(NAME "ccan_struct_${_pack_name}"
      COMMAND "${CCAN_C4GROUP}" "${_pack_path}" "-l"
      WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
    set_tests_properties("ccan_struct_${_pack_name}" PROPERTIES
      TIMEOUT 30
      LABELS "ccan;ccan_struct")
  endif()
endforeach()

# Tier B — engine-load smoke (clonk --smoke-run 350)
file(GLOB CCAN_SMOKE_SCENARIOS
  "${CMAKE_SOURCE_DIR}/../content-community/*/Tests.c4f/*Smoke.c4s")
foreach(scenario ${CCAN_SMOKE_SCENARIOS})
  get_filename_component(scenario_name "${scenario}" NAME_WE)
  string(REPLACE "Smoke" "" pack_name "${scenario_name}")
  add_test(NAME "ccan_smoke_${pack_name}"
    COMMAND "$<TARGET_FILE:clonk>"
            --console --smoke-run 350
            -s "${scenario}"
    WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
  set_tests_properties("ccan_smoke_${pack_name}" PROPERTIES
    TIMEOUT 60
    LABELS "ccan;ccan_smoke;smoke"
    PASS_REGULAR_EXPRESSION "${pack_name} PASS"
    FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endforeach()

# Symlink content-community packs into the build dir so bare definition
# names like "DWMedalSystem.c4d" resolve during smoke runs. Covers
# top-level packs and sub-defs inside .c4s/.c4f packs.
file(GLOB CCAN_COMMUNITY_PACKS
  "${CMAKE_SOURCE_DIR}/../content-community/*/*.c4d"
  "${CMAKE_SOURCE_DIR}/../content-community/*/*.c4f"
  "${CMAKE_SOURCE_DIR}/../content-community/*/*.c4s"
  "${CMAKE_SOURCE_DIR}/../content-community/*/*/*.c4d"
  "${CMAKE_SOURCE_DIR}/../content-community/*/*/*.c4f"
  "${CMAKE_SOURCE_DIR}/../content-community/*/*/*.c4s")
foreach(pack ${CCAN_COMMUNITY_PACKS})
  get_filename_component(pack_name "${pack}" NAME)
  set(link_target "${CMAKE_BINARY_DIR}/${pack_name}")
  if(NOT EXISTS "${link_target}")
    file(CREATE_LINK "${pack}" "${link_target}" SYMBOLIC)
  endif()
endforeach()

# --- Engine unit tests for the SmokeRunTicks state semantics -------------
add_test_target(SmokeRunFlag
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstSmokeRunFlag.cpp"
	LINK_ENGINE
)
add_test_target(SelectionLimits
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstSelectionLimits.cpp"
	LINK_ENGINE
)

# --- Scenario Origin parent-folder gate (cycle 174) ------------------------
add_test_target(ParentFolderGating
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstParentFolderGating.cpp"
	LINK_ENGINE
)

# --- Network desync CI smoke ---------------------------------------------
# See spec network-desync-ci-smoke. Runs two headless engine instances on
# localhost with tc netem impairment (Linux only), asserting no desync fatal
# errors over N ticks.
#
# Console builds only: the smoke harness runs the engine binary directly,
# and GUI builds (WITH_DEVELOPER_MODE=On) call gtk_init at startup, which
# exits(1) on headless CI runners before any smoke output.
find_program(TC tc)

if (PYTHON3 AND USE_CONSOLE)
	set(tc_args "")
	if (TC)
		list(APPEND tc_args "--tc-program" "${TC}")
	endif()
	add_test(NAME net_desync_smoke
		COMMAND "${PYTHON3}"
			"${CMAKE_SOURCE_DIR}/tools/net_desync_smoke.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--scenario" "${CMAKE_SOURCE_DIR}/tests/fixtures/NetSyncSmoke.c4s"
			"--ticks" "2000"
			"--timeout" "120"
			"--state-hash"
			${tc_args}
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(net_desync_smoke PROPERTIES
		TIMEOUT 180
		LABELS "network;smoke"
		RUN_SERIAL TRUE)
endif()

# --- Network abort freeze CI smoke -----------------------------------------
# See spec net-abort-freeze-fix. Host+client on loopback against a local
# mock league server (instant Start, delayed End); /close on host stdin
# triggers the abort teardown. Asserts the teardown wall-clock stays
# under bound.
if (PYTHON3 AND USE_CONSOLE)
	add_test(NAME net_abort_smoke
		COMMAND "${PYTHON3}"
			"${CMAKE_SOURCE_DIR}/tools/net_abort_smoke.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--scenario" "${CMAKE_SOURCE_DIR}/tests/fixtures/NetSyncSmoke.c4s"
			"--mock-end-delay" "5.0"
			"--assert-ms" "4000"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(net_abort_smoke PROPERTIES
		TIMEOUT 120
		LABELS "network;smoke"
		RUN_SERIAL TRUE)
endif()

# --- Join-failure message pin (upstream #91, cycle 153) --------------------
# Console builds only (headless engine spawn, same reason as the network
# smokes above). The driver launches the engine with a bogus clonk://
# direct-join address (RFC 2606 .invalid TLD = fast NXDOMAIN) and asserts
# (a) the engine exits non-zero and (b) the localized join-failure reason
# line appears in the engine log. Hermetic child env (temp HOME + C
# locale) pins the language so a persisted ~/.legacyclonk/config or a
# de_DE runner cannot flip the reason text the assertion greps for.
if (PYTHON3 AND USE_CONSOLE)
	add_test(NAME join_failure_message_pin
		COMMAND "${PYTHON3}"
			"${CMAKE_SOURCE_DIR}/tools/join_failure_message_pin.py"
			"--engine" "$<TARGET_FILE:clonk>"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(join_failure_message_pin PROPERTIES
		# NXDOMAIN + engine startup complete in ~1s; headroom for loaded CI
		# runners and slow DNS resolver timeouts on the 20s query turning
		# point (the engine re-fails at the timeout LogFatal site).
		TIMEOUT 120
		LABELS "network")
endif()

# --- Network settings-sync CI smoke ---------------------------------------
# See spec net-preround-settings-fix. Two headless engines on loopback;
# asserts host->client landscape/rules/goals/seed sync via JoinData.
if (PYTHON3 AND USE_CONSOLE)
	add_test(NAME net_settings_sync_smoke
		COMMAND "${PYTHON3}"
			"${CMAKE_SOURCE_DIR}/tools/net_settings_sync_smoke.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--scenario" "${CMAKE_SOURCE_DIR}/tests/fixtures/NetSettingsSync.c4s"
			"--ticks" "2000"
			"--timeout" "100"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(net_settings_sync_smoke PROPERTIES
		TIMEOUT 300
		LABELS "network;smoke"
		RUN_SERIAL TRUE)
endif()

# --- Live reconnect smoke ----------------------------------------------
# See spec live-network-test-harness. Boots two headless engine instances
# on loopback, partitions the client via tc-by-port (or SIGSTOP fallback),
# and verifies the disconnect -> dormancy -> PID_Reconn -> snapshot-restore
# -> state-hash-convergence path.
#
# Console builds only, for the same headless-engine reason as above.
if (PYTHON3 AND USE_CONSOLE)
	set(live_reconn_tc_args "")
	if (TC)
		list(APPEND live_reconn_tc_args "--tc-program" "${TC}")
	endif()
	add_test(NAME live_reconnect_smoke
		COMMAND "${PYTHON3}"
			"${CMAKE_SOURCE_DIR}/tools/live_reconnect_smoke.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--scenario" "${CMAKE_SOURCE_DIR}/tests/fixtures/NetSyncSmoke.c4s"
			"--ticks" "2000"
			"--timeout" "120"
			"--state-hash"
			${live_reconn_tc_args}
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(live_reconnect_smoke PROPERTIES
		TIMEOUT 180
		LABELS "network;smoke"
		RUN_SERIAL TRUE)

	# Default-config variant: omits ReconnectEnabled from the temp
	# config so the engine runs on the compiled default -- the flip's
	# own regression (spec reconnect-default-on-soak, cycle 122).
	add_test(NAME live_reconnect_smoke_default_config
		COMMAND "${PYTHON3}"
			"${CMAKE_SOURCE_DIR}/tools/live_reconnect_smoke.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--scenario" "${CMAKE_SOURCE_DIR}/tests/fixtures/NetSyncSmoke.c4s"
			"--ticks" "2000" "--timeout" "120" "--state-hash" "--default-config"
			${live_reconn_tc_args}
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(live_reconnect_smoke_default_config PROPERTIES
		TIMEOUT 180 LABELS "network;smoke" RUN_SERIAL TRUE)
endif()

# --- Placeholder-art lint (spec hostile-object-bugfix, cycle 93) -----------
# Fails CI when a def's ActMap facet region is a single flat color block
# (>= 16 opaque px, one RGB) — the cycle-70 placeholder-art bug class.
# The Autobuild CI has no content checkout; the EXISTS guard mirrors the
# parameter_override_smoke precedent and skips registration there.
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}")
	add_test(NAME content_gfx_lint
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/lint_placeholder_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}")
	set_tests_properties(content_gfx_lint PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- Siege stage-art gate (spec siege-flagship, cycle 181) -----------------
# Reddens when the SiegeGate stage sheets stop being pairwise byte-distinct,
# the two BoilingOilCauldron copies drift apart, or any shipped siege sheet
# regresses to a retired placeholder hash. EXISTS guard mirrors
# content_gfx_lint: Autobuild CI has no content checkout.
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}")
	add_test(NAME siege_stage_gfx
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/check_siege_stage_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}")
	set_tests_properties(siege_stage_gfx PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- Release-content lint (spec release-content-groups-lint, cycle 96) ------
# Models the release manifest against the content tree: every shipped
# scenario's DefinitionN refs must resolve to shipped packs. Autobuild CI
# has no content checkout; the EXISTS guard mirrors content_gfx_lint above.
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}")
	add_test(NAME content_release_lint
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/lint_release_content.py"
			"${CMAKE_SOURCE_DIR}/autobuild/ci.toml"
			"${LEGACYCLONK_CONTENT_DIR}")
	set_tests_properties(content_release_lint PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- clonkgfx library selftest (spec clonk-gfx-skill, cycle 99) -----------
if(PYTHON3)
	add_test(NAME clonkgfx_selftest
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/test_clonkgfx.py")
	set_tests_properties(clonkgfx_selftest PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- classicart raster-pipeline selftest (spec art-pipeline-v3, cycle 144)
# Cross-validates the full-filter decoder against PIL on the three in-tree
# donor sheets and exercises op determinism + encode round-trip. The donor
# EXISTS guard mirrors content_gfx_lint: Autobuild CI has no content
# checkout and would otherwise redden this entry.
if(PYTHON3 AND EXISTS "${CMAKE_SOURCE_DIR}/../content/Objects.c4d/Vehicles.c4d/Sailboat.c4d/Graphics.png")
	add_test(NAME classicart_selftest
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/classicart.py" --selftest)
	set_tests_properties(classicart_selftest PROPERTIES TIMEOUT 120 LABELS "lint")
endif()

# --- Generator --check byte gates (spec clonk-gfx-skill, cycle 99) --------
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/Scorpion.c4d/Graphics.png")
	add_test(NAME gfx_check_scorpion
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_scorpion_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/Scorpion.c4d/Graphics.png" --check)
	set_tests_properties(gfx_check_scorpion PROPERTIES TIMEOUT 60 LABELS "lint")
endif()
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/Camel.c4d/Graphics.png")
	add_test(NAME gfx_check_camel
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_camel_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/Camel.c4d/Graphics.png" --check)
	set_tests_properties(gfx_check_camel PROPERTIES TIMEOUT 60 LABELS "lint")
endif()
# --- Windmill+Wing donor-art byte gate (spec art-pipeline-v3, cycle 144) --
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Structures.c4d/Windmill.c4d/Graphics.png")
	add_test(NAME gfx_check_windmill
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_windmill_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Structures.c4d/Windmill.c4d/Graphics.png"
			"${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Structures.c4d/Windmill.c4d/Wing.c4d/Graphics.png" --check)
	set_tests_properties(gfx_check_windmill PROPERTIES TIMEOUT 60 LABELS "lint")
endif()
# --- Vision judge serialization (spec vision-judge-serialization, cycle 121)
# Shared-lock contract: every ollama-judge CTest entry MUST carry
# RESOURCE_LOCK "qwen_judge" (the ctest scheduler never starts two of
# them at once — the wait is pre-spawn, burning no TIMEOUT clock) AND
# the explicit "vision" label. Applies to the three GPU entries:
# vision_qa_scorpion, vision_qa_agriculture_lobster, playtest_vision.
# VERIFIED EXEMPTION: playtest_sweep takes no judge lock —
# tools/playtest_sweep.py has zero ollama/qwen/judge references (engine
# subprocesses only; labels playtest;smoke) — do NOT "fix" it later.
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/Scorpion.c4d/Graphics.png")
	add_test(NAME vision_qa_scorpion
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/vision_qa.py"
			--image "${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/Scorpion.c4d/Graphics.png"
			--facet 0,0,24,14 --phases 6 --gate-mode feature
			--json "${CMAKE_BINARY_DIR}/vision_qa_scorpion.json")
	set_tests_properties(vision_qa_scorpion PROPERTIES
		TIMEOUT 5400  # 6-phase probe: ~50-72 judge calls x 40-60s (cycle 125)
		RESOURCE_LOCK "qwen_judge"
		LABELS "vision_qa;vision;lint"
		PASS_REGULAR_EXPRESSION "GATE PASS"
		FAIL_REGULAR_EXPRESSION "GATE FAIL|ORACLE FAIL"
		SKIP_REGULAR_EXPRESSION "^SKIP: ")
endif()

# --- Agriculture batch --check byte gates (spec agriculture-art-batch,
# cycle 110) --------------------------------------------------------------
set(AGRI_DEFS
	"Animals.c4d/Lobster.c4d"
	"Items.c4d/CookedLobster.c4d"
	"Items.c4d/DeadLobster.c4d"
	"Items.c4d/Pearl.c4d"
	"Structures.c4d/Oyster.c4d"
	"Structures.c4d/TidalPool.c4d"
	"Tools.c4d/LobsterTrap.c4d"
	"Vegetation.c4d/Wheat.c4d"
	"Vegetation.c4d/AppleTree.c4d"
	"Tools.c4d/FishTrap.c4d"
	"Tools.c4d/Sickle.c4d"
	"Vegetation.c4d/WheatSeed.c4d"
	"Items.c4d/Foodstuff.c4d/WheatSheaf.c4d"
	"Items.c4d/Foodstuff.c4d/SmokedFish.c4d"
	"Structures.c4d/Smokehouse.c4d"
	"Tools.c4d/FishingNet.c4d"
	"Tools.c4d/FishingRod.c4d"
	"Items.c4d/Foodstuff.c4d/Apple.c4d"
	"Vegetation.c4d/AppleSeed.c4d")
foreach(agri_def ${AGRI_DEFS})
	get_filename_component(agri_def_name "${agri_def}" NAME_WE)
	if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/${agri_def}/Graphics.png")
		add_test(NAME "gfx_check_${agri_def_name}"
			COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_agriculture_gfx.py" "${agri_def_name}"
				"${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/${agri_def}/Graphics.png" --check)
		set_tests_properties("gfx_check_${agri_def_name}" PROPERTIES TIMEOUT 60 LABELS "lint")
	endif()
endforeach()

# --- FirstLight mission scenario gate + long behavior smoke (spec
# firstlight-visible, cycle 168) --------------------------------------------
# Task-4 measurement (.opencode/scratch/168/balance/timeline.md): with the
# shipped Climate=50,0 the seasonal winter froze the homestead pond from
# ~frame 10640, drying the fish trap before the second audit — the ledger
# win (frame 12600) was UNREACHABLE in every run. The shipped fix is the
# mission's Scenario.txt [Weather] Climate=50,0 -> 0,0 (content commit
# 46c94690), and the winnable-kit fix is Script.c -> 6 seeds + build
# materials (content commit, cycle 168 critic FIX-NOW). No CTest read the
# mission files before this block, so the fixes were unpinned. Two gates
# close the gap:
#   (a) firstlight_scenario_gate — mechanical file gate: the shipped mission
#       keeps Climate=0,0 and an empty HomeBaseMaterial/Production section,
#       and Script.c's workbench kit carries exactly 6 AGWS, 14 WOOD, 1 METL
#       and NO ROPE contents (the as-shipped winnable-kit contract, cycle-168
#       critic FIX-NOW 2: rope work was re-scoped to timber because Rope.c4d
#       is not loaded by this mission's def set — CreateContents(ROPE) was a
#       silent no-op that stranded the windmill's rope leg at "0/1"). It also
#       pins the components contract: every component id named by the
#       Windmill/Smokehouse DefCore Components= lines must be one of
#       WOOD/METL (would have caught both the old CLNK id and the ROPE id;
#       catches reverts of the fixes).
#   (b) firstlight_climate_smoke — behavior pin: plays FirstLight's exact
#       [Weather] with a carved pond + trap (balance-driver replica) and
#       asserts the pond stays liquid through the old freeze window
#       (trap InLiquid + Water census at frames 11200/12600/14700).
#       NO "Smoke" suffix in the scenario name: the glob hardcodes
#       --smoke-run 350 and would permanently RED the 16000-frame entry
#       (LavaWallLong precedent).
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Missions.c4f/FirstLight.c4s/Scenario.txt")
	add_test(NAME firstlight_scenario_gate
		COMMAND "${PYTHON3}" -c "import re,sys; scen=open('${LEGACYCLONK_CONTENT_DIR}/Missions.c4f/FirstLight.c4s/Scenario.txt').read(); scr=open('${LEGACYCLONK_CONTENT_DIR}/Missions.c4f/FirstLight.c4s/Script.c').read(); wm=open('${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Structures.c4d/Windmill.c4d/DefCore.txt').read(); sm=open('${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Structures.c4d/Smokehouse.c4d/DefCore.txt').read(); ids=[i.split('=')[0].strip() for ln in re.findall(r'^Components=(.+)$', wm, re.M)+re.findall(r'^Components=(.+)$', sm, re.M) for i in ln.split(';')]; ok=bool(re.search(r'^Climate=0,0$', scen, re.M)) and 'HomeBaseMaterial=' not in scen and 'HomeBaseProduction=' not in scen and scr.count('CreateContents(AGWS, pBase)')==6 and scr.count('CreateContents(WOOD, pBase)')==14 and scr.count('CreateContents(METL, pBase)')==1 and scr.count('CreateContents(ROPE, pBase)')==0 and bool(ids) and all(i in ('WOOD','METL') for i in ids); sys.exit(0 if ok else 1)")
	set_tests_properties(firstlight_scenario_gate PROPERTIES TIMEOUT 30 LABELS "lint")
endif()
if(NOT USE_SANITIZER AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Tests.c4f/FirstLightClimate.c4s")
	add_test(NAME firstlight_climate_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 16000 --frame-rate-cap 1000
			--parameter "Seed=721"
			-s "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Tests.c4f/FirstLightClimate.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(firstlight_climate_smoke PROPERTIES
		TIMEOUT 300
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "FirstLightClimate PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- ColonyBay coastal-fold gate (spec content-cleanup, cycle 192) ----------
# Mechanical file gate pinning the ColonyBay <- Coastal fold: the scenario
# must enroll Coastal.c4d, schedule the coastal TIDE/FOGG weather events,
# and place a Dock (DKST). Behavior stays covered by scenario_link_gate's
# L sweep (ColonyBay boots with zero unknown identifiers) plus this cycle's
# direct boot log (T3 evidence).
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Worlds.c4f/ColonyBay.c4s/Scenario.txt")
	add_test(NAME colonybay_fold_gate
		COMMAND "${PYTHON3}" -c "import re,sys; scen=open('${LEGACYCLONK_CONTENT_DIR}/Worlds.c4f/ColonyBay.c4s/Scenario.txt').read(); scr=open('${LEGACYCLONK_CONTENT_DIR}/Worlds.c4f/ColonyBay.c4s/Script.c').read(); ok=bool(re.search(r'Definition[0-9]+=Coastal[.]c4d', scen, re.M)) and bool(re.search(r'^Event=TIDE=', scen, re.M)) and bool(re.search(r'^Event=FOGG=', scen, re.M)) and 'CreateConstruction(DKST' in scr; sys.exit(0 if ok else 1)")
	set_tests_properties(colonybay_fold_gate PROPERTIES TIMEOUT 30 LABELS "lint")
endif()

# --- Trade-campaign merge gate (spec trade-campaign-merge, cycle 193) -----
# Mechanical file gate pinning the merged trade campaign: OceanTrade.c4f
# holds exactly the three scenarios with pairwise-distinct win conditions
# (SilkRoad MONE=8 wealth / SilkRoadOfTheSea VALG=10 settlement value /
# StormLane goal-less -- its win is the STLD 3-delivery race), the old
# SilkRoad.c4f pack is gone, and the six moved SilkRoad defs live in
# OceanTrade.c4d. RED-demonstrated pre-merge (.opencode/scratch/193/).
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/OceanTrade.c4f/StormLane.c4s/Scenario.txt")
	add_test(NAME trade_campaign_gate
		COMMAND "${PYTHON3}" -c "import os,re,sys; base='${LEGACYCLONK_CONTENT_DIR}'; otf=base+'/OceanTrade.c4f'; rd=lambda p: open(p).read() if os.path.exists(p) else ''; ok=True; ok = ok and sorted(d[:-4] for d in os.listdir(otf) if d.endswith('.c4s'))==['SilkRoad','SilkRoadOfTheSea','StormLane']; sr=rd(otf+'/SilkRoad.c4s/Scenario.txt'); sos=rd(otf+'/SilkRoadOfTheSea.c4s/Scenario.txt'); sl=rd(otf+'/StormLane.c4s/Scenario.txt'); ok = ok and re.findall(r'^Goals=(.*)$', sr, re.M)==['MONE=8'] and re.findall(r'^Goals=(.*)$', sos, re.M)==['VALG=10'] and re.findall(r'^Goals=(.*)$', sl, re.M)==[]; ok = ok and not os.path.exists(base+'/SilkRoad.c4f'); moved=[('AMB1','Ambush.c4d'),('BNDR','Boundary.c4d'),('MULE','Mule.c4d'),('RDDR','RaidDirector.c4d'),('RSPN','Respawner.c4d'),('TCHS','TeamChest.c4d')]; ok = ok and all(os.path.isdir(base+'/OceanTrade.c4d/'+d) and re.search(r'^id='+i+r'$', rd(base+'/OceanTrade.c4d/'+d+'/DefCore.txt'), re.M) for i,d in moved); sys.exit(0 if ok else 1)"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(trade_campaign_gate PROPERTIES TIMEOUT 30 LABELS "lint")
endif()

# --- ArenaChampions bot-round smoke + gates (spec arena-rotation,
# cycle 172) --------------------------------------------------------------
# The rotation check: a scripted 4-player bot round on the arena format
# must FINISH - ended BY THE GOAL, not by the smoke. ArenaBotRound.c4s
# stages the whole game in-script — four TestPlayer fixtures join two
# Random teams (2+2), a fighter clonk kills defending-crew clonks one per
# 35-frame step, every kill is asserted against the KILT goal's team-score
# locals (KillHook #appendto CLNK wiring), the RSPN respawner must
# demonstrably top the defender back up mid-round (charges 3->1), and the
# round is decided by KILT's own 35-frame Guard timer: the smoke polls the
# guard's fired flag (Local 1000) and logs "ArenaBotRound PASS" only once
# the goal has initiated the game-over itself (it never calls GameOver, so
# a KILT that fails to end the round fails loud instead of passing
# silently). The scenario lives in the def-pack Tests.c4f fixture home
# (WeatherEvents.c4d/Tests.c4f) because the browser lists *.c4f packs: a
# Tests.c4f inside the browsable ArenaChampions.c4f would leak test
# scenarios into the browser (menu_walk_smoke A6). NO "Smoke" suffix in
# the scenario name: the glob must not double-register it (wincond_mode_smoke
# precedent).
if(EXISTS "${LEGACYCLONK_CONTENT_DIR}/WeatherEvents.c4d/Tests.c4f/ArenaBotRound.c4s")
	add_test(NAME arena_bot_round_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 1600 --frame-rate-cap 1000
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			-s "${LEGACYCLONK_CONTENT_DIR}/WeatherEvents.c4d/Tests.c4f/ArenaBotRound.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(arena_bot_round_smoke PROPERTIES
		TIMEOUT 240
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "ArenaBotRound PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- Grabstein-Rallye bot-race smoke (cycle 200, roadmap grabstein-rallye-prototype) ---
# Four TestPlayer fixtures run the GrabsteinRallye course: the twin's
# GRBotDriver effect drives all four cursors (real MoveTo commands +
# stuck-watchdog DigFreeRect assist), the leader crossing the finish
# column hands the round to RACE+RVLR, and the twin asserts the dug-pixel
# telemetry (GRHM:lap=1 total>0). NO "Smoke" suffix in the scenario name:
# the Tests.c4f glob must not double-register it (arena_bot_round_smoke
# precedent) - a glob entry would run it playerless at 350 ticks,
# permanently RED. Seed 200 pins the seam layout (RNG-fed
# DrawMaterialQuad positions) and the PXS settles of the instable Sand.
# Phase B T3: the run is now a 3-leg cup (legs 1-2 re-arm the course,
# leg 3 ends engine-owned), so the budget grows from 2100 to 4200 ticks
# (3 legs ~2500 incl. the engine-end sequence, headroom x1.7).
if(EXISTS "${LEGACYCLONK_CONTENT_DIR}/WeatherEvents.c4d/Tests.c4f/GrabsteinRallyeRound.c4s")
	add_test(NAME grabstein_rallye_round_smoke
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 4200 --frame-rate-cap 1000
			--parameter "Seed=200"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			--smoke-player-fixture "${CMAKE_SOURCE_DIR}/tests/fixtures/TestPlayer.c4p"
			-s "${LEGACYCLONK_CONTENT_DIR}/WeatherEvents.c4d/Tests.c4f/GrabsteinRallyeRound.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(grabstein_rallye_round_smoke PROPERTIES
		TIMEOUT 240
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "GrabsteinRallyeRound PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# Mechanical file gate for the task-1/task-2 arena content contracts the
# bot smoke depends on (would have caught the KILC regression and the
# kitchen-sink store revert before any engine run):
#   (a) all five shipped maps pin exactly `Goals=MELE=1;KILT=1` and
#       `Rules=TACC=1` — no KILC (broken GetCaptain rule) may come back,
#       and both [PlayerN] sections carry the identical trimmed arena
#       store (HomeBaseMaterial/HomeBaseProduction literals);
#   (b) the Respawner DefCore keeps `TimerCall=Timer` (the team-wide
#       refill loop; dropping it kills the in-round respawn proof);
#   (c) Tidemark's tide keeps the DrawMaterialQuad column raise (the
#       rescue fix from task 2) — no plain DrawMaterial() 1px scrape.
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/ArenaChampions.c4f/Dustsprint.c4s/Scenario.txt")
	add_test(NAME arena_scenario_gate
		COMMAND "${PYTHON3}" -c "import sys; base='${LEGACYCLONK_CONTENT_DIR}/ArenaChampions.c4f/'; hbm='HomeBaseMaterial=CNKT=4;LOAM=4;WOOD=4;METL=2;FLNT=5;TFLN=3;GUNP=6;ARWP=1;XARP=1;BARL=2;CLNK=3;MCLK=1'; hbp='HomeBaseProduction=WOOD=1;FLNT=2;TFLN=1;GUNP=2;ARWP=1;XARP=1;CLNK=1'; ok=all([len([ln for ln in open(base+n+'.c4s/Scenario.txt').read().splitlines() if ln=='Goals=MELE=1;KILT=1'])==1 and len([ln for ln in open(base+n+'.c4s/Scenario.txt').read().splitlines() if ln=='Rules=TACC=1'])==1 and len([ln for ln in open(base+n+'.c4s/Scenario.txt').read().splitlines() if ln==hbm])==2 and len([ln for ln in open(base+n+'.c4s/Scenario.txt').read().splitlines() if ln==hbp])==2 for n in ['Dustsprint','Embervein','Frostlance','Mirrorwood','Tidemark']]); ok=ok and 'TimerCall=Timer' in open(base+'Objects.c4d/Respawner.c4d/DefCore.txt').read(); ok=ok and 'DrawMaterialQuad' in open(base+'Tidemark.c4s/Script.c').read() and 'DrawMaterial(' not in open(base+'Tidemark.c4s/Script.c').read(); sys.exit(0 if ok else 1)"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(arena_scenario_gate PROPERTIES TIMEOUT 30 LABELS "lint")
endif()

# Byte gate for the deterministic KillTarget/KillHook icon art
# (tools/gen_arena_gfx.py --check): the committed Graphics.png files must
# byte-match the generator output (gen_desert_gfx.py gfx_check_* pattern).
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/ArenaChampions.c4f/Objects.c4d/KillTarget.c4d/Graphics.png")
	add_test(NAME gfx_check_KillTarget
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_arena_gfx.py" --check
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(gfx_check_KillTarget PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Animals.c4d/Lobster.c4d/Graphics.png")
	add_test(NAME vision_qa_agriculture_lobster
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/vision_qa.py"
			--image "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Animals.c4d/Lobster.c4d/Graphics.png"
			--facet 0,0,16,12 --phases 2 --scale 8 --gate-mode feature
			--json "${CMAKE_BINARY_DIR}/vision_qa_agriculture_lobster.json")
	set_tests_properties(vision_qa_agriculture_lobster PROPERTIES
		TIMEOUT 2400
		RESOURCE_LOCK "qwen_judge"
		LABELS "vision_qa;vision;lint"
		PASS_REGULAR_EXPRESSION "GATE PASS"
		FAIL_REGULAR_EXPRESSION "GATE FAIL|ORACLE FAIL"
		SKIP_REGULAR_EXPRESSION "^SKIP: ")
endif()

# --- Desert batch --check byte gates (spec placeholder-art-debt-drive-down,
# cycle 100) --------------------------------------------------------------
foreach(def DatePalm Date Oasis Quarry Quicksand SandDrift SandstoneBlock)
	if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/${def}.c4d/Graphics.png")
		add_test(NAME "gfx_check_${def}"
			COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_desert_gfx.py" "${def}"
				"${LEGACYCLONK_CONTENT_DIR}/Desert.c4d/${def}.c4d/Graphics.png" --check)
		set_tests_properties("gfx_check_${def}" PROPERTIES TIMEOUT 60 LABELS "lint")
	endif()
endforeach()

# --- Cog donor-art byte gate (spec art-pipeline-v3, cycle 144) ------------
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/OceanTrade.c4d/Cog.c4d/Graphics.png")
	add_test(NAME gfx_check_cog
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_cog_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/OceanTrade.c4d/Cog.c4d/Graphics.png" --check)
	set_tests_properties(gfx_check_cog PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- Saltpan + Piratesloop art byte gates (spec trade-campaign-merge,
# cycle 193) -- gen_<def>_gfx.py --check must byte-match the committed PNGs.
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/TradeGoods.c4d/SaltPan.c4d/Graphics.png")
	add_test(NAME gfx_check_saltpan
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_saltpan_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/TradeGoods.c4d/SaltPan.c4d/Graphics.png" --check
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(gfx_check_saltpan PROPERTIES TIMEOUT 60 LABELS "lint")
endif()
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/OceanTrade.c4d/PirateSloop.c4d/Graphics.png")
	add_test(NAME gfx_check_piratesloop
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_piratesloop_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/OceanTrade.c4d/PirateSloop.c4d/Graphics.png" --check
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(gfx_check_piratesloop PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- Dock art byte gate (cycle 194, release blocker v376: the Colony Bay
# dock was invisible, a 96-byte transparent placeholder; the committed
# Graphics.png must byte-match gen_dock_gfx.py --check output).
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Coastal.c4d/Dock.c4d/Graphics.png")
	add_test(NAME gfx_check_dock
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_dock_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/Coastal.c4d/Dock.c4d/Graphics.png" --check
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(gfx_check_dock PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- Lighthouse art byte gate (cycle 196, frontier-mvp ART-PREREQ LHGT:
# the last invisible Coastal def was the beacon tower, a 96-byte
# transparent placeholder; the committed Graphics.png must byte-match
# gen_lighthouse_gfx.py --check output).
if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Coastal.c4d/Lighthouse.c4d/Graphics.png")
	add_test(NAME gfx_check_lighthouse
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_lighthouse_gfx.py"
			"${LEGACYCLONK_CONTENT_DIR}/Coastal.c4d/Lighthouse.c4d/Graphics.png" --check
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(gfx_check_lighthouse PROPERTIES TIMEOUT 60 LABELS "lint")
endif()

# --- Playtest sweep (spec scenario-playtest-harness, cycle 97) -----------
# Runs every shipped playtest scenario (ci.toml [groups.content] set,
# minus Tests.c4f) headless for N ticks via tools/playtest_sweep.py.
# Same EXISTS guard as content_release_lint above: Autobuild CI has no
# content checkout.
if (PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}")
	add_test(NAME playtest_sweep
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/playtest_sweep.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--content-dir" "${LEGACYCLONK_CONTENT_DIR}"
			"--ci-toml" "${CMAKE_SOURCE_DIR}/autobuild/ci.toml"
			"--report" "${CMAKE_BINARY_DIR}/playtest_sweep_report.tsv"
			"--log-dir" "${CMAKE_BINARY_DIR}"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(playtest_sweep PROPERTIES
		TIMEOUT 900
		LABELS "playtest;smoke")
endif()

# --- scenario_log_sweep (spec scenario-log-clean-sweep, cycle 173) --------
# Zero-script-error gate on the shipped scenario roster: boots the fixed
# recon-affected set (every scenario that logged `[error]` on the
# 2026-09-26 recon — Fantasy x4, FarWorlds x4, Knights x3, SilkRoad,
# Worlds CaveExplorer+Stormwatch, Races x3, Tutorial 01/02/06/07) headless
# and fails on any engine `[error]` line (--tick 70, per-scenario 350 for
# the runtime-exercising entries: SiegeOfHighKeep FindObject storm ~frame
# 44, Stormwatch CrisisDirector ~70, Tutorial02/06/07). EXCLUSIONS —
# pinned here because they cannot be swept to zero today: Hazard.c4f (13
# scenarios; owner directive 2026-09-18 — "not interested in the eke and
# hazard stuff"), the root stray content/SiegeRange.c4s (content-cleanup's
# territory — owns the FindObject int-arg x26 cluster) and
# Tutorial.c4f/Tutorial03+04 (ancient pre-#strict eq""/goto() scripts
# needing full rewrites; deferred follow-up). --full extends the sweep to
# every shipped content/**/*.c4s (Tests.c4f pruned) with those exclusions
# skipped-and-reported (106 pass / 16 skip on e8b0ef98 content). The
# driver owns fail detection and prints the aggregate
# `scenario_log_sweep PASS` line. TIMEOUT: measured 5.4 s via ctest at 4
# concurrent engines (x2 headroom ~11 s); 60 s covers ~5x-slower CI.
if(PYTHON3 AND EXISTS "${CMAKE_SOURCE_DIR}/tools/scenario_log_sweep.py"
   AND EXISTS "${LEGACYCLONK_CONTENT_DIR}")
	add_test(NAME scenario_log_sweep
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/scenario_log_sweep.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--content" "${LEGACYCLONK_CONTENT_DIR}"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(scenario_log_sweep PROPERTIES
		TIMEOUT 60
		LABELS "lint"
		PASS_REGULAR_EXPRESSION "scenario_log_sweep PASS")
endif()

# --- Playtest vision judge (spec playtest-vision-tier2, cycle 108) --------
# tools/playtest_vision.py spawns the console engine with --screenshot-at,
# validates the PNG + SceneTruth sidecar deterministically (judge-independent
# RED layer: artifact faults print "FAIL: artifact ..." and exit 1), and only
# then contacts the ollama judge. The judge (ollama) is absent on CI runners,
# so after the engine-side capture + deterministic artifact validation the
# entry prints "SKIP: ..." and exits 0; SKIP_REGULAR_EXPRESSION below makes
# ctest count the entry as skipped (still exit 0) — CI stays green without
# ollama. The loop machine runs --gate-mode feature/full manually for real
# gating; advisory is the default so verdicts are recorded even when a judge
# exists.
if(PYTHON3 AND USE_CONSOLE AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/WeatherEvents.c4d/Tests.c4f/VisionShotSmoke.c4s")
	add_test(NAME playtest_vision
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/playtest_vision.py"
			"--engine" "$<TARGET_FILE:clonk>"
			"--scenario" "${LEGACYCLONK_CONTENT_DIR}/WeatherEvents.c4d/Tests.c4f/VisionShotSmoke.c4s"
			"--tick" "120"
			"--work-dir" "${CMAKE_BINARY_DIR}/ptv"
			"--gate-mode" "advisory"
			"--json-out" "${CMAKE_BINARY_DIR}/ptv/record.json"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(playtest_vision PROPERTIES
		TIMEOUT 2400  # lock wait (VQ_LOCK_TIMEOUT 1800s) + own battery budget
		RESOURCE_LOCK "qwen_judge"
		LABELS "playtest;vision"
		SKIP_REGULAR_EXPRESSION "^SKIP: ")
endif()

# --- Vision judge-lock selftest (spec vision-judge-serialization, cycle 121)
# Hermetic RED/GREEN proof that judge_lock() serializes two vision_qa
# batteries: an in-process fake-ollama stub records server-side
# (start,end) timestamps and the peak in-flight count; no GPU, no
# ollama, no engine, no content checkout. Deliberately NO RESOURCE_LOCK
# (touches no GPU) and NO SKIP_REGULAR_EXPRESSION (must never skip);
# label "lint" keeps it in the ctest -LE vision parallel phase and the
# ASan lane's -E 'smoke|net_' set. NOT WIN32: the selftest deliberately
# defeats the SKIP guards, and Windows has no fcntl — spec s4.6 keeps
# Windows behavior unchanged (fail-loud judge path, no ported lock).
if(PYTHON3 AND NOT WIN32)
	add_test(NAME vision_lock_selftest
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/test_vision_lock.py")
	set_tests_properties(vision_lock_selftest PROPERTIES TIMEOUT 120 LABELS "lint")
endif()

# --- AutoTasks acceptance run (spec auto-tasks-mvp, cycle 180) --------------
# 5-minute standing-jobs proof: the roadmap check "a clonk told to chop wood
# keeps chopping and delivering for 5 minutes" is 10,500 ticks (5 min game
# time @35 fps, ~10.5 s wall under --frame-rate-cap 1000). Own stanza, NOT the
# glob: the glob hardcodes --smoke-run 350 and the scenario is named without
# the "Smoke" suffix so it cannot double-register (firstlight_climate_smoke
# precedent :903-915). NOT USE_SANITIZER gate per pxs_perf_gate (:450).
# Seed pinned (anti-overfit, R5); re-pin only with calibration evidence
# (.opencode/scratch/180/task5-calibration.md).
if(NOT USE_SANITIZER AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Tests.c4f/AutoTasksAccept.c4s")
	add_test(NAME auto_tasks_acceptance
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/run_engine_headless.py"
			"$<TARGET_FILE:clonk>" --console --smoke-run 10500 --frame-rate-cap 1000
			--parameter "Seed=181"
			-s "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Tests.c4f/AutoTasksAccept.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(auto_tasks_acceptance PROPERTIES
		TIMEOUT 420
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "AutoTasksAccept PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()

# --- save_continue_e2e (spec save-continue, cycle 189) -----------------------
# Two-phase headless proof of the "Continue last game" check: phase A runs the
# SaveContinueProof fixture (packed first — QuickSave from a directory-form
# source is corrupted, cycle-189 finding) to --smoke-run 700 and the
# --smoke-save-at:700:SCProof probe QuickSaves; phase B resumes the savegame
# and asserts "SaveContinueProof PASS" (t2380 ladder, GameOver). Own stanza,
# NOT the glob: the name carries no "Smoke" suffix so it cannot double-register
# (auto_tasks_acceptance precedent :1135). NOT USE_SANITIZER gate per
# pxs_perf_gate (:450); the fixture keeps the cycle-180 seed pin Seed=181
# (the driver's phase A; the savegame carries it into phase B). Windows
# calibrated in .opencode/scratch/189/task4-calibration.md.
if(PYTHON3 AND NOT USE_SANITIZER
   AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Tests.c4f/SaveContinueProof.c4s"
   AND EXISTS "${CMAKE_SOURCE_DIR}/tools/save_continue_e2e.py")
	add_test(NAME save_continue_e2e
		COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/save_continue_e2e.py"
			"$<TARGET_FILE:clonk>"
			"${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/Tests.c4f/SaveContinueProof.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(save_continue_e2e PROPERTIES
		TIMEOUT 240
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "SaveContinueProof E2E PASS"
		FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endif()
