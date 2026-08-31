# First custom object — a 60-minute modder tutorial

This tutorial takes you from a fresh `git clone` to a custom object that
fires a callback, using only the console build. Budget: **under 60
minutes** (assuming build dependencies are present; a first-time C++23
compile can eat 30+ minutes on its own).

??? note "What you will build"
    A `GlowStone.c4d` object with `id=GWST` that prints
    `Glow Stone online!` when it spawns. The tutorial ships a ready-made
    skeleton at `LegacyClonk/docs/skeletons/GlowStone.c4d/` — you copy it,
    tweak two files, pack it, and see it in a scenario.

!!! info "Working directory"
    Run **every** command in this tutorial from the **workspace root** —
    the directory that contains both `LegacyClonk/` and `content/`. All
    paths below (`LegacyClonk/build/...`, `content/Objects.c4d/...`,
    `LegacyClonk/docs/skeletons/...`) are written relative to that root.

---

## Checkpoint 1 — Build the engine (0–10 min)

Build the console engine and the `c4group` archive tool:

```bash
cmake -B LegacyClonk/build -S LegacyClonk -DUSE_CONSOLE=ON
cmake --build LegacyClonk/build
```

You now have `LegacyClonk/build/clonk` (the console engine) and
`LegacyClonk/build/c4group` (the archive tool). On Windows the binaries
are `clonk.exe` and `c4group.exe`.

??? question "Checkpoint 1: verify"
    ```text
    $ ls LegacyClonk/build/c4group LegacyClonk/build/clonk
    LegacyClonk/build/c4group
    LegacyClonk/build/clonk
    ```

??? tip "Repeatable setup with `lc`"
    The `lc` launcher (at the workspace root) automates game-folder
    setup. Run `lc setup` once to symlink the binary, planet graphics,
    and content into `~/clonk/`. Run `lc doctor` to diagnose a broken
    setup. Run `lc smoke` to run the headless smoke harness.

---

## Checkpoint 2 — Understand the `.c4d` pack (10–20 min)

A `.c4d` is a **definition pack**: a folder (or packed group) that tells
the engine "this is a thing in the world." It contains five files:

| File | Role |
|---|---|
| `DefCore.txt` | Identity card: `id`, `Category`, `Version`. |
| `ActMap.txt` | Animation state machine (named actions). |
| `Graphics.png` | The sprite sheet. |
| `Script.c` | The behaviour (C4Script callbacks). |
| `Names.txt` | Display-name table. |

Copy the shipped skeleton into the content tree:

```bash
cp -r LegacyClonk/docs/skeletons/GlowStone.c4d content/Objects.c4d/
```

For a file-by-file dissection of a real `.c4d`, see
[C4D pack anatomy](c4d-anatomy.md). For the full `DefCore.txt` field
table, see [DefCore.txt fields](../reference/defcore.md).

??? question "Checkpoint 2: verify"
    ```text
    $ ls -R content/Objects.c4d/GlowStone.c4d
    content/Objects.c4d/GlowStone.c4d:
    ActMap.txt  DefCore.txt  Graphics.png  Names.txt  Script.c
    ```

---

## Checkpoint 3 — Give your object an identity (20–35 min)

Edit `content/Objects.c4d/GlowStone.c4d/DefCore.txt`:

```ini
[DefCore]
id=GWST
Name=Glow Stone
Category=C4D_StaticBack
Version=4,9,8
```

The 4-letter `id` is what scenarios reference (e.g.
`CreateObject(GWST, ...)`). `Category=C4D_StaticBack` (bit 0, value `1`)
is a static background object with no physics. `Version=4,9,8` is the
definition version — the engine warns on definitions whose version is
below `4`, so match the `4,9,8` convention used across the content tree.
See [Constants](../reference/constants.md) for the full category bit
table.

??? tip "Make it yours"
    Change `id=GWST` to any 4-letter identifier you like (e.g.
    `id=GLWO`). The tutorial's smoke test uses `GWST`, so if you change
    it, update the smoke's `C4Id("GWST")` line to match.

??? question "Checkpoint 3: verify"
    ```text
    $ LegacyClonk/build/c4group content/Objects.c4d/GlowStone.c4d -l
    Maker: Open directory  Creation: 0
    Version: 1.2  CRC: 0 (0)
    ActMap.txt       ...
    DefCore.txt      ...
    Graphics.png     ...
    Names.txt        ...
    Script.c         ...
    5 Entries, ...
    ```
    The output lists all 5 files — proof the folder is in the right
    place and `c4group` can read it.

---

## Checkpoint 4 — Give your object behaviour (35–45 min)

Edit `content/Objects.c4d/GlowStone.c4d/Script.c` and add an
`Initialize` callback:

```c
#strict 2

local g_initialized;

func Initialize()
{
    // Script-visible flag so the smoke test can assert this callback fired.
    LocalN("g_initialized") = true;
    Message("Glow Stone online!", this);
    return true;
}
```

`Initialize` fires once when the object is created. See
[Callback convention](../c4script/callbacks-convention.md) for when each
lifecycle callback fires.

*(No gate for this checkpoint — the gate at checkpoint 5 covers it.)*

---

## Checkpoint 5 — Pack and ship (45–55 min)

A `.c4d` exists in two forms: a **folder** (editable) and a **packed
group** (a single file, ready to ship). `c4group` converts between them:

```bash
# Pack the folder into a single .c4d file:
LegacyClonk/build/c4group content/Objects.c4d/GlowStone.c4d -p

# List the contents of the packed group:
LegacyClonk/build/c4group content/Objects.c4d/GlowStone.c4d -l

# Unpack back to a folder (when you want to edit again):
LegacyClonk/build/c4group content/Objects.c4d/GlowStone.c4d -u
```

??? warning "Don't double-pack"
    `-p` expects a **folder**. If you run `-p` on an already-packed
    `.c4d` file, it silently no-ops or errors. Always `-u` (unpack) first
    if you need to edit, then `-p` to re-pack.

??? question "Checkpoint 5: verify"
    ```text
    $ LegacyClonk/build/c4group content/Objects.c4d/GlowStone.c4d -l
    ...
    DefCore.txt       ...
    Script.c         ...
    ...
    ```
    The output contains `DefCore.txt` — proof the pack succeeded.

    <!-- TODO: c4group reference page — full -a/-e/-g/-y enumeration. -->

---

## Checkpoint 6 — See it in the world (55–60 min)

The tutorial ships a **smoke scenario** — a headless scenario that
spawns your `GlowStone`, asserts it round-trips its `id` and `Name`,
fires `Initialize`, and survives removal + idempotent re-create. Run it:

```bash
LegacyClonk/build/clonk --console --smoke-run 350 \
  content/Objects.c4d/Tests.c4f/FirstObjectSmoke.c4s
```

??? question "Checkpoint 6: verify"
    ```text
    FirstObjectSmoke PASS
    ```
    Exit code: `0`.

    If you see `FatalError` or a non-zero exit, see the
    [smoke scenario contract](https://legacyclonk.github.io/LegacyClonk/)
    or run `lc doctor` to diagnose your setup.

---

## Where next?

- [C4Script guide](../c4script/index.md) — syntax, types, proplists, effects.
- [Cookbook](../cookbook/index.md) — copy-paste recipes.
- [C4D pack anatomy](c4d-anatomy.md) — file-by-file dissection of a real `.c4d`.
- [DefCore.txt fields](../reference/defcore.md) — the full 93-row field table.
- [Constants](../reference/constants.md) — `C4D_*` category bits and more.
- [First scenario](first-scenario.md) — build a playable `.c4s` from
  scratch.
