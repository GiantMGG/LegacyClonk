# Fix CI Failures — Design Spec

**Date:** 2026-08-24
**Topic:** Resolve the four failing CI jobs on commit 19ff8776 in the LegacyClonk repository.

## Goal

This change fixes two distinct compile-time failures that are currently breaking 4 of 11 CI jobs. The first failure is a missing-include error in `C4Fonts.cpp` that surfaces only when the precompiled header (PCH) is disabled (the `Linux debugrec x64` build). The second failure is a `std::size_t` vs `uint64_t` type mismatch in `C4Aul.cpp` that surfaces on macOS (clang/libc++) where `std::size_t` is `unsigned long` and `uint64_t` is `unsigned long long` — two distinct types. The `macOS x64`, `macOS arm64`, and `Merge universal Mac` jobs all fail because of this second issue (the merge job has no macOS artifacts to merge). Both fixes are minimal, surgical, and platform-portable.

## Context

The LegacyClonk CI matrix (`autobuild/ci.toml`) builds the engine across Windows, Linux, and macOS for several architectures, plus a `debugrec` variant on Linux. On commit 19ff8776, the most recent run has 4 failing jobs out of 11:

| Job | Platform | Failure |
|-----|----------|---------|
| Linux debugrec x64 | Linux | `C4Fonts.cpp` compile error (missing includes, PCH disabled) |
| macOS x64 | macOS | `C4Aul.cpp` template instantiation error (`std::size_t` type mismatch) |
| macOS arm64 | macOS | same `C4Aul.cpp` error |
| Merge universal Mac | macOS | downstream failure — no macOS artifacts to merge |

The `Merge universal Mac` job is not an independent failure: it depends on the two macOS build jobs producing artifacts. Once the macOS builds are fixed, the merge job will succeed automatically. No separate work is required for it.

The codebase relies heavily on a precompiled header (`C4PCH.h` or equivalent) that transitively includes many engine headers. Most `.cpp` files omit includes that the PCH silently provides. The `debugrec` build is the only CI variant that disables PCH (`-DUSE_PCH=Off -DDEBUGREC=On`), which is why the `C4Fonts.cpp` problem only manifests there.

## Root Cause Analysis

### Fix 1: `C4Fonts.cpp` missing includes

`C4Fonts.cpp` references the types `C4Group`, `C4GroupSet`, and the global `Application` object, but does not directly include the headers that define them (`C4Group.h`, `C4GroupSet.h`, `C4Application.h`). In the normal CI builds the PCH provides these headers transitively, so compilation succeeds. The `Linux debugrec x64` job disables PCH, which exposes the missing includes as hard compile errors.

### Fix 2: `C4Aul.cpp` `std::size_t` type mismatch

In `C4AulScriptEngine::CompileFunc` (`src/C4Aul.cpp`, lines 557 and 584), a `std::size_t sectionCount` variable is passed to `mkNamingCountAdapt`, which forwards it to `StdCompiler::Value(...)`. The `StdCompiler` base class in `StdCompiler.h` provides `Value` overloads for `uint64_t` (line 203), `int32_t` (line 204), and `uint32_t` (line 205), but **not** for `unsigned long` (which is what `std::size_t` resolves to on macOS).

On Linux (GCC/libstdc++), `uint64_t` is a typedef for `unsigned long`, so `std::size_t` (also `unsigned long`) matches the `Value(uint64_t &)` overload and compilation succeeds. On macOS (clang/libc++), `uint64_t` is a typedef for `unsigned long long`, while `std::size_t` is `unsigned long`. These are two distinct integer types in C++, so no `Value` overload matches and template instantiation fails.

Every other `mkNamingCountAdapt` call site in the codebase uses `int32_t` or `uint32_t`, which is the established portable convention.

## Proposed Changes

### Fix 1: `src/C4Fonts.cpp`

Add three includes so that `C4Fonts.cpp` no longer depends on the PCH to provide the definitions of `Application`, `C4Group`, and `C4GroupSet`. The includes should be placed with the other local includes near the top of the file (after the existing `#include <C4Fonts.h>` block, alongside the existing `#include <C4Config.h>` etc.):

```cpp
#include <C4Application.h>
#include <C4Group.h>
#include <C4GroupSet.h>
```

No other source changes are required for this fix.

### Fix 2: `src/C4Aul.cpp`

Replace `std::size_t` with `uint32_t` in the two `sectionCount` declarations in `C4AulScriptEngine::CompileFunc`, and adjust the initialization on the compiler branch to truncate explicitly:

- **Line 557** (compiler branch — variable is default-constructed then filled by `mkNamingCountAdapt`):
  ```cpp
  std::size_t sectionCount;
  ```
  becomes
  ```cpp
  uint32_t sectionCount;
  ```

- **Line 584** (decompiler branch — variable is initialized from `SectionLocalNamed.size()`):
  ```cpp
  std::size_t sectionCount{SectionLocalNamed.size()};
  ```
  becomes
  ```cpp
  uint32_t sectionCount{static_cast<uint32_t>(SectionLocalNamed.size())};
  ```

