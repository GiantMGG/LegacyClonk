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
	AddOverride("TeamColors", "1");
	// RandomTeamCount must be applied while the team distribution is still
	// the default (Free): SetRandomTeamCount reassigns teams when a random
	// mode is active (C4Teams.cpp), and ReassignAllTeams asserts ctrl-host
	// in Debug builds — the unit-test harness has no Control host set up.
	AddOverride("RandomTeamCount", "3");
	AddOverride("TeamDist", "Random");

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

// --- Rules=/Goals= ID-list overrides (spec pregame-options-parity-2 §2.4) --
// C1: a Rules override REPLACES the whole rules list (defaults gone, Goals untouched).
TEST_CASE("ParameterOverrides_RulesOverrideReplacesList", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Rules.Clear();
	Game.Parameters.Rules.SetIDCount(C4Id("ENRG"), 1, true);
	Game.Parameters.Goals.Clear();
	Game.Parameters.Goals.SetIDCount(C4Id("MELE"), 1, true);

	AddOverride("Rules", "NMTT=1;TACC=2");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.Rules.GetNumberOfIDs() == 2);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("NMTT")) == 1);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("TACC")) == 2);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("ENRG")) == 0);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MELE")) == 1);
}

// C2: a Goals override REPLACES the whole goals list (Rules untouched).
TEST_CASE("ParameterOverrides_GoalsOverrideReplacesList", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Rules.Clear();
	Game.Parameters.Rules.SetIDCount(C4Id("ENRG"), 1, true);
	Game.Parameters.Goals.Clear();
	Game.Parameters.Goals.SetIDCount(C4Id("MELE"), 1, true);

	AddOverride("Goals", "MONE=1;VALG=2");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.Goals.GetNumberOfIDs() == 2);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MONE")) == 1);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 2);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MELE")) == 0);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("ENRG")) == 1);
}

// C3: a bare ID parses with count 0 — the clamp must raise it to 1
// (InitGoals places exactly iCount objects, C4Game.cpp:3975-3977 — spec §4.7 trap).
TEST_CASE("ParameterOverrides_ZeroCountClampedToOne", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Goals.Clear();

	AddOverride("Goals", "MELE");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.Goals.GetNumberOfIDs() == 1);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MELE")) == 1);
}

// C4: a malformed value is caught, logged, skipped — list unchanged, no crash.
TEST_CASE("ParameterOverrides_MalformedIDListIgnoredNoCrash", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Rules.Clear();
	Game.Parameters.Rules.SetIDCount(C4Id("ENRG"), 1, true);

	AddOverride("Rules", "%%invalid%%");
	REQUIRE_NOTHROW(Game.ApplyParameterOverrides());

	REQUIRE(Game.Parameters.Rules.GetNumberOfIDs() == 1);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("ENRG")) == 1);
}

// C5: two occurrences of the same key — the last one wins.
TEST_CASE("ParameterOverrides_IDListLastOccurrenceWins", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Rules.Clear();

	AddOverride("Rules", "ENRG=1");
	AddOverride("Rules", "NMTT=1");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.Rules.GetNumberOfIDs() == 1);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("NMTT")) == 1);
}

// --- Seed=/landscape-param overrides (spec landscape-generator-research §2.1) --
// C7: a Seed override writes Parameters.RandomSeed (negative values are
// legal — the LCG takes a uint32 seed, C4Random.h:34, and the flow already
// passes arbitrary int32).
TEST_CASE("ParameterOverrides_SeedOverrideWritesRandomSeed", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.RandomSeed = 1;

	AddOverride("Seed", "1234");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.RandomSeed == 1234);

	Game.ParameterOverrides.clear();
	AddOverride("Seed", "-5");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.RandomSeed == -5);
}

// C8: malformed seed values are logged and skipped — parameters unchanged.
// 2147483648 is int32 overflow — atoi would be UB here (spec §2.1a).
TEST_CASE("ParameterOverrides_SeedOverrideMalformedIgnored", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.RandomSeed = 4711;

	AddOverride("Seed", "");
	AddOverride("Seed", "abc");
	AddOverride("Seed", "2147483648");
	AddOverride("Seed", "12x");
	REQUIRE_NOTHROW(Game.ApplyParameterOverrides());

	REQUIRE(Game.Parameters.RandomSeed == 4711);
}

// C9: a landscape-param override clamps into the scenario C4SVal bounds,
// zeroes the deviation, and preserves Min/Max (spec §2.1b).
TEST_CASE("ParameterOverrides_LandscapeParamOverrideClampsToSValBounds", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();

	Game.GameC4S.Landscape.Amplitude.Set(10, 5, 0, 100);
	Game.GameC4S.Landscape.LiquidLevel.Set(50, 10, 0, 100);

	AddOverride("Amplitude", "150");
	AddOverride("LiquidLevel", "45");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.GameC4S.Landscape.Amplitude.Std == 100);
	REQUIRE(Game.GameC4S.Landscape.Amplitude.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.Amplitude.Min == 0);
	REQUIRE(Game.GameC4S.Landscape.Amplitude.Max == 100);
	REQUIRE(Game.GameC4S.Landscape.LiquidLevel.Std == 45);
	REQUIRE(Game.GameC4S.Landscape.LiquidLevel.Rnd == 0);

	// in-bounds value: the mean moves to it exactly
	Game.ParameterOverrides.clear();
	AddOverride("Amplitude", "30");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.GameC4S.Landscape.Amplitude.Std == 30);
	REQUIRE(Game.GameC4S.Landscape.Amplitude.Rnd == 0);
}

