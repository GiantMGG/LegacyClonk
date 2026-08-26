# Modder's quickstart — first custom object in under 60 minutes

This guide takes you from a fresh `git clone` to a custom object that fires
a callback, using only the console build (the full GUI build is currently
broken and out of scope). Budget: under 60 minutes.

## Prerequisites

- **CMake ≥ 4.0.** Debian stable ships CMake 3.31 and Ubuntu 24.04 LTS ships
  3.28 — both are insufficient. Install a recent CMake via
  `pip install cmake==4.4.2` or `snap install cmake --classic`.
- **A C++23 compiler.** GCC 14+, Clang 18+, or MSVC 19.40+ are known to work.
- **Build essentials** (`build-essential` on Debian/Ubuntu, or the equivalent
  "Desktop development with C++" workload on Windows).

See the root `README.md` for platform-specific build instructions.

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
ln -s "$(pwd)/build/clonk" ~/clonk/myclonk
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

The console engine starts in interactive mode. To load a scenario, pass its
`.c4f` path as the first argument:

```bash
# Example: load the tutorial scenario from the content tree
./myclonk /path/to/content-community/Tutorials/Tutorial.c4f
```

If you run `./myclonk` without arguments it drops into a prompt; type the
scenario path (or `help` for available commands). Any scenario placed under
`~/clonk/` that loads `Objects.c4d` will pick up your `MySword.c4d`: your
sword spawns and prints `Hello!` above it. The `Initialize` callback fires in
the console build too.

## Where next?

- [C4Script guide](c4script/index.md) — syntax, types, proplists, effects.
- [Cookbook](cookbook/index.md) — copy-paste recipes.
- [Function reference](reference/functions/index.md) — every built-in
  function, harvested from the engine.
- [Callback reference](reference/callbacks/object-lifecycle.md) — every
  engine callback, grouped by when it fires.
