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

# ===========================================================================
# L-series: live listing layouts (Phase-0 population crawl prerequisite).
# L1/L2 model the live CCAN pages (5-column default and 11-column enriched);
# L4/L5/L6 pin the new evidence-based behaviour; L3 is the legacy 7-column
# synthetic pin above (stays green throughout).
# ===========================================================================

# The enriched column order the Phase-0 population tool passes to
# parse_listing (Task 2). test_ccan_index does not import the tool; the
# literal is kept inline per the L7 convention.
LIVE_COLUMN_ORDER = [
    "entry_type", "title", "dl", "category", "author",
    "engine", "niveau", "votes", "downloads", "size", "uploaded",
]

LIVE_5COL_HTML = """<html><body>
<table>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=6417">Clonkworks Expansion</a></td><td><a href="ccan-dl-auth.pl/6417/Clonkworks.c4d">Clonkworks.c4d</a></td><td><a href="ccan-user.pl?a=info&i=89">TomB</a></td><td>2026-08-27</td></tr>
<tr><td>Objekt</td><td><a href="ccan-view.pl?a=view&i=6416">Bridge Kit</a></td><td><a href="ccan-dl-auth.pl/6416/Bridge.c4d">Bridge.c4d</a></td><td><a href="ccan-user.pl?a=info&i=4242">Alice</a></td><td>2026-07-15</td></tr>
<tr><td>Dokument</td><td><a href="ccan-view.pl?a=view&i=6415">Design Doc</a></td><td><a href="ccan-dl-auth.pl/6415/Design.pdf">Design.pdf</a></td><td><a href="ccan-user.pl?a=info&i=77">Bob</a></td><td>2026-06-01</td></tr>
</table>
<div>Seite 1 von 124 – Einträge 1-30 von 3697, davon 2 unter Niveau</div>
</body></html>"""

def test_l1_live_default_5col_listing():
    """Live default listing renders 5 columns - every row must survive the
    legacy >=7-cell gate, and the footer must report the range total, not the
    'davon N' clause."""
    page = CI.parse_listing(LIVE_5COL_HTML)
    assert len(page.entries) == 3
    assert [e.ccan_id for e in page.entries] == [6417, 6416, 6415]
    e0 = page.entries[0]
    assert e0.title == "Clonkworks Expansion"
    assert e0.author_nick == "TomB"
    assert e0.uploaded == "2026-08-27"
    assert e0.engine == ""
    assert e0.size_label == ""
    assert e0.niveau_numeric is None
    assert page.page_number == 1
    assert page.total_pages == 124
    assert page.total_entries == 3697

def test_l3_legacy_seven_column_pin():
    """The legacy synthetic 7-column fixture parses exactly as before the
    evidence rework - positional columns, appended fields defaulted."""
    page = CI.parse_listing(LISTING_HTML_3)
    assert len(page.entries) == 3
    assert [e.ccan_id for e in page.entries] == [100, 200, 300]
    e0 = page.entries[0]
    assert e0.title == "Pack One"
    assert e0.author_nick == "Alice"
    assert e0.uploaded == "2025-01-01"
    assert e0.engine == "LC"
    assert e0.filename == "Pack1.c4s"
    assert e0.file_type == "c4s"
    assert e0.size_label == "1.0 MB"
    assert e0.is_pack is True
    # Appended Phase-0 fields stay defaulted for the legacy layout.
    assert e0.entry_type == ""
    assert e0.category == ""
    assert e0.niveau_label is None
    assert e0.niveau_numeric is None
    assert e0.votes is None
    assert e0.downloads is None
    assert e0.author_uid == 0
    assert page.total_entries == 3695

