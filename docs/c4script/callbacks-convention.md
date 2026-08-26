# The `~` callback convention

The engine identifies callbacks by name. The `~` prefix in the engine's
`PSF_*` macros (`#define PSF_Initialize "~Initialize"`) signals that the
function is a *callback*: the engine looks it up on the relevant object's
script and calls it if present.

## What you write

You write the callback without the `~`:

```c
func Initialize() {
    Message("Hello!", this);
}
```

## What the engine does

When the engine creates the object, it calls the `Initialize` callback on
the object's script. If your script defines `func Initialize()`, it runs.

## Where the canonical list lives

Every engine callback is declared as a `PSF_*` macro in
`src/C4Script.h`. The [callback reference](../reference/callbacks/object-lifecycle.md)
is harvested directly from that file, so it is always in sync with the
engine.

## The `Fx{}` template

Effect callbacks use a `{}` placeholder (`PSF_FxStart` → `"Fx{}Start"`).
The engine substitutes the effect name, so an effect named `IntStun` fires
`FxIntStunStart`. See [Effects](effects.md).
