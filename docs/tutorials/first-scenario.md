# First scenario — a 60-minute modder tutorial

This tutorial takes you from a fresh checkout to a playable
`MyFirstScenario.c4s` melee scenario with a hand-painted `Map.bmp`, a
`Script.c` that places a `Goal` object and sets a win condition, player
starts, and a `Scenario.txt` with the standard sections. Budget: **under
60 minutes** (assuming the engine is already built — see
[First custom object](first-object.md) Checkpoint 1 if not).

??? note "What you will build"
    A `MyFirstScenario.c4s` melee scenario with a hand-painted `Map.bmp`,
    a `Script.c` that places a `Goal` object and sets a win condition,
    player starts, and a `Scenario.txt` with
    `[Head]`/`[Definitions]`/`[Game]`/`[Landscape]`/`[Player1]` sections.
    The tutorial ships a ready-made skeleton at
    `LegacyClonk/docs/skeletons/MyFirstScenario.c4s/` — you copy it,
    read it, run it, and tweak it.

!!! info "Working directory"
    Run **every** command in this tutorial from the **workspace root** —
    the directory that contains both `LegacyClonk/` and `content/`. All
    paths below are written relative to that root.

---

## Checkpoint 1 — Copy the skeleton (0–5 min)

The tutorial ships a ready-made skeleton. Copy it into your content tree
so you can edit and run it:

```bash
cp -r LegacyClonk/docs/skeletons/MyFirstScenario.c4s content/
```

The skeleton is a folder (not a packed group), so you can edit every file
directly. It contains:

| File | Role |
|---|---|
| `Scenario.txt` | Scenario config: `[Head]`/`[Definitions]`/`[Game]`/`[Landscape]`/`[Player1]` |
| `Map.bmp` | 100×40 hand-painted landscape (1 px = `MapZoom` ingame px) |
| `Script.c` | `Initialize` (create GOAL), `InitializePlayer`, `FxLoseTimer` |
| `Title.txt` | DE/US title card |

??? question "Checkpoint 1: verify"
    ```text
    $ ls content/MyFirstScenario.c4s/
    Map.bmp  Scenario.txt  Script.c  Title.txt
    ```

---

## Checkpoint 2 — Understand `Scenario.txt` (5–20 min)

The skeleton's `Scenario.txt` has five sections. Each is annotated below.

### `[Head]` — identity

```ini
[Head]
Title=MyFirstScenario
Version=1
MaxPlayer=2
Origin=docs\skeletons\MyFirstScenario.c4s
```

- **`Title`**: shown in the scenario picker.
- **`Version`**: definition version (used for savegame compatibility).
- **`MaxPlayer`**: maximum number of players the scenario supports.
- **`Origin`**: the on-disk path the engine records for diagnostics.

### `[Definitions]` — which definition packs load

```ini
[Definitions]
Definition1=Objects.c4d
```

`Objects.c4d` is the master definition pack that holds every `.c4d`
object the scenario references. Without it, `CreateObject(GOAL)` and
the `CLNK` crew id would be undefined. See
[C4D pack anatomy](c4d-anatomy.md) for a file-by-file dissection of a
real `.c4d`.

### `[Game]` — rules and goals

```ini
[Game]
StructNeedEnergy=0
Goals=MELE=1
Rules=KILC=1;TACC=1
```

- **`StructNeedEnergy=0`**: structures do not require energy to function.
- **`Goals=MELE=1`**: load the `Melee` goal (last-clonk-standing) with
  priority 1. The engine's built-in melee goal handles the win condition.
- **`Rules=KILC=1;TACC=1`**: `KILC` = kill count tracking; `TACC` = team
  account. See [Constants](../reference/constants.md) for the full rule
  bit table.

### `[Landscape]` — the map

```ini
[Landscape]
Map.bmp=Map.bmp
Sky=Clouds2
MapWidth=100
MapHeight=40
MapZoom=15
Material=Earth
BottomOpen=0
```

- **`Map.bmp=Map.bmp`**: the engine reads `Map.bmp` from the scenario
  folder. 1 px in the BMP = `MapZoom` (15) ingame px, so the 100×40 BMP
  renders as a 1500×600 px landscape.
- **`Sky=Clouds2`**: the sky texture.
- **`Material=Earth`**: the default material for map pixels that don't
  match a known material colour.
- **`BottomOpen=0`**: the landscape is closed at the bottom (no falling
  out of the world).

### `[Player1]` — the player's starting kit

```ini
[Player1]
Crew=CLNK=3
Wealth=100
HomeBaseMaterial=CNKT=3;LOAM=5;WOOD=5;FLNT=5;TFLN=5;METL=1
```

- **`Crew=CLNK=3`**: spawn 3 Clonks.
- **`Wealth=100`**: starting gold.
- **`HomeBaseMaterial`**: the buyable toolbox stock.

??? question "Checkpoint 2: verify"
    ```text
    $ cat content/MyFirstScenario.c4s/Scenario.txt
    [Head]
    Title=MyFirstScenario
    ...
    ```

    The file exists and has all five sections.

---

## Checkpoint 3 — Understand `Map.bmp` (20–30 min)

The skeleton ships a 100×40 24-bit BMP. The engine reads each pixel's
RGB and maps it to a material via `Material.c4g/TEXMAP.TXT`:

