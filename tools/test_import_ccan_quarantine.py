"""Pytest suite for the `quarantine` subcommand. No network, tmp_path only."""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import import_ccan as I


def _record(tmp_path: Path, *, sha: str, size: int) -> Path:
    rec = tmp_path / "quarantine.toml"
    body = (
        "[quarantine.4242]\n"
        'title = "Testpack"\n'
        "ccan_id = 4242\n"
        'author_nick = "Tester"\n'
        "author_uid = 1\n"
        'uploaded = "2026-01-01"\n'
        'blob_url = "https://example.invalid/dl/Testpack.zip"\n'
        f'sha256 = "{sha}"\n'
        f"blob_size = {size}\n"
        "file_count = 2\n"
        "scenario_count = 1\n"
        f'hold_dir = "{(tmp_path / "hold").as_posix()}"\n'
        'status = "awaiting-author-license"\n'
        'outreach_thread = "https://example.invalid/t/1"\n')
    rec.write_text(body, encoding="utf-8")
    return rec


def _blob(tmp_path: Path, data: bytes) -> Path:
    hold = tmp_path / "hold"
    hold.mkdir(exist_ok=True)
    p = hold / "Testpack.zip"
    p.write_bytes(data)
    return p


def _run(tmp_path: Path, rec: Path, hold: Path, extra=()):
    rc = I.main(["quarantine", "4242",
                 "--record", str(rec),
                 "--hold-dir", str(hold),
                 "--outreach-dir", str(tmp_path / "outreach")]
                + list(extra))
    return rc, tmp_path / "outreach"


def test_quarantine_sha_mismatch(tmp_path, capsys):
    data = b"not the blob"
    rec = _record(tmp_path, sha="0" * 64, size=len(data))
    _blob(tmp_path, data)
    rc, _ = _run(tmp_path, rec, tmp_path / "hold")
    assert rc == 1
    assert "SHA256 MISMATCH" in capsys.readouterr().out


def test_quarantine_missing_blob(tmp_path, capsys):
    rec = _record(tmp_path, sha="0" * 64, size=10)
    rc, _ = _run(tmp_path, rec, tmp_path / "hold")
    assert rc == 1
    assert "MISSING blob" in capsys.readouterr().out


def test_quarantine_verified_and_letters_byte_identical(tmp_path):
    data = b"seepack-standin-blob-bytes"
    sha = hashlib.sha256(data).hexdigest()
    rec = _record(tmp_path, sha=sha, size=len(data))
    _blob(tmp_path, data)
    rc1, outdir = _run(tmp_path, rec, tmp_path / "hold")
    assert rc1 == 0
    de1 = (outdir / "letter-de.md").read_bytes()
    en1 = (outdir / "letter-en.md").read_bytes()
    assert b"Testpack" in de1 and b"Testpack" in en1
    assert b"@@TITLE@@" not in de1 and b"@@TITLE@@" not in en1
    # Second run regenerates byte-identical letters.
    rc2, _ = _run(tmp_path, rec, tmp_path / "hold")
    assert rc2 == 0
    assert (outdir / "letter-de.md").read_bytes() == de1
    assert (outdir / "letter-en.md").read_bytes() == en1
