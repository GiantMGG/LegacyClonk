# C4D pack anatomy — file-by-file dissection

A `.c4d` (definition pack) is the fundamental unit of modding in
LegacyClonk. This page dissects a real shipped `.c4d` —
`content/WeatherEvents.c4d/Blizzard.c4d/` — file by file, so you can see
how the pieces fit together.

!!! note "Tutorial vs reference"
    This is a **reference** page. If you are looking for the step-by-step
    tutorial, see [First custom object](first-object.md).

---

## The five files

A `.c4d` folder contains these files:

| File | Role |
|---|---|
| `DefCore.txt` | Identity card: `id`, `Category`, `Version`. |
| `ActMap.txt` | Animation state machine (named actions). |
| `Graphics.png` | The sprite sheet. `ActMap.txt`'s `Length` indexes frames here. |
| `Script.c` | The behaviour. C4Script callbacks (`Initialize`, `Hit`, etc.). |
| `Names.txt` | Display-name table indexed by `Name=N` in `DefCore.txt`. |

Some `.c4d` packs also include `StringTblDE.txt` / `StringTblUS.txt` for
localized strings, and `DescDE.txt` / `DescUS.txt` for description text.

---

## `DefCore.txt` — the identity card

From `Blizzard.c4d/DefCore.txt`:

```ini
[DefCore]
id=BLZD
Version=1
Category=65536
TimerCall=Execute
Timer=5
```

- **`id`**: The 4-letter identifier scenarios reference (e.g.
  `CreateObject(BLZD, ...)`). This is the single most important field.
- **`Category`**: What kind of thing the object is.
  `65536` = `C4D_StaticBack` (a static background object). See
  [Constants](../reference/constants.md) for the full bit table.
- **`Version`**: Definition version (used for savegame compatibility).
- **`TimerCall` / `Timer`**: Call `Execute()` every 5 frames.

For the full 93-row field table, see
[DefCore.txt fields](../reference/defcore.md).

---

## `ActMap.txt` — the animation state machine

From `Blizzard.c4d/ActMap.txt`:

```ini
[ActMap]
Action=Idle
Length=1
Delay=1
Facet=(0,0,1,1,0,0)
NextAction=Idle
End
```

Each `[ActMap]` block defines one **action** — a named animation state.
- **`Action`**: The name (referenced in `Script.c` via `SetAction(...)`).
- **`Length`**: Number of frames in this action.
- **`Delay`**: Frames between each animation step.
- **`Facet`**: `(X, Y, W, H, OffX, OffY)` — the sub-rectangle of
  `Graphics.png` to display.
- **`NextAction`**: Which action to transition to when this one finishes.

`Blizzard.c4d` has a single `Idle` action with `Length=1` — it displays
one frame and loops. More complex objects have `Walk`, `Jump`, `Fight`,
etc.

---

## `Graphics.png` — the sprite sheet

A PNG file containing all the sprites for all actions. `ActMap.txt`'s
`Facet=(X, Y, W, H, ...)` selects which sub-rectangle to display for each
frame. `Length=N` means the action plays N consecutive facets (stepping
right by `W` pixels each frame).

`Blizzard.c4d/Graphics.png` is a tiny 1×1 placeholder — weather events
don't need visible sprites. A real object (e.g. a Clonk) has a large
sprite sheet with dozens of animation frames.

---

## `Script.c` — the behaviour

From `Blizzard.c4d/Script.c` (abridged):

```c
#strict

public func Construction()
{
    baseline_wind = GetWind(0, 0, true);
    baseline_temp = GetTemperature();
    return 1;
}

public func Start()
{
    Log("A blizzard descends!");
    SetTemperature(-30);
}

public func Execute()  // called every Timer=5 frames
{
    SetTemperature(-30);
}
```

The script defines **callbacks** — functions the engine calls at
specific moments. `Construction` fires when the object is created (before
`Initialize`), `Start` is a custom entry point, and `Execute` fires on
the `Timer` interval declared in `DefCore.txt`.

For the full callback list, see
[Object lifecycle callbacks](../reference/callbacks/object-lifecycle.md)
and [Callback convention](../c4script/callbacks-convention.md).

---

## `Names.txt` — the display-name table

From `Blizzard.c4d/Names.txt`:

```ini
[Names]
1=Blizzard
```

The `Name=N` field in `DefCore.txt` indexes into this table. When a
script calls `GetName(obj)`, it returns the string from `Names.txt`. This
is how the same definition can have different display names in different
locales (via `StringTblDE.txt`, `StringTblUS.txt`, etc.).

---

## The folder ↔ packed-group duality

A `.c4d` exists in two forms:

1. **A folder** (`GlowStone.c4d/`) — editable, contains the raw files.
2. **A packed group** (`GlowStone.c4d` — a single file) — ready to ship.

The `c4group` tool converts between them:

```bash
c4group GlowStone.c4d -p   # Pack folder → file
c4group GlowStone.c4d -u   # Unpack file → folder
c4group GlowStone.c4d -l   # List contents
```

The engine loads both forms identically — it does not care whether a
`.c4d` is a folder or a packed file. During development you edit the
folder; for distribution you pack it.
