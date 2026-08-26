# Custom sword

**You will learn:** how to create a definition with a `Hit` callback that
calls [`Explode`](../reference/functions/Explode.md).

## Steps

1. Copy `docs/skeletons/MySword.c4d/` into `content/Objects.c4d/`.
2. Edit `DefCore.txt` and set `Name=Sword`.
3. Edit `Script.c` and add a `Hit` callback.
4. Run the engine and pick a scenario that loads `Objects.c4d`.

## Complete files

`DefCore.txt`:

```
Name = Sword
Category = 1024
Picture = 0,0,16,16
```

`Script.c`:

```c
func Hit() {
    Explode(20, this);
}
```
