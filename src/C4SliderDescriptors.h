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

// Slider-contract descriptor table (spec world-generator-ux-rework).
// Single source of truth for FOUR consumers: (1) the settings-screen
// slider-row builder, (2) the --parameter key dispatch, (3) the JoinData
// net-sync block, (4) the Catch2 pinning test. Research §8 is the
// dataset; rows 1-5 are the five legacy keys, rows 6-11 the six new
// ones. Ranges/defaults are NOT in the table: they are read from the
// loaded scenario C4S at dialog-build time (Min/Max from the live
// C4SVal, thumb at Std) — exactly what the stepper code does today.

#pragma once

#include "C4Scenario.h"

#include <iterator>

struct C4SliderDescriptor
{
	const char *szLabel;                  // human label, hardcoded English (§8 col 1)
	const char *szIniKey;                 // raw --parameter/INI key (§8 col 3)
	C4SVal C4SLandscape::*pField;         // live C4S member (member-pointer)
	const char *szUnit;                   // readout unit suffix (§8 col 6)
};

inline constexpr C4SliderDescriptor kSliderDescriptors[]
{
	{"Hill height",            "Amplitude",       &C4SLandscape::Amplitude,    ""},
	{"Hill phase offset",      "Phase",           &C4SLandscape::Phase,        ""},
	{"Number of hills",        "Period",          &C4SLandscape::Period,       ""},
	{"Landscape randomness",   "Random",          &C4SLandscape::Random,       ""},
	{"Water level",            "LiquidLevel",     &C4SLandscape::LiquidLevel,  ""},
	{"Map width",              "MapWidth",        &C4SLandscape::MapWdt,       ""},
	{"Map height",             "MapHeight",       &C4SLandscape::MapHgt,       ""},
	{"Zoom factor",            "MapZoom",         &C4SLandscape::MapZoom,      "×"},
	{"Gravity level",          "Gravity",         &C4SLandscape::Gravity,      "%"},
	{"Vegetation amount",      "VegetationLevel", &C4SLandscape::VegLevel,     ""},
	{"In-earth object amount", "InEarthLevel",    &C4SLandscape::InEarthLevel, ""},
};
