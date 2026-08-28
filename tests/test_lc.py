"""Unit tests for the LegacyClonk launcher (lc)."""

import importlib.util
import importlib.machinery
import os
import sys
from pathlib import Path

import pytest

# Load lc as a module (it has no .py extension). The launcher lives at
# LegacyClonk/tools/lc; the tests live at LegacyClonk/tests/test_lc.py.
_LC_PATH = Path(__file__).parent.parent / "tools" / "lc"
_loader = importlib.machinery.SourceFileLoader("lc", str(_LC_PATH))
spec = importlib.util.spec_from_loader("lc", _loader)
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)


# --- Fixtures ---

@pytest.fixture
def fake_workspace(tmp_path):
    """Create a fake workspace structure for testing.

    Returns a dict with paths to the fake workspace, build dir, planet dir,
    content dir, and binary.
    """
    ws = tmp_path / "ws"
    lc_dir = ws / "LegacyClonk"
    build = lc_dir / "build"
    planet = lc_dir / "planet"
    content = ws / "content"

    build.mkdir(parents=True)
    planet.mkdir(parents=True)
    content.mkdir(parents=True)

    # Fake binary
    binary = build / "clonk"
    binary.write_text("#!/bin/sh\necho fake")
    binary.chmod(0o755)

    # Fake planet c4g (directories, matching real layout)
    (planet / "Graphics.c4g").mkdir()
    (planet / "System.c4g").mkdir()
    (planet / "Graphics.c4g" / "Version.txt").write_text("fake")
    (planet / "System.c4g" / "Version.txt").write_text("fake")

    # Fake content packs (directories, matching real layout)
    (content / "Agriculture.c4d").mkdir()
    (content / "Knights.c4f").mkdir()
    (content / "Agriculture.c4d" / "Objects.txt").write_text("fake")
    (content / "Knights.c4f" / "Objects.txt").write_text("fake")

    return {
        "workspace": ws,
        "build": build,
        "planet": planet,
        "content": content,
        "binary": binary,
    }


# --- Binary discovery tests ---

def test_binary_discovery_build_dir(fake_workspace):
    """Finds build/clonk when it exists."""
    result = lc.discover_binary(fake_workspace["build"])
    assert result == fake_workspace["binary"]


def test_binary_discovery_override(fake_workspace, tmp_path):
    """--binary flag takes precedence over build dir search."""
    custom = tmp_path / "custom_clonk"
    custom.write_text("#!/bin/sh\necho custom")
    custom.chmod(0o755)

    result = lc.discover_binary(fake_workspace["build"], override=custom)
    assert result == custom


def test_binary_discovery_not_found(tmp_path):
    """Raises FileNotFoundError with a clear message when no binary found."""
    empty_build = tmp_path / "empty_build"
    empty_build.mkdir()

    with pytest.raises(FileNotFoundError, match="clonk"):
        lc.discover_binary(empty_build)


# --- Setup tests ---

def test_setup_creates_symlinks(fake_workspace, tmp_path):
    """After setup, Graphics.c4g and System.c4g exist in the game folder."""
    game_folder = tmp_path / "game"

    lc.setup_game_folder(
        fake_workspace["binary"],
        game_folder,
        fake_workspace["content"],
        fake_workspace["planet"],
    )

    assert (game_folder / "clonk").is_symlink()
    assert (game_folder / "clonk").exists()
    assert (game_folder / "Graphics.c4g").is_symlink()
    assert (game_folder / "Graphics.c4g").exists()
    assert (game_folder / "System.c4g").is_symlink()
    assert (game_folder / "System.c4g").exists()
    assert (game_folder / "Agriculture.c4d").is_symlink()
    assert (game_folder / "Agriculture.c4d").exists()
    assert (game_folder / "Knights.c4f").is_symlink()
    assert (game_folder / "Knights.c4f").exists()


def test_setup_idempotent(fake_workspace, tmp_path):
    """Running setup twice produces the same game folder."""
    game_folder = tmp_path / "game"

    lc.setup_game_folder(
        fake_workspace["binary"],
        game_folder,
        fake_workspace["content"],
        fake_workspace["planet"],
    )

    # Snapshot the symlink targets after first run
    targets_before = {
        p.name: os.readlink(p) for p in game_folder.iterdir() if p.is_symlink()
    }

    # Run setup again
    lc.setup_game_folder(
        fake_workspace["binary"],
        game_folder,
        fake_workspace["content"],
        fake_workspace["planet"],
    )

    targets_after = {
        p.name: os.readlink(p) for p in game_folder.iterdir() if p.is_symlink()
    }

    assert targets_before == targets_after


# --- Stale symlink tests ---

def test_setup_stale_symlink_refresh(tmp_path):
    """If the binary moves, re-running setup refreshes the stale symlink."""
    ws = tmp_path / "ws"
    build_old = ws / "LegacyClonk" / "build"
    build_new = ws / "LegacyClonk" / "build2"
    planet = ws / "LegacyClonk" / "planet"
    content = ws / "content"

    build_old.mkdir(parents=True)
    build_new.mkdir(parents=True)
    planet.mkdir(parents=True)
    content.mkdir(parents=True)

    binary_old = build_old / "clonk"
    binary_old.write_text("#!/bin/sh\necho fake")
    binary_old.chmod(0o755)

    binary_new = build_new / "clonk"
    binary_new.write_text("#!/bin/sh\necho fake2")
    binary_new.chmod(0o755)

    (planet / "Graphics.c4g").mkdir()
    (planet / "System.c4g").mkdir()
    (content / "Agriculture.c4d").mkdir()

    game_folder = tmp_path / "game"

    # First setup with old binary
    lc.setup_game_folder(binary_old, game_folder, content, planet)
    bin_link = game_folder / "clonk"
    assert bin_link.exists()
    assert bin_link.resolve() == binary_old.resolve()

    # Delete old binary — symlink becomes stale
    binary_old.unlink()
    assert not bin_link.exists()  # broken symlink: target gone

    # Re-run setup with new binary at a different path
    lc.setup_game_folder(binary_new, game_folder, content, planet)

    # Symlink should now point to the new binary
    assert bin_link.exists()
    assert bin_link.resolve() == binary_new.resolve()


