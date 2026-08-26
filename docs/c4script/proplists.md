# Proplists

A proplist is an ordered key/value container. It is the primary data
structure in C4Script — definitions, effects, and menu items are all
proplists under the hood.

## Literal

```c
var p = { x = 10, y = 20 };
Log("%d", p.x);
```

## Methods

A proplist value can be a function, making the proplist an object:

```c
var point = {
    x = 0, y = 0,
    DistanceTo = function(other) {
        return Distance(this.x, this.y, other.x, other.y);
    }
};
```

## Inheritance

Proplists inherit from their prototype. Use `GetPrototype` / `SetPrototype`
to inspect or change the chain.

## Common uses

- Menu item descriptors (see [Wire a menu](../cookbook/wire-a-menu.md)).
- Effect `vVar` payloads (see [Effects](effects.md)).
- Custom data attached to objects via `LocalN`.
