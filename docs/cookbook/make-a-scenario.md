# Make a scenario

**You will learn:** how to assemble a playable `.c4f` scenario folder.

## Steps

1. Create a folder `content/MyScenario.c4f/`.
2. Add a `Map.txt` (the landscape) and `Objects.txt` (initial objects).
3. Add a `Script.c` with a `Initialize` callback that sets up the goal.
4. Symlink or copy the folder into your runtime `~/clonk/` folder.

## Complete files

`Map.txt`:

```
Earth=12;
Tunnel=0;
Water=0;
```

`Objects.txt`:

```
[0]
id=Rock
x=100
y=50
```

`Script.c`:

```c
func Initialize() {
    CreateObject(Goal, 0, 0, -1);
    Message("Scenario started", this);
}
```
