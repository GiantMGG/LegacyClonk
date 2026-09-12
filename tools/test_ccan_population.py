"""Pytest suite for tools/ccan_population.py.

Synthetic inline fixtures; no network — ``mirror_fetch`` is monkeypatched on
the tool's *own* imported reference (patch the tool's name, not the source
module). The stats math is pinned P1-P4 against hand-computed reference
values; the crawl/cache/reconciliation behaviour is pinned P5-P7 with a
fetch-counting fake; P8 pins the validation-sample parity semantics.

Run::

    python3.11 -m pytest tools/test_ccan_population.py -v
"""
import json
import statistics
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ccan_population as cp

def ref_quantiles_inclusive(values, n):
    """Independent reference for ``statistics.quantiles(..., method=
    'inclusive')``, replicating the stdlib's exact arithmetic: integer
    divmod positioning + one division (bit-identical; self-checked against
    the stdlib inside P1 so the cross-check is honest)."""
    data = sorted(values)
    ld = len(data)
    out = []
    for i in range(1, n):
        j, delta = divmod(i * (ld - 1), n)
        out.append((data[j] * (n - delta) + data[j + 1] * delta) / n)
    return out

def expected_summary(values):
    """Test-side mirror of cp._summary (built from the reference quantiles)."""
    out = {"n": len(values), "mean": None, "median": None,
           "q1": None, "q2": None, "q3": None}
    for i in range(1, 10):
        out[f"d{i}"] = None
    out["low_n"] = len(values) < cp.MIN_STRATUM_N
    if not values:
        return out
    out["mean"] = statistics.mean(values)
    out["median"] = statistics.median(values)
    if len(values) >= 2:
        out["q1"], out["q2"], out["q3"] = ref_quantiles_inclusive(values, 4)
        for i, v in enumerate(ref_quantiles_inclusive(values, 10), 1):
            out[f"d{i}"] = v
    return out

def _mk(ccan_id, title, category, engine, niveau, votes, downloads):
    return {
        "schema": 1, "ccan_id": ccan_id, "entry_type": "Szenario",
        "title": title, "category": category, "engine": engine,
        "uploaded": "2026-01-01", "size_label": "1.0 MB",
        "niveau_label": "x", "niveau_numeric": niveau, "votes": votes,
        "downloads": downloads, "author_nick": "A", "author_uid": 1,
        "version": None, "players": None,
        "fetched_at": "2026-09-12T00:00:00Z",
    }

def mini_population():
    """The P1/P2/P4 fixture (20 rows, two categories, 4 tiers).

    LC tier: 11 rows, ratings sum to 27.5 -> C_LC = 2.5, of which 10 rows
    carry votes >= 3 (the plan's prose example rows R=3.0/v=5 and
    R=2.0/v=10 are ids 100/101) and 1 vote-count row is the 1-vote
    `absolut genial (3,0)` noise row (id 108, Hazard-3D class).
    CR tier: 6 rows. legacy tier: 2 rows with NO voted rows (forces the
    archive-wide prior fallback). other tier: 1 row.
    """
    return [
        # LC — Action (6)
        _mk(100, "LC A1", "Action", "LC", 3.0, 5, 200),
        _mk(101, "LC A2", "Action", "LC", 2.0, 10, 90),
        _mk(102, "LC A3", "Action", "LC", 3.0, 6, 250),
        _mk(103, "LC A4", "Action", "LC", 2.0, 8, 60),
        _mk(104, "LC A5", "Action", "LC", 3.0, 4, 120),
        _mk(105, "LC A6", "Action", "LC", 2.0, 12, 40),
        # LC — Scenarien (5)
        _mk(106, "LC S1", "Scenarien", "LC", 3.0, 7, 300),
        _mk(107, "LC S2", "Scenarien", "LC", 2.0, 9, 150),
        _mk(108, "Hazard 3D", "Scenarien", "LC", 3.0, 1, 126),  # noise row
        _mk(109, "LC S4", "Scenarien", "LC", 2.5, 3, 55),
        _mk(110, "LC S5", "Scenarien", "LC", 2.0, 11, 80),
        # CR (6)
        _mk(200, "CR A1", "Action", "CR", 1.0, 1, 80),
        _mk(201, "CR A2", "Action", "CR", 3.0, 5, 200),
        _mk(202, "CR A3", "Action", "CR", 2.5, 0, 20),
        _mk(203, "CR S1", "Scenarien", "CR", 1.0, 2, 50),
        _mk(204, "CR S2", "Scenarien", "CR", 2.0, 0, 45),
        _mk(205, "CR S3", "Scenarien", "CR", 2.0, 8, 150),
        # legacy (2, no voted rows)
        _mk(300, "L4 A1", "Action", "4.5", 3.0, 0, 25),
        _mk(301, "L4 S1", "Scenarien", "clonk 4 gold", 1.0, 0, 10),
        # other (1) — an engine string that stays outside LC/CR/legacy.
        _mk(400, "O S1", "Scenarien", "Mystery", 2.0, 0, 5),
    ]

