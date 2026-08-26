# Modder docs — contributor note

This directory holds the LegacyClonk modder documentation, built with
MkDocs Material and deployed via `mike` to GitHub Pages.

## Local preview

1. `pip install -r docs/requirements.txt`
2. `python tools/harvest_callbacks.py` (generates `docs/reference/**` pages)
3. `mkdocs serve` — open <http://127.0.0.1:8000>

The generated reference pages are gitignored; re-run the harvest whenever
the engine source changes.

## Editing content

- Hand-written pages live directly under `docs/` (quickstart, guide, cookbook).
- Curated descriptions for auto-generated reference live in
  `docs/reference/**/_curated.yaml` sidecars.
- The harvest script (`tools/harvest_callbacks.py`) is the only Python a
  reference maintainer touches.
