# Scenario objective

**You will learn:** how to add a win condition to a scenario via the
`IsFulfilled` callback.

## Steps

1. Create a goal object (category `C4D_Goal`).
2. Implement `IsFulfilled` to return `true` when the win condition is met.
3. Place the goal object in the scenario's `Objects.txt`.

## Complete files

`Script.c`:

```c
func IsFulfilled() {
    // Win when at least 10 rocks exist.
    return ObjectCount(Rock) >= 10;
}
```
