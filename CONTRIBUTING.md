# Contributing to LegacyClonk

Thank you for your interest in contributing to LegacyClonk! This guide covers the TODO/FIXME marker convention and points to the resources you need to get started.

## TODO/FIXME marker convention

Every new `TODO`, `FIXME`, `HACK`, `XXX`, or `BUG` marker in source code must include a link to an open issue on the upstream tracker:

```
// TODO(legacyclonk/LegacyClonk#NNN): <one-line summary>
// FIXME(legacyclonk/LegacyClonk#NNN): <one-line summary>
```

### Rules

1. **Accepted prefixes:** `TODO`, `FIXME`, `HACK`, `XXX`, `BUG` — upper-case only.
2. **Required suffix:** `(legacyclonk/LegacyClonk#NNN)` where `#NNN` is an open issue on the [upstream tracker](https://github.com/legacyclonk/LegacyClonk/issues). The full `owner/repo#NNN` form is mandatory.
3. **One-line summary** after the colon. If the marker spans multiple lines, the issue link must be on the first line.
4. **File the issue first.** The issue must already exist before you push the marker. Use `gh issue create --repo legacyclonk/LegacyClonk --title "..." --body "..."` or the web UI.
5. **The lint does not verify the issue is open** — it checks format only. Code review is the backstop.

### Enforcement

The `tools/check_todos.py` lint runs in CI (`.github/workflows/todo-lint.yml`) on every push and pull request. It fails if a non-conforming marker is added.

### Grandfathered markers

57 existing markers are grandfathered via `tools/todo-legacy-allowlist.txt`. If you move a grandfathered marker (changing its line number), the lint will fail. You must either:
- (a) Add an issue link and remove the allowlist entry, or
- (b) Update the allowlist entry to the new line number.

## Build instructions

See `AGENTS.md` in the repository root for build configuration, CMake options, and toolchain requirements.

## Code style

- Tabs, UTF-8, trim trailing whitespace, final newline (`.editorconfig`).
- Run `python3 tools/auto_format.py <lc_dir> -w` to format in place.

## Tests

Tests use Catch2. Enable with `-DUSE_TESTS=On` at configure time. See `AGENTS.md` for details.

## Triage worksheet

The full inventory of TODO/FIXME markers is in `docs/TODO-FIXME-triage.md`. This is a frozen snapshot — future cycles resolve the oldest open markers and flip their status to `resolved`.
