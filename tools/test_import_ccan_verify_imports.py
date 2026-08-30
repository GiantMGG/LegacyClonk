"""Pytest suite for the `verify-imports` subcommand (Phase 4 update
detection). Synthetic master index + mocked fetch. No network.

Run::

    python3.11 -m pytest tools/test_import_ccan_verify_imports.py -v
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import import_ccan as I

BLOB = b"pack-blob-bytes"

def _make_cc(tmp_path: Path, packs: dict) -> Path:
    cc = tmp_path / "cc"
    cc.mkdir()
    # On-disk destination dirs.
    for dest in packs:
        (cc / dest).mkdir()
    # Master index.
    lines = ["# Master attribution index.\n\n"]
    for dest in sorted(packs):
        lines.append(f"[pack.{dest}]\n")
        for f, v in packs[dest].items():
            if isinstance(v, str):
                lines.append(f'{f} = "{v}"\n')
            else:
                lines.append(f"{f} = {v}\n")
        lines.append("\n")
    (cc / "ATTRIBUTION.toml").write_text("".join(lines), encoding="utf-8")
    return cc

def _run_verify(cc: Path, tmp_path: Path, *, snapshot_dir=None,
                fake_fetch=None, monkeypatch):
    if fake_fetch:
        monkeypatch.setattr(I, "fetch_url", fake_fetch)
    argv = ["verify-imports", "--content-community", str(cc),
            "--rate-limit", "0"]
    if snapshot_dir:
        argv += ["--snapshot-dir", str(snapshot_dir)]
    return I.main(argv)

def test_verify_imports_no_changes(tmp_path, monkeypatch):
    sha = hashlib.sha256(BLOB).hexdigest()
    cc = _make_cc(tmp_path, {
        "Alpha": {"ccan_id": 100, "sha256": sha, "filename": "Alpha.c4s",
                  "download_url": "https://x/Alpha.c4s"},
    })
    monkeypatch.setattr(I, "fetch_url", lambda url, rate_limit=0: BLOB)
    rc = _run_verify(cc, tmp_path, monkeypatch=monkeypatch)
    assert rc == 0
    report = Path("ccan_verify_imports_report.md")
    assert report.is_file()
    text = report.read_text(encoding="utf-8")
    assert "unchanged: 1" in text
    report.unlink()

def test_verify_imports_detects_sha256_mismatch(tmp_path, monkeypatch):
    cc = _make_cc(tmp_path, {
        "Alpha": {"ccan_id": 100, "sha256": "oldsha",
                  "filename": "Alpha.c4s",
                  "download_url": "https://x/Alpha.c4s"},
    })
    monkeypatch.setattr(I, "fetch_url", lambda url, rate_limit=0: BLOB)
    rc = _run_verify(cc, tmp_path, monkeypatch=monkeypatch)
    assert rc == 1  # changed -> non-zero
    report = Path("ccan_verify_imports_report.md")
    text = report.read_text(encoding="utf-8")
    assert "changed: 1" in text
    assert "oldsha" in text
    assert hashlib.sha256(BLOB).hexdigest() in text
    report.unlink()

def test_verify_imports_detects_deleted_entry(tmp_path, monkeypatch):
    cc = _make_cc(tmp_path, {
        "Alpha": {"ccan_id": 100, "sha256": "x",
                  "filename": "Alpha.c4s",
                  "download_url": "https://x/Alpha.c4s"},
    })
    # fetch_url sys.exits on 404; simulate that.
    def fake_fetch(url, rate_limit=0):
        raise SystemExit("CCAN entry not found (HTTP 404): " + url)
    monkeypatch.setattr(I, "fetch_url", fake_fetch)
    rc = _run_verify(cc, tmp_path, monkeypatch=monkeypatch)
    assert rc == 1
    report = Path("ccan_verify_imports_report.md")
    text = report.read_text(encoding="utf-8")
    assert "missing (CCAN deleted): 1" in text
    report.unlink()

def test_verify_imports_detects_local_missing(tmp_path, monkeypatch):
    cc = _make_cc(tmp_path, {
        "Alpha": {"ccan_id": 100, "sha256": "x",
                  "filename": "Alpha.c4s",
                  "download_url": "https://x/Alpha.c4s"},
    })
    # Remove the on-disk destination dir so it's "local_missing".
    (cc / "Alpha").rmdir()
    monkeypatch.setattr(I, "fetch_url", lambda url, rate_limit=0: BLOB)
    rc = _run_verify(cc, tmp_path, monkeypatch=monkeypatch)
    assert rc == 1
    report = Path("ccan_verify_imports_report.md")
    text = report.read_text(encoding="utf-8")
    assert "local_missing" in text
    report.unlink()

def test_verify_imports_reads_blob_from_snapshot(tmp_path, monkeypatch):
    sha = hashlib.sha256(BLOB).hexdigest()
    cc = _make_cc(tmp_path, {
        "Alpha": {"ccan_id": 100, "sha256": sha,
                  "filename": "Alpha.c4s",
                  "download_url": "https://x/Alpha.c4s"},
    })
    snap = tmp_path / "snap"
    (snap / "entries" / "100").mkdir(parents=True)
    (snap / "entries" / "100" / "Alpha.c4s").write_bytes(BLOB)
    # fetch_url must NOT be called when the snapshot has the blob.
    def boom(url, rate_limit=0):
        raise AssertionError("fetch_url should not be called")
    monkeypatch.setattr(I, "fetch_url", boom)
    rc = _run_verify(cc, tmp_path, snapshot_dir=snap, monkeypatch=monkeypatch)
    assert rc == 0
    Path("ccan_verify_imports_report.md").unlink()

def test_verify_imports_missing_master_index_exits(tmp_path, monkeypatch):
    cc = tmp_path / "cc"
    cc.mkdir()
    with pytest.raises(SystemExit, match="generate the master index"):
        _run_verify(cc, tmp_path, monkeypatch=monkeypatch)