# ===========================================================================
# P1 — distributions: per-tier and per-(tier x category), hand-computed
# ===========================================================================

def test_p1_distributions_match_hand_computed_values():
    # Reference self-check: our position formula must equal the stdlib's
    # inclusive quantiles on a few shapes (then expected_summary below is a
    # genuine independent cross-check of the tool's wiring).
    for values, n in [([1, 2, 3, 4], 4), ([1, 2, 3, 4, 5, 6], 10),
                      ([10, 20, 30, 40, 50], 4)]:
        assert ref_quantiles_inclusive(values, n) == pytest.approx(
            statistics.quantiles(values, n=n, method="inclusive"), abs=1e-12)

    rows = mini_population()
    analysis = cp.analyze(rows)
    dist = analysis["distributions"]
    scored = analysis["scored"]

    def group_values(group_rows, metric):
        return [r[metric] for r in group_rows if r.get(metric) is not None]

    # --- Archive-wide ---
    for metric in cp._METRICS:
        got = dist["archive"][metric]
        exp = expected_summary(group_values(scored, metric))
        assert got == exp, f"archive {metric}"

    # --- Per tier ---
    for tier in analysis["tiers_sorted"]:
        tier_rows = [r for r in scored if r["tier"] == tier]
        for metric in cp._METRICS:
            got = dist[("tier", tier)][metric]
            exp = expected_summary(group_values(tier_rows, metric))
            assert got == exp, f"tier {tier} {metric}"

    # --- Per (tier x category) ---
    for tier in analysis["tiers_sorted"]:
        tier_rows = [r for r in scored if r["tier"] == tier]
        cats = sorted({r.get("category") or "(none)" for r in tier_rows})
        for cat in cats:
            cat_rows = [r for r in tier_rows
                        if (r.get("category") or "(none)") == cat]
            for metric in cp._METRICS:
                got = dist[("tier_category", tier, cat)][metric]
                exp = expected_summary(group_values(cat_rows, metric))
                assert got == exp, f"tier x cat {tier}/{cat} {metric}"

    # --- Literal hand-spots (the arithmetic is pinned here, not only by the
    # reference): LC bayes median, LC downloads Q3, (LC,Action) votes mean.
    lc_bayes = dist[("tier", "LC")]["bayes_rating"]
    assert lc_bayes["median"] == pytest.approx(2.5, abs=1e-12)
    assert lc_bayes["q2"] == pytest.approx(2.5, abs=1e-12)
    assert dist[("tier", "LC")]["downloads"]["q3"] == pytest.approx(175.0)
    assert dist[("tier_category", "LC", "Action")]["votes"]["mean"] == \
        pytest.approx(45 / 6)
    # The <=20-row mini population can afford archive-wide summaries only;
    # LC (11 rows) is the single non-low-n tier, the rest are low-n.
    assert dist["archive"]["votes"]["low_n"] is False
    assert dist[("tier", "LC")]["bayes_rating"]["low_n"] is False
    assert dist[("tier", "CR")]["bayes_rating"]["low_n"] is True

