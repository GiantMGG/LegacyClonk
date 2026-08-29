# Contributing to LegacyClonk

You are a C++ developer who has never seen Clonk before, and you want to land
your first PR inside an hour. This page is that hour. By the end you will have
cloned the workspace, built the console and GUI engines, run the test suite,
added a new Catch2 unit test, wired it into CTest, run the style gate, and
opened a pull request that goes green on CI.

If you want the "what is this engine" question answered first, read
[Engine architecture](architecture.md) — this page assumes you already know
you want to contribute C++.

## TL;DR — new contributor checklist

!!! tip "The 10-box path — also use this as your PR self-review"
    - [ ] Clone the workspace and extract the `deps` tarball (`deps/fix_paths.sh`).
    - [ ] Build the console engine: `cmake --build build`.
    - [ ] Build the GUI engine (same command, configured without `-DUSE_CONSOLE=ON`).
    - [ ] `ctest --test-dir build --output-on-failure` is green.
    - [ ] Write a new Catch2 test (copy `tests/TstC4Math.cpp`).
    - [ ] Wire it via `add_test_target` in `tests/CMakeLists.txt`.
    - [ ] Run `python3 tools/auto_format.py <LegacyClonk-dir> -w` (style gate).
    - [ ] Commit with the repo's message conventions.
    - [ ] Push to your fork and open the PR.
    - [ ] CI goes green on the matrix lanes.

## 0–10 min — Get the source & deps

The repo is a multi-repo workspace: the engine lives in `LegacyClonk/`, pre-built
libraries in `deps/`, default content in `content/`, community content in
`content-community/`. Clone the workspace top level, not `LegacyClonk/` alone.

```bash
git clone https://github.com/legacyclonk/LegacyClonk.git clonk_ws
cd clonk_ws
```

### Extract the pre-built dependencies

Grab the latest `deps` tarball for your platform from
<https://github.com/legacyclonk/deps/releases/latest> and extract it into a
folder called `deps` at the workspace root, so you end up with
`deps/include`, `deps/lib`, etc. Then run the path-fix script:

```bash
cd deps
./fix_paths.sh   # use Git Bash on Windows
cd ..
```

`LegacyClonk/deps` is a symlink to `../deps` (already created in the repo);
CMake finds libraries via `deps/include` and `deps/lib` relative to
`CMakeLists.txt`. If the symlink is missing on your machine, recreate it:
`ln -s ../deps LegacyClonk/deps`.

!!! tip "Save 5 minutes"
    The `deps` tarball is platform-specific — download the one matching your
    OS and architecture. Extracting the wrong one produces confusing
    link-time errors much later.

## 10–25 min — Build

There are two engine targets: the **console** build (dedicated server, no GUI)
and the **GUI** build (what you play). CI builds both. You want both locally.

### Configure once, with tests on

```bash
cd LegacyClonk
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DUSE_TESTS=On -DWITH_DEVELOPER_MODE=ON
```

