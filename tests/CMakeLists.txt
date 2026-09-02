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
	cmake_parse_arguments(PARSE_ARGV 1 "ADD_TEST" "LINK_ENGINE" "" "SOURCES;INCLUDE_DIRS;LIBRARIES")

	add_executable("${TARGET}" ${ADD_TEST_SOURCES})
	target_include_directories("${TARGET}" PRIVATE "${CMAKE_SOURCE_DIR}/src" ${ADD_TEST_INCLUDE_DIRS})
	target_compile_definitions("${TARGET}" PRIVATE C4ENGINE)
	if (USE_CONSOLE)
		target_compile_definitions("${TARGET}" PRIVATE USE_CONSOLE=1)
	endif ()
	target_link_libraries("${TARGET}" PRIVATE Catch2::Catch2WithMain standard ${ADD_TEST_LIBRARIES})

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

add_test_target(C4MaterialReactions
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4MaterialReactions.cpp"
	LINK_ENGINE
)

# --- Offline pre-game options (spec pregame-options-parity) ----------------
add_test_target(OptionsOverride
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4GameOptions.cpp"
	LINK_ENGINE
)

# The scenario lives in the content repo (sibling checkout); only register
# the smoke test when that file is actually present.
if(EXISTS "${CMAKE_SOURCE_DIR}/../content/WeatherEvents.c4d/Tests.c4f/OptionsOverride.c4s")
	add_test(NAME parameter_override_smoke
		COMMAND "$<TARGET_FILE:clonk>" --console --smoke-run 350
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

foreach(scenario ${SMOKE_SCENARIOS})
  get_filename_component(scenario_name "${scenario}" NAME_WE)  # e.g. EventSmoke
  add_test(NAME "smoke_${scenario_name}"
    COMMAND "$<TARGET_FILE:clonk>"
            --console --smoke-run 350
            -s "${scenario}"
    WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
  set_tests_properties("smoke_${scenario_name}" PROPERTIES
    TIMEOUT 60
    LABELS "smoke"
    PASS_REGULAR_EXPRESSION "${scenario_name} PASS"
    FAIL_REGULAR_EXPRESSION "FatalError|\\[error\\]|\\[fatal\\]")
endforeach()

# --- PXS perf gate (spec pxs-particle-budget-benchmark) --------------------
# Raw-throughput companion to smoke_PXSPerfSmoke: --frame-rate-cap 1000
# lifts the 28 ms/tick pace so per-window wall-clock reflects simulation
# cost (spec frame-rate-cap-engine-option, cycle 64).
# EXISTS guard: the Autobuild CI has no content checkout — without it the
# entry would point at a missing scenario and fail on every leg.
if(NOT USE_SANITIZER AND EXISTS "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/PXSPerfSmoke.c4s")
	add_test(NAME pxs_perf_gate
		COMMAND "$<TARGET_FILE:clonk>"
			--console --smoke-run 350 --frame-rate-cap 1000
			-s "${LEGACYCLONK_CONTENT_DIR}/PixelPhysics.c4d/Tests.c4f/PXSPerfSmoke.c4s"
		WORKING_DIRECTORY "${CMAKE_BINARY_DIR}")
	set_tests_properties(pxs_perf_gate PROPERTIES
		TIMEOUT 60
		LABELS "smoke"
		PASS_REGULAR_EXPRESSION "PXSPerfSmoke PASS"
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
		COMMAND "$<TARGET_FILE:clonk>"
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

# --- Network desync CI smoke ---------------------------------------------
# See spec network-desync-ci-smoke. Runs two headless engine instances on
# localhost with tc netem impairment (Linux only), asserting no desync fatal
# errors over N ticks.
#
# Console builds only: the smoke harness runs the engine binary directly,
# and GUI builds (WITH_DEVELOPER_MODE=On) call gtk_init at startup, which
# exits(1) on headless CI runners before any smoke output.
find_program(TC tc)
find_program(PYTHON3 python3)

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