# ===========================================================================
# P2 — Bayesian shrinkage (m=5), exact numbers
# ===========================================================================

def test_p2_bayesian_shrinkage():
    rows = mini_population()
    priors = cp.compute_priors(rows)

    # C_tier = plain mean over the tier's votes>=1 rows (NOT vote-weighted).
    lc_voted_ratings = [r["niveau_numeric"] for r in rows
                        if r["engine"] == "LC" and (r["votes"] or 0) >= 1]
    assert len(lc_voted_ratings) == 11
    assert priors["C_tier"]["LC"] == pytest.approx(2.5, abs=1e-12)
    assert priors["C_tier"]["LC"] == pytest.approx(
        sum(lc_voted_ratings) / len(lc_voted_ratings))
    # Vote-weighted mean would be 176.5/75 = 2.353… != 2.5 — proving the
    # prior is NOT vote-weighted (the plan's R=3.0/v=5 + R=2.0/v=10 example
    # is live in the fixture as ids 100/101).
    weighted = sum(r["niveau_numeric"] * r["votes"] for r in rows
                   if r["engine"] == "LC" and (r["votes"] or 0) >= 1)
    weighted /= sum(r["votes"] for r in rows
                    if r["engine"] == "LC" and (r["votes"] or 0) >= 1)
    assert weighted != pytest.approx(2.5, abs=1e-2)

    # 1-vote R=3.0 (Hazard-3D class) -> (5*2.5 + 3.0)/6 = 2.5833…
    assert cp.bayes_rating(2.5, 1, 3.0) == pytest.approx(2.583333333, abs=1e-9)
    scored = cp.score_rows(rows, priors)
    row108 = next(r for r in scored if r["ccan_id"] == 108)
    assert row108["bayes_rating"] == pytest.approx(2.583333333, abs=1e-9)
    assert row108["votes"] == 1
    assert row108["wilson_lower"] is not None

    # 20-vote R=1.0 -> (12.5 + 20.0)/25 = 1.3 (m+votes = 25 exactly).
    assert cp.bayes_rating(2.5, 20, 1.0) == pytest.approx(1.3, abs=1e-9)

    # Zero-vote rows collapse to the tier prior; archive-wide fallback when a
    # tier has no voted rows (legacy/other) — C_archive over 15 voted rows.
    row300 = next(r for r in scored if r["ccan_id"] == 300)
    assert row300["bayes_rating"] == pytest.approx(priors["C_tier"]["legacy"])
    assert priors["C_archive"] == pytest.approx(
        sum(r["niveau_numeric"] for r in rows if (r["votes"] or 0) >= 1) / 15)
    assert priors["C_tier"]["legacy"] == pytest.approx(priors["C_archive"])
    assert priors["C_tier"]["other"] == pytest.approx(priors["C_archive"])

# ===========================================================================
# P3 — Wilson lower bound, hand-computed (z=1.96)
# ===========================================================================

def test_p3_wilson_lower_bound():
    # (R=3.0, v=1): p-hat clamped to 0.99 -> wilson_lower ≈ 0.2024.
    assert cp.wilson_lower(3.0, 1) == pytest.approx(0.2024, abs=1e-4)
    # (R=3.0, v=50): ≈ 0.9111.
    assert cp.wilson_lower(3.0, 50) == pytest.approx(0.9111, abs=1e-4)
    # Skipped below one vote (a zero-vote row has no community ballot).
    assert cp.wilson_lower(3.0, 0) is None
    assert cp.wilson_lower(3.0, None) is None

# ===========================================================================
# P4 — threshold derivation + TOML emission
# ===========================================================================