ENRICHED_11COL_HTML = """<html><body>
<table>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=6421">Hazard 3D</a></td><td><a href="ccan-dl-auth.pl/6421/Hazard3D.c4d">Hazard3D.c4d</a></td><td><a href="ccan-view.pl?a=&f1=ca&grp=1">Scenarien</a></td><td><a href="ccan-user.pl?a=info&i=4242">Alice</a></td><td><a href="ccan-view.pl?a=&f1=ev&x=LC">LC</a></td><td>absolut genial (3,0) (1 Vote)</td><td>1</td><td>126</td><td>16.7 MB</td><td>2026-08-27</td></tr>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=6417">Clonkworks Expansion</a></td><td><a href="ccan-dl-auth.pl/6417/Clonkworks.c4d">Clonkworks.c4d</a></td><td><a href="ccan-view.pl?a=&f1=ca&grp=1">Scenarien</a></td><td><a href="ccan-user.pl?a=info&i=89">TomB</a></td><td><a href="ccan-view.pl?a=&f1=ev&x=LC">LC</a></td><td>sehr gut (2,0) (3 Votes)</td><td>3</td><td>340</td><td>5.2 MB</td><td>2026-07-01</td></tr>
<tr><td>Objekt</td><td><a href="ccan-view.pl?a=view&i=6422">Sound Pack</a></td><td><a href="ccan-dl-auth.pl/6422/Sound.zip">Sound.zip</a></td><td><a href="ccan-view.pl?a=&f1=ca&grp=2">Sonstige</a></td><td><a href="ccan-user.pl?a=info&i=77">Bob</a></td><td><a href="ccan-view.pl?a=&f1=ev&x=CR">CR</a></td><td>befriedigend (1,5) (2 Votes)</td><td>2</td><td>45</td><td>12.4 MB</td><td>2026-05-30</td></tr>
</table>
<div>Seite 1 von 42 – Einträge 1-30 von 1240, davon 5 unter Niveau</div>
</body></html>"""

def test_l2_enriched_11col_listing():
    """Enriched layout renders 11 columns: the full extended record must be
    filled and ccan_id must come from the view link, never the author UID."""
    page = CI.parse_listing(ENRICHED_11COL_HTML, column_order=LIVE_COLUMN_ORDER)
    assert len(page.entries) == 3
    assert [e.ccan_id for e in page.entries] == [6421, 6417, 6422]
    e0 = page.entries[0]
    assert e0.ccan_id == 6421
    assert e0.title == "Hazard 3D"
    assert e0.author_nick == "Alice"
    assert e0.author_uid == 4242
    assert e0.engine == "LC"
    assert e0.category == "Scenarien"
    assert e0.niveau_label == "absolut genial"
    assert e0.niveau_numeric == pytest.approx(3.0)
    assert e0.votes == 1
    assert e0.downloads == 126
    assert e0.size_label == "16.7 MB"
    assert e0.uploaded == "2026-08-27"
    assert page.page_number == 1
    assert page.total_pages == 42
    assert page.total_entries == 1240

NIVEAU_VARIANTS_HTML = """<html><body>
<table>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=8001">Row One</a></td><td><a href="ccan-dl-auth.pl/8001/A.c4d">A.c4d</a></td><td><a href="ccan-view.pl?a=&f1=ca&grp=1">Scenarien</a></td><td><a href="ccan-user.pl?a=info&i=1">A</a></td><td><a href="ccan-view.pl?a=&f1=ev&x=LC">LC</a></td><td>gut (1,2) (0 Votes)</td><td>0</td><td>75</td><td>1.0 MB</td><td>2026-01-01</td></tr>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=8002">Row Two</a></td><td><a href="ccan-dl-auth.pl/8002/B.c4d">B.c4d</a></td><td><a href="ccan-view.pl?a=&f1=ca&grp=1">Scenarien</a></td><td><a href="ccan-user.pl?a=info&i=2">B</a></td><td><a href="ccan-view.pl?a=&f1=ev&x=LC">LC</a></td><td>absolut genial (3.0) (1 Vote)</td><td>1</td><td>200</td><td>2.0 MB</td><td>2026-01-02</td></tr>
<tr><td>News</td><td><a href="ccan-view.pl?a=view&i=8003">Announcement</a></td><td><a href="ccan-dl-auth.pl/8003/N.pdf">N.pdf</a></td><td><a href="ccan-view.pl?a=&f1=ca&grp=3">News</a></td><td><a href="ccan-user.pl?a=info&i=3">C</a></td><td><a href="ccan-view.pl?a=&f1=ev&x=LC">LC</a></td><td></td><td></td><td>42</td><td>0.5 MB</td><td>2026-01-03</td></tr>
</table>
</body></html>"""

