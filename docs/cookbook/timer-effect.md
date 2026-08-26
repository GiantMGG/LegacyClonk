# Timer effect

**You will learn:** how to create a stackable timed effect with
[`AddEffect`](../reference/functions/AddEffect.md).

## Steps

1. In `Script.c`, define an `Fx<MyEffect>Start`, `Fx<MyEffect>Timer`, and
   `Fx<MyEffect>Stop` callback.
2. Call `AddEffect("IntPoison", this, 100, 35, this);` from a trigger
   (e.g. `Damage`).
3. The engine calls `FxIntPoisonTimer` every 35 frames.

## Complete files

`Script.c`:

```c
func Damage(int iChange, int iCausedBy) {
    AddEffect("IntPoison", this, 100, 35, this);
}

func FxIntPoisonStart(target, nr, temp) {
    return true;
}

func FxIntPoisonTimer(target, nr, time) {
    DoEnergy(-1, target);
    if (time > 350) return -1; // end the effect
    return;
}
```
