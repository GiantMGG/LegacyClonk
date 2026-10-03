/*
 * LegacyClonk
 *
 * Copyright (c) 2026, The LegacyClonk Team and contributors
 *
 * Distributed under the terms of the ISC license; see accompanying file
 * "COPYING" for details.
 *
 * "Clonk" is a registered trademark of Matthes Bender, used with permission.
 * See accompanying file "TRADEMARK" for details.
 *
 * To redistribute this file separately, substitute the full license texts
 * for the above references.
 */

// Savegame-finder pins (spec save-continue).
//
// C4Config::FindNewestSavegame() must scan the savegame root (the
// Config.General.SaveGameFolder folder resolved onto the exe path — the
// same composition C4Game::QuickSave uses, C4Game.cpp:2193) recursively
// for leaf *.c4s groups (folder or packed), rank the candidates by file
// mtime (newest first, mtime ties broken lexicographically by full path),
// and return the full path of the first candidate whose scenario core
// verifies as a savegame (Head.SaveGame == 1) — or "" when none does.
// Verification uses the real core loader, so an unreadable or non-savegame
// newest candidate falls through to the next-newest one.
//
// Path compares in the CHECK sites below go through std::filesystem::path
// equality because the engine's return is `/`-joined while fixture
// .string() renders `\` on Windows (MSVC normalizes separators in path
// comparison; identical on Linux).
//
// Fixtures are folder-groups under std::filesystem::temp_directory_path():
// a directory named "<Name>.c4s" holding a minimal Scenario.txt core
// ([Head] + SaveGame). C4Group::Open handles folder-groups and
// C4Scenario::Load reads the [Head] section exactly like C4Game::OpenScenario
// does (C4Game.cpp:325); missing [Definitions]/[Game]/… sections simply fall
// back to their defaults in the INI read. Mtimes are pinned explicitly via
// std::filesystem::last_write_time (never sleeps); the ranking helper
// (FileTime, StdFile.cpp) works on second granularity, so one-second offsets
// fully separate ranks.
//
// Each case saves and restores Config.General.SaveGameFolder / ExePath
// (the TstC4ConfigMigration pattern of free global-Config manipulation,
// LINK_ENGINE-provided via TstEngineGlobals.cpp). The finder reads
// Config.General.SaveGameFolder as a folder name relative to ExePath, so the
// fixture stores it as a bare relative name while ExePath carries the
// trailing separator (the same asymmetry AtExePath expects, see
// TstFreeGameEntry.cpp).

#include <catch2/catch_all.hpp>

#include "C4Config.h"
#include "C4Strings.h"
#include <StdFile.h>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

namespace
{

// Build a fresh fixture root under the system temp dir. Fixed names (no pid
// suffix) are fine: the cases run sequentially inside one binary and each
// removes its own root before use.
std::filesystem::path MakeRoot(const char *szTag)
{
	const auto root = std::filesystem::temp_directory_path() / ("savecontinue_t1_" + std::string(szTag));
	std::filesystem::remove_all(root);
	std::filesystem::create_directories(root);
	return root;
}

// Write a minimal scenario core whose [Head] section carries the given
// SaveGame flag — the same document C4Game::OpenScenario's core read
// (C4Game.cpp:325) parses.
void WriteCore(const std::filesystem::path &core, int saveGame)
{
	std::ofstream out{core, std::ios::binary};
	out << "[Head]\n";
	out << "Title=SaveContinue fixture\n";
	out << "SaveGame=" << saveGame << "\n";
	out.close();
}

// Write a folder-group savegame fixture: <root>/<name>.c4s/Scenario.txt.
// Returns the path of the .c4s folder (the path the finder reports).
std::filesystem::path WriteSavegameFixture(const std::filesystem::path &root, const char *szName, int saveGame)
{
	const auto scenario = root / (std::string(szName) + ".c4s") / "Scenario.txt";
	std::filesystem::create_directories(scenario.parent_path());
	WriteCore(scenario, saveGame);
	return scenario.parent_path();
}

// Pin a file's mtime to the given offset from its current value. Never
// sleeps; the ranking helper (FileTime, StdFile.cpp) works on second
// granularity, so one-second offsets fully separate ranks. Pinning is
// relative (current time + offset) rather than absolute: the C++20
// sys<->file_clock conversion (file_time_type::clock::from_sys) is not
// available on MSVC's _File_time_clock, while file_clock time_point
// arithmetic is portable everywhere.
void PinMtime(const std::filesystem::path &path, std::time_t offsetSeconds)
{
	const auto current = std::filesystem::last_write_time(path);
	std::filesystem::last_write_time(path, current + std::chrono::seconds{offsetSeconds});
}

// Save/restore guard for the config slots the finder reads: the savegame
// folder (relative name, composed onto ExePath) and the exe path itself.
struct ConfigSlots
{
	ConfigSlots()
	{
		savedFolder = Config.General.SaveGameFolder.getData();
		savedExe = Config.General.ExePath;
	}

