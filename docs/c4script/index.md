# C4Script language guide

C4Script is the scripting language used by the LegacyClonk engine to drive
object behaviour, scenarios, and game rules. This guide covers the language
from first principles.

## Pages

- [Syntax](syntax.md) — lexical structure, operators, comments.
- [Types](types.md) — the C4Script value types and how they convert.
- [Control flow](control-flow.md) — `if`, `while`, `for`, `return`.
- [Proplists](proplists.md) — the ubiquitous key/value container.
- [Effects](effects.md) — timed, stackable state attached to objects.
- [Actions](actions.md) — the animation + state-machine system.
- [Callback convention](callbacks-convention.md) — the `~` prefix and how
  the engine calls into your scripts.

## Reference

For the exhaustive list of every built-in function, every engine callback,
every global constant, and every `DefCore.txt` field, see the
[auto-generated reference](../reference/functions/index.md).
