"""Pytest suite for tools/import_ccan.py.

Two layers (spec Test plan Tiers 1 + 2):
1. Synthetic-fixture unit tests (fast, deterministic, no network).
2. Offline integration test using the vendored sample pack in
   tools/fixtures/ccan_sample/ (no network, real c4group).

Run::

    python3 -m pytest tools/test_import_ccan.py -v
    python3 -m pytest tools/test_import_ccan.py -v -k integration
"""
import sys
from pathlib import Path

import pytest

# Make tools/ importable.
sys.path.insert(0, str(Path(__file__).parent))
import import_ccan as I

HERE = Path(__file__).parent
FIX = HERE / "fixtures" / "ccan_sample"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_manifest_entry() -> I.ManifestEntry:
	return I.ManifestEntry(
		ccan_id=4242,
		title="Sample",
		author_nick="SampleAuthor",
		author_uid=9999,
		uploaded="2026-08-27",
		engine="LC",
		license="CC-BY-NC-4.0",
		license_rationale="Synthetic fixture for offline integration test.",
		filename="Sample.c4d",
		destination="Sample",
		notes="Test fixture.",
	)

@pytest.fixture
def sample_metadata() -> I.CcanMetadata:
	return I.CcanMetadata(
		ccan_id=4242,
		title="Sample",
		author_nick="SampleAuthor",
		author_uid=9999,
		uploaded="2026-08-27",
		engine="LC",
		filename="Sample.c4d",
		description_de="Sample DE description for offline integration test.",
		description_us="Sample US description for offline integration test.",
	)

@pytest.fixture
def sample_manifest(tmp_path: Path, sample_manifest_entry: I.ManifestEntry) -> Path:
	p = tmp_path / "manifest.toml"
	e = sample_manifest_entry
	p.write_text(
		f"[entry.{e.ccan_id}]\n"
		f'title = "{e.title}"\n'
		f"ccan_id = {e.ccan_id}\n"
		f'author_nick = "{e.author_nick}"\n'
		f"author_uid = {e.author_uid}\n"
		f'uploaded = "{e.uploaded}"\n'
		f'engine = "{e.engine}"\n'
		f'license = "{e.license}"\n'
		f'license_rationale = "{e.license_rationale}"\n'
		f'filename = "{e.filename}"\n'
		f'destination = "{e.destination}"\n'
		f'notes = "{e.notes}"\n',
		encoding="utf-8",
	)
	return p

# ---------------------------------------------------------------------------
# Tier 1 — Unit tests
# ---------------------------------------------------------------------------

def test_parse_ccan_metadata_from_synthetic_fixture():
	html = (FIX / "meta.html").read_text(encoding="utf-8")
	m = I.parse_ccan_metadata(html, 4242)
	assert m.title == "Sample"
	assert m.author_nick.startswith("SampleAuthor")
	assert m.author_uid == 9999
	assert m.uploaded == "2026-08-27"
	assert m.engine == "LC"
	assert m.filename == "Sample.c4d"
	assert "Sample DE description" in m.description_de
	assert "Sample US description" in m.description_us

def test_load_manifest_validates_required_fields(tmp_path: Path):
	# Missing `filename` field.
	p = tmp_path / "bad.toml"
	p.write_text(
		"[entry.6421]\n"
		'title = "x"\n'
		"ccan_id = 6421\n"
		'author_nick = "y"\n'
		"author_uid = 1\n"
		'uploaded = "2026-01-01"\n'
		'engine = "LC"\n'
		'license = "CC-BY-NC-4.0"\n'
		'license_rationale = "z"\n'
		# filename missing
		'destination = "x"\n'
		'notes = "n"\n',
		encoding="utf-8",
	)
	with pytest.raises(SystemExit) as exc:
		I.load_manifest(p)
	assert "filename" in str(exc.value)

def test_load_manifest_rejects_unknown_license(tmp_path: Path):
	p = tmp_path / "bad.toml"
	p.write_text(
		"[entry.6421]\n"
		'title = "x"\n'
		"ccan_id = 6421\n"
		'author_nick = "y"\n'
		"author_uid = 1\n"
		'uploaded = "2026-01-01"\n'
		'engine = "LC"\n'
		'license = "unknown"\n'
		'license_rationale = "z"\n'
		'filename = "x.c4s"\n'
		'destination = "x"\n'
		'notes = "n"\n',
		encoding="utf-8",
	)
	with pytest.raises(SystemExit) as exc:
		I.load_manifest(p)
	assert "unknown" in str(exc.value)