// C10: malformed landscape-param values are logged and skipped — field unchanged.
TEST_CASE("ParameterOverrides_LandscapeParamOverrideMalformedIgnored", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.GameC4S.Landscape.Amplitude.Set(30, 0, 0, 100);

	AddOverride("Amplitude", "");
	AddOverride("Amplitude", "xyz");
	REQUIRE_NOTHROW(Game.ApplyParameterOverrides());

	REQUIRE(Game.GameC4S.Landscape.Amplitude.Std == 30);
	REQUIRE(Game.GameC4S.Landscape.Amplitude.Rnd == 0);
}

// C11: two occurrences of Seed= — the last one wins (the override list is
// applied in order; same semantics the cycle-84 TeamDist case pins).
TEST_CASE("ParameterOverrides_SeedLastOccurrenceWins", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();

	AddOverride("Seed", "1");
	AddOverride("Seed", "2");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.RandomSeed == 2);
}

// --- JoinData landscape-override staging (spec net-preround-settings-fix) --
// C12: a staged block applies to GameC4S.Landscape (the client-side join
// path: HandleJoinData stages, OpenScenario applies after GameC4S.Load).
TEST_CASE("StagedLandscapeOverridesApply", "[parameter-override]")
{
	Game.Default();
	Game.GameC4S.Landscape.Amplitude.Set(30, 0, 0, 100);
	Game.GameC4S.Landscape.Phase.Set(31, 0, 0, 100);
	Game.GameC4S.Landscape.Period.Set(32, 0, 0, 100);
	Game.GameC4S.Landscape.Random.Set(33, 0, 0, 100);
	Game.GameC4S.Landscape.LiquidLevel.Set(34, 0, 0, 100);

	C4SLandscape ls;
	ls.Default();
	ls.Amplitude.Set(45, 0, 0, 100);
	ls.Phase.Set(46, 0, 0, 100);
	ls.Period.Set(47, 0, 0, 100);
	ls.Random.Set(48, 0, 0, 100);
	ls.LiquidLevel.Set(49, 0, 0, 100);

	C4LandscapeOverrides overrides;
	overrides.SetFrom(ls);
	Game.StageLandscapeOverrides(overrides);
	Game.ApplyStagedLandscapeOverrides();

	REQUIRE(Game.GameC4S.Landscape.Amplitude.Std == 45);
	REQUIRE(Game.GameC4S.Landscape.Amplitude.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.Phase.Std == 46);
	REQUIRE(Game.GameC4S.Landscape.Period.Std == 47);
	REQUIRE(Game.GameC4S.Landscape.Random.Std == 48);
	REQUIRE(Game.GameC4S.Landscape.LiquidLevel.Std == 49);
}

// C13: with nothing staged, apply is a no-op (host/offline paths).
TEST_CASE("NoStagedBlockIsNoOp", "[parameter-override]")
{
	Game.Default();
	Game.GameC4S.Landscape.Amplitude.Set(30, 0, 0, 100);

	Game.ApplyStagedLandscapeOverrides();

	REQUIRE(Game.GameC4S.Landscape.Amplitude.Std == 30);
}

// C14: the six cycle-112 --parameter keys clamp into the scenario C4SVal
// bounds through the descriptor-driven dispatch (spec
// world-generator-ux-rework --parameter generalization).
TEST_CASE("ParameterOverrides_SixNewLandscapeKeysClamp", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();

	Game.GameC4S.Landscape.MapWdt.Set(100, 0, 64, 250);
	Game.GameC4S.Landscape.MapHgt.Set(50, 0, 40, 250);
	Game.GameC4S.Landscape.MapZoom.Set(10, 0, 5, 15);
	Game.GameC4S.Landscape.Gravity.Set(100, 0, 10, 200);
	Game.GameC4S.Landscape.VegLevel.Set(50, 30, 0, 100);
	Game.GameC4S.Landscape.InEarthLevel.Set(50, 0, 0, 100);

	AddOverride("MapWidth", "10000");
	AddOverride("MapHeight", "10");
	AddOverride("MapZoom", "1");
	AddOverride("Gravity", "500");
	AddOverride("VegetationLevel", "75");
	AddOverride("InEarthLevel", "25");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.GameC4S.Landscape.MapWdt.Std == 250);
	REQUIRE(Game.GameC4S.Landscape.MapWdt.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.MapHgt.Std == 40);
	REQUIRE(Game.GameC4S.Landscape.MapHgt.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.MapZoom.Std == 5);
	REQUIRE(Game.GameC4S.Landscape.MapZoom.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.Gravity.Std == 200);
	REQUIRE(Game.GameC4S.Landscape.Gravity.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.VegLevel.Std == 75);
	REQUIRE(Game.GameC4S.Landscape.VegLevel.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.InEarthLevel.Std == 25);
	REQUIRE(Game.GameC4S.Landscape.InEarthLevel.Rnd == 0);
}

