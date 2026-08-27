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

add_test_target(C4ValueCoercion
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4ValueCoercion.cpp"
	LINK_ENGINE
)
add_test_target(C4AulParse
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4AulParse.cpp"
	LINK_ENGINE
)

add_test_target(C4WeatherEvents
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4WeatherEvents.cpp"
	LINK_ENGINE
)

add_test_target(C4ReplayController
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstC4ReplayController.cpp"
	LINK_ENGINE
)
