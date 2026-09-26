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

// Pin for the C4Game::OpenScenario Origin parent-folder gate (cycle 174).
//
// Every scenario's Scenario.txt Origin chain is a subset of the chain the
// initial RegisterParentFolders(ScenarioFilename) call already registers
// (all in-tree origins are ancestors of their scenario — asserted by the
// cycle-174 content sweep). Re-running it there is redundant, and when the
// Origin cannot be resolved relative to the engine's CWD (a real install
// has no pack folders next to the binary) the bare-pack CWD-relative open
// fails and logs a spurious
//   [critical] FATAL ERROR: File not found or invalid: <pack>.c4f
// at startup (observed in the 2026-09-19 SaltRoad playtest; cosmetic, the
// game continued — the return value is ignored).
//
// The gate itself is the narrowest testable seam: OpenScenario needs the
// whole game state, RegisterParentFolders is unchanged by the fix. The
// engine-level before/after evidence lives in
// .opencode/scratch/174/nolink_saltroad_console.log (FATAL present) vs
// .opencode/scratch/174/nolink_saltroad_console_fixed.log (absent).
//
// Fixture note: every discriminator is filesystem-free, so each case yields
// the same verdict in any CWD, with or without the dev build/ pack symlinks.
// Cases that must see the sides differ (2/4) use an Origin that cannot
// resolve against any CWD — RealPath deterministically gives up on both
// sides and the two paths can never compare equal. Case 3 must see the
// sides equal and passes the very same string on both sides: identical
// inputs canonicalize identically (whether realpath resolves via the dev
// symlinks or gives up on both), so ItemIdentical is true everywhere.

#include <catch2/catch_all.hpp>

#include "C4Game.h"

TEST_CASE("ParentFolderGating_Skipped_WhenScenarioChainRegistered", "[parent-folder]")
{
	// Cycle-174 playtest fixture shape: the first RegisterParentFolders
	// call succeeded (c4f parent found -> fParentsRegistered) and the Origin
	// points at the same pack. The re-registration must be skipped, even
	// though the Origin and the absolute scenario path are never identical
	// (the Origin cannot resolve relative to any CWD).
	REQUIRE_FALSE(ShouldRegisterScenarioOrigin(
		"NoSuchPackX.c4f/Scen.c4s",
		"/definitely/not/existing/Scen.c4s",
		true));
}

TEST_CASE("ParentFolderGating_Runs_WhenScenarioChainMissing", "[parent-folder]")
{
	// Section scenarios inside .c4g groups: the first call finds no c4f
	// parent, so the Origin chain (Western.c4f/Goldrush.c4s) stays
	// load-bearing and must keep registering exactly as before the fix
	// (regression red line from the 2026-08-27 Origin/relative-resolution
	// design).
	REQUIRE(ShouldRegisterScenarioOrigin(
		"Western.c4f/Goldrush.c4s",
		"/definitely/not/existing/Goldrush.c4s/SectAshCity.c4g",
		false));
}

TEST_CASE("ParentFolderGating_Skipped_WhenOriginResolvesToScenario", "[parent-folder]")
{
	// Origin identical to the scenario path: ItemIdentical realpaths both
	// sides to the same string on every platform and in every CWD (identical
	// inputs canonicalize identically, whether realpath resolves through the
	// dev build/ pack symlinks or gives up on both), so the gate
	// deterministically returns false and the re-registration is skipped as
	// a literal no-op. No dependence on any host path or on pack symlinks in
	// the process CWD.
	REQUIRE_FALSE(ShouldRegisterScenarioOrigin(
		"SaltRoad.c4f/SaltRoad03.c4s",
		"SaltRoad.c4f/SaltRoad03.c4s",
		false));
}

TEST_CASE("ParentFolderGating_Skipped_WhenOriginEmpty", "[parent-folder]")
{
	// Matches the pre-existing getLength() guard.
	REQUIRE_FALSE(ShouldRegisterScenarioOrigin("", "/unchanged/Scen.c4s", false));
	REQUIRE_FALSE(ShouldRegisterScenarioOrigin(nullptr, "/unchanged/Scen.c4s", false));
}