def test_p4_threshold_derivation_and_toml():
    rows = mini_population()
    analysis = cp.analyze(rows)
    th = analysis["thresholds"]

    lc = th["LC"]
    assert lc["low_n"] is False
    assert lc["voted1"] == 11
    assert lc["voted3"] == 10

    # votes>=3 stratum excludes the 1-vote 3.0 noise row by construction.
    votes3_ids = sorted(r["ccan_id"] for r in analysis["scored"]
                        if r["tier"] == "LC" and (r["votes"] or 0) >= 3)
    assert len(votes3_ids) == 10
    assert 108 not in votes3_ids

    # Hand-computed p75 values (reference + literal arithmetic).
    votes3 = [r for r in analysis["scored"]
              if r["tier"] == "LC" and (r["votes"] or 0) >= 3]
    bayes = sorted(r["bayes_rating"] for r in votes3)
    exp_p75_bayes = ref_quantiles_inclusive(bayes, 4)[2]
    assert lc["p75_bayes_rating"] == pytest.approx(exp_p75_bayes, abs=1e-9)
    # Literal: sorted bayes [.., 2.7222, 2.75, 2.7727, 2.7917], pos 6.75 ->
    # 2.72222 + 0.75*(2.75-2.72222) = 2.743056.
    assert lc["p75_bayes_rating"] == pytest.approx(2.743055556, abs=1e-6)
    assert lc["p75_downloads"] == pytest.approx(175.0, abs=1e-9)
    assert lc["p75_raw_niveau"] == pytest.approx(3.0, abs=1e-9)
    # Pass set: ids 100, 102, 106 (bayes >= p75 AND downloads >= 175).
    assert lc["pass"] == 3

    # Below-threshold tiers are low-n and carry no cutoffs.
    for tier in ("CR", "legacy", "other"):
        assert th[tier]["low_n"] is True
        assert "p75_bayes_rating" not in th[tier]

    # The emitted TOML reproduces cutoffs + constants + lineage.
    toml_text = cp.render_thresholds_toml(analysis, {"footer_total": 3697})
    data = tomllib.loads(toml_text)
    assert data["schema"] == 1
    assert data["method"] == {"m": 5.0, "z": 1.96, "min_votes": 3,
                              "min_stratum_n": 10, "quantile": 0.75}
    lc_toml = data["tier"]["LC"]
    assert lc_toml["low_n"] is False
    assert lc_toml["pass"] == 3
    assert lc_toml["cutoff_bayes_rating"] == \
        pytest.approx(exp_p75_bayes, abs=1e-9)
    assert lc_toml["cutoff_downloads"] == pytest.approx(175.0, abs=1e-9)
    assert lc_toml["cutoff_raw_niveau"] == pytest.approx(3.0, abs=1e-9)
    assert "cutoff_bayes_rating" not in data["tier"]["CR"]
    assert data["lineage"]["footer_total"] == 3697
    assert data["lineage"]["dataset_rows"] == 20

# ===========================================================================
# Crawl fixtures + fake mirror_fetch (no network)
# ===========================================================================

ROW_TMPL = (
    "<tr><td>{typ}</td><td><a href=\"ccan-view.pl?a=view&i={i}\">"
    "<title></title>{title}</a></td>"
    "<td><a href=\"ccan-dl-auth.pl/{i}/{fn}\">{fn}</a></td>"
    "<td><a href=\"ccan-view.pl?a=&f1=ca&grp=1\">{cat}</a></td>"
    "<td><a href=\"ccan-user.pl?a=info&i={uid}\">{nick}</a></td>"
    "<td><a href=\"ccan-view.pl?a=&f1=ev&x={eng}\">{eng}</a></td>"
    "<td>{niveau}</td><td>{votes}</td><td>{dl}</td>"
    "<td>{size}</td><td>{date}</td></tr>")

