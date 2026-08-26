# Effects

Effects are timed, stackable state attached to objects. They are the
preferred way to implement buffs, poison, shields, and any transient state.

## Creating an effect

```c
func Hit() {
    AddEffect("IntStun", this, 100, 35, this);
}
```

## Effect callbacks

Effects fire callbacks prefixed with `Fx<Name>`:

- `Fx<Name>Start` — when the effect starts.
- `Fx<Name>Timer` — every `iInterval` frames.
- `Fx<Name>Stop` — when the effect ends.
- `Fx<Name>Effect` — when a new effect of the same name would be added
  (lets you stack/refresh instead of duplicating).

Example:

```c
func FxIntStunStart(target, nr, temp, ...) {
    // Initialise stun.
    return true;
}

func FxIntStunTimer(target, nr, time) {
    // Apply stun each tick.
    return;
}
```

See the [effect callbacks reference](../reference/callbacks/effects.md) for
the full list of effect callbacks harvested from the engine.
