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
set_tests_properties(C4NetIOIPv6Loopback PROPERTIES TIMEOUT 30)

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
	"Vegetation.c4d/AppleTree.c4d")
foreach(agri_def ${AGRI_DEFS})
	get_filename_component(agri_def_name "${agri_def}" NAME_WE)
	if(PYTHON3 AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/${agri_def}/Graphics.png")
		add_test(NAME "gfx_check_${agri_def_name}"
			COMMAND "${PYTHON3}" "${CMAKE_SOURCE_DIR}/tools/gen_agriculture_gfx.py" "${agri_def_name}"
				"${LEGACYCLONK_CONTENT_DIR}/Agriculture.c4d/${agri_def}/Graphics.png" --check)
		set_tests_properties("gfx_check_${agri_def_name}" PROPERTIES TIMEOUT 60 LABELS "lint")
	endif()
endforeach()

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
