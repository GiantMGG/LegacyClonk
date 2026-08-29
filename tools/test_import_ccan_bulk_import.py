"""Pytest suite for the `bulk-import` subcommand (Phase 3 master index).

Isolates the master-index read/write + bulk-import orchestration by mocking
``_import_one`` to return a canned ``ImportResult`` with a real tmp_path
blob. No network, no c4group.

Run::

    python3.11 -m pytest tools/test_import_ccan_bulk_import.py -v
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import import_ccan as I


def _entry(ccan_id, destination, *, title=None, filename=None):
    return I.ManifestEntry(
        ccan_id=ccan_id,
        title=title or f"Pack{ccan_id}",
        author_nick="Author",
        author_uid=ccan_id,
        uploaded="2025-01-01",
        engine="LC",
        license="CC-BY-NC-4.0",
        license_rationale="r",
        filename=filename or f"{destination}.c4s",
        destination=destination,
        notes="n",
        requires=[],
        smoke=I.SmokeConfig(),
    )


def _write_manifest(tmp_path: Path, entries: list[I.ManifestEntry]) -> Path:
    p = tmp_path / "manifest.toml"
    lines = []
    for e in entries:
        lines.append(f"[entry.{e.ccan_id}]\n")
        for f in ("title", "ccan_id", "author_nick", "author_uid", "uploaded",
                  "engine", "license", "license_rationale", "filename",
                  "destination", "notes"):
            v = getattr(e, f)
            if isinstance(v, str):
                lines.append(f'{f} = "{v}"\n')
            else:
                lines.append(f"{f} = {v}\n")
    p.write_text("".join(lines), encoding="utf-8")
    return p


def _make_blob(tmp_path: Path, content: bytes = b"blob") -> Path:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(content)
    return blob


def test_bulk_import_writes_master_index(tmp_path, monkeypatch):
    e1 = _entry(100, "Alpha")
    e2 = _entry(200, "Beta")
    manifest = _write_manifest(tmp_path, [e1, e2])
    cc = tmp_path / "cc"
    cc.mkdir()
    blob = _make_blob(tmp_path)
    meta = I.CcanMetadata(
        ccan_id=0, title="", author_nick="", author_uid=0, uploaded="",
        engine="", filename="", description_de="", description_us="")

    calls = []
    def fake_import_one(entry, entries, content_community, c4group, force,
                        rate_limit, snapshot_dir=None):
        calls.append(entry.ccan_id)
        return I.ImportResult(
            status="imported", metadata=meta, blob_path=blob)

    monkeypatch.setattr(I, "_import_one", fake_import_one)
    monkeypatch.setattr(I, "resolve_c4group", lambda: Path("/bin/true"))

    rc = I.main([
        "bulk-import",
        "--manifest", str(manifest),
        "--content-community", str(cc),
        "--rate-limit", "0",
        "--failures-log", str(tmp_path / "fail.jsonl"),
    ])
    assert rc == 0
    assert calls == [100, 200]
    master = (cc / "ATTRIBUTION.toml").read_text(encoding="utf-8")
    assert "[pack.Alpha]" in master
    assert "[pack.Beta]" in master
    assert hashlib.sha256(b"blob").hexdigest() in master


def test_bulk_import_idempotent_second_run_skips(tmp_path, monkeypatch):
    e1 = _entry(100, "Alpha")
    manifest = _write_manifest(tmp_path, [e1])
    cc = tmp_path / "cc"
    cc.mkdir()
    blob = _make_blob(tmp_path)
    meta = I.CcanMetadata(
        ccan_id=0, title="", author_nick="", author_uid=0, uploaded="",
        engine="", filename="", description_de="", description_us="")

    statuses = iter(["imported", "skipped"])
    def fake_import_one(entry, entries, content_community, c4group, force,
                        rate_limit, snapshot_dir=None):
        return I.ImportResult(status=next(statuses), metadata=meta,
                               blob_path=blob)

    monkeypatch.setattr(I, "_import_one", fake_import_one)
    monkeypatch.setattr(I, "resolve_c4group", lambda: Path("/bin/true"))

    I.main(["bulk-import", "--manifest", str(manifest),
            "--content-community", str(cc), "--rate-limit", "0",
            "--failures-log", str(tmp_path / "f.jsonl")])
    before = (cc / "ATTRIBUTION.toml").read_text(encoding="utf-8")
    # Second run: _import_one returns "skipped" -> master index untouched.
    I.main(["bulk-import", "--manifest", str(manifest),
            "--content-community", str(cc), "--rate-limit", "0",
            "--failures-log", str(tmp_path / "f.jsonl")])
    after = (cc / "ATTRIBUTION.toml").read_text(encoding="utf-8")
    assert before == after


def test_bulk_import_continues_after_failure(tmp_path, monkeypatch):
    e1 = _entry(100, "Alpha")
    e2 = _entry(200, "Beta")
    e3 = _entry(300, "Gamma")
    manifest = _write_manifest(tmp_path, [e1, e2, e3])
    cc = tmp_path / "cc"
    cc.mkdir()
    blob = _make_blob(tmp_path)
    meta = I.CcanMetadata(
        ccan_id=0, title="", author_nick="", author_uid=0, uploaded="",
        engine="", filename="", description_de="", description_us="")

    def fake_import_one(entry, entries, content_community, c4group, force,
                        rate_limit, snapshot_dir=None):
        if entry.ccan_id == 200:
            raise SystemExit("validation failed")
        return I.ImportResult(status="imported", metadata=meta,
                              blob_path=blob)

    monkeypatch.setattr(I, "_import_one", fake_import_one)
    monkeypatch.setattr(I, "resolve_c4group", lambda: Path("/bin/true"))

    rc = I.main(["bulk-import", "--manifest", str(manifest),
                 "--content-community", str(cc), "--rate-limit", "0",
                 "--failures-log", str(tmp_path / "f.jsonl")])
    assert rc == 1  # failures present
    master = (cc / "ATTRIBUTION.toml").read_text(encoding="utf-8")
    assert "[pack.Alpha]" in master
    assert "[pack.Gamma]" in master
    assert "[pack.Beta]" not in master
    fail = (tmp_path / "f.jsonl").read_text(encoding="utf-8")
    assert "validation failed" in fail
    assert "200" in fail


def test_master_index_sorted_by_destination(tmp_path, monkeypatch):
    entries = [_entry(1, "Zeta"), _entry(2, "Alpha"), _entry(3, "Mu")]
    manifest = _write_manifest(tmp_path, entries)
    cc = tmp_path / "cc"
    cc.mkdir()
    blob = _make_blob(tmp_path)
    meta = I.CcanMetadata(
        ccan_id=0, title="", author_nick="", author_uid=0, uploaded="",
        engine="", filename="", description_de="", description_us="")

    def fake_import_one(entry, entries, content_community, c4group, force,
                        rate_limit, snapshot_dir=None):
        return I.ImportResult(status="imported", metadata=meta,
                              blob_path=blob)

    monkeypatch.setattr(I, "_import_one", fake_import_one)
    monkeypatch.setattr(I, "resolve_c4group", lambda: Path("/bin/true"))

    I.main(["bulk-import", "--manifest", str(manifest),
            "--content-community", str(cc), "--rate-limit", "0",
            "--failures-log", str(tmp_path / "f.jsonl")])
    master = (cc / "ATTRIBUTION.toml").read_text(encoding="utf-8")
    pos = {name: master.index(name) for name in
           ("[pack.Alpha]", "[pack.Mu]", "[pack.Zeta]")}
    assert pos["[pack.Alpha]"] < pos["[pack.Mu]"] < pos["[pack.Zeta]"]


def test_master_index_update_in_place(tmp_path, monkeypatch):
    e1 = _entry(100, "Alpha")
    manifest = _write_manifest(tmp_path, [e1])
    cc = tmp_path / "cc"
    cc.mkdir()
    # Pre-populate master index with an old sha256 block.
    (cc / "ATTRIBUTION.toml").write_text(
        "# Master attribution index.\n\n"
        "[pack.Alpha]\n"
        'ccan_id = 100\n'
        'sha256 = "oldsha"\n'
        'imported_at = "2026-01-01"\n\n',
        encoding="utf-8")
    blob = _make_blob(tmp_path)
    meta = I.CcanMetadata(
        ccan_id=0, title="", author_nick="", author_uid=0, uploaded="",
        engine="", filename="", description_de="", description_us="")

    def fake_import_one(entry, entries, content_community, c4group, force,
                        rate_limit, snapshot_dir=None):
        return I.ImportResult(status="imported", metadata=meta,
                              blob_path=blob)

    monkeypatch.setattr(I, "_import_one", fake_import_one)
    monkeypatch.setattr(I, "resolve_c4group", lambda: Path("/bin/true"))

    I.main(["bulk-import", "--manifest", str(manifest),
            "--content-community", str(cc), "--rate-limit", "0",
            "--failures-log", str(tmp_path / "f.jsonl")])
    master = (cc / "ATTRIBUTION.toml").read_text(encoding="utf-8")
    assert "oldsha" not in master
    assert hashlib.sha256(b"blob").hexdigest() in master
    # Only one Alpha block.
    assert master.count("[pack.Alpha]") == 1
