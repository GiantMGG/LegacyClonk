# BSD port

LegacyClonk builds and runs **console-only** on FreeBSD 14.x and OpenBSD 7.x.
GUI / X11 / SDL / GTK builds on BSD are out of scope for this roadmap item —
the console build is enough to verify the source-portability pillar.

## Why BSD "just works" via the Linux path

CMake's `set(C4_OS ...)` block in `CMakeLists.txt` (~line 404) gates on
`APPLE` / `UNIX` / `WIN32`. BSD defines `__unix__`, so CMake sets
`UNIX=ON`, and BSD silently enters the `elseif (UNIX)` branch and gets
`C4_OS="linux64"` (or `"linux-arm64"` on aarch64). This is **correct**:
`C4_OS` is used only for content-pack path suffixes, which are
platform-agnostic. There is no `"bsd64"` value and none is needed.

The `else (Unknown platform)` `FATAL_ERROR` branch is only reached for
architectures the `C4_OS` block does not enumerate (e.g. riscv64,
powerpc64). BSD x86_64/aarch64 do not hit it.

## Required engine patches

The engine source has five `__linux__`-only `#elif`/`#ifdef` guards that
were broadened to also cover `__FreeBSD__` and `__OpenBSD__`:

| File | Site | Why |
|---|---|---|
| `src/StdOSVersion.cpp` | `:130` | POSIX branch for `GetLocal()` / `GetFriendlyOSName()` (uses `uname(3)`). Without this patch the symbols are undefined on BSD → link error. |
| `src/C4Thread.cpp` | `:36` | `pthread_setname_np` for thread names. FreeBSD signature matches Linux (`pthread_t, const char *`); OpenBSD signature is `(const char *)` only (like macOS). |
| `src/C4Config.cpp` | `:41, :67, :93, :497, :633` | `<clocale>` include, German-locale detection, `UserPath` default (`$HOME/.legacyclonk`), `~/.legacyclonk` mkdir, `ExePath`/`TempPath` init. All use the same XDG/locale/`getenv("TMPDIR")` conventions as Linux. (`:961` is already an `#else` and covers BSD.) |
| `src/C4Group.cpp` | `:1493` | Executable-bit detection via `access(X_OK)`. POSIX; works identically on BSD. |
| `CMakeLists.txt` | after `:428` | FreeBSD-only `target_link_libraries(... execinfo)` block. `backtrace()` / `backtrace_symbols_fd()` live in the `libexecinfo` port on FreeBSD; OpenBSD has them in libc and needs no extra flag. |

## Build flags

| CMake flag | Value | Rationale |
|---|---|---|
| `CMAKE_BUILD_TYPE` | `RelWithDebInfo` | Matches existing CI. |
| `CMAKE_PREFIX_PATH` | `/usr/local` | BSD ports install headers/libs under `/usr/local`; CMake does not search there by default. |
| `USE_CONSOLE` | `ON` | Skips GUI/SDL/X11/OpenGL/GTK deps — the only viable console-only path. |
| `USE_TESTS` | `ON` | Run the Catch2 test suite + smoke scenarios inside the VM. |
| `USE_LTO` | `OFF` | LTO across mixed base/ports toolchains on BSD is flaky. Not the property under test. |
| `USE_MINIUPNPC` | `ON` (fallback `OFF`) | Required for network UPnP features. If the FreeBSD `miniupnpc` port does not ship `miniupnpc-config.cmake` (required by `find_package(miniupnpc CONFIG REQUIRED)` at `CMakeLists.txt:599`), fall back to `-DUSE_MINIUPNPC=OFF`. UPnP is non-critical for a build smoke test. |
| `WITH_DEVELOPER_MODE` | `OFF` (default) | GTK not installed; would fail `pkg_check_modules(GTK3)`. |

## FreeBSD package list

```sh
pkg install -y \
  cmake ninja git pkgconf openssl curl zlib \
  fmtlib libiconv miniupnpc spdlog catch2
```

## OpenBSD package list

```sh
pkg_add -I -v \
  cmake ninja git pkgconf openssl curl zlib \
  fmtlib libiconv miniupnpc spdlog catch2
```

## Known gaps

### Inotify on BSD (`C4FileMonitor`)

The inotify implementation is `#ifdef __linux__` (`C4FileMonitor.cpp:30`).
On BSD the header falls through to a no-op stub (`C4FileMonitor.h:103-105`).
This is acceptable because `C4FileMonitor` is only constructed by the GTK
developer-mode file watcher, which is `OFF` in console-only builds.

### OpenBSD `pthread_setname_np` signature

OpenBSD 7.x's `pthread_setname_np` takes `(const char *)` only (no
`pthread_t` first argument), matching macOS rather than Linux/FreeBSD.
The `C4Thread.cpp` patch uses a per-BSD branch matching this. If a future
OpenBSD release changes the signature, the OpenBSD lane (which carries
`continue-on-error: true` in `bsd.yml`) will surface the drift without
failing the workflow.

### OpenBSD base-Clang C++23 support

OpenBSD 7.9 ships a base Clang with incomplete C++23 support. The engine
requires C++23 by default (`CMakeLists.txt:115`). The OpenBSD lane in
`bsd.yml` carries `continue-on-error: true` and is documented as
best-effort pending base-OS C++23 support. The FreeBSD lane is the
authoritative BSD gate.

## CI lane

The BSD CI lane lives in `.github/workflows/bsd.yml` — a standalone
workflow independent of `build.yml`, `c-cpp.yml`, `autobuild/ci.toml`,
and the `deps/` tarball flow. It boots a FreeBSD (and OpenBSD) VM on a
stock `ubuntu-latest` GitHub runner via `vmactions/freebsd-vm` /
`vmactions/openbsd-vm`, pinned to commit SHAs (see the workflow file).
