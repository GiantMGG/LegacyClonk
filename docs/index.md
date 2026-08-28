# LegacyClonk Modder Docs

Welcome to the LegacyClonk modder documentation. LegacyClonk is a C++23
fan-made continuation of the Clonk Rage engine. These docs cover everything
a modder needs to create custom objects, scenarios, and effects with the
C4Script language.

[Start modding in 1 hour](tutorials/first-object.md){ .md-button .md-button--primary }

## What you will find here

- **[First object tutorial](tutorials/first-object.md)** — from `git clone` to a first custom object
  firing a callback in under 60 minutes.
- **[C4Script guide](c4script/index.md)** — the hand-written language
  reference: syntax, types, control flow, proplists, effects, actions, and
  the `~` callback convention.
- **[Cookbook](cookbook/index.md)** — copy-paste recipes for common modder
  tasks.
- **[Reference](reference/functions/index.md)** — auto-generated,
  always-in-sync callback, function, constant, and DefCore.txt field
  reference harvested directly from the engine source.

## Why auto-generated reference?

The C4Script callback list, built-in function list, global constants, and
DefCore.txt field list are all harvested directly from engine source, so the
reference can never drift from the engine. The harvest is a read-only Python
script that parses three specific engine files; it does not require the
engine to build and does not modify any engine source.