!!! warning "Canonical source"
    The root [`README.md`](https://github.com/legacyclonk/LegacyClonk/blob/main/README.md) "Compiling - Quick Start" section
    is the canonical build reference. The one-liners below are a quick
    orientation only — if anything disagrees, the README wins.

### Per-OS one-liner

**Linux** (g++ ≥ 15.1 or clang++ ≥ 22.1):

```bash
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DUSE_TESTS=On -DWITH_DEVELOPER_MODE=ON
cmake --build build
```

**macOS** (open-source clang++ ≥ 22.1, e.g. `brew install llvm@22 ninja`):

```bash
export LLVM_PREFIX="$(brew --prefix llvm@22)"
cmake -B build -G Ninja -DCMAKE_TOOLCHAIN_FILE=$PWD/autobuild/platforms/clang_mac.cmake -DUSE_TESTS=On
cmake --build build
```

**Windows** (latest MSVC): open the CMake project in Visual Studio, or from a
Developer Command Prompt:

```powershell
cmake -B build -G "Ninja" -DCMAKE_BUILD_TYPE=RelWithDebInfo -DUSE_TESTS=On
cmake --build build
```

### Console vs GUI

The default build produces the GUI engine (`clonk`). For the dedicated-server
console build, add `-DUSE_CONSOLE=ON` at configure time and rebuild into a
separate build directory:

```bash
cmake -B build-console -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DUSE_CONSOLE=ON -DUSE_TESTS=On
cmake --build build-console
```

!!! warning "`USE_TESTS=On` is not the default"
    `USE_TESTS` defaults to `OFF`. CI passes `-DUSE_TESTS=On`. If you configure
    without it you will find no `test_*` targets and an empty CTest — re-run
    the configure step above with `-DUSE_TESTS=On`.

## 25–35 min — Run the test suite

There are two kinds of tests:

- **Catch2 unit tests** in `tests/Tst*.cpp` — exercise engine internals that
  can be driven without a full game boot. Registered as CTest entries via the
  `add_test_target` helper in `tests/CMakeLists.txt`.
- **Headless smoke scenarios** in `content/**/Tests.c4f/*Smoke.c4s` — C4Script-
  level scenarios booted with `--smoke-run 350`. Discovered by the glob at
  `tests/CMakeLists.txt:113-117` and registered one CTest entry per scenario
  (`smoke_<Name>`).

### Run the whole suite

```bash
ctest --test-dir build --output-on-failure
```

Expected: a summary line `100% tests passed` (or, on a known-flaky day, the
documented subset). Each Catch2 test prints its `TEST_CASE` name on failure;
each smoke scenario prints `<Name> PASS` on success (matched by
`PASS_REGULAR_EXPRESSION` at `tests/CMakeLists.txt:129`).

### Run a single test

```bash
ctest -R C4Math --test-dir build --output-on-failure
```

`-R` filters the test name (the `NAME` passed to `add_test`, e.g. `C4Math`,
`StdBuf`, `smoke_Event`). Use `-VV` for full verbose output.

### Catch2 vs smoke — which do I add?

| Use a Catch2 test when… | Use a smoke scenario when… |
|---|---|
| The behaviour is a pure function or class with no game-world state. | The behaviour needs the engine booted, a landscape, objects, effects. |
| You can `REQUIRE(...)` an expected value directly. | You want to assert on C4Script-level game state across N ticks. |
| You don't need `Game`/`Application`/`Config` globals (or you accept the `LINK_ENGINE` wiring). | The scenario is naturally expressed as a `Script.c` driving `AddEffect`. |

See the workspace-root `AGENTS.md` "Smoke scenario contract" section for the
`Script.c` shape and the exit-code table.

## 35–50 min — Add a new Catch2 test

The fastest path is to copy an existing test and rewire it. `tests/TstC4Math.cpp`
is the canonical copy-template — it shows the three things every Catch2 test
needs:

```cpp
#include <catch2/catch_all.hpp>

#include "C4Math.h"   // the header under test

TEST_CASE("Distance computes integer Pythagorean distance", "[C4Math]")
{
	REQUIRE(Distance(0, 0, 0, 0) == 0);
	REQUIRE(Distance(0, 0, 3, 4) == 5);
	REQUIRE(Distance(0, 0, -3, -4) == 5);
}
```

The three invariants: `#include <catch2/catch_all.hpp>` first; a tag in the
second `TEST_CASE` arg (e.g. `"[C4Math]"`); `REQUIRE(...)` (not `assert`) for
the hard assertions.

### Step 1 — copy the template

```bash
cd LegacyClonk/tests
cp TstC4Math.cpp TstMyFeature.cpp
```

Edit `TstMyFeature.cpp`: change the `#include` to the header you are testing,
rewrite the `TEST_CASE` name/tag/body. Keep the ISC license header block.

### Step 2 — wire it into CTest

`add_test_target` is defined at `tests/CMakeLists.txt:14`. It builds an
executable `test_<Name>`, links `Catch2::Catch2WithMain` (which provides
`main()`), and registers a CTest entry named `<Name>`. There are two forms:

**Form A — standalone test (no engine globals).** Use when the code under test
is a free function or a class that does not touch `Game`, `Application`,
`Config`, etc.:

```cmake
add_test_target(MyFeature
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstMyFeature.cpp"
)
```

**Form B — test that needs the engine (`LINK_ENGINE`).** Use when the test
touches engine singletons. `LINK_ENGINE` links `clonk_engine` **and** pulls in
`tests/TstEngineGlobals.cpp` (see `tests/CMakeLists.txt:26-34`):

```cmake
add_test_target(MyFeature
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstMyFeature.cpp"
	LINK_ENGINE
)
```

Add your line to `tests/CMakeLists.txt` after the existing `add_test_target`
calls (the file is grouped roughly by subsystem). Reconfigure and rebuild:

```bash
cmake --build build
ctest -R MyFeature --test-dir build --output-on-failure
```

### The two engine-integration gotchas

!!! warning "Gotcha 1 — `LINK_ENGINE` pulls `TstEngineGlobals.cpp`"
    `src/C4WinMain.cpp` defines `main()` *and* the engine singletons
    (`Game`, `Application`, `Console`, `FullScreen`, `Config`). It is excluded
    from `clonk_engine` (the OBJECT library tests link against) because its
    `main()` would clash with Catch2's `main()` on macOS and Windows. So a
    `LINK_ENGINE` test binary links `TstEngineGlobals.cpp` instead — a 31-line
    TU that defines exactly those singletons. If your test references an
    engine global but you forgot `LINK_ENGINE`, you will get link errors
    (`undefined reference to Game` / `Application` / `Config`).

!!! warning "Gotcha 2 — never `#include` C4WinMain.cpp from a test"
    Catch2 ships its own `main()` via `Catch2WithMain`. Including
    `C4WinMain.cpp` in a test target produces a duplicate-`main` link error on
    macOS/Windows. The `LINK_ENGINE` + `TstEngineGlobals.cpp` split exists
    precisely to avoid this — use it, do not work around it.

### Worked example — a 15-line test

`tests/TstMyFeature.cpp`. This reuses the real `Distance()` free function
declared at `src/C4Math.h:33` so it compiles and passes out of the box —
swap the function under test for your own:

```cpp
// (ISC license header block — copy from TstC4Math.cpp)

#include <catch2/catch_all.hpp>

#include "C4Math.h"

TEST_CASE("Distance handles the unit square corners", "[C4Math]")
{
	REQUIRE(Distance(0, 0, 1, 0) == 1);   // right
	REQUIRE(Distance(0, 0, 0, 1) == 1);   // up
	REQUIRE(Distance(0, 0, 1, 1) == 1);   // diagonal, truncated
}
```

`tests/CMakeLists.txt` (add after the existing `C4Math` line):

```cmake
add_test_target(MyFeature
	SOURCES "${CMAKE_SOURCE_DIR}/tests/TstMyFeature.cpp"
)
```

Verify:

```bash
cmake --build build
ctest -R MyFeature --test-dir build --output-on-failure
```
Expected: `1/1 MyFeature ... Passed` and `100% tests passed`.

## 50–60 min — Open a PR

### Fork and branch

1. Fork `legacyclonk/LegacyClonk` on GitHub (top-right **Fork** button).
2. Add your fork as a remote and create a feature branch off `main`:

```bash
git remote add fork git@github.com:<you>/LegacyClonk.git
git checkout -b feat/my-feature
```

### Run the style gate before every commit

`tools/auto_format.py` is the project's style gate. Run it in **write** mode on
the `LegacyClonk/` directory before staging:

```bash
python3 tools/auto_format.py LegacyClonk -w
```

(Omit `-w` for a dry run that only reports what it would change.) See the
[Style gate](#style-gate) appendix for exactly which files it formats and
which rules it enforces.

### Commit conventions

- One logical change per commit.
- Subject line ≤ 72 chars, imperative mood: `feat: add BoundClamp test`,
  `fix: handle negative exponent in Pow`, `docs: clarify deps symlink`.
  Match the existing repo history's prefix style when in doubt.
- Body wraps at ~72 cols, explains *why*, not *what*.

### Push and open the PR

```bash
git push -u fork feat/my-feature
```

Open the PR against `legacyclonk/LegacyClonk:main`. Paste the
[TL;DR checklist](#tldr-new-contributor-checklist) into the PR description as
your self-review. CI kicks off automatically — see the next section for what
runs.

### What CI runs on your PR

CI is driven by `autobuild/ci.toml` and the workflows in `.github/workflows/`.
The matrix distils to:

| OS | Lanes | Builds? | Publishes? |
|---|---|---|---|
| Windows | x86, x64, aarch64, debugrec | yes | x64 only |
| Linux | x64, aarch64, debugrec, cxx26 | yes | (release pipeline) |
| macOS | x64, aarch64, universal | yes | universal only |

Every lane runs `cmake --build` and `ctest`. The `debugrec` lanes build with
`DEBUGREC=On -DUSE_PCH=Off`. The `cxx26` lane builds with `-DUSE_CXX_26=ON`
and is the one that catches C++26-incompatible code early. See the
[CI matrix](#ci-matrix) appendix for the full per-lane table.

## CI matrix

Distilled from `autobuild/ci.toml` (Windows `:60-90`, Linux `:92-122`,
macOS `:124-145`). Workflow files live in `.github/workflows/` — `c-cpp.yml`
is the main build matrix.

| OS family | Arch | Lane name | Publish? | Notes |
|---|---|---|---|---|
| Windows | x86 | (default) | no | `vs_arch = X86` |
| Windows | x64 | (default) | **yes** | `include-groups` + `publish-groups` |
| Windows | aarch64 | (default) | no | `windows-11-arm` runner |
| Windows | x86 | `debugrec` | no | `exclude-release`, `DEBUGREC=On` |
| Linux | x64 | (default) | release pipeline | `gcc_arch = x86_64` |
| Linux | aarch64 | (default) | release pipeline | `ubuntu-22.04-arm` runner |
| Linux | x64 | `debugrec` | no | `exclude-release`, `DEBUGREC=On` |
| Linux | x64 | `cxx26` | no | `exclude-release`, `-DUSE_CXX_26=ON` |
| macOS | x64 | (default) | no | `build-only`, `macos-15-intel` |
| macOS | aarch64 | (default) | no | `build-only`, `macos-latest` |
| macOS | universal | (default) | **yes** | `publish-only` |

**Publish lanes** (Windows x64, macOS universal) produce the itch.io release
artefacts; the rest are build-and-test only. The `debugrec` and `cxx26` lanes
are the two non-default configurations a PR will exercise — both are
`exclude-release`, so they never publish.

## Style gate

`tools/auto_format.py` is the project's style gate. Run it on the
`LegacyClonk/` directory:

```bash
python3 tools/auto_format.py LegacyClonk          # dry run — reports only
python3 tools/auto_format.py LegacyClonk -w        # write changes in place
```

### What it formats

| Pass | Files touched |
|---|---|
| CMake | `CMakeLists.txt`, `config.h.cmake`, `cmake/filelists/*.txt` |
| C++ | `src/**/*.{cpp,h}` and `tests/**/*.{cpp,h}` — **but `src/res/` is excluded** (see `tools/auto_format.py:43-45`) |
| Tools | `tools/*.sh` (shell), `tools/*.py` (python) |
| YAML | root `.travis.yml`, `appveyor.yml` |

### What it enforces

- **Non-line-leading tab rejection** — a tab that is not at the start of a
  line raises `FormattingError` (`tools/auto_format.py:121-124`). Fix by hand.
- **Trailing whitespace** trimmed (`:149-151`).
- **Trailing newline** — file ends in exactly one `\n` (`:135-141`).
- **3+ blank lines condensed** to a single blank (`:126-128`).
- **Keyword-`(` spacing** — enforces a space between `if`/`for`/`while`/
  `else` (C++) or `if`/`elseif`/`else`/`endif` (CMake) and the opening paren
  (`:143-147`).

The `.editorconfig` (tabs, UTF-8, trailing-newline, final-newline) is the
human-readable counterpart — your editor should already be picking it up.

## AGENTS.md conventions at a glance

The workspace-root `AGENTS.md` (at `clonk_ws/AGENTS.md`, **not** inside
`LegacyClonk/`) is the contributor's quick-reference for repo conventions.
The rules most likely to bite a new contributor:

- **`#pragma once` guards every header** — no `#ifndef` include guards.
  (Documented in [Engine architecture](architecture.md).)
- **`C4ForwardDeclarations.h` is the single source of forward declarations**
  — add forward declarations there, not scattered across headers. It is the
  *only* forward-declaration header. (See [Engine architecture](architecture.md).)
- **Tabs, UTF-8, trim trailing whitespace, final newline** — enforced by
  `.editorconfig` and `tools/auto_format.py`. (Workspace-root `AGENTS.md`,
  "Code style".)
- **C++23 by default; C++26 is opt-in** — pass `-DUSE_CXX_26=ON` at configure
  time. No source files use C++26 features yet. (Workspace-root `AGENTS.md`,
  "Build".)
- **The `deps` symlink inside `LegacyClonk/` is required** — `LegacyClonk/deps`
  → `../deps`. CMake expects `deps/include` and `deps/lib` relative to
  `CMakeLists.txt`. (Workspace-root `AGENTS.md`, "Layout" + "Build".)

## See also

!!! seealso "See also"
    - [Engine architecture](architecture.md)
    - [C4Aul deep dive](c4aul.md)
    - [Network lockstep deep dive](network.md)
    - [Rendering pipeline deep dive](rendering.md)
    - [Contributors overview](index.md)
    - Root [`README.md`](https://github.com/legacyclonk/LegacyClonk/blob/main/README.md) — canonical build instructions
    - [Troubleshooting](troubleshooting.md) — build/test failure modes
