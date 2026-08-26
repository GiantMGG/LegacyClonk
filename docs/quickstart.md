# Modder's quickstart — first custom object in under 60 minutes

This guide takes you from a fresh `git clone` to a custom object that fires
a callback, using only the console build (the full GUI build is currently
broken and out of scope). Budget: under 60 minutes.

## 1. Clone and configure (console build only)

```bash
git clone https://github.com/legacyclonk/LegacyClonk.git
cd LegacyClonk
cmake -B build -DUSE_CONSOLE=ON
```

## 2. Build

```bash
cmake --build build
```

You now have `build/clonk` (the console engine) and `build/c4group` (the
archive tool).

## 3. Set up a runtime folder

```bash
mkdir -p ~/clonk
ln -s build/clonk ~/clonk/myclonk
ln -s planet/Graphics.c4g planet/System.c4g ~/clonk
```

## 4. Copy the shipped skeleton

```bash
cp -r docs/skeletons/MySword.c4d content/Objects.c4d/
```

Edit `content/Objects.c4d/MySword.c4d/DefCore.txt` and set `Name=My Sword`.

## 5. Add a callback

Edit `content/Objects.c4d/MySword.c4d/Script.c` and add:

```c
func Initialize() {
    Message("Hello!", this);
}
```

## 6. Run and see the message

```bash
cd ~/clonk
./myclonk
```

Pick a scenario that loads `Objects.c4d`. Your sword spawns and prints
`Hello!` above it. The `Initialize` callback fires in the console build too.

## Where next?

- [C4Script guide](c4script/index.md) — syntax, types, proplists, effects.
- [Cookbook](cookbook/index.md) — copy-paste recipes.
- [Function reference](reference/functions/index.md) — every built-in
  function, harvested from the engine.
- [Callback reference](reference/callbacks/object-lifecycle.md) — every
  engine callback, grouped by when it fires.
