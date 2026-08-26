# Wire a menu

**You will learn:** how to build a context menu with
[`CreateMenu`](../reference/functions/CreateMenu.md) and
[`AddMenuItem`](../reference/functions/AddMenuItem.md).

## Steps

1. In `Script.c`, add a callback that opens a menu (e.g. `Activate`).
2. Call `CreateMenu(0, this, 0, 0, "Menu", 0, 0, 0);` to open an empty menu.
3. Call `AddMenuItem("Option A", "OnOptionA", Icon, this);` for each option.
4. Implement the `OnOptionA` callback to react to the selection.

## Complete files

`Script.c`:

```c
func Activate(object by) {
    CreateMenu(0, this, 0, 0, "Menu", 0, 0, 0);
    AddMenuItem("Option A", "OnOptionA", Rock, this);
    AddMenuItem("Option B", "OnOptionB", Rock, this);
}

func OnOptionA(id idDef, object pTarget) {
    Message("A", this);
}
```