def test_normalize_generates_attribution_copying_changesle(
	tmp_path: Path,
	sample_manifest_entry: I.ManifestEntry,
	sample_metadata: I.CcanMetadata,
):
	pack_dir = tmp_path / "Sample"
	pack_dir.mkdir()
	I.normalize(sample_manifest_entry, sample_metadata, pack_dir)
	assert (pack_dir / "COPYING").read_text(encoding="utf-8").startswith(
		"This work is licensed"
	)
	assert (pack_dir / "ChangesLE.txt").read_text(encoding="utf-8") == ""
	attr = (pack_dir / "ATTRIBUTION.txt").read_text(encoding="utf-8")
	assert "Title:    Sample" in attr
	assert "Author:   SampleAuthor (CCAN user ID 9999)" in attr
	assert "Uploaded: 2026-08-27" in attr
	assert (
		"Source:   https://ccan.de/cgi-bin/ccan/ccan-view.pl?a=view&i=4242"
		in attr
	)
	assert "License:  CC-BY-NC-4.0 (see COPYING)" in attr
	assert "Description (DE):\nSample DE description" in attr
	assert "Description (US):\nSample US description" in attr
	assert "License rationale:\nSynthetic fixture" in attr

def test_idempotency_check_skips_already_imported(
	tmp_path: Path,
	sample_manifest_entry: I.ManifestEntry,
):
	# Pre-create an ATTRIBUTION.txt that matches the manifest entry.
	pack = tmp_path / "Sample"
	pack.mkdir()
	(pack / "ATTRIBUTION.txt").write_text(
		"Source: https://ccan.de/cgi-bin/ccan/ccan-view.pl?a=view&i=4242\n"
		"Uploaded: 2026-08-27\n",
		encoding="utf-8",
	)
	assert I.is_already_imported(sample_manifest_entry, tmp_path) is True
	# A different uploaded date -> not idempotent.
	e2 = I.ManifestEntry(**{**sample_manifest_entry.__dict__, "uploaded": "2025-01-01"})
	assert I.is_already_imported(e2, tmp_path) is False

def test_validate_runs_c4group_l_and_checks_exit_code(monkeypatch):
	# Mock subprocess.run: first call returns exit 0 (ok), second call exit 1 (fail).
	calls = []

	class FakeProc:
		def __init__(self, returncode, stdout, stderr):
			self.returncode = returncode
			self.stdout = stdout
			self.stderr = stderr

	def fake_run(cmd, **kwargs):
		calls.append(cmd)
		if len(calls) == 1:
			return FakeProc(0, "ok listing\n", "")
		return FakeProc(1, "", "boom\n")

	monkeypatch.setattr(I.subprocess, "run", fake_run)
	ok1, out1 = I.validate(Path("/fake/pack"), Path("/fake/c4group"))
	assert ok1 is True and "ok listing" in out1
	ok2, out2 = I.validate(Path("/fake/pack"), Path("/fake/c4group"))
	assert ok2 is False and "boom" in out2

def test_unpack_dispatches_on_extension(tmp_path: Path):
	# .txt rejection.
	txt = tmp_path / "x.txt"
	txt.write_text("links")
	with pytest.raises(ValueError, match="Text-only"):
		I.unpack(txt, tmp_path / "out", Path("/bin/true"))
	# .zip extraction.
	import zipfile
	z = tmp_path / "x.zip"
	with zipfile.ZipFile(z, "w") as zf:
		zf.writestr("inside/a.txt", "hello")
	out = tmp_path / "out_zip"
	ret = I.unpack(z, out, Path("/bin/true"))
	assert (ret / "inside" / "a.txt").read_text() == "hello"

def test_verify_manifest_detects_duplicate_destinations(tmp_path: Path):
	p = tmp_path / "dup.toml"
	p.write_text(
		"[entry.100]\n"
		'title = "A"\nccan_id = 100\nauthor_nick = "x"\nauthor_uid = 1\n'
		'uploaded = "2026-01-01"\nengine = "LC"\n'
		'license = "CC-BY-NC-4.0"\nlicense_rationale = "r"\n'
		'filename = "a.c4s"\ndestination = "SameDest"\nnotes = "n"\n'
		"[entry.101]\n"
		'title = "B"\nccan_id = 101\nauthor_nick = "x"\nauthor_uid = 1\n'
		'uploaded = "2026-01-01"\nengine = "LC"\n'
		'license = "CC-BY-NC-4.0"\nlicense_rationale = "r"\n'
		'filename = "b.c4s"\ndestination = "SameDest"\nnotes = "n"\n',
		encoding="utf-8",
	)
	with pytest.raises(SystemExit) as exc:
		I.load_manifest(p)
	assert "Duplicate destination" in str(exc.value)

