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

// [PlayerN] start-list descriptor table (spec round-setup-parity-complete).
// Single source of truth for THREE consumers: (1) the three picker
// sections in C4OfflineOptionsDlg (Store goods / Store restock /
// Construction blueprints), (2) the three --parameter parity keys in
// C4Game.cpp (Knowledge=/HomeBaseMaterial=/HomeBaseProduction=),
// (3) the SliderContract pinning test. Rows map onto C4SPlrStart
// ID-list members; the INI names are the C4SPlrStart::CompileFunc
// names (C4Scenario.cpp:278-280). Semantics per row: the two store rows
// carry real stock/restock counts (1..25 mirrors the
// MaxHomeBaseProduction = 25 cap, C4Player.cpp:1694; 1..10 the
// BoundBy(11-count,1,10) production domain, C4Player.cpp:1710); the
// blueprints row is presence semantics — writes use the authored
// count-0 idiom (Knowledge=WMIL=0), reads accept both idioms
// (GetIDCount(id, 1) > 0 — the Construct gate, C4Command.cpp:1757).

#pragma once

#include "C4Def.h"
#include "C4Scenario.h"

#include <algorithm>
#include <cstdint>

// One [PlayerN] ID-list surface
struct C4PlrStartListDescriptor
{
	const char *szLabel;                     // section header shown ("Store goods", ...)
	const char *szIniKey;                    // INI / --parameter key ("HomeBaseMaterial", ...)
	C4IDList C4SPlrStart::*pList;            // member pointer into C4SPlrStart
	uint32_t dwDefCategory;                  // picker filter (C4D_SelectHomebase / C4D_SelectKnowledge)
	bool fCountChannel;                      // rows get count sliders
	int32_t iCountMin, iCountMax, iDefault;  // slider range + bulk-All default when fCountChannel
	bool fPresenceIdiom;                     // writes use the authored count-0 idiom
};

inline constexpr C4PlrStartListDescriptor kPlrStartListDescriptors[]
{
	{"Store goods",             "HomeBaseMaterial",   &C4SPlrStart::HomeBaseMaterial,   C4D_SelectHomebase,   true,  1, 25, 5,  false},
	{"Store restock",           "HomeBaseProduction", &C4SPlrStart::HomeBaseProduction, C4D_SelectHomebase,   true,  1, 10, 1,  false},
	{"Construction blueprints", "Knowledge",          &C4SPlrStart::BuildKnowledge,     C4D_SelectKnowledge,  false, 0, 0,  0,  true },
};

// Count-slider params for one PlrStart picker row. Unlike the
// win-condition resolver (ResolveCountSliderParams, whose ceiling grows
// to cover authored counts), the range here is FIXED by the descriptor:
// an authored count above the ceiling pins for display (iDefault =
// iCountMax) but stays in the list until the player edits the row — the
// list is never silently rewritten (the cycle-114 resolver guarantee,
// adapted to a fixed range). Absent rows (authored count 0) floor at
// the descriptor default.
struct C4PlrStartCountParams
{
	bool fEligible;
	int32_t iMin, iMax, iDefault;
};

constexpr C4PlrStartCountParams ResolvePlrStartCountParams(const C4PlrStartListDescriptor &rDescriptor, int32_t iAuthoredCount)
{
	if (!rDescriptor.fCountChannel) return {false, 1, 1, 1};
	const int32_t iDefault = (iAuthoredCount > 0)
		? (std::min)((std::max)(iAuthoredCount, rDescriptor.iCountMin), rDescriptor.iCountMax)
		: rDescriptor.iDefault;
	return {true, rDescriptor.iCountMin, rDescriptor.iCountMax, iDefault};
}

// Store-tab wrap geometry (spec pregame-store-tab D2). Pure constexpr
// family, no engine state: the Store sheet lays defs out in "band" rows of
// K cells, K = max(4, floor(width / 235px)) from the sheet width. With the
// worst measured Knights census (75 store goods + 75 restock + 115
// blueprint defs across content/Objects.c4d + content/Knights.c4d) the
// content height at 1080p (width 1900px → K = 8) is 936px <= the 990px
// viewport budget — the player check ("no scroll at 1080p") is unit-pinned
// in TstSliderContract.
constexpr int32_t kStoreWrapMinBandCells = 4;
constexpr int32_t kStoreWrapCellWidth    = 235;  // one def cell (icon + name + count)
constexpr int32_t kStoreWrapBandHeight   = 24;
constexpr int32_t kStoreWrapHeaderHeight = 20;   // PlrStartSectionHeader with All/None
constexpr int32_t kStoreWrapEditorStrip  = 36;   // shared count-editor strip

// Sheet width -> cells per band: K = max(4, floor(width / 235px))
constexpr int32_t ComputeStoreWrapColumns(int32_t iWidth)
{
	return (std::max)(kStoreWrapMinBandCells, iWidth / kStoreWrapCellWidth);
}

// Def count + cells per band -> band rows: ceil(N / K)
constexpr int32_t ComputeStoreWrapBands(int32_t iCount, int32_t iColumns)
{
	return (iCount + iColumns - 1) / iColumns;
}

// Total Store-sheet content height from the three section def counts:
// (bands(goods) + bands(restock) + bands(blueprints)) * band + headers + editor strip
constexpr int32_t ComputeStoreWrapContentHeight(int32_t iGoodsCount, int32_t iRestockCount, int32_t iBlueprintCount, int32_t iColumns)
{
	return (ComputeStoreWrapBands(iGoodsCount, iColumns)
	        + ComputeStoreWrapBands(iRestockCount, iColumns)
	        + ComputeStoreWrapBands(iBlueprintCount, iColumns)) * kStoreWrapBandHeight
	       + 3 * kStoreWrapHeaderHeight
	       + kStoreWrapEditorStrip;
}
