# Material reactions

Materials are defined as `.c4m` files inside `Material.c4g`. Besides the
physical fields (`Density`, `Friction`, `Instable`, ...), a material can
carry one or more `[Reaction]` sections that customize how its pixels
interact with other materials.

This page documents the `React` reaction type — the two-product pixel
reaction used for e.g. lava + water → rock + steam. The engine also ships
built-in reaction types (`Convert`, `Incinerate`, `Corrode`, `Poof`,
`Insert`, ...); see `src/C4Material.cpp` for those.

## A `[Reaction]` section

The shipped `Water.c4m` reaction pair is a typical `React` section:

```ini
[Reaction]
Type=React
TargetSpec=Lava
CheckSlide=0
LSProduct=Rock
PXSProduct=Steam
Rate=100
```

| Key | Default | Description |
|---|---|---|
| `Type` | — | `React` for the two-product reaction documented here. |
| `TargetSpec` | — | Which materials the reaction applies to: a material name, or one of the class specs `All`, `Sky`, `Solid`, `SemiSolid`, `Background`, `Incindiary`, `Extinguisher`, `Inflammable`, `Corrosive`, `Corrode`. |
| `Rate` | `100` | Chance the reaction fires per contact: it fires iff `Random(100) < Rate`. |
| `LSProduct` | *(omitted)* | Product written into the static landscape pixel at the contact point. `Sky` makes the pixel vanish. Omitted → the static pixel is untouched. |
| `PXSProduct` | *(omitted)* | Product of the moving pixel (or the attempted static insertion). `Sky` makes the moving pixel vanish. Omitted → see the per-event table below. |
| `ByProduct` | *(omitted)* | Second product, cast as a new PXS at the contact point. Only fires on the moving-PXS event — see below. |
| `ByProductRate` | `0` | Chance the byproduct is cast: it is cast iff `Random(100) < ByProductRate`. The default of `0` disables the byproduct entirely. |
| `CheckSlide` | `1` | If set, splash/slide checks run before the reaction. The shipped `React` sections use `CheckSlide=0` for immediate contact. |

## Per-event behavior

A `React` reaction is evaluated on three engine events, and which product
keys apply depends on the event:

| Event | Fires when | `LSProduct` | `PXSProduct` | `ByProduct` |
|---|---|---|---|---|
| Pre-move check (`meePXSPos`) | A moving PXS is embedded in the target material, or `InsertMaterial` probes the material below an insertion | applied to the contact pixel | a fresh PXS of the product is spawned at the PXS position (velocity zeroed) | **never cast** |
| PXS movement (`meePXSMove`) | A moving PXS collides with the target material | applied to the contact pixel | the PXS converts in place to the product (velocity zeroed) | cast as a new PXS at the contact point, gated by `ByProductRate` |
| Mass movement (`meeMassMove`) | An instable-liquid interface moves (mass mover) | applied — the mover and neighbor pixels resolve to one `LSProduct` pixel | not applied (no PXS is involved) | **never cast** |

Two consequences of this table are deliberate but easy to miss:

- **`ByProduct` only fires on the moving-PXS event.** On the pre-move
  check and on mass movement the byproduct never appears.
- **On the pre-move check the PXS (or insertion) is always consumed —
  even if `PXSProduct` is omitted.** This is unlike the movement event,
  where an omitted `PXSProduct` leaves the PXS unchanged. The asymmetry
  is what keeps PXS-only products such as steam from ever inserting
  statically: `InsertMaterial`'s probe consumes the insertion and spawns
  the product as a fresh PXS instead. If you omit `PXSProduct` on a
  pre-move-check reaction, the contacting PXS simply dies.

## `TargetSpec=All` overrides every default reaction

!!! warning "TargetSpec=All replaces the material's default reactions — including Insert"

    A `[Reaction]` section with `TargetSpec=All` registers against every
    material **including sky**, and thereby overrides all of the
    material's default reactions for every pair — including the default
    `Insert` (static insertion into the landscape).

    The hazard is real: copying the shipped `Steam.c4m` pattern below for
    a non-gas material silently disables static insertion against
    *everything*. Steam gets away with it because it is a buoyant,
    PXS-only gas that must never statically insert.

When several `[Reaction]` sections target overlapping pairs, the last
section wins. The shipped `Steam.c4m` uses exactly this composition: the
`All` section registers the condensation reaction against every material
including sky, then the `Sky` section overwrites the sky slot with a
slower rate:

```ini
[Reaction]
Type=React
TargetSpec=All
CheckSlide=0
PXSProduct=Water
Rate=20

[Reaction]
Type=React
TargetSpec=Sky
CheckSlide=0
PXSProduct=Water
Rate=5
```

Net behavior: a steam PXS touching any material condenses into water with
a 20% chance per check, and against open sky with a 5% chance.
