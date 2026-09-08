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
// (spec net-preround-settings-fix §8, W1/W2).
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
// SetFrom/ApplyTo move the five C4SVals in the right slots.
TEST_CASE("LandscapeOverridesBlockRoundTrip", "[joindata][wire]")
{
	C4SLandscape ls;
	ls.Default();
	ls.Amplitude.Set(45, 0, 0, 100);
	ls.Phase.Set(50, 5, 0, 100);
	ls.Period.Set(15, 0, 0, 100);
	ls.Random.Set(20, 2, 0, 100);
	ls.LiquidLevel.Set(40, 0, 0, 100);

	C4LandscapeOverrides src;
	src.SetFrom(ls);
	REQUIRE(src.Valid == 1);

	C4LandscapeOverrides dst;
	const StdBuf wire = roundTripBlock(src, dst);

	REQUIRE(dst.Valid == 1);
	REQUIRE(dst.Vals[0] == src.Vals[0]);
	REQUIRE(dst.Vals[1] == src.Vals[1]);
	REQUIRE(dst.Vals[2] == src.Vals[2]);
	REQUIRE(dst.Vals[3] == src.Vals[3]);
	REQUIRE(dst.Vals[4] == src.Vals[4]);

	// Re-serialise and assert byte-equality (pins layout/endianness).
	const StdBuf re = DecompileToBuf<StdCompilerBinWrite>(dst);
	REQUIRE(re.getSize() == wire.getSize());
	REQUIRE(std::memcmp(re.getData(), wire.getData(), re.getSize()) == 0);

	// Apply-path sanity: ApplyTo writes the five C4SVals back.
	C4SLandscape target;
	target.Default();
	dst.ApplyTo(target);
	REQUIRE(target.Amplitude.Std == 45);
	REQUIRE(target.Amplitude.Rnd == 0);
	REQUIRE(target.Phase.Std == 50);
	REQUIRE(target.Period.Std == 15);
	REQUIRE(target.Random.Std == 20);
	REQUIRE(target.LiquidLevel.Std == 40);
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
