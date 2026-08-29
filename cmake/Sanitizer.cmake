# cmake/Sanitizer.cmake
#
# Compile and link with the requested sanitizers. Pass via CMake:
#   cmake -DUSE_SANITIZER=address,undefined ...
#
# Accepted values (comma-, semicolon-, or space-separated):
#   address undefined thread memory leak
#
# When non-empty, the constructed -fsanitize=... token is applied to every
# target via the global add_compile_options / add_link_options, alongside
# -fno-omit-frame-pointer (cleaner stack traces) and
# -fno-sanitize-recover=all (non-zero exit on any finding).
#
# MSVC is intentionally not supported on day 1: the option silently no-ops
# with a STATUS message so a Windows ASan lane can be added later without
# touching this file.

set(USE_SANITIZER "" CACHE STRING "Sanitizers to enable (e.g. address,undefined)")

if (USE_SANITIZER)
	if (MSVC)
		message(STATUS "USE_SANITIZER=${USE_SANITIZER} requested but MSVC is not yet supported; skipping")
	else ()
		# Normalise "address,undefined" / "address;undefined" / "address undefined"
		string(REGEX REPLACE "[, ;]+" ";" SAN_LIST "${USE_SANITIZER}")
		list(JOIN SAN_LIST "," SAN_CSV)
		set(SAN_FLAGS "-fsanitize=${SAN_CSV}")
		set(SAN_RECOVER_FLAGS "-fno-sanitize-recover=all")

		add_compile_options(${SAN_FLAGS} ${SAN_RECOVER_FLAGS} -fno-omit-frame-pointer)
		add_link_options(${SAN_FLAGS})

		message(STATUS "Sanitizers enabled: ${SAN_CSV}")
	endif ()
endif ()