CRAWL_ROWS = [
    dict(i=1000, typ="Szenario", title="Test Pack A", fn="A.c4d",
         cat="Scenarien", uid=4242, nick="Alice", eng="LC",
         niveau="absolut genial (3,0) (1 Vote)", votes=1, dl=126,
         size="16.7 MB", date="2026-08-27"),
    dict(i=1001, typ="Szenario", title="Test Pack B", fn="B.c4d",
         cat="Scenarien", uid=89, nick="TomB", eng="LC",
         niveau="sehr gut (2,0) (3 Votes)", votes=3, dl=340,
         size="5.2 MB", date="2026-07-01"),
    dict(i=1002, typ="Objekt", title="Sound Pack", fn="S.zip",
         cat="Sonstige", uid=77, nick="Bob", eng="CR",
         niveau="befriedigend (1,5) (2 Votes)", votes=2, dl=45,
         size="12.4 MB", date="2026-05-30"),
]

DEFAULT_HTML = """<html><body><table>""" + "".join(
    "<tr><td>{typ}</td><td><a href=\"ccan-view.pl?a=view&i={i}\">{title}</a>"
    "</td><td><a href=\"ccan-dl-auth.pl/{i}/{fn}\">{fn}</a></td>"
    "<td><a href=\"ccan-user.pl?a=info&i={uid}\">{nick}</a></td>"
    "<td>{date}</td></tr>".format(**r) for r in CRAWL_ROWS) + """</table>
<div>Seite 1 von 1 – Einträge 1-30 von 3</div></body></html>"""

def listing_html(footer_total=3):
    return ("<html><body><table>"
            + "".join(ROW_TMPL.format(**r) for r in CRAWL_ROWS)
            + f"</table><div>Seite 1 von 1 – Einträge 1-30 von "
              f"{footer_total}</div></body></html>")

def per_entry_html(i, title, category, engine, niveau, votes, downloads):
    return f"""<html><head><title>CCAN - {title}</title></head><body>
<table>
<tr><th>Titel</th><td>{title}</td></tr>
<tr><th>Kategorie</th><td>{category}</td></tr>
<tr><th>Engine-Version</th><td>{engine}</td></tr>
</table>
<div>Niveau: {niveau} - {votes} Stimmen - {downloads} Downloads</div>
</body></html>"""

def _fake_fetch_factory(responses: dict) -> object:
    """fetch-counting fake mirror_fetch; substring match, first wins."""
    calls = []

    def fake(url, rate_limit=0, max_retries=3):
        calls.append(url)
        for key, val in responses.items():
            if key in url:
                if isinstance(val, Exception):
                    return None, str(val)
                return val, None
        return b"", None

    fake.calls = calls
    return fake

def crawl_base_args(tmp_path, extra):
    return ["crawl", "--population-dir", str(tmp_path),
            "--rate-limit", "0", "--retry", "0"] + extra

def crawled_jsonl(tmp_path):
    path = tmp_path / "ccan_population.v1.jsonl"
    assert path.is_file()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8")
            .splitlines()]
    assert rows
    return rows

def rows_without_fetched_at(rows):
    return [{k: v for k, v in r.items() if k != "fetched_at"} for r in rows]

# ===========================================================================
# P5 — reconciliation pass; P6 — reconciliation failure exits 1
# ===========================================================================

