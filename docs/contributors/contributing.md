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

*(Stub — content added in Task 3.)*

## 35–50 min — Add a new Catch2 test

*(Stub — content added in Task 3.)*

## 50–60 min — Open a PR

*(Stub — content added in Task 4.)*

## CI matrix

*(Stub — content added in Task 4.)*

## Style gate

*(Stub — content added in Task 4.)*

## AGENTS.md conventions at a glance

*(Stub — content added in Task 4.)*

## See also

!!! seealso "See also"
    - [Engine architecture](architecture.md)
    - [C4Aul deep dive](c4aul.md)
    - [Network lockstep deep dive](network.md)
    - [Rendering pipeline deep dive](rendering.md)
    - [Contributors overview](index.md)
    - Root [`README.md`](https://github.com/legacyclonk/LegacyClonk/blob/main/README.md) — canonical build instructions