The loop variables on lines 564 and 587 that iterate over `sectionCount` / `SectionLocalNamed` remain unchanged. The loop on line 564 uses `std::size_t i` and compares `i < sectionCount`; after the change `sectionCount` is `uint32_t`. The `i < sectionCount` comparison promotes both operands to a common unsigned type and remains correct. No truncation hazard exists because section counts are bounded far below 2^32 in any realistic save file.

## Scope

### In Scope

- Adding three includes to `src/C4Fonts.cpp` to fix the `Linux debugrec x64` build.
- Adding missing includes to 8 additional files that have the same latent PCH dependency issue: `C4Movement.cpp`, `C4Object.cpp`, `C4ObjectList.cpp`, `C4ObjectMenu.cpp`, `C4PXS.cpp`, `C4SolidMask.cpp`, `C4Weather.cpp`, `C4Wrappers.cpp`.
- Changing `std::size_t` to `uint32_t` on two lines of `src/C4Aul.cpp` to fix the macOS builds (and by extension the `Merge universal Mac` job).

### Out of Scope (Non-Goals)

- Adding new `Value(unsigned long &)` / `Value(size_t &)` overloads to `StdCompiler`. That would be a broader, more invasive change with its own review surface; the targeted `uint32_t` fix is smaller and matches the existing codebase convention.
- Changing the on-disk save format. `mkNamingCountAdapt` serializes the count through `mkIntPackAdapt`, which packs the value based on its magnitude rather than the in-memory integer width. Since realistic section counts are far below 2^32, the packed output is identical whether the count is stored as `uint32_t` or `uint64_t`. No migration is needed.
- Refactoring `CompileFunc` to share code between the compiler and decompiler branches.

## Success Criteria

The fix is considered successful when **all** of the following hold:

1. **`Linux debugrec x64` compiles.** A local build configured with `-DUSE_PCH=Off -DDEBUGREC=On` compiles `C4Fonts.cpp` without errors and produces a working `clonk` binary.
2. **macOS builds compile.** The `macOS x64` and `macOS arm64` CI jobs compile `C4Aul.cpp` without the `std::size_t` template instantiation error and produce artifacts.
3. **`Merge universal Mac` succeeds.** Once the two macOS build jobs produce artifacts, the universal merge job succeeds without any further code change.
4. **No regressions on Linux.** A local Linux build (the primary developer platform) with the default configuration still compiles and the existing test suite (`cmake --build build --target test`) still passes.
5. **No save-format regression.** Loading an existing save game written before this change still works (verified by loading an existing save in a local build).

Where CI cannot be run locally (e.g. macOS), the success criterion is that the next CI run on the affected branches is green for the previously-failing jobs.

## Risks and Mitigations

### Risk 1: `uint32_t` truncation of `SectionLocalNamed.size()`

If a save file ever contained more than 2^32 sections, the `static_cast<uint32_t>` would truncate. This is not a realistic concern: section counts are orders of magnitude smaller than 2^32, and the existing serialization format for `mkNamingCountAdapt` would already not support such counts portably. **Mitigation:** the explicit `static_cast` makes the truncation visible at the call site; no further guard is needed given the count's realistic upper bound.

### Risk 2: The `Linux debugrec x64` build exposes further latent PCH dependencies in other files

Fixing `C4Fonts.cpp` may unmask the same class of problem in the next translation unit the debugrec build reaches. **Mitigation:** This risk materialized during implementation — 8 additional files (`C4Movement.cpp`, `C4Object.cpp`, `C4ObjectList.cpp`, `C4ObjectMenu.cpp`, `C4PXS.cpp`, `C4SolidMask.cpp`, `C4Weather.cpp`, `C4Wrappers.cpp`) had the same latent PCH dependency issue. The scope was expanded to fix all 8 files by adding their missing includes, making the `Linux debugrec x64` build pass completely.

### Risk 3: Include ordering / macro side-effects from the new includes in `C4Fonts.cpp`

Adding includes can, in principle, change macro definitions or trigger ODR violations. **Mitigation:** the three added headers (`C4Application.h`, `C4Group.h`, `C4GroupSet.h`) are standard engine headers already pulled in transitively by the PCH in other builds, so they are known to coexist cleanly with the rest of the codebase. The change only makes the dependency explicit.

## Decision Summary

- **Fix 1:** Add `#include <C4Application.h>`, `#include <C4Group.h>`, and `#include <C4GroupSet.h>` to `src/C4Fonts.cpp`. These are the headers that define the `Application` global, `C4Group`, and `C4GroupSet` types used in the file but currently supplied only by the PCH.
- **Fix 2:** Change `std::size_t` to `uint32_t` for the two `sectionCount` variables in `C4AulScriptEngine::CompileFunc` (lines 557 and 584 of `src/C4Aul.cpp`), with an explicit `static_cast<uint32_t>` on the decompiler-branch initialization. `uint32_t` has a portable `Value(uint32_t &)` overload on all target platforms and matches the existing codebase convention for `mkNamingCountAdapt` counts.
- **No `StdCompiler` overload additions.** Adding a `Value(unsigned long &)` overload was rejected as a broader change with a larger review surface and potential for unintended side-effects; the targeted `uint32_t` fix is smaller and consistent with the existing codebase.
- **No save-format migration.** The integer width change is memory-only and does not affect the serialized format.

## Open Questions

None. Both fixes are well-defined and the design is approved.