def test_p5_crawl_reconciliation_pass_writes_dataset(tmp_path, monkeypatch):
    responses = {
        "pg=0&nr=30": DEFAULT_HTML.encode("utf-8"),
        "ac=ty-ti": listing_html(3).encode("utf-8"),
    }
    fake = _fake_fetch_factory(responses)
    monkeypatch.setattr(cp, "mirror_fetch", fake)

    rc = cp.main(crawl_base_args(tmp_path, ["--validate-count", "0"]))
    assert rc == 0

    rows = crawled_jsonl(tmp_path)
    ids = [r["ccan_id"] for r in rows]
    assert ids == sorted(ids)
    assert ids == [1000, 1001, 1002]
    # Schema field order is exactly the dataset contract.
    assert list(rows[0]) == cp.DATASET_COLUMNS
    assert rows[0]["schema"] == 1
    assert rows[0]["version"] is None
    assert rows[0]["players"] is None
    assert rows[0]["fetched_at"].endswith("Z")
    assert rows[0]["niveau_numeric"] == 3.0
    assert rows[0]["votes"] == 1
    assert rows[0]["downloads"] == 126
    assert rows[0]["author_uid"] == 4242
    assert rows[0]["author_nick"] == "Alice"
    assert rows[0]["engine"] == "LC"
    assert rows[0]["category"] == "Scenarien"

    csv_path = tmp_path / "ccan_population.v1.csv"
    assert csv_path.is_file()
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ",".join(cp.DATASET_COLUMNS)
    assert len(lines) == 4  # header + 3 rows

    meta = json.loads(
        (tmp_path / "population-meta.json").read_text(encoding="utf-8"))
    assert meta["reconciliation"] == "pass"
    assert meta["footer_total"] == 3
    assert meta["crawled_unique"] == 3
    assert meta["request_count"] == 2  # default page + enriched page 0

def test_p6_reconciliation_mismatch_exits_one(tmp_path, monkeypatch, capsys):
    responses = {
        "pg=0&nr=30": DEFAULT_HTML.encode("utf-8"),
        "ac=ty-ti": listing_html(4).encode("utf-8"),  # footer lies
    }
    fake = _fake_fetch_factory(responses)
    monkeypatch.setattr(cp, "mirror_fetch", fake)

    rc = cp.main(crawl_base_args(tmp_path, ["--validate-count", "0"]))
    assert rc == 1
    err = capsys.readouterr().err
    assert "RECONCILIATION MISMATCH" in err
    assert "unique=3" in err
    assert "footer_total=4" in err

# ===========================================================================
# P7 — idempotent re-crawl: cache hits, zero refetches
# ===========================================================================

def test_p7_recrawl_reuses_cache_without_refetch(tmp_path, monkeypatch):
    responses = {
        "pg=0&nr=30": DEFAULT_HTML.encode("utf-8"),
        "ac=ty-ti": listing_html(3).encode("utf-8"),
    }
    fake = _fake_fetch_factory(responses)
    monkeypatch.setattr(cp, "mirror_fetch", fake)

    args = crawl_base_args(tmp_path, ["--validate-count", "0"])
    assert cp.main(args) == 0
    first = crawled_jsonl(tmp_path)
    n_fetches_first_run = len(fake.calls)
    assert n_fetches_first_run == 2

    # Second run: every raw page is already cached -> zero fetches, and the
    # rewritten dataset is identical modulo fetched_at.
    fake.calls = []
    assert cp.main(args) == 0
    assert fake.calls == []
    second = crawled_jsonl(tmp_path)
    assert rows_without_fetched_at(second) == rows_without_fetched_at(first)
    # raw cache carries the default + enriched page after the second run.
    cached = sorted(p.name for p in (tmp_path / "raw-listings").iterdir())
    assert "pg-default.html" in cached
    assert "pg-0000.html" in cached

# ===========================================================================
# P8 — validation-sample parity: mismatch is a finding, never an abort
# ===========================================================================

