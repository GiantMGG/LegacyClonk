"""Pytest suite for tools/ccan_index.py.

Synthetic HTML fixtures (inline strings); no network.

Run::

    python3.11 -m pytest tools/test_ccan_index.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ccan_index as CI

LISTING_HTML_3 = """<html><body>
<table>
<tr><td><a href="ccan-view.pl?a=view&i=100">Pack One</a></td><td>Alice</td><td>2025-01-01</td><td>LC</td><td>Pack1.c4s</td><td>c4s</td><td>1.0 MB</td></tr>
<tr><td><a href="ccan-view.pl?a=view&i=200">Pack Two</a></td><td>Bob</td><td>2025-02-02</td><td>CR</td><td>Pack2.c4d</td><td>c4d</td><td>2.0 MB</td></tr>
<tr><td><a href="ccan-view.pl?a=view&i=300">Pack Three</a></td><td>Carol</td><td>2025-03-03</td><td>both</td><td>Pack3.zip</td><td>zip</td><td>3.0 MB</td></tr>
</table>
<div>Seite 1 von 41 - Eintraege 1 bis 30 von 3695</div>
</body></html>"""

PER_ENTRY_HTML = """<!DOCTYPE html>
<html><head><title>CCAN - Sample Pack</title></head><body>
<table>
<tr><th>Titel</th><td>Sample Pack</td></tr>
<tr><th>Autor</th><td>SampleAuthor (UID: 4242)</td></tr>
<tr><th>Zeit</th><td>2026-08-27</td></tr>
<tr><th>Engine-Version</th><td>LC</td></tr>
<tr><th>Download</th><td>Sample.c4d</td></tr>
<tr><th>Beschreibung</th><td>Feel free to use this if you wanna make your own 3D scenarios</td></tr>
<tr><th>Description (US)</th><td>Sample US description</td></tr>
</table>
<div id="comments"><p>First comment by Dave.</p><p>Second comment by Eve.</p></div>
</body></html>"""

def test_parse_listing_collects_entries():
    page = CI.parse_listing(LISTING_HTML_3)
    assert len(page.entries) == 3
    ids = [e.ccan_id for e in page.entries]
    assert ids == [100, 200, 300]
    e0 = page.entries[0]
    assert e0.title == "Pack One"
    assert e0.author_nick == "Alice"
    assert e0.uploaded == "2025-01-01"
    assert e0.engine == "LC"
    assert e0.filename == "Pack1.c4s"
    assert e0.file_type == "c4s"
    assert e0.size_label == "1.0 MB"
    assert e0.is_pack is True

def test_parse_listing_detects_pagination_and_total():
    page = CI.parse_listing(LISTING_HTML_3)
    assert page.page_number == 1
    assert page.total_pages == 41
    assert page.total_entries == 3695

def test_parse_listing_empty_table():
    page = CI.parse_listing("<html><body><table></table></body></html>")
    assert page.entries == []
    assert page.total_entries == 0

def test_parse_per_entry_populates_all_fields():
    per = CI.parse_per_entry(PER_ENTRY_HTML, 4242)
    assert per.ccan_id == 4242
    assert per.title == "Sample Pack"
    assert per.author_nick.startswith("SampleAuthor")
    assert per.author_uid == 4242
    assert per.uploaded == "2026-08-27"
    assert per.engine == "LC"
    assert per.filename == "Sample.c4d"
    assert "feel free to use this" in per.description_de.lower()
    assert per.description_us == "Sample US description"
    assert "First comment by Dave" in per.comments
    assert "Second comment by Eve" in per.comments
    assert per.view_url == (
        "https://ccan.de/cgi-bin/ccan/ccan-view.pl?a=view&i=4242")
    assert per.download_url == (
        "https://ccan.de/cgi-bin/ccan/ccan-dl-auth.pl/4242/Sample.c4d")

def test_extract_comments_returns_empty_when_absent():
    assert CI.extract_comments("<html><body>no comments</body></html>") == ""

def test_extract_comments_case_insensitive_id():
    html = '<div id="Comments">hello world</div>'
    assert "hello world" in CI.extract_comments(html)