def test_l4_niveau_variants():
    """Both comma and dot decimals parse; the optional embedded vote count is
    honoured; a News row with a missing Niveau cell stays None/None."""
    page = CI.parse_listing(NIVEAU_VARIANTS_HTML, column_order=LIVE_COLUMN_ORDER)
    e1, e2, e3 = page.entries
    assert e1.niveau_label == "gut"
    assert e1.niveau_numeric == pytest.approx(1.2)
    assert e1.votes == 0
    assert e1.downloads == 75
    assert e2.niveau_label == "absolut genial"
    assert e2.niveau_numeric == pytest.approx(3.0)
    assert e2.votes == 1
    assert e3.entry_type == "News"
    assert e3.niveau_numeric is None
    assert e3.votes is None

AUTHOR_UID_HTML = """<html><body>
<table>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=9001">Pack A</a></td><td><a href="ccan-dl-auth.pl/9001/A.c4d">A.c4d</a></td><td><a href="ccan-user.pl?a=info&i=4242">Alice</a></td><td>2026-02-01</td></tr>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=9002">Pack B</a></td><td><a href="ccan-dl-auth.pl/9002/B.c4d">B.c4d</a></td><td><a href="ccan-user.pl?a=info&i=77">Bob</a></td><td>2026-02-02</td></tr>
</table>
</body></html>"""

def test_l5_author_uid_extraction():
    """The author cell's ccan-user.pl href yields both nick and UID."""
    page = CI.parse_listing(AUTHOR_UID_HTML)
    assert page.entries[0].author_nick == "Alice"
    assert page.entries[0].author_uid == 4242
    assert page.entries[1].author_nick == "Bob"
    assert page.entries[1].author_uid == 77

UNIDENTIFIED_CELLS_HTML = """<html><body>
<table>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=700">GoodPack</a></td><td><a href="ccan-dl-auth.pl/700/Good.c4d">Good.c4d</a></td><td><a href="ccan-user.pl?a=info&i=5">Dana</a></td><td>2026-08-01</td><td>???</td></tr>
<tr><td>No ID Row</td><td>garbage</td><td>more</td></tr>
</table>
</body></html>"""

def test_l6_unidentifiable_columns_are_counted_and_skipped():
    """A cell with no evidence and no remaining layout slot is skipped (never
    mis-mapped) and counted in parse_failures; a row without any view link is
    skipped and counted too."""
    page = CI.parse_listing(UNIDENTIFIED_CELLS_HTML)
    assert [e.ccan_id for e in page.entries] == [700]
    e0 = page.entries[0]
    assert e0.title == "GoodPack"
    assert e0.author_nick == "Dana"
    assert e0.engine == ""
    assert e0.size_label == ""
    assert page.parse_failures == 2  # 1 extra cell + 1 view-less row

# ===========================================================================
# L7: the committed ground-truth fixture (Task-3, plan Step 5). A real saved
# excerpt of page 1 of the Phase-0 enriched-listing crawl, checked in to
# fixtures/ccan_sample/listing_enriched.html so the live layout is hardened
# against variance permanently. Column order is kept inline per the L7
# convention (test_ccan_index does not import the population tool).
# ===========================================================================

HERE = Path(__file__).resolve().parent
FIXTURE_ENRICHED = HERE / "fixtures" / "ccan_sample" / "listing_enriched.html"


