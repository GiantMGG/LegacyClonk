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

add_test_target(C4RecordRoundtrip
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4RecordRoundtrip.cpp"
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
  "${LEGACYCLONK_CONTENT_DIR}/**/Tests.c4f/*Smoke.c4s")

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

# --- Engine unit tests for the SmokeRunTicks state semantics -------------
add_test_target(SmokeRunFlag
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstSmokeRunFlag.cpp"
	LINK_ENGINE
)
