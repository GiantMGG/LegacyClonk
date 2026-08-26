# Flammable object

**You will learn:** how to make an object catch fire using
[`Incinerate`](../reference/functions/Incinerate.md).

## Steps

1. Create a new `.c4d` folder under `content/Objects.c4d/`.
2. Set `ContactIncinerate=1` in `DefCore.txt` so the object ignites on contact.
3. (Optional) Add an `Incineration` callback in `Script.c` to react.

## Complete files

`DefCore.txt`:

```
Name = Crate
Category = 1024
ContactIncinerate = 1
```

`Script.c`:

```c
func Incineration(int iCausedBy) {
    // Explode after burning for a moment.
    Schedule("Explode(30, this)", 70);
}
```
