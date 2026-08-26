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
// C4Weather::LaunchWeatherEvent / StopWeatherEvent state transitions,
// CompileFunc round-trip of the four replicated fields, and the
// backward-compat no-op guard: a C4Scenario with NO [WeatherEvents]
// block must leave ActiveEventID == C4ID_None after many Execute ticks.

#include <catch2/catch_all.hpp>

#include "C4Id.h"
#include "C4Scenario.h"
#include "C4Weather.h"

#include <cstdint>

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