- **Earth** material RGB ≈ `127,95,63` (from `Earth.c4m`'s `Color` field).
- **Black** `(0,0,0)` → Tunnel/air.
- **Sky** top portion → rendered as open sky.

There are three landscape paths in LegacyClonk:

1. **Static `Map.bmp`** — this skeleton's path. 1 px = `MapZoom` ingame px.
2. **Dynamic `[Landscape]` fields** — `MapWdt`, `MapHgt`, `Amplitude`,
   `Phase`, `Random`, `Liquid`, `LiquidLevel` generate a landscape
   procedurally with no `Map.bmp`. (See the
   [OpenClonk wiki](https://www.openclonk.org/wiki/) for a deep dive.)
3. **Generated `Landscape.txt`** — the map-generator S2 DSL
   (`map { overlay … }`). Out of scope for this tutorial; linked from
   [Where next?](#where-next).

??? tip "Paint your own map"
    Open the engine console's landscape brush, or use an external editor
    (GIMP, Paint.NET) to paint a BMP with material colours. Save as
    24-bit BMP. The `Material=Earth` fallback fills any unmatched colour
    with earth.

??? question "Checkpoint 3: verify"
    ```text
    $ file content/MyFirstScenario.c4s/Map.bmp
    ... PC bitmap, ... 100 x 40 x 24 ...
    ```

    The BMP is 100×40, 24-bit.

---

## Checkpoint 4 — Read `Script.c` (30–45 min)

The skeleton's `Script.c` has three callbacks:

```c
#strict 2

protected func Initialize()
{
    // Create the win-condition goal object at the map centre.
    CreateObject(GOAL, 50, 20, NO_OWNER);
    Log("MyFirstScenario online!");
    return true;
}

protected func InitializePlayer(int plr, int x, int y, object base, int team)
{
    // Equip the player's first Clonk with a sword and a loaf.
    var clonk = GetHiRank(plr);
    if (clonk) clonk->CreateContents(SWORD);
    return true;
}
```

- **`Initialize`** fires once at scenario load. `CreateObject(GOAL, ...)`
  spawns the goal object that drives the win condition. See
  [Scenario objective](../cookbook/scenario-objective.md) for the
  `IsFulfilled` pattern the goal object uses.
- **`InitializePlayer`** fires for each player when they join. Equipping
  the crew here guarantees the kit is ready before play starts.

The goal object (defined in `content/Objects.c4d/Goals.c4d/Goal.c4d`)
implements `IsFulfilled` — the engine polls it every frame and calls
`GameOver()` when it returns `true`.

??? warning "`IsFulfilled` returning `true` immediately"
    If the win condition is already met on frame 0, `GameOver()` fires
    instantly and the scenario ends before play starts. Guard against
    this in your `IsFulfilled`.

??? question "Checkpoint 4: verify"
    ```text
    $ grep -c 'func ' content/MyFirstScenario.c4s/Script.c
    2
    ```

    Two callbacks: `Initialize` and `InitializePlayer`.

---

## Checkpoint 5 — Run it (45–55 min)

Run the skeleton headless:

```bash
LegacyClonk/build/clonk --console --smoke-run 350 \
  content/MyFirstScenario.c4s
```

??? question "Checkpoint 5: verify"
    ```text
    MyFirstScenario online!
    ```
    Exit code: `0`. No `FatalError` in the output.

    If you see `definition not found`, the
    `[Definitions] Definition1=Objects.c4d` line cannot resolve
    `Objects.c4d` from the engine's working directory. Run from the
    workspace root and ensure `content/Objects.c4d` exists.

---

## Checkpoint 6 — Tweak it (55–60 min)

Now make the scenario yours:

1. Edit `Scenario.txt` `[Head]` `Title` to your scenario name.
2. Edit `Map.bmp` to paint a different landscape (see Checkpoint 3).
3. Add a lose-condition timer to `Script.c`:

```c
protected func Initialize()
{
    CreateObject(GOAL, 50, 20, NO_OWNER);
    AddEffect("IntLoseTimer", this, 100, 35, this);
    Log("MyFirstScenario online!");
    return true;
}

func FxIntLoseTimerTimer(object target, int nr, int time)
{
    if (time > 3500)  // ~100 seconds at 35 frames/tick
    {
        Log("Time up!");
        GameOver();
        return -1;
    }
    return true;
}
```

See [Timer effect](../cookbook/timer-effect.md) for the full
`AddEffect` + `Fx*Timer` pattern.

??? question "Checkpoint 6: verify"
    Re-run the smoke:

    ```bash
    LegacyClonk/build/clonk --console --smoke-run 350 \
      content/MyFirstScenario.c4s
    ```

    Exit code: `0`. No `FatalError`.

---

## Where next?

- [C4Script guide](../c4script/index.md) — syntax, types, proplists, effects.
- [Cookbook](../cookbook/index.md) — copy-paste recipes.
- [Scenario objective](../cookbook/scenario-objective.md) — the `IsFulfilled`
  win-condition pattern (used in the skeleton's `Script.c`).
- [Timer effect](../cookbook/timer-effect.md) — the `AddEffect` +
  `Fx*Timer` pattern (used for the lose-condition timer in Checkpoint 6).
- [C4D pack anatomy](c4d-anatomy.md) — file-by-file dissection of a real
  `.c4d`.
- [DefCore.txt fields](../reference/defcore.md) — the full 93-row field
  table.
- [Constants](../reference/constants.md) — `C4D_*` category bits and more.
- [Make a scenario](../cookbook/make-a-scenario.md) — the collapsed
  cookbook pointer.