def test_l7_ground_truth_fixture_parses():
    """Parse the committed live page-1 excerpt: >=1 entry, ccan_id from the
    view link, and Niveau/votes populated on the sampled rows."""
    html = FIXTURE_ENRICHED.read_text(encoding="utf-8",
                                      errors="replace")
    page = CI.parse_listing(html, column_order=LIVE_COLUMN_ORDER)
    assert len(page.entries) >= 1
    for entry in page.entries[:5]:
        assert entry.ccan_id
        # The view link is the id source — the author UID link must not win.
        assert entry.title
    sampled = [e for e in page.entries if e.niveau_numeric is not None]
    assert sampled, "fixture rows must carry Niveau evidence"
    assert any(e.votes is not None for e in sampled)
    assert page.total_entries == 3697

# ===========================================================================
# L8: the LIVE footer shape (Task-3 amendment, pinned after the Phase-0
# crawl's real-data validation). The live listing renders the footer line
# INSIDE a <td> (COLSPAN=12), with IMG/A tags between the range tokens, and
# NO "Seite/Page x von y" pagination block anywhere. The entry-range total
# must be read from the accumulated page text exactly like the synthetic
# L1/L2 footers — the mismatch the <td> wrapper introduced (total_entries
# silently 0 on every live page) is what this pin guards.
# ===========================================================================
LIVE_FOOTER_IN_TD_HTML = """<html><body>
<table>
<tr><td>Szenario</td><td><a href="ccan-view.pl?a=view&i=6421">Hazard 3D</a></td><td><a href="ccan-dl-auth.pl/6421/Hazard3D.c4d">Hazard3D.c4d</a></td><td><a href="ccan-view.pl?a=&f1=ca&grp=1">Action</a></td><td><a href="ccan-user.pl?a=info&i=8313">Kodenith</a></td><td><a href="ccan-view.pl?a=&f1=ev&x=LC">LC</a></td><td>absolut genial (3,0) (1 Vote)</td><td>1</td><td>126</td><td>16.7 MB</td><td>09.09.26 23:46</td></tr>
<tr><td class="br" colspan="12"><span class="hi">&nbsp;</span>Zeige&nbsp;Eintr&auml;ge <img src="/img/first.gif" width="13" height="13" border="0"><img src="/img/prev.gif" width="13" height="13" border="0">1-30<a href="ccan-view.pl?a=&ac=ty-ti-ni-tm-rp-vo-dc-ca-ev-si&sc=tm&so=d&nr=30&reveal=1&pg=1"><img src="/img/next.gif" width="13" height="13" border="0"></a><a href="ccan-view.pl?a=&ac=ty-ti-ni-tm-rp-vo-dc-ca-ev-si&sc=tm&so=d&nr=30&reveal=1&pg=123"><img src="/img/last.gif" width="13" height="13" border="0"></a><a href="ccan-view.pl?a=&ac=ty-ti-ni-tm-rp-vo-dc-ca-ev-si&sc=tm&so=d&reveal=1&nr=60&pg=0"><img src="/img/more.gif" width="13" height="13" border="0"></a><a href="ccan-view.pl?a=&ac=ty-ti-ni-tm-rp-vo-dc-ca-ev-si&sc=tm&so=d&reveal=1&nr=15&pg=0"><img src="/img/less.gif" width="13" height="13" border="0"></a> von 3697</td></tr>
</table>
</body></html>"""

def test_l8_live_footer_inside_td_extracts_entry_total():
    """The live footer lives inside a <td> (COLSPAN=12) with IMG/A tags
    between the range tokens and no 'Seite/Page x von y' block. The record
    row must still parse and the entry-range total must come out as 3697."""
    page = CI.parse_listing(LIVE_FOOTER_IN_TD_HTML,
                            column_order=LIVE_COLUMN_ORDER)
    assert len(page.entries) == 1
    assert page.entries[0].ccan_id == 6421
    assert page.entries[0].niveau_label == "absolut genial"
    assert page.entries[0].votes == 1
    assert page.entries[0].downloads == 126
    # The <td>-wrapped footer must still feed the entry-range regex; the
    # pagination block stays absent (total_pages 0) exactly as live.
    assert page.total_entries == 3697
    assert page.total_pages == 0
