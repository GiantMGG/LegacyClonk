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

// Wire-format round-trip of the C4LandscapeOverrides JoinData block
// (spec net-preround-settings-fix §8, W1/W2; spec world-generator-ux-rework
// extends the block 5 -> 11 slots).
//
// The unit under test is the BLOCK (own CompileFunc), not a whole
// default-constructed C4PacketJoinData: the packet's default-constructed
// Parameters carries a Scenario C4GameRes with a null res core, and
// packing it segfaults under NDEBUG (documented at C4Network2.cpp:2050-2054).
// The full-packet wiring is pinned end-to-end by net_settings_sync_smoke.

#include <catch2/catch_all.hpp>

#include "C4Network2.h"
#include "StdCompiler.h"

#include <cstring>
#include <iterator>

namespace
{
// Binary round-trip: serialise src via StdCompilerBinWrite, deserialise
// into dst via StdCompilerBinRead, return the wire bytes.
StdBuf roundTripBlock(const C4LandscapeOverrides &src, C4LandscapeOverrides &dst)
{
	StdBuf wire = DecompileToBuf<StdCompilerBinWrite>(src);
	CompileFromBuf<StdCompilerBinRead>(dst, wire);
	return wire;
}
}

// W1: a populated block round-trips field-exact and byte-exact, and
// SetFrom/ApplyTo move all eleven C4SVals in the right slots.
TEST_CASE("LandscapeOverridesBlockRoundTrip", "[joindata][wire]")
{
	C4SLandscape ls;
	ls.Default();
	ls.Amplitude.Set(45, 0, 0, 100);
	ls.Phase.Set(50, 5, 0, 100);
	ls.Period.Set(15, 0, 0, 100);
	ls.Random.Set(20, 2, 0, 100);
	ls.LiquidLevel.Set(40, 0, 0, 100);
	ls.MapWdt.Set(120, 0, 64, 250);
	ls.MapHgt.Set(80, 0, 40, 250);
	ls.MapZoom.Set(8, 0, 5, 15);
	ls.Gravity.Set(150, 0, 10, 200);
	ls.VegLevel.Set(60, 0, 0, 100);
	ls.InEarthLevel.Set(70, 0, 0, 100);

	C4LandscapeOverrides src;
	src.SetFrom(ls);
	REQUIRE(src.Valid == 1);
	REQUIRE(std::size(src.Vals) == 11);

	C4LandscapeOverrides dst;
	const StdBuf wire = roundTripBlock(src, dst);

	REQUIRE(dst.Valid == 1);
	for (std::size_t i = 0; i < std::size(dst.Vals); ++i)
	{
		REQUIRE(dst.Vals[i] == src.Vals[i]);
	}

	// Re-serialise and assert byte-equality (pins layout/endianness):
	// 11 C4SVals (4x int32 = 16 bytes each) + Valid (4 bytes) = 180.
	const StdBuf re = DecompileToBuf<StdCompilerBinWrite>(dst);
	REQUIRE(re.getSize() == wire.getSize());
	REQUIRE(std::memcmp(re.getData(), wire.getData(), re.getSize()) == 0);
	REQUIRE(wire.getSize() == 11 * 16 + 4);

	// Apply-path sanity: ApplyTo writes all eleven C4SVals back.
	C4SLandscape target;
	target.Default();
	dst.ApplyTo(target);
	REQUIRE(target.Amplitude.Std == 45);
	REQUIRE(target.Amplitude.Rnd == 0);
	REQUIRE(target.Phase.Std == 50);
	REQUIRE(target.Period.Std == 15);
	REQUIRE(target.Random.Std == 20);
	REQUIRE(target.LiquidLevel.Std == 40);
	REQUIRE(target.MapWdt.Std == 120);
	REQUIRE(target.MapHgt.Std == 80);
	REQUIRE(target.MapZoom.Std == 8);
	REQUIRE(target.Gravity.Std == 150);
	REQUIRE(target.VegLevel.Std == 60);
	REQUIRE(target.InEarthLevel.Std == 70);
}

// W2: a default-constructed block round-trips with Valid == 0
// (old-format-packet decode safety).
TEST_CASE("LandscapeOverridesDefaultDecodesAsInvalid", "[joindata][wire]")
{
	C4LandscapeOverrides src;
	C4LandscapeOverrides dst;
	roundTripBlock(src, dst);
	REQUIRE(dst.Valid == 0);
}

// W3 (cycle 112): a 107-era five-slot buffer (five C4SVals + Valid,
// 84 bytes) decodes without throwing; the five legacy slots survive and
// the Valid gate holds (Valid stays 0 -> the block is NOT applied).
TEST_CASE("LandscapeOverridesLegacyFiveSlotBufferDecodesAsOldFormat", "[joindata][wire]")
{
	// Hand-craft the 107-era wire buffer: five C4SVal slots + Valid.
	C4SLandscape ls;
	ls.Default();
	ls.Amplitude.Set(45, 0, 0, 100);
	ls.Phase.Set(50, 5, 0, 100);
	ls.Period.Set(15, 0, 0, 100);
	ls.Random.Set(20, 2, 0, 100);
	ls.LiquidLevel.Set(40, 0, 0, 100);

	StdBuf legacy;
	const C4SVal LegacySlots[5] = {ls.Amplitude, ls.Phase, ls.Period, ls.Random, ls.LiquidLevel};
	for (const C4SVal &rVal : LegacySlots)
		legacy.Append(DecompileToBuf<StdCompilerBinWrite>(rVal));
	const int32_t iValid = 1;
	legacy.Append(DecompileToBuf<StdCompilerBinWrite>(iValid));
	REQUIRE(legacy.getSize() == 5 * 16 + 4);

	C4LandscapeOverrides dst;
	REQUIRE_NOTHROW(CompileFromBuf<StdCompilerBinRead>(dst, legacy));

	// old-format gate: the short buffer leaves Valid == 0 -> not applied
	REQUIRE(dst.Valid == 0);

	// the five legacy slots still decode
	REQUIRE(dst.Vals[0] == LegacySlots[0]);
	REQUIRE(dst.Vals[1] == LegacySlots[1]);
	REQUIRE(dst.Vals[2] == LegacySlots[2]);
	REQUIRE(dst.Vals[3] == LegacySlots[3]);
	REQUIRE(dst.Vals[4] == LegacySlots[4]);
}