	~ConfigSlots()
	{
		Config.General.SaveGameFolder.Copy(savedFolder.c_str());
		SCopy(savedExe.c_str(), Config.General.ExePath, CFG_MaxString);
	}

	std::string savedFolder;
	std::string savedExe;
};

// Point the finder's savegame root at <fixtureRoot>/Savegames.c4f.
void SetSavegameRoot(const std::filesystem::path &fixtureRoot)
{
	SCopy((fixtureRoot.string() + "/").c_str(), Config.General.ExePath, CFG_MaxString);
	Config.General.SaveGameFolder.Copy("Savegames.c4f");
}

std::filesystem::path SavegameDir(const std::filesystem::path &fixtureRoot)
{
	return fixtureRoot / "Savegames.c4f";
}

} // namespace

TEST_CASE("SaveContinue.NewestSavegame_EmptyRoot", "[savecontinue][finder]")
{
	// Case (1): absent and empty savegame roots both report no savegame.
	ConfigSlots guard;
	const auto root = MakeRoot("empty_root");
	SetSavegameRoot(root);
	// No Savegames.c4f at all -> no savegame.
	CHECK(Config.FindNewestSavegame().empty());
	// Folder exists but holds nothing -> still no savegame.
	std::filesystem::create_directories(SavegameDir(root));
	CHECK(Config.FindNewestSavegame().empty());
}

TEST_CASE("SaveContinue.NewestSavegame_NewestWins", "[savecontinue][finder]")
{
	// Case (2): distinct mtimes -> the newest .c4s wins, regardless of
	// creation or iterator order.
	ConfigSlots guard;
	const auto root = MakeRoot("newest_wins");
	SetSavegameRoot(root);
	const auto savegames = SavegameDir(root);
	const auto older = WriteSavegameFixture(savegames, "Alpha", 1);
	const auto newer = WriteSavegameFixture(savegames, "Bravo", 1);
	PinMtime(older, 1000);
	PinMtime(newer, 2000);
	CHECK(std::filesystem::path{Config.FindNewestSavegame()} == newer);
}

TEST_CASE("SaveContinue.NewestSavegame_MtimeTieLexicographic", "[savecontinue][finder]")
{
	// Case (3): equal mtimes -> lexicographically first full path wins,
	// deterministically.
	ConfigSlots guard;
	const auto root = MakeRoot("tie_lex");
	SetSavegameRoot(root);
	const auto savegames = SavegameDir(root);
	const auto a = WriteSavegameFixture(savegames, "alpha", 1);
	const auto b = WriteSavegameFixture(savegames, "bravo", 1);
	PinMtime(a, 5000);
	PinMtime(b, 5000);
	CHECK(std::filesystem::path{Config.FindNewestSavegame()} == a);
}