# ---------------------------------------------------------------------------
# Tier 2 — Offline integration test (vendored sample, no network, real c4group)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_integration_import_sample_pack_end_to_end(
	tmp_path: Path,
	sample_manifest_entry: I.ManifestEntry,
	sample_metadata: I.CcanMetadata,
	monkeypatch,
):
	"""End-to-end import of the vendored Sample.c4d fixture, no network."""
	# Resolve the real c4group binary.
	c4group = I.resolve_c4group()

	# Mock the network: serve meta.html and the packed Sample.c4d from disk.
	# IMPORTANT: fetch_pack must COPY the fixture into a per-test cache dir and
	# return that copy's path. Returning the fixture path directly would let
	# `unpack`'s `c4group -u` consume/transform the packed file in-place and
	# destroy the fixture for subsequent test runs.
	cache_dir = tmp_path / "cache"
	cache_dir.mkdir()
	import shutil as _shutil

	def fake_fetch_pack(entry, cache_dir, rate_limit=I.DEFAULT_RATE_LIMIT):
		dest_dir = cache_dir / str(entry.ccan_id)
		dest_dir.mkdir(parents=True, exist_ok=True)
		dest = dest_dir / entry.filename
		_shutil.copy(str(FIX / "Sample.c4d"), str(dest))
		return dest

	monkeypatch.setattr(I, "fetch_metadata_html", lambda e, rate_limit=I.DEFAULT_RATE_LIMIT: (FIX / "meta.html").read_text(encoding="utf-8"))
	monkeypatch.setattr(I, "fetch_pack", fake_fetch_pack)
	monkeypatch.setattr(I, "CACHE_DIR", cache_dir)

	# Build a one-entry manifest.
	manifest = tmp_path / "manifest.toml"
	e = sample_manifest_entry
	manifest.write_text(
		f"[entry.{e.ccan_id}]\n"
		f'title = "{e.title}"\n'
		f"ccan_id = {e.ccan_id}\n"
		f'author_nick = "{e.author_nick}"\n'
		f"author_uid = {e.author_uid}\n"
		f'uploaded = "{e.uploaded}"\n'
		f'engine = "{e.engine}"\n'
		f'license = "{e.license}"\n'
		f'license_rationale = "{e.license_rationale}"\n'
		f'filename = "{e.filename}"\n'
		f'destination = "{e.destination}"\n'
		f'notes = "{e.notes}"\n',
		encoding="utf-8",
	)

	content_community = tmp_path / "cc"
	content_community.mkdir()

	# Drive the import via cmd_import's internals: call _import_one directly.
	I._import_one(
		entry=sample_manifest_entry,
		content_community=content_community,
		c4group=c4group,
		force=False,
		rate_limit=0,
	)

	# 1. The unpacked pack directory exists at content-community/Sample/Sample.c4d.
	pack_dir = content_community / "Sample"
	assert pack_dir.is_dir(), f"destination not created: {pack_dir}"
	assert (pack_dir / "Sample.c4d").is_dir(), "unpacked pack missing"

	# 2. The three normalized files exist and match expected (modulo date footer).
	copying = (pack_dir / "COPYING").read_text(encoding="utf-8")
	assert copying == (FIX / "expected" / "COPYING").read_text(encoding="utf-8")
	attr = (pack_dir / "ATTRIBUTION.txt").read_text(encoding="utf-8")
	expected_attr = (FIX / "expected" / "ATTRIBUTION.txt").read_text(encoding="utf-8")
	# Strip the date-stamped footer for comparison: keep everything up to the
	# "Imported by" line.
	attr_body = attr[: attr.index("Imported by")]
	expected_body = expected_attr[: expected_attr.index("Imported by")]
	assert attr_body == expected_body
	assert "Imported by LegacyClonk import_ccan.py on" in attr
	assert (pack_dir / "ChangesLE.txt").read_text(encoding="utf-8") == ""

	# 3. c4group -l succeeds on the imported pack (the unpacked pack dir,
	#    not the destination root — matches spec Tier 3 canary verification).
	ok, _ = I.validate(pack_dir / "Sample.c4d", c4group)
	assert ok, "c4group -l failed on the imported pack"

	# 4. Idempotency: re-import is a no-op.
	assert I.is_already_imported(sample_manifest_entry, content_community) is True

	# 5. --force re-imports.
	I._import_one(
		entry=sample_manifest_entry,
		content_community=content_community,
		c4group=c4group,
		force=True,
		rate_limit=0,
	)
	assert (pack_dir / "Sample.c4d").is_dir(), "force re-import lost the pack"
