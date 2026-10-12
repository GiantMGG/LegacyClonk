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

// Pin for the C4Group::OpenAsChild dangling-folder-entry guard (cycle 216).
//
// A folder-form group's children are disk entries, so a child that is
// neither a directory nor an existing file can never be a group. Before the
// guard, opening such a child (a dangling symlink) recursed forever:
//
//   C4Group::Open -> OpenAsChild -> AccessEntry -> SetFilePtr2Entry
//     -> C4Group_IsGroup -> C4Group::Open -> ...
//
// until the stack was exhausted (SIGSEGV, ~1500 frames, 8 MB stack; gdb
// evidence .opencode/scratch/216/gdb-bt.txt). The crash surfaced in
// C4ScenarioListLoader when a games-folder symlink pointed at a removed
// pack (build3/SilkRoad.c4f after the cycle-193 SilkRoad -> OceanTrade
// fold): scenario selection died instead of enumerating past the link.
//
// The guard makes the probe fail fast when the mother is a folder-form
// group (pMother->Status == GRPF_Folder) and the child path is not an
// existing file. Packed-mother children (GRPF_File) are exempt: their
// child paths are pack-internal, not on-disk files.
//
// Fixture note: all paths are absolute (std::filesystem::temp_directory_path),
// so the verdicts do not depend on the test's CWD or dev-build/ pack
// symlinks. On platforms where create_symlink fails (Windows privilege),
// the dangling-symlink case SKIPs; the subfolder case still runs, proving
// the guard never over-rejects a real folder child.

#include <catch2/catch_all.hpp>

#include <atomic>
#include <filesystem>
#include <string>
#include <thread>

#include "C4Group.h"

namespace fs = std::filesystem;

namespace
{
// Unique-enough per-process scratch dir, removed in teardown. The name
// carries a monotonic counter + thread-id hash so parallel ctest runs or
// repeated batteries never share state.
class TempGroupDir
{
public:
	explicit TempGroupDir(const char *tag)
	{
		static std::atomic<unsigned> s_counter{};
		const auto unique = std::to_string(s_counter++)
			+ "-" + std::to_string(std::hash<std::thread::id>{}(std::this_thread::get_id()));
		root = fs::temp_directory_path() / ("tst_c4group_dangling-" + std::string(tag) + "-" + unique);
		std::error_code ec;
		fs::remove_all(root, ec);
		fs::create_directories(root, ec);
		REQUIRE_FALSE(ec);
	}

	~TempGroupDir()
	{
		std::error_code ec;
		fs::remove_all(root, ec);
	}

	fs::path root;
};
} // namespace

TEST_CASE("C4Group dangling folder-child is rejected cleanly", "[c4group]")
{
	TempGroupDir tmp("mother");
	const fs::path mother = tmp.root / "mother";
	REQUIRE(fs::create_directories(mother));
	REQUIRE(fs::create_directories(mother / "realsub"));

	// Dangling symlink target must not exist.
	const fs::path dangling = mother / "dangling.c4f";
	std::error_code ec;
	fs::create_symlink(mother / "no-such-target.c4f", dangling, ec);
	if (ec)
	{
		SKIP("symlink creation not supported in this environment");
	}
	REQUIRE(fs::is_symlink(dangling));

	SECTION("C4Group::Open on the dangling child returns false without crashing")
	{
		C4Group h;
		REQUIRE_FALSE(h.Open(dangling.string().c_str()));
	}

	SECTION("C4Group_IsGroup on the dangling path returns false")
	{
		REQUIRE_FALSE(C4Group_IsGroup(dangling.string().c_str()));
	}
}

TEST_CASE("C4Group real subfolder child still opens as folder", "[c4group]")
{
	TempGroupDir tmp("realsub");
	const fs::path mother = tmp.root / "mother";
	REQUIRE(fs::create_directories(mother));
	const fs::path realsub = mother / "realsub";
	REQUIRE(fs::create_directories(realsub));

	// The dangling-entry guard must not over-reject: a real folder child of
	// a folder-form mother still opens and reports GRPF_Folder.
	C4Group h;
	REQUIRE(h.Open(realsub.string().c_str()));
	REQUIRE(h.GetStatus() == GRPF_Folder);
}
