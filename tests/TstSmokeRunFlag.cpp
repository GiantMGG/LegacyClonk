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
 */

// Stage 1 unit tests for the SmokeRunTicks field semantics and the
// SmokeRunActive() accessor (spec headless-scenario-smoke-harness).
//
// These are pure state tests — they exercise C4Game::Default and the
// SmokeRunTicks/SmokeRunActive members directly, WITHOUT calling
// C4Game::ParseCommandLine (which unconditionally calls LogNTr at line 2710;
// LogNTr dereferences Application.LogSystem.GetLogger() which is null in
// test binaries because Application.Init() is never called). The
// --smoke-run parse path is regression-gated by the Tier 2 smoke scenarios
// (smoke_EventSmoke / smoke_PickerSmoke) which run the full engine.
//
// The C4Game global is provided by TstEngineGlobals.cpp (linked via
// LINK_ENGINE).

#include <catch2/catch_all.hpp>

#include "C4Game.h"

#include <cstdint>

TEST_CASE("SmokeRunTicks_DefaultsToZero", "[smoke-run]")
{
	Game.Default();
	REQUIRE(Game.SmokeRunTicks == 0);
}

TEST_CASE("SmokeRunActive_False_WhenZero", "[smoke-run]")
{
	Game.Default();
	REQUIRE_FALSE(Game.SmokeRunActive());
}

TEST_CASE("SmokeRunActive_True_WhenPositive", "[smoke-run]")
{
	Game.Default();
	Game.SmokeRunTicks = 350;  // simulate a successful --smoke-run 350 parse
	REQUIRE(Game.SmokeRunActive());
}

TEST_CASE("Default_ClearsSmokeRunTicks", "[smoke-run]")
{
	// Set the flag, then call Default() — SmokeRunTicks must reset to 0.
	Game.Default();
	Game.SmokeRunTicks = 350;
	REQUIRE(Game.SmokeRunTicks == 350);
	Game.Default();
	REQUIRE(Game.SmokeRunTicks == 0);
	REQUIRE_FALSE(Game.SmokeRunActive());
}
