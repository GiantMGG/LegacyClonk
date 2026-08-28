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

*(Stub — content added in Task 2.)*

## 10–25 min — Build

*(Stub — content added in Task 2.)*

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