TEST_CASE("SaveContinue.NewestSavegame_SkipsNonC4s", "[savecontinue][finder]")
{
	// Case (4): non-.c4s entries and dot-prefixed entries are ignored even
	// when they carry a newer mtime.
	ConfigSlots guard;
	const auto root = MakeRoot("skips_non_c4s");
	SetSavegameRoot(root);
	const auto savegames = SavegameDir(root);
	const auto only = WriteSavegameFixture(savegames, "Only", 1);
	// newer decoys that must not be considered
	const auto txt = savegames / "notes.txt"; WriteCore(txt, 1);
	const auto hidden = savegames / ".hidden.c4s"; WriteCore(hidden, 1);
	PinMtime(only, 3000);
	PinMtime(txt, 4000);
	PinMtime(hidden, 5000);
	CHECK(std::filesystem::path{Config.FindNewestSavegame()} == only);
}

TEST_CASE("SaveContinue.NewestSavegame_FallbackNextNewest", "[savecontinue][finder]")
{
	// Case (5): the newest candidate's core is not a savegame
	// (Head.SaveGame == 0) -> falls through to the next-newest valid core.
	ConfigSlots guard;
	const auto root = MakeRoot("fallback_head");
	SetSavegameRoot(root);
	const auto savegames = SavegameDir(root);
	const auto valid = WriteSavegameFixture(savegames, "Valid", 1);
	const auto newestNotSave = WriteSavegameFixture(savegames, "NewestButNotSave", 0);
	PinMtime(valid, 1000);
	PinMtime(newestNotSave, 2000);
	CHECK(std::filesystem::path{Config.FindNewestSavegame()} == valid);
}

TEST_CASE("SaveContinue.NewestSavegame_SkipsUnreadableGroup", "[savecontinue][finder]")
{
	// Case (5, unreadable flavor): the newest candidate is not even an
	// openable group (plain garbage file named .c4s) -> falls through to
	// the next-newest valid core.
	ConfigSlots guard;
	const auto root = MakeRoot("fallback_unreadable");
	SetSavegameRoot(root);
	const auto savegames = SavegameDir(root);
	const auto valid = WriteSavegameFixture(savegames, "Valid", 1);
	const auto garbage = savegames / "Garbage.c4s";
	{
		std::ofstream out{garbage, std::ios::binary};
		out << "this is not a clonk group";
		out.close();
	}
	PinMtime(valid, 1000);
	PinMtime(garbage, 2000);
	CHECK(std::filesystem::path{Config.FindNewestSavegame()} == valid);
}

TEST_CASE("SaveContinue.NewestSavegame_RecursiveSubfolderScan", "[savecontinue][finder]")
{
	// Recursive scan (plan step 3): a leaf .c4s nested in a subfolder is
	// found, and non-.c4s subfolders are traversed.
	ConfigSlots guard;
	const auto root = MakeRoot("recursive");
	SetSavegameRoot(root);
	const auto savegames = SavegameDir(root);
	const auto nested = WriteSavegameFixture(savegames / "SubFolder", "nested", 1);
	CHECK(std::filesystem::path{Config.FindNewestSavegame()} == nested);
}

TEST_CASE("SaveContinue.NewestSavegame_ReturnsFullPath", "[savecontinue][finder]")
{
	// Case (6): the returned value is the full path, directly usable by
	// SCopy (fits a _MAX_PATH buffer without truncation) and pointing at a
	// directory the game can open as a group.
	ConfigSlots guard;
	const auto root = MakeRoot("full_path");
	SetSavegameRoot(root);
	const auto scenario = WriteSavegameFixture(SavegameDir(root), "Slot01", 1);
	const std::string found = Config.FindNewestSavegame();
	CHECK_FALSE(found.empty());
	CHECK(std::filesystem::path{found} == scenario);
	CHECK(found.length() < _MAX_PATH);
	char dst[_MAX_PATH + 1];
	SCopy(found.c_str(), dst, _MAX_PATH);
	CHECK(SEqual(dst, found.c_str()));
	CHECK(SEqualNoCase(GetExtension(found.c_str()), "c4s"));
	CHECK(std::filesystem::is_directory(found));
}
