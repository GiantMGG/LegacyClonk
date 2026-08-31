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

// Unit tests for --parameter Key=Value overrides (spec pregame-options-parity).
//
// ParseCommandLine cannot be called from test binaries (it unconditionally
// logs via Application.LogSystem, which is null here — same caveat as
// TstSmokeRunFlag.cpp). These tests therefore exercise ApplyParameterOverrides
// directly on a hand-filled ParameterOverrides vector. The parse path (both
// --parameter forms) is regression-gated end-to-end by parameter_override_smoke.
//
// The replay-skip guard (spec edge case 1) is NOT unit-testable here: it lives
// at the OpenScenario apply site (src/C4Game.cpp) behind
// !GameC4S.Head.Replay, and reaching it requires a loaded scenario
// (GameC4S.Load + Parameters.Load), i.e. a booted game.

#include <catch2/catch_all.hpp>

#include "C4Game.h"
#include "C4Teams.h"
#include "StdCompiler.h"

namespace
{
	void AddOverride(const char *key, const char *value)
	{
		Game.ParameterOverrides.emplace_back(StdStrBuf{key}, StdStrBuf{value});
	}
}

TEST_CASE("ParameterOverrides_AppliedToParametersAndTeams", "[parameter-override]")
{
	Game.Default();
	Game.Teams.Clear();
	Game.ParameterOverrides.clear();
	Game.Parameters.ControlRate = 1;  // deterministic start

	AddOverride("ControlRate", "5");
	AddOverride("TeamDist", "Random");
	AddOverride("TeamColors", "1");
	AddOverride("RandomTeamCount", "3");

	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.ControlRate == 5);
	REQUIRE(Game.Teams.GetTeamDist() == C4TeamList::TEAMDIST_Random);
	REQUIRE(Game.Teams.IsTeamColors());
	REQUIRE(Game.Teams.GetRandomTeamCount() == 3);
}

TEST_CASE("ParameterOverrides_LastOccurrenceWins", "[parameter-override]")
{
	Game.Default();
	Game.Teams.Clear();
	Game.ParameterOverrides.clear();

	AddOverride("TeamDist", "Free");
	AddOverride("TeamDist", "Random");

	Game.ApplyParameterOverrides();

	REQUIRE(Game.Teams.GetTeamDist() == C4TeamList::TEAMDIST_Random);
}

TEST_CASE("ParameterOverrides_InvalidValuesIgnored", "[parameter-override]")
{
	Game.Default();
	Game.Teams.Clear();
	Game.ParameterOverrides.clear();
	Game.Parameters.ControlRate = 1;

	AddOverride("ControlRate", "99");
	AddOverride("ControlRate", "0");
	AddOverride("TeamDist", "Bogus");
	AddOverride("TeamColors", "2");
	AddOverride("RandomTeamCount", "-1");
	AddOverride("UnknownKey", "x");

	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.ControlRate == 1);
	REQUIRE(Game.Teams.GetTeamDist() == C4TeamList::TEAMDIST_Free);
	REQUIRE_FALSE(Game.Teams.IsTeamColors());
	REQUIRE(Game.Teams.GetRandomTeamCount() == 0);
}

TEST_CASE("ParameterOverrides_TeamDistNoneRejectedWithoutAutoGenerate", "[parameter-override]")
{
	Game.Default();
	Game.Teams.Clear();
	Game.ParameterOverrides.clear();

	REQUIRE_FALSE(Game.Teams.IsAutoGenerateTeams());

	AddOverride("TeamDist", "None");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Teams.GetTeamDist() == C4TeamList::TEAMDIST_Free);
}

TEST_CASE("ParameterOverrides_TeamDistNoneAcceptedWithAutoGenerate", "[parameter-override]")
{
	Game.Default();
	Game.Teams.Clear();
	Game.ParameterOverrides.clear();

	StdStrBuf teamsIni;
	teamsIni.Ref("[Teams]\nAutoGenerateTeams=1\n");
	CompileFromBuf<StdCompilerINIRead>(mkNamingAdapt(Game.Teams, "Teams"), teamsIni);
	REQUIRE(Game.Teams.IsAutoGenerateTeams());

	AddOverride("TeamDist", "None");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Teams.GetTeamDist() == C4TeamList::TEAMDIST_None);
}

TEST_CASE("ParameterOverrides_DefaultClearsOverrides", "[parameter-override]")
{
	Game.ParameterOverrides.clear();
	AddOverride("TeamDist", "Random");
	REQUIRE(Game.ParameterOverrides.size() == 1);
	Game.Default();
	REQUIRE(Game.ParameterOverrides.empty());
}
