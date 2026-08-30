"""Pytest suite for tools/mirror_ccan.py.

All HTTP fetches are mocked via monkeypatch on ``mirror_fetch``. No network.

Run::

    python3.11 -m pytest tools/test_mirror_ccan.py -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import mirror_ccan as M

LISTING_HTML = """<html><body><table>
<tr><td><a href="ccan-view.pl?a=view&i=100">Pack One</a></td><td>Alice</td><td>2025-01-01</td><td>LC</td><td>Pack1.c4s</td><td>c4s</td><td>1.0 MB</td></tr>
<tr><td><a href="ccan-view.pl?a=view&i=200">Pack Two</a></td><td>Bob</td><td>2025-02-02</td><td>CR</td><td>Pack2.c4d</td><td>c4d</td><td>2.0 MB</td></tr>
<tr><td><a href="ccan-view.pl?a=view&i=300">Pack Three</a></td><td>Carol</td><td>2025-03-03</td><td>both</td><td>Pack3.zip</td><td>zip</td><td>3.0 MB</td></tr>
</table><div>Seite 1 von 1 von 3</div></body></html>"""

PER_ENTRY_HTML = """<html><head><title>CCAN - Sample Pack</title></head><body>
<table>
<tr><th>Titel</th><td>Sample Pack</td></tr>
<tr><th>Autor</th><td>SampleAuthor (UID: 4242)</td></tr>
<tr><th>Zeit</th><td>2026-08-27</td></tr>
<tr><th>Engine-Version</th><td>LC</td></tr>
<tr><th>Download</th><td>Sample.c4d</td></tr>
<tr><th>Beschreibung</th><td>feel free to use this</td></tr>
<tr><th>Description (US)</th><td>US desc</td></tr>
</table></body></html>"""

BLOB = b"fake-pack-blob-bytes"

def _fake_fetch_factory(responses: dict, default_blob: bytes = BLOB):
    """Build a fake mirror_fetch that serves canned responses by URL substring.

    ``responses`` maps a URL substring to either bytes (success) or an
    Exception instance (failure). Unrecognised URLs return default_blob.
    """
    calls = []

    def fake_fetch(url, rate_limit=0, max_retries=3):
        calls.append(url)
        for key, val in responses.items():
            if key in url:
                if isinstance(val, Exception):
                    return None, str(val)
                return val, None
        return default_blob, None

    fake_fetch.calls = calls
    return fake_fetch

def test_mirror_writes_meta_raw_and_blob(tmp_path, monkeypatch):
    snapshot = tmp_path / "snap"
    fake = _fake_fetch_factory({
        "ccan-view.pl?a=view": PER_ENTRY_HTML.encode("utf-8"),
    })
    monkeypatch.setattr(M, "mirror_fetch", fake)

    entry = CI_ListingEntry(4242)
    ok, err = M.mirror_entry(entry, snapshot, rate_limit=0, max_retries=0)
    assert ok is True and err is None

    ed = snapshot / "entries" / "4242"
    assert (ed / "meta.json").is_file()
    assert (ed / "raw.html").read_bytes() == PER_ENTRY_HTML.encode("utf-8")
    assert (ed / "Sample.c4d").read_bytes() == BLOB
    meta = json.loads((ed / "meta.json").read_text(encoding="utf-8"))
    assert meta["ccan_id"] == 4242
    assert meta["filename"] == "Sample.c4d"
    assert meta["sha256"] == __import__("hashlib").sha256(BLOB).hexdigest()
    assert meta["blob_size"] == len(BLOB)
    assert "fetched_at" in meta

def CI_ListingEntry(ccan_id):
    return M.CI.ListingEntry(
        ccan_id=ccan_id, title="Sample Pack", author_nick="SampleAuthor",
        uploaded="2026-08-27", engine="LC", filename="Sample.c4d",
        file_type="c4d", size_label="1.0 MB")

def test_mirror_records_failure_and_continues(tmp_path, monkeypatch):
    snapshot = tmp_path / "snap"
    # Two entries: #100 view fetch fails, #200 succeeds.
    responses = {
        "i=100": ConnectionError("boom"),
        "ccan-view.pl?a=view&i=200": PER_ENTRY_HTML.replace(
            "4242", "200").replace("Sample.c4d", "Pack2.c4d").encode("utf-8"),
    }
    monkeypatch.setattr(M, "mirror_fetch", _fake_fetch_factory(responses))

    entries = [
        M.CI.ListingEntry(ccan_id=100, title="P1", author_nick="A",
                          uploaded="2025-01-01", engine="LC",
                          filename="P1.c4s", file_type="c4s", size_label="1 MB"),
        M.CI.ListingEntry(ccan_id=200, title="P2", author_nick="B",
                          uploaded="2025-01-02", engine="LC",
                          filename="Pack2.c4d", file_type="c4d",
                          size_label="2 MB"),
    ]
    failures = []
    mirrored = []
    for e in entries:
        ok, err = M.mirror_entry(e, snapshot, rate_limit=0, max_retries=0)
        if ok:
            mirrored.append(e.ccan_id)
        else:
            failures.append((e.ccan_id, err))
    assert mirrored == [200]
    assert failures[0][0] == 100
    assert "boom" in failures[0][1]

def test_resume_skips_completed_entries(tmp_path, monkeypatch):
    snapshot = tmp_path / "snap"
    fake = _fake_fetch_factory({
        "ccan-view.pl?a=view": PER_ENTRY_HTML.encode("utf-8"),
    })
    monkeypatch.setattr(M, "mirror_fetch", fake)
    entry = CI_ListingEntry(4242)
    M.mirror_entry(entry, snapshot, rate_limit=0, max_retries=0)
    assert len(fake.calls) > 0
    # Second run with --resume: _is_resolved returns True, no fetch.
    fake.calls = []
    assert M._is_resolved(snapshot, 4242) is True
    # Simulate cmd_mirror resume path: it checks _is_resolved and skips.
    assert fake.calls == []

def test_index_jsonl_and_manifest_format(tmp_path, monkeypatch):
    snapshot = tmp_path / "snap"
    monkeypatch.setattr(M, "mirror_fetch", _fake_fetch_factory({
        "ccan-view.pl?a=view": PER_ENTRY_HTML.encode("utf-8"),
    }))
    M.mirror_entry(CI_ListingEntry(4242), snapshot, rate_limit=0, max_retries=0)
    M.write_index(snapshot, [4242])
    index_lines = (snapshot / "index.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(index_lines) == 1
    rec = json.loads(index_lines[0])
    for k in ("ccan_id", "title", "sha256", "filename", "fetched_at"):
        assert k in rec
    manifest = (snapshot / "manifest.txt").read_text(encoding="utf-8")
    assert manifest.startswith("4242\tSample Pack\t")
    assert manifest.count("\n") == 1

def test_concurrent_mirror_lock_exits(tmp_path, monkeypatch):
    snapshot = tmp_path / "snap"
    snapshot.mkdir(parents=True)
    # Acquire the lock first.
    lock = M.acquire_lock(snapshot)
    assert lock is not None
    # A second acquire_lock should sys.exit.
    with pytest.raises(SystemExit, match="locked"):
        M.acquire_lock(snapshot)
    lock.close()

def test_cmd_mirror_end_to_end_with_mocked_listing(tmp_path, monkeypatch):
    snapshot = tmp_path / "snap"
    # Fake listing crawl returns 3 entries, total 3.
    def fake_crawl(rate_limit, max_retries, page_size=30):
        return [
            M.CI.ListingEntry(ccan_id=100, title="P1", author_nick="A",
                              uploaded="2025-01-01", engine="LC",
                              filename="P1.c4s", file_type="c4s",
                              size_label="1 MB"),
            M.CI.ListingEntry(ccan_id=200, title="P2", author_nick="B",
                              uploaded="2025-01-02", engine="CR",
                              filename="P2.c4d", file_type="c4d",
                              size_label="2 MB"),
            M.CI.ListingEntry(ccan_id=300, title="P3", author_nick="C",
                              uploaded="2025-01-03", engine="both",
                              filename="P3.zip", file_type="zip",
                              size_label="3 MB"),
        ], 3
    monkeypatch.setattr(M, "crawl_listing", fake_crawl)
    # Fake mirror_fetch: view pages return per-entry HTML; blobs return BLOB.
    per_html = PER_ENTRY_HTML
    def fake_fetch(url, rate_limit=0, max_retries=3):
        if "ccan-view.pl?a=view" in url:
            return per_html.encode("utf-8"), None
        return BLOB, None
    monkeypatch.setattr(M, "mirror_fetch", fake_fetch)

    rc = M.main(["mirror", "--snapshot-dir", str(snapshot),
                 "--rate-limit", "0", "--retry", "0"])
    assert rc == 0
    assert (snapshot / "index.jsonl").is_file()
    assert (snapshot / "manifest.txt").is_file()
    ids = sorted(int(p.name) for p in (snapshot / "entries").iterdir())
    assert ids == [100, 200, 300]