// C15: malformed values and unknown keys are skipped without crashing.
TEST_CASE("ParameterOverrides_NewLandscapeKeysMalformedSkipped", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.GameC4S.Landscape.MapZoom.Set(10, 0, 5, 15);
	Game.GameC4S.Landscape.Gravity.Set(100, 0, 10, 200);

	AddOverride("MapZoom", "abc");
	AddOverride("Gravity", "");
	AddOverride("NoSuchKey", "5");
	REQUIRE_NOTHROW(Game.ApplyParameterOverrides());

	REQUIRE(Game.GameC4S.Landscape.MapZoom.Std == 10);
	REQUIRE(Game.GameC4S.Landscape.MapZoom.Rnd == 0);
	REQUIRE(Game.GameC4S.Landscape.Gravity.Std == 100);
	REQUIRE(Game.GameC4S.Landscape.Gravity.Rnd == 0);
}

// --- Win-condition parity keys (spec adjustable-winning-conditions §3) ----
// C16: the four keys dispatch through the shared codec — the family swap
// composes exactly like the end-to-end wincond_override_smoke.
TEST_CASE("ParameterOverrides_WinConditionKeysThroughCodec", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Rules.Clear();
	Game.Parameters.Goals.Clear();
	// authored baseline: goldmine goal + energy rule
	Game.Parameters.Goals.SetIDCount(C4Id("GLDM"), 1, true);
	Game.Parameters.Rules.SetIDCount(C4Id("ENRG"), 1, true);

	AddOverride("CooperativeGoal", "ValueGain");
	AddOverride("ValueGain", "2500");
	AddOverride("Elimination", "KillTheCaptain");
	Game.ApplyParameterOverrides();

	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 25); // 2500 points / 100
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("GLDM")) == 0);  // family swap removed the baseline
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MNTK")) == 0);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("KILC")) == 1);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("FGRV")) == 0);  // KILC does not pull FGRV
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("ENRG")) == 1);  // surgical: unrelated rule survives
}

// C17: Mode writes are additive (Melee) / surgical (Cooperative) and the
// deprecated MeleeTeamwork alias encodes to MELE (ConvertGoals:591-592).
TEST_CASE("ParameterOverrides_WinConditionModeKeys", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Goals.Clear();
	Game.Parameters.Goals.SetIDCount(C4Id("VALG"), 3, true); // authored settlement goal

	AddOverride("Mode", "Melee");
	Game.ApplyParameterOverrides();
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MELE")) == 1);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 3); // additive: authored goals survive

	Game.ParameterOverrides.clear();
	AddOverride("Mode", "Cooperative");
	Game.ApplyParameterOverrides();
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MELE")) == 0); // only the mode family removed
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 3);

	Game.ParameterOverrides.clear();
	AddOverride("Mode", "MeleeTeamwork"); // deprecated alias
	Game.ApplyParameterOverrides();
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("MELE")) == 1);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 3);
}

// C18: whole-list Goals=/Rules= overrides and the win-condition keys
// compose in CLI insertion order — last writer wins (spec edge case 7).
TEST_CASE("ParameterOverrides_WinConditionInsertionOrderInterplay", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Goals.Clear();

	// whole list first, then the target key refines it
	AddOverride("Goals", "VALG=5");
	AddOverride("ValueGain", "700");
	Game.ApplyParameterOverrides();
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 7); // 700 -> 7

	// reverse order: the whole-list override replaces the refined count
	Game.ParameterOverrides.clear();
	Game.Parameters.Goals.Clear();
	AddOverride("ValueGain", "700");
	AddOverride("Goals", "VALG=5");
	Game.ApplyParameterOverrides();
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 5);
}

// C19: unknown names and malformed values log + skip, never partially
// apply (the Parse*OverrideValue discipline).
TEST_CASE("ParameterOverrides_WinConditionMalformedSkipped", "[parameter-override]")
{
	Game.Default();
	Game.ParameterOverrides.clear();
	Game.Parameters.Rules.Clear();
	Game.Parameters.Goals.Clear();
	Game.Parameters.Goals.SetIDCount(C4Id("GLDM"), 1, true);

	AddOverride("Mode", "Bogus");
	AddOverride("Elimination", "NoSuchMode");
	AddOverride("CooperativeGoal", "Wrong");
	AddOverride("ValueGain", "abc");
	REQUIRE_NOTHROW(Game.ApplyParameterOverrides());

	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("GLDM")) == 1);
	REQUIRE(Game.Parameters.Goals.GetIDCount(C4Id("VALG")) == 0);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("KILC")) == 0);
	REQUIRE(Game.Parameters.Rules.GetIDCount(C4Id("CTFL")) == 0);
}
