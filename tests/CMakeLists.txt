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

add_test_target(C4NetIO
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4NetIO.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4NetIO.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4Network2Address.cpp"
		"${CMAKE_SOURCE_DIR}/src/StdSync.cpp"
)

add_test_target(C4NetIOIPv6Loopback
	SOURCES
		"${CMAKE_SOURCE_DIR}/tests/TstC4NetIOIPv6Loopback.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4NetIO.cpp"
		"${CMAKE_SOURCE_DIR}/src/C4Network2Address.cpp"
		"${CMAKE_SOURCE_DIR}/src/StdSync.cpp"
)
set_tests_properties(C4NetIOIPv6Loopback PROPERTIES TIMEOUT 30)

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
find_program(TC tc)
find_program(PYTHON3 python3)

if (PYTHON3)
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
