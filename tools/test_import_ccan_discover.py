"""Pytest suite for the `discover` subcommand (Phase 2 license triage).

Synthetic index.jsonl fixtures written to tmp_path. No network.

Run::

    python3.11 -m pytest tools/test_import_ccan_discover.py -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import import_ccan as I


def _write_index(tmp_path: Path, records: list[dict]) -> Path:
    snap = tmp_path / "snap"
    snap.mkdir()
    idx = snap / "index.jsonl"
    idx.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return snap


def _meta(ccan_id, *, title="P", description_de="", description_us="",
          comments="", engine="LC", filename="P.c4s", blob_size=1000,
          author_nick="A", author_uid=1, uploaded="2025-01-01"):
    return {
        "ccan_id": ccan_id, "title": title, "author_nick": author_nick,
        "author_uid": author_uid, "uploaded": uploaded, "engine": engine,
        "filename": filename, "description_de": description_de,
        "description_us": description_us, "comments": comments,
        "sha256": "x", "blob_size": blob_size,
        "fetched_at": "2026-08-30T00:00:00Z",
        "view_url": "https://ccan.de/cgi-bin/ccan/ccan-view.pl?a=view&i=%d" % ccan_id,
        "download_url": "https://ccan.de/cgi-bin/ccan/ccan-dl-auth.pl/%d/%s" % (ccan_id, filename),
        "is_pack": True,
    }


def _run_discover(snap: Path, tmp_path: Path, *, engine="LC", max_size=0.0):
    out_m = tmp_path / "ccan_discovered.toml"
    out_s = tmp_path / "ccan_triage_skip.txt"
    rc = I.main([
        "discover",
        "--snapshot-dir", str(snap),
        "--engine", engine,
        "--max-size", str(max_size),
        "--out-manifest", str(out_m),
        "--out-skip", str(out_s),
    ])
    return rc, out_m, out_s


def test_triage_default_ok(tmp_path):
    snap = _write_index(tmp_path, [_meta(100, title="Hazard 3D")])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    text = out_m.read_text(encoding="utf-8")
    assert "[entry.100]" in text
    assert 'license = "CC-BY-NC-4.0"' in text
    assert 'destination = "Hazard3D"' in text
    assert out_s.read_text(encoding="utf-8") == ""


def test_triage_skip_keyword_en(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, description_de="Please no reupload of this pack."),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    assert out_m.read_text(encoding="utf-8") == "" or "[entry.100]" not in out_m.read_text(encoding="utf-8")
    skip = out_s.read_text(encoding="utf-8")
    assert "100\tskip\tno reupload" in skip


def test_triage_skip_keyword_de(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, description_de="Bitte kein reupload."),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    skip = out_s.read_text(encoding="utf-8")
    assert "100\tskip\tkein reupload" in skip


def test_triage_ambiguous(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, description_de="feel free to use this but please ask first"),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    text = out_m.read_text(encoding="utf-8")
    assert "[entry.100]" in text
    assert 'license = "unknown"' in text


def test_triage_first_matching_rule_wins(tmp_path):
    # "no reupload" (skip) appears before "please ask" (ambiguous) in the
    # rule file; an entry matching both should be skip.
    snap = _write_index(tmp_path, [
        _meta(100, description_de="no reupload please ask"),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    skip = out_s.read_text(encoding="utf-8")
    assert "100\tskip\tno reupload" in skip
    assert "[entry.100]" not in out_m.read_text(encoding="utf-8")


def test_filter_engine_lc(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, engine="CR", title="CR Pack"),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path, engine="LC")
    assert rc == 0
    skip = out_s.read_text(encoding="utf-8")
    assert "100\tengine_filter" in skip


def test_filter_text_only(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, filename="compilation.txt", title="Comp"),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    skip = out_s.read_text(encoding="utf-8")
    assert "100\ttext_only" in skip


def test_filter_max_size(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, blob_size=2_000_000, title="Big"),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path, max_size=1.0)
    assert rc == 0
    skip = out_s.read_text(encoding="utf-8")
    assert "100\tsize_filter" in skip


def test_destination_slug_collision(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, title="Hazard 3D"),
        _meta(200, title="Hazard 3D"),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    text = out_m.read_text(encoding="utf-8")
    assert 'destination = "Hazard3D"' in text
    assert 'destination = "Hazard3D-200"' in text
    skip = out_s.read_text(encoding="utf-8")
    assert "200\tdestination_collision" in skip


def test_discovered_manifest_loads(tmp_path):
    snap = _write_index(tmp_path, [
        _meta(100, title="Pack A", filename="A.c4s"),
        _meta(200, title="Pack B", filename="B.c4s"),
        _meta(300, title="Pack C", filename="C.c4s"),
    ])
    rc, out_m, out_s = _run_discover(snap, tmp_path)
    assert rc == 0
    entries = I.load_manifest(out_m)
    assert len(entries) == 3
    assert {e.ccan_id for e in entries} == {100, 200, 300}


def test_discover_missing_index_exits(tmp_path):
    snap = tmp_path / "nosnap"
    snap.mkdir()
    with pytest.raises(SystemExit, match="Snapshot index not found"):
        _run_discover(snap, tmp_path)
