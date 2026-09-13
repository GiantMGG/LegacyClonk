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

// Migration tests for the v369 ReconnectEnabled default flip.
// Spec: .opencode/specs/2026-09-13-1350-reconnect-default-on-soak.md
//
// C4Config::AdaptToCurrentVersion() is private (C4Config.h), so these
// cases drive the public C4Config::Load() path instead -- Load calls the
// migration internally (C4Config.cpp:538), after the INI compile applied
// all defaults. That covers strictly more than a direct call would: the
// absent-key defaulting (General.Version -> 347) is exercised for real,
// then the <= 368 gate, then the General.Version = C4XVERBUILD stamp.

#include <catch2/catch_all.hpp>

#include "C4Config.h"
#include "C4Version.h"

#include <filesystem>
#include <fstream>
#include <string>

namespace
{

// Write a fixture config file into the system temp dir. Fixed names
// (no pid suffix) are fine: RUN_SERIAL is not needed because the three
// cases run sequentially inside one binary, and each case rewrites its
// own file before use.
std::filesystem::path WriteFixture(const std::string &tag, const std::string &contents)
{
	const auto path = std::filesystem::temp_directory_path()
		/ ("reconn_migration_" + tag + ".cfg");
	std::ofstream out{path, std::ios::binary};
	out << contents;
	out.close();
	return path;
}

} // namespace

TEST_CASE("C4ConfigMigration.GateOpenV367ConfigMigrates", "[config][reconnect]")
{
	// Case 1 (gate open): a pre-v369 config (Version <= 368) carrying the
	// engine-written ReconnectEnabled=0 is migrated -- the gate
	// force-enables reconnect and stamps General.Version = C4XVERBUILD.
	Config.Default();
	const auto path = WriteFixture("v367",
		"[General]\n"
		"Version=367\n"
		"[Network]\n"
		"ReconnectEnabled=0\n");
	REQUIRE(Config.Load(false, path.string().c_str()));
	CHECK(Config.Network.ReconnectEnabled);
	CHECK(Config.General.Version == C4XVERBUILD);
}

TEST_CASE("C4ConfigMigration.GateClosedOptOutHonored", "[config][reconnect]")
{
	// Case 2 (gate closed): a config already stamped with the current
	// build's version (saved by v369+). The gate is closed, so a written
	// ReconnectEnabled=0 is a genuine post-migration opt-out and is
	// honored permanently.
	Config.Default();
	const std::string version = std::to_string(C4XVERBUILD);
	const auto path = WriteFixture("optout",
		"[General]\nVersion=" + version + "\n[Network]\nReconnectEnabled=0\n");
	REQUIRE(Config.Load(false, path.string().c_str()));
	CHECK_FALSE(Config.Network.ReconnectEnabled);
	CHECK(Config.General.Version == C4XVERBUILD);
}

TEST_CASE("C4ConfigMigration.AbsentVersionKeyDefaultsTo347", "[config][reconnect]")
{
	// Case 3 (no Version key): a config whose [General] section carries
	// no Version key compiles General.Version to its default 347
	// (C4Config.cpp:81) -- the gate fires and force-enables reconnect.
	Config.Default();
	const auto path = WriteFixture("noversion",
		"[General]\nName=Test\n[Network]\nReconnectEnabled=0\n");
	REQUIRE(Config.Load(false, path.string().c_str()));
	CHECK(Config.Network.ReconnectEnabled);
	CHECK(Config.General.Version == C4XVERBUILD);
}
