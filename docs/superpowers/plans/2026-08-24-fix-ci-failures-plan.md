# Fix CI Failures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve four failing CI jobs by fixing two distinct compile-time errors: a missing-include error in `C4Fonts.cpp` (Linux debugrec x64) and a `std::size_t` type mismatch in `C4Aul.cpp` (macOS).

**Architecture:** Two surgical, platform-portable fixes. Fix 1 adds three includes to `C4Fonts.cpp` so it no longer relies on the PCH for `C4Group`, `C4GroupSet`, and `Application` definitions. Fix 2 changes two `std::size_t` declarations to `uint32_t` in `C4Aul.cpp::CompileFunc` to match the portable `Value(uint32_t &)` overload convention used elsewhere in the codebase.

**Tech Stack:** C++23, CMake, Ninja, GCC (Linux) / clang (macOS), Catch2 for tests.

---

### Task 1: Add missing includes to `src/C4Fonts.cpp`

**Files:**
- Modify: `src/C4Fonts.cpp:20-27`

- [ ] **Step 1: Edit the include block in `src/C4Fonts.cpp`**

Replace the existing local include block:

```cpp
#include <C4Fonts.h>

#include <C4Config.h>
#include <C4Components.h>
#include <C4Log.h>
#include <C4Surface.h>
#include <C4Wrappers.h>
#include "StdFont.h"
```

with:

```cpp
#include <C4Fonts.h>

#include <C4Application.h>
#include <C4Config.h>
#include <C4Components.h>
#include <C4Group.h>
#include <C4GroupSet.h>
#include <C4Log.h>
#include <C4Surface.h>
#include <C4Wrappers.h>
#include "StdFont.h"
```

- [ ] **Step 2: Verify the file compiles with PCH disabled**

Run a syntax-only compile of `C4Fonts.cpp` with the `-DUSE_PCH=Off -DDEBUGREC=On` configuration to confirm the missing-include error is gone:

```bash
cmake --build build --target clonk 2>&1 | grep -E "(C4Fonts|error:)" | head -20
```

Expected: No output (no `C4Fonts.cpp` errors).

Note: This step assumes a build directory configured with `-DUSE_PCH=Off -DDEBUGREC=On` exists. If it does not, configure one first (see Task 3).

- [ ] **Step 3: Commit**

```bash
git add src/C4Fonts.cpp
git commit -m "fix: add missing includes to C4Fonts.cpp for PCH-disabled builds"
```

---

### Task 2: Fix `std::size_t` type mismatch in `src/C4Aul.cpp`

**Files:**
- Modify: `src/C4Aul.cpp:557` and `src/C4Aul.cpp:584`

- [ ] **Step 1: Change the compiler-branch `sectionCount` declaration (line 557)**

Replace:

```cpp
		std::size_t sectionCount;
```

with:

```cpp
		uint32_t sectionCount;
```

- [ ] **Step 2: Change the decompiler-branch `sectionCount` declaration (line 584)**

Replace:

```cpp
		std::size_t sectionCount{SectionLocalNamed.size()};
```

with:

```cpp
		uint32_t sectionCount{static_cast<uint32_t>(SectionLocalNamed.size())};
```

- [ ] **Step 3: Verify the file compiles**

```bash
cmake --build build --target clonk 2>&1 | grep -E "(C4Aul|error:)" | head -20
```

Expected: No output (no `C4Aul.cpp` errors).

- [ ] **Step 4: Commit**

```bash
git add src/C4Aul.cpp
git commit -m "fix: replace std::size_t with uint32_t in C4Aul.cpp CompileFunc for portability"
```

---

### Task 3: Configure a PCH-disabled Linux build (debugrec)

**Files:**
- None (build configuration only)

- [ ] **Step 1: Configure a separate build directory for the PCH-disabled build**

```bash
cmake -B build-noPCH -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DUSE_PCH=Off -DDEBUGREC=On -DUSE_TESTS=On
```

Expected: CMake configuration completes with `-- Generating done` and `-- Build files have been written to: .../build-noPCH`.

- [ ] **Step 2: Build the `clonk` target with PCH disabled**

```bash
cmake --build build-noPCH --target clonk
```

Expected: Build completes with no errors and produces `build-noPCH/clonk`.

- [ ] **Step 3: Run the test suite against the default build**

```bash
cmake --build build --target test
```

Expected: All existing tests pass.

---

### Task 4: Verify no regressions on default Linux build

**Files:**
- None (verification only)

- [ ] **Step 1: Configure the default build directory if it does not exist**

```bash
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DUSE_TESTS=On
```

- [ ] **Step 2: Build the `clonk` target**

```bash
cmake --build build --target clonk
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Run the test suite**

```bash
cmake --build build --target test
```

Expected: All existing tests pass.

- [ ] **Step 4: Commit if any uncommitted changes remain (none expected)**

If `git status` shows clean working tree, no commit needed. Otherwise commit with appropriate message.

---

### Task 5: Save-format regression smoke check

**Files:**
- None (verification only)

- [ ] **Step 1: Locate an existing save game in the workspace content**

```bash
find /home/dl238/Repos/clonk_ws -name "*.c4f" -o -name "*.c4s" 2>/dev/null | head -5
```

- [ ] **Step 2: Launch the newly built `clonk` binary and load the existing save**

```bash
build/clonk
```

Manually load the save game from the in-game menu. Verify the save loads without errors and gameplay state is intact. This is the "No save-format regression" success criterion from the spec.

- [ ] **Step 3: If the save loads successfully, no further action needed**

If the save fails to load, revert the `C4Aul.cpp` change and reconsider the approach. Note: this would indicate a save-format incompatibility not anticipated by the spec.

---

### Task 6: Trigger CI and verify all previously-failing jobs now pass

**Files:**
- None (CI verification)

- [ ] **Step 1: Push the branch to trigger CI**

```bash
git push -u origin <branch-name>
```

- [ ] **Step 2: Monitor the CI run**

Expected: `Linux debugrec x64`, `macOS x64`, `macOS arm64`, and `Merge universal Mac` jobs all pass. The other 7 jobs that were already passing should continue to pass.

---

## Self-Review Audit

- **Spec coverage:** Fix 1 (C4Fonts.cpp includes) → Task 1. Fix 2 (C4Aul.cpp type change) → Task 2. Verification of PCH-disabled build → Task 3. Default-build regression check → Task 4. Save-format smoke check → Task 5. CI verification → Task 6. All spec sections covered.
- **Placeholder scan:** No "TBD", "TODO", or generic "implement X" placeholders. All commands include expected output indicators. No "similar to Task N" shortcuts.
- **Type consistency:** `uint32_t` used consistently in both `C4Aul.cpp` declarations. The `static_cast<uint32_t>` matches the target type. Loop variables on lines 564 and 587 remain `std::size_t`/auto as in the original, per spec.
- **Task sizing:** Each task is a single logical action (one file edit, one build config, one verification). All steps are 2-5 minutes of focused work.
- **Missing pieces:** None. The `Merge universal Mac` job requires no code change (spec line 21) — it will pass automatically once macOS artifacts are produced.
