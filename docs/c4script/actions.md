# Actions

Actions are the engine's animation + state-machine system. Each action is
defined in the object's `ActMap.txt` and the engine advances through the
action's phases, calling the `ActMap`'s `NextAction` when the phase wraps.

## Defining an action

In `ActMap.txt`:

```
ActMap = {
  Walk = {
    Prototype = Action,
    Name = "Walk",
    Procedure = DFA_WALK,
    Directions = 2,
    FlipDir = 1,
    Length = 8,
    Delay = 2,
    NextAction = "Walk",
  },
};
```

## Action callbacks

The engine fires callbacks as actions progress. See the
[action callbacks reference](../reference/callbacks/actions.md).

## Switching actions

```c
SetAction("Walk");
SetAction("Jump");
```