# --- Run tests ---

def test_run_forwards_args(fake_workspace, tmp_path, monkeypatch):
    """run --smoke-run:350 forwards --smoke-run:350 to the binary."""
    game_folder = tmp_path / "game"
    game_folder.mkdir()

    captured = {}

    def fake_execv(path, args):
        captured["path"] = path
        captured["args"] = args

    monkeypatch.setattr(os, "chdir", lambda p: captured.__setitem__("chdir", p))
    monkeypatch.setattr(os, "execv", fake_execv)

    lc.run_engine(
        fake_workspace["binary"],
        game_folder,
        ["--smoke-run:350"],
    )

    assert captured["path"] == str(fake_workspace["binary"].resolve())
    assert captured["args"] == [str(fake_workspace["binary"].resolve()), "--smoke-run:350"]


def test_run_chdirs_to_game_folder(fake_workspace, tmp_path, monkeypatch):
    """On all platforms (critical on macOS), cwd passed to the binary is the game folder."""
    game_folder = tmp_path / "game"
    game_folder.mkdir()

    captured = {}

    def fake_chdir(path):
        captured["chdir"] = path

    def fake_execv(path, args):
        captured["execv_path"] = path
        captured["execv_args"] = args

    monkeypatch.setattr(os, "chdir", fake_chdir)
    monkeypatch.setattr(os, "execv", fake_execv)

    lc.run_engine(
        fake_workspace["binary"],
        game_folder,
        [],
    )

    assert captured["chdir"] == str(game_folder)
    assert captured["execv_path"] == str(fake_workspace["binary"].resolve())


# --- Smoke tests ---

def test_smoke_subcommand(fake_workspace, tmp_path, monkeypatch):
    """lc smoke dispatches through _cmd_smoke and prepends --smoke-run:350."""
    game_folder = tmp_path / "game"

    captured = {}

    def fake_execv(path, args):
        captured["path"] = path
        captured["args"] = args

    monkeypatch.setattr(os, "chdir", lambda p: captured.__setitem__("chdir", p))
    monkeypatch.setattr(os, "execv", fake_execv)

    rc = lc.main([
        "smoke",
        "--build-dir", str(fake_workspace["build"]),
        "--game-folder", str(game_folder),
    ])

    assert rc == 0
    # smoke prepends --smoke-run:350 to the (empty) engine args
    assert captured["args"] == [
        str(fake_workspace["binary"].resolve()),
        "--smoke-run:350",
    ]
    assert captured["chdir"] == str(game_folder)


# --- Doctor tests ---

def test_doctor_ready(fake_workspace, tmp_path, capsys):
    """doctor returns 0 when everything is in place."""
    game_folder = tmp_path / "game"

    lc.setup_game_folder(
        fake_workspace["binary"],
        game_folder,
        fake_workspace["content"],
        fake_workspace["planet"],
    )

    result = lc.doctor(
        fake_workspace["binary"],
        game_folder,
        fake_workspace["content"],
        fake_workspace["planet"],
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "READY" in output


def test_doctor_not_ready(tmp_path, capsys):
    """doctor returns 1 when binary is missing."""
    game_folder = tmp_path / "game"
    game_folder.mkdir()

    missing_binary = tmp_path / "nonexistent" / "clonk"

    result = lc.doctor(
        missing_binary,
        game_folder,
        tmp_path / "no_content",
        tmp_path / "no_planet",
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "NOT READY" in output


# --- Game folder CLI tests ---

def test_game_folder_default(tmp_path, monkeypatch):
    """--game-folder not given: defaults to ~/clonk."""
    fake_bin = tmp_path / "fake_clonk"
    fake_bin.write_text("#!/bin/sh\necho fake")
    fake_bin.chmod(0o755)

    captured = {}

    def fake_setup(binary, game_folder, content_dir, planet_dir, **kwargs):
        captured["game_folder"] = game_folder

    monkeypatch.setattr(lc, "setup_game_folder", fake_setup)
    monkeypatch.setattr(lc, "discover_binary", lambda *a, **kw: fake_bin)

    lc.main(["setup"])

    assert captured["game_folder"] == Path.home() / "clonk"


def test_game_folder_override(tmp_path, monkeypatch):
    """--game-folder PATH: uses the given path."""
    fake_bin = tmp_path / "fake_clonk"
    fake_bin.write_text("#!/bin/sh\necho fake")
    fake_bin.chmod(0o755)

    custom_game_folder = tmp_path / "custom_game"

    captured = {}

    def fake_setup(binary, game_folder, content_dir, planet_dir, **kwargs):
        captured["game_folder"] = game_folder

    monkeypatch.setattr(lc, "setup_game_folder", fake_setup)
    monkeypatch.setattr(lc, "discover_binary", lambda *a, **kw: fake_bin)

    lc.main(["setup", "--game-folder", str(custom_game_folder)])

    assert captured["game_folder"] == custom_game_folder
