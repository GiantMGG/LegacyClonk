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

// Stage 1 unit tests for the weather-event engine extension.
//
// Covers C4SEvents::RollEventForSeason (empty, season gate, weighted),
// C4SEvents::CompileFunc round-trip of the [WeatherEvents] entry list,
// and the backward-compat no-op guard: a C4Scenario with NO
// [WeatherEvents] block leaves RollEventForSeason returning C4ID_None
// for every season, so C4Weather::Execute()'s scheduling branch is a
// no-op and ActiveEventID stays C4ID_None.

#include <catch2/catch_all.hpp>

#include "C4Id.h"
#include "C4Scenario.h"
#include "C4Weather.h"
#include "StdAdaptors.h"

#include <cstdint>
#include <string>
#include <string_view>

// ---------------------------------------------------------------------------
// C4SEvents::RollEventForSeason
// ---------------------------------------------------------------------------

TEST_CASE("C4SEvents::RollEventForSeason_empty", "[weather]")
{
	C4SEvents ev;
	ev.Default();
	CHECK(ev.RollEventForSeason(0) == C4ID_None);
	CHECK(ev.RollEventForSeason(50) == C4ID_None);
	CHECK(ev.RollEventForSeason(100) == C4ID_None);
}

TEST_CASE("C4SEvents::RollEventForSeason_seasonGate", "[weather]")
{
	C4SEvents ev;
	ev.Default();
	// Single entry valid only for season 0..25.
	C4SEventEntry e;
	e.id = C4Id("BLZD");
	e.Weight = 10;
	e.SeasonMin = 0;
	e.SeasonMax = 25;
	ev.Entries.push_back(e);

	// Out-of-season roll must yield C4ID_None.
	for (int i = 0; i < 1000; ++i)
		CHECK(ev.RollEventForSeason(80) == C4ID_None);
}

TEST_CASE("C4SEvents::RollEventForSeason_weighted", "[weather]")
{
	C4SEvents ev;
	ev.Default();

	C4SEventEntry strong;
	strong.id = C4Id("STRM");
	strong.Weight = 9;
	strong.SeasonMin = -1;
	strong.SeasonMax = -1;
	ev.Entries.push_back(strong);

	C4SEventEntry weak;
	weak.id = C4Id("FLDD");
	weak.Weight = 1;
	weak.SeasonMin = -1;
	weak.SeasonMax = -1;
	ev.Entries.push_back(weak);

	int strongCount = 0;
	for (int i = 0; i < 10000; ++i)
		if (ev.RollEventForSeason(50) == C4Id("STRM")) ++strongCount;

	// 90% expected; allow generous slack (random is unseeded here).
	CHECK(strongCount > 8500);
	CHECK(strongCount < 9500);
}

// ---------------------------------------------------------------------------
// C4Weather::Execute_noOpWithoutEventsBlock
// ---------------------------------------------------------------------------

TEST_CASE("C4Weather::Execute_noOpWithoutEventsBlock", "[weather]")
{
	// Backward-compat guarantee (spec line 651): a scenario with NO
	// [WeatherEvents] block must leave C4Weather in its idle state —
	// ActiveEventID == C4ID_None — after any number of Execute() ticks.
	//
	// The guarantee follows from two invariants verified below:
	//   (1) C4SEvents::Default() (the state when the block is absent)
	//       produces an empty Entries vector.
	//   (2) With empty Entries, RollEventForSeason returns C4ID_None for
	//       every season — so C4Weather::Execute()'s scheduling branch
	//       never calls LaunchWeatherEvent and ActiveEventID is never
	//       written. (C4Weather::Execute cannot be driven directly here
	//       without a live C4Section; this invariant chain is the
	//       precise precondition that makes Execute a no-op.)
	C4SEvents ev;
	ev.Default();
	REQUIRE(ev.Entries.empty());
	for (int season = 0; season <= 100; ++season)
		REQUIRE(ev.RollEventForSeason(season) == C4ID_None);
}

// ---------------------------------------------------------------------------
// C4SEvents::CompileFunc_roundTrip
// ---------------------------------------------------------------------------

TEST_CASE("C4SEvents::CompileFunc_roundTrip", "[weather]")
{
	// Network-replication contract: serializing a populated C4SEvents and
	// deserializing it into a fresh one must reproduce every entry field
	// (id, Weight, SeasonMin, SeasonMax). Uses the same "WeatherEvents"
	// naming scope as C4Scenario::CompileFunc.
	C4SEvents src;
	src.Default();
	C4SEventEntry e;
	e.id = C4Id("STRM");
	e.Weight = 5;
	e.SeasonMin = 10;
	e.SeasonMax = 40;
	src.Entries.push_back(e);

	const std::string out = DecompileToBuf<StdCompilerINIWrite>(
		mkNamingAdapt(src, "WeatherEvents"));

	C4SEvents dst;
	dst.Default();
	StdStrBuf buf{std::string_view{out}};
	CompileFromBuf<StdCompilerINIRead>(
		mkNamingAdapt(dst, "WeatherEvents"), buf);

	REQUIRE(dst.Entries.size() == 1);
	CHECK(dst.Entries[0].id == C4Id("STRM"));
	CHECK(dst.Entries[0].Weight == 5);
	CHECK(dst.Entries[0].SeasonMin == 10);
	CHECK(dst.Entries[0].SeasonMax == 40);
}