def test_p8_validation_parity_reports_mismatch_not_abort(tmp_path,
                                                         monkeypatch, capsys):
    # Planted mismatch: the per-entry page for #1000 says 999 Stimmen while
    # the listing says 1 vote.
    responses = {
        "pg=0&nr=30": DEFAULT_HTML.encode("utf-8"),
        "ac=ty-ti": listing_html(3).encode("utf-8"),
        "a=view&i=1000": per_entry_html(
            1000, "Test Pack A", "Scenarien", "LC",
            "absolut genial (3,0)", 999, 126).encode("utf-8"),
        "a=view&i=1001": per_entry_html(
            1001, "Test Pack B", "Scenarien", "LC",
            "sehr gut (2,0)", 3, 340).encode("utf-8"),
        "a=view&i=1002": per_entry_html(
            1002, "Sound Pack", "Sonstige", "CR",
            "befriedigend (1,5)", 2, 45).encode("utf-8"),
    }
    fake = _fake_fetch_factory(responses)
    monkeypatch.setattr(cp, "mirror_fetch", fake)

    rc = cp.main(crawl_base_args(tmp_path, ["--validate-count", "3"]))
    assert rc == 0  # findings never abort the crawl

    out = capsys.readouterr().out
    assert "1 finding(s)" in out

    parity = json.loads(
        (tmp_path / "validation-parity.json").read_text(encoding="utf-8"))
    assert len(parity) == 3
    row1000 = next(r for r in parity if r["ccan_id"] == 1000)
    assert row1000["fields"]["votes"] == {
        "listing": 1, "page": 999, "verdict": "mismatch"}
    # All other fields for #1000 still match.
    assert row1000["fields"]["category"]["verdict"] == "match"
    assert row1000["fields"]["engine"]["verdict"] == "match"
    assert row1000["fields"]["niveau_numeric"]["verdict"] == "match"
    assert row1000["fields"]["downloads"]["verdict"] == "match"

    # The report's parity table carries the finding prominently.
    markdown = cp.render_parity_table(parity)
    assert "mismatch" in markdown
    assert "999" in markdown
    assert "| 1000 | votes | 1 | 999 | mismatch |" in markdown

# ===========================================================================
# P9 — live per-entry page shape adaptation (Task-3 real-data pin): the
# live CCAN page labels the count "Downloadzahl" (number in the next <td>)
# and wraps the Niveau numeric in <span>s. The Task-2 regex fallbacks alone
# grab the entry ID from the "Download" link row (downloads) and miss the
# span-wrapped numeric (Niveau unparsed). The table-cell primary source must
# win; the regexes stay as the synthetic-shape fallback (P8 covers them).
# ===========================================================================

LIVE_ENTRY_HTML = """<!DOCTYPE html>
<html><head><title>CCAN - Codename: Modern Combat</title></head><body>
<table>
<tr><td>Zeit:</td><td>19.1.2021 13:31</td></tr>
<tr><td>Dateigr&ouml;&szlig;e:</td><td>38.9 MB</td></tr>
<tr><td>Downloadzahl:</td><td>293</td></tr>
<tr><td>Kategorie:</td><td>Melee</td></tr>
<tr><td>Engine-Version:</td><td>CR</td></tr>
<tr><td>Niveau:</td>
<td bgcolor="#BBF044">gut <span style="font-size:70%">(0.7)</span> (3 Votes)
[<select name="v"><option value="+3">absolut genial</option></select>]</td></tr>
</table>
</body></html>"""

def test_p9_live_entry_page_shape_parses_fields():
    """The live per-entry label-value table is the primary source: Niveau
    inside <span> tags, Downloadzahl count, votes from the same cell."""
    fields = cp.parse_page_fields(LIVE_ENTRY_HTML, ccan_id=6331)
    assert fields["category"] == "Melee"
    assert fields["engine"] == "CR"
    assert fields["niveau_label"] == "gut"
    assert fields["niveau_numeric"] == pytest.approx(0.7)
    assert fields["votes"] == 3
    assert fields["downloads"] == 293

def test_p9_live_entry_page_negative_rating_parses():
    """Negative ratings and zero-padded labels parse through the same path."""
    negative = LIVE_ENTRY_HTML.replace(
        "gut <span style=\"font-size:70%\">(0.7)</span> (3 Votes)",
        "nicht schlecht, nicht gut <span style=\"font-size:70%\">(-0.2)</span> (13 Votes)")
    negative = negative.replace("<td>Downloadzahl:</td><td>293</td>",
                                "<td>Downloadzahl:</td><td>226</td>")
    fields = cp.parse_page_fields(negative, ccan_id=4514)
    assert fields["niveau_label"] == "nicht schlecht, nicht gut"
    assert fields["niveau_numeric"] == pytest.approx(-0.2)
    assert fields["votes"] == 13
    assert fields["downloads"] == 226
