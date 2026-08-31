# Troubleshooting

Every new contributor hits at least one of the seven failure modes below. They
are ordered by onboarding phase: toolchain → dependencies → compile → test →
run. Each section follows the same invariant shape — **Symptom** (the error
you see, quoted verbatim), **Cause** (one short paragraph), **Fix** (a
copy-pasteable command block), **Citation** (the `file:line` of the emitting
code, so the citation-freshness gate keeps this page honest).

Two lookup modes: paste your error into the site search box (MkDocs Material
indexes the quoted strings below), or scan the symptom index.

## Symptom index

| You see | Go to |
|---|---|
| `CMake Error at CMakeLists.txt:14 (cmake_minimum_required)` | [§1 CMake too old](#1-cmake-too-old) |
| `Could NOT find ZLIB` / missing `deps/include` | [§2 deps symlink missing](#2-deps-symlink-missing) |
| `'L_tmpnam' was not declared in this scope` | [§3 glibc GUI-build conflict](#3-glibc-gui-build-conflict) |
| `Error loading graphics of <name> (<id>)` in smoke output | [§4 Graphics stubs](#4-graphics-stubs) |
| `FATAL ERROR: File not found or invalid: <Pack>.c4d` | [§5 Smoke-harness CWD](#5-smoke-harness-cwd) |
| No `test_*` targets / empty CTest | [§6 USE_TESTS defaults OFF](#6-use_tests-defaults-off) |
| Engine exits immediately at startup | [§7 Game folder](#7-game-folder) |

## 1. CMake too old

**Symptom.** Configure fails immediately:

```
CMake Error at CMakeLists.txt:14 (cmake_minimum_required):
  CMake 4.0 or higher is required.  You are running version 3.31.6.
```

**Cause.** Distro package managers ship CMake < 4.0 (Debian stable ships
3.31, Ubuntu 24.04 LTS ships 3.28). The project floor is
`cmake_minimum_required(VERSION 4.0...4.4)` at `CMakeLists.txt:14`.

**Fix.**

```bash
pip install cmake==4.4.2   # or: snap install cmake --classic
hash -r                    # make this shell pick up the new cmake
```

**Citation.** `CMakeLists.txt:14`.

## 2. deps symlink missing

**Symptom.** CMake configure fails with `Could NOT find ZLIB` (or the same
`Could not find ...` shape for other deps-provided libraries — OpenSSL, SDL).

**Cause.** The `LegacyClonk/deps` symlink is missing or broken on your
machine. CMake searches `deps/include` and `deps/lib` relative to
`CMakeLists.txt` (`CMakeLists.txt:59-62`).

**Fix.** Recreate the symlink — the target depends on your checkout layout:

```bash
# Standalone clone (deps tarball extracted at the workspace root,
# the layout docs/contributors/contributing.md describes):
ln -s ../deps LegacyClonk/deps

# This workspace (built deps live in deps/output):
ln -s ../deps/output LegacyClonk/deps
```

**Citation.** `CMakeLists.txt:59-62`.

## 3. glibc GUI-build conflict

**Symptom.** GUI-build compile errors like:

```
src/C4Strings.h:24: error: 'L_tmpnam' was not declared in this scope
```

**Cause.** An environment-specific *dev-environment* failure class — not a
universal blocker. A toolchain (e.g. homebrew GCC 16 with
`-isystem /usr/include`) shadows the system glibc headers: the system
`stdio.h` wins over the toolchain's, and `L_tmpnam` and related macros go
undefined.

**Fix.** The workaround CI and every content cycle use — build the
dedicated-server console target:

```bash
cmake -B build-console -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DUSE_CONSOLE=ON -DUSE_TESTS=On
cmake --build build-console
```

Or fix the environment itself: a system GCC ≥ 15.1 or clang++ ≥ 22.1 (the
versions the README lists as supported).

**Citation.** `src/C4Strings.h:24`.

## 4. Graphics stubs

**Symptom.** In smoke-test output:

```
[error] Error loading graphics of <name> (<id>)
```

The `smoke_<Name>` CTest entry then fails via the FAIL_REGULAR_EXPRESSION
gate at `tests/CMakeLists.txt:142` (CCAN variant at
`tests/CMakeLists.txt:211`).

**Cause.** Definitions whose `Graphics.png` was a placeholder stub; the
loader at `src/C4Def.cpp:505` rejects them.

**Fix.**

```bash
python3 tools/fix_stub_graphics.py ../content
```

**Citation.** `src/C4Def.cpp:505`, `tests/CMakeLists.txt:142`,
`tests/CMakeLists.txt:211`.

## 5. Smoke-harness CWD

**Symptom.** The engine aborts during a smoke run:

```
FATAL ERROR: File not found or invalid: <Pack>.c4d
```

**Cause.** The engine forces its working directory to the exe dir at startup
— `SetWorkingDirectory(ExePath)` under the `forceWorkingDirectory` flag
(`src/C4Config.cpp:661-662`, entry point `src/C4Config.cpp:628`) — so bare
pack names resolve relative to that CWD. The standing fix is the
configure-time symlink loop that links every content pack into the build dir
(`tests/CMakeLists.txt:148-158`).

**Fix.**

```bash
cmake -B build          # re-configure: the symlink loop re-runs
# or link the missing pack manually:
ln -s ../content/<Pack>.c4d build/<Pack>.c4d
```

**Citation.** `src/C4Config.cpp:628`, `src/C4Config.cpp:661-662`,
`tests/CMakeLists.txt:148-158`.

## 6. USE_TESTS defaults OFF

**Symptom.** No `test_*` targets; `ctest` from the build dir reports
`No tests were found!!!`.

**Fix.** `USE_TESTS` defaults to `OFF` — re-run the configure step with
`-DUSE_TESTS=On`. The warning and the exact configure line live in
[Contributing — Configure once, with tests
on](contributing.md#configure-once-with-tests-on).

## 7. Game folder

**Symptom.** The engine exits immediately at startup — "won't start" per the
README: "Without them, the engine won't start."

**Cause.** Your game folder lacks the `Graphics.c4g` / `System.c4g` symlinks.

**Fix.** Follow the README's
[Setup game folder](https://github.com/legacyclonk/LegacyClonk/blob/main/README.md#setup-game-folder)
section — the setup commands live there.

**Citation.** `README.md:88`.
