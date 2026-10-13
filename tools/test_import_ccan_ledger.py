"""Pytest suite for the `ledger` subcommand (IMPORT-LEDGER.md rendering).

Renders the human-readable import ledger from the master ATTRIBUTION.toml
index ([pack.*] blocks) + the curated manifest (smoke-waiver section).

Run::

    python3.11 -m pytest tools/test_import_ccan_ledger.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import import_ccan as I

LEDGER_COLUMNS = (
    "rank | ccan_id | title | author | rating | votes | downloads | "
    "license | license_rationale | destination | verification"
)

def _write_attribution(tmp_path: Path) -> Path:
    cc = tmp_path / "cc"
    cc.mkdir()
    (cc / "ATTRIBUTION.toml").write_text(
        "[pack.Alpha]\n"
        "ccan_id = 100\n"
        'title = "Alpha Pack"\n'
        'author_nick = "Author"\n'
        "rating = 2.9\n"
        "votes = 23\n"
        "downloads = 2615\n"
        "rank = 1\n"
        'license = "CC-BY-NC-4.0"\n'
        'license_rationale = "CCAN default"\n'
        'verification = "ccan_smoke_Alpha"\n\n',
        encoding="utf-8",
    )
    return cc

def _write_manifest(tmp_path: Path, *, skip=False, reason="") -> Path:
    p = tmp_path / "manifest.toml"
    lines = [
        "[entry.100]\n"
        'title = "Alpha Pack"\n'
        "ccan_id = 100\n"
        'author_nick = "Author"\n'
        "author_uid = 7\n"
        'uploaded = "2026-01-01"\n'
        'engine = "LC"\n'
        'license = "CC-BY-NC-4.0"\n'
        'license_rationale = "CCAN default"\n'
        'filename = "Alpha.c4s"\n'
        'destination = "Alpha"\n'
        'notes = "n"\n',
    ]
    if skip or reason:
        lines.append("[entry.100.smoke]\n")
        lines.append("skip = true\n" if skip else "skip = false\n")
        if reason:
            lines.append(f'reason = "{reason}"\n')
    p.write_text("".join(lines), encoding="utf-8")
    return p

def _run_ledger(cc: Path, manifest: Path, out: Path) -> int:
    return I.main([
        "ledger",
        "--manifest", str(manifest),
        "--content-community", str(cc),
        "--out", str(out),
    ])

def test_ledger_renders_table_with_license_column(tmp_path):
    cc = _write_attribution(tmp_path)
    manifest = _write_manifest(tmp_path)
    out = tmp_path / "IMPORT-LEDGER.md"
    rc = _run_ledger(cc, manifest, out)
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert f"| {LEDGER_COLUMNS} |" in text
    row = ("| 1 | 100 | Alpha Pack | Author | 2.9 | 23 | 2615 | "
           "CC-BY-NC-4.0 | CCAN default | Alpha | ccan_smoke_Alpha |")
    assert row in text

def test_ledger_renders_waiver_section(tmp_path):
    cc = _write_attribution(tmp_path)
    manifest = _write_manifest(tmp_path, skip=True, reason="legacy fatal")
    out = tmp_path / "IMPORT-LEDGER.md"
    rc = _run_ledger(cc, manifest, out)
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "## Smoke waivers" in text
    assert "Alpha" in text
    assert "legacy fatal" in text

def test_ledger_missing_attribution_fails_cleanly(tmp_path):
    manifest = _write_manifest(tmp_path)
    out = tmp_path / "IMPORT-LEDGER.md"
    with pytest.raises(SystemExit) as exc:
        I.main([
            "ledger",
            "--manifest", str(manifest),
            "--content-community", str(tmp_path / "cc"),
            "--out", str(out),
        ])
    assert exc.value.code != 0
    assert "ATTRIBUTION.toml" in str(exc.value)
