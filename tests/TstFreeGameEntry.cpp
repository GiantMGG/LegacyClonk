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

// Free Game multi-root content-resolution pins (spec freegame-real-player-states).
//
// C4Config::ResolveFreeGameContent() must report C4FreeGameRoot::ExePath when
// the bundled Free Game scenario (Worlds.c4f/Outset.c4s) lives beside the
// binary, fall back to UserPath when it only exists in the user directory,
// prefer ExePath when both roots carry it, and report None when neither does
// (the "content not installed" signal the Free Game button turns into its
// existing message box).
//
// Fixtures are plain files under std::filesystem::temp_directory_path(): the
// engine treats scenario paths as opaque strings and the resolver's only
// check is ItemExists. Mirroring real config values, the fixture ExePath
// slot is stored WITH a trailing separator (AtExePath does not add one)
// while the UserPath slot is stored WITHOUT one (AtUserPath appends it) --
// this is exactly the path-asymmetry the resolver must respect.
//
// Each case saves and restores Config.General.ExePath / Config.General.UserPath
// (char arrays, copied via SCopy) -- the TstC4ConfigMigration pattern of free
// global-Config manipulation, LINK_ENGINE-provided via TstEngineGlobals.cpp.

#include <catch2/catch_all.hpp>

#include "C4Config.h"
#include "C4Strings.h"

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
	const auto root = std::filesystem::temp_directory_path() / ("freegame_t1_" + std::string(szTag));
	std::filesystem::remove_all(root);
	std::filesystem::create_directories(root);
	return root;
}

// Root carrying the Free Game scenario as a plain file: <root>/Worlds.c4f/Outset.c4s.
std::filesystem::path WriteFreeGameFixture(const char *szTag)
{
	const auto root = MakeRoot(szTag);
	const auto scenario = root / "Worlds.c4f" / "Outset.c4s";
	std::filesystem::create_directories(scenario.parent_path());
	std::ofstream out{scenario, std::ios::binary};
	out << "dummy scenario file: the resolver only checks existence";
	out.close();
	return root;
}

// Save/restore guard for the two path slots the resolver reads. The global
// Config comes from TstEngineGlobals.cpp; the guard keeps each case
// independent of the others and of prior runs.
struct PathSlots
{
	PathSlots()
	{
		savedExe = Config.General.ExePath;
		savedUser = Config.General.UserPath;
	}

	~PathSlots()
	{
		SCopy(savedExe.c_str(), Config.General.ExePath, CFG_MaxString);
		SCopy(savedUser.c_str(), Config.General.UserPath, CFG_MaxString);
	}

	std::string savedExe;
	std::string savedUser;
};

// ExePath lives WITH a trailing separator (AtExePath concats, no separator
// added); UserPath lives WITHOUT one (AtUserPath appends it).
void SetExePath(const std::filesystem::path &root)
{
	SCopy((root.string() + "/").c_str(), Config.General.ExePath, CFG_MaxString);
}

void SetUserPath(const std::filesystem::path &root)
{
	SCopy(root.string().c_str(), Config.General.UserPath, CFG_MaxString);
}

// Chooser fixtures: plain files whose names encode the sort order the
// chooser must follow (C4Config::FirstPlayerFile, spec freegame-real-player-states
// §4.2 auto-add). Only names + existence matter; content is irrelevant.
void WritePlayerFixture(const std::filesystem::path &root, const char *szName)
{
	std::ofstream out{root / szName, std::ios::binary};
	out << "dummy player file: only the name and existence matter";
	out.close();
}

} // namespace

TEST_CASE("FreeGameEntry.FirstPlayerFile_SortedFirst", "[freegame][chooser]")
{
	const auto root = MakeRoot("chooser_sorted");
	// DirectoryIterator order is filesystem-dependent, so the chooser must
	// not rely on it: b_second.c4p outranks a_first.c4p on typical
	// readdir orderings, but the pin must see the lexicographic first.
	WritePlayerFixture(root, "b_second.c4p");
	WritePlayerFixture(root, "a_first.c4p");
	WritePlayerFixture(root, "notes.txt");
	const std::string first = C4Config::FirstPlayerFile(root.string().c_str());
	REQUIRE_FALSE(first.empty());
	CHECK(first == (root / "a_first.c4p").string());
}

TEST_CASE("FreeGameEntry.FirstPlayerFile_EmptyDir", "[freegame][chooser]")
{
	const auto root = MakeRoot("chooser_empty");
	// no player files: the chooser reports none, the caller blocks with a
	// guide message (spec §4.2 case 3)
	CHECK(C4Config::FirstPlayerFile(root.string().c_str()).empty());
}

TEST_CASE("FreeGameEntry.FirstPlayerFile_IgnoresNonPlayerFiles", "[freegame][chooser]")
{
	// only non-.c4p files and no dot-prefixed entries qualify: still none
	const auto root = MakeRoot("chooser_nonplr");
	WritePlayerFixture(root, "x.txt");
	WritePlayerFixture(root, "y.c4s");
	CHECK(C4Config::FirstPlayerFile(root.string().c_str()).empty());
}

TEST_CASE("FreeGameEntry.ResolveFreeGameContent_ExePathHit", "[freegame][resolver]")
{
	PathSlots guard;
	const auto exeRoot = WriteFreeGameFixture("exe_hit");
	const auto userRoot = MakeRoot("exe_hit_user");
	SetExePath(exeRoot);
	SetUserPath(userRoot);
	// Content under the ExePath root only -> ExePath wins.
	CHECK(Config.ResolveFreeGameContent() == C4FreeGameRoot::ExePath);
}

TEST_CASE("FreeGameEntry.ResolveFreeGameContent_UserPathFallback", "[freegame][resolver]")
{
	PathSlots guard;
	const auto exeRoot = MakeRoot("user_hit_exe");
	const auto userRoot = WriteFreeGameFixture("user_hit");
	SetExePath(exeRoot);
	SetUserPath(userRoot);
	// Content under the UserPath root only -> UserPath fallback wins.
	CHECK(Config.ResolveFreeGameContent() == C4FreeGameRoot::UserPath);
}

TEST_CASE("FreeGameEntry.ResolveFreeGameContent_BothPreferExePath", "[freegame][resolver]")
{
	PathSlots guard;
	const auto exeRoot = WriteFreeGameFixture("both_exe");
	const auto userRoot = WriteFreeGameFixture("both_user");
	SetExePath(exeRoot);
	SetUserPath(userRoot);
	// Content under both roots -> ExePath is probed first and wins.
	CHECK(Config.ResolveFreeGameContent() == C4FreeGameRoot::ExePath);
}

TEST_CASE("FreeGameEntry.ResolveFreeGameContent_None", "[freegame][resolver]")
{
	PathSlots guard;
	const auto exeRoot = MakeRoot("none_exe");
	const auto userRoot = MakeRoot("none_user");
	SetExePath(exeRoot);
	SetUserPath(userRoot);
	// Content nowhere -> None (the Free Game button shows its message box).
	CHECK(Config.ResolveFreeGameContent() == C4FreeGameRoot::None);
}
