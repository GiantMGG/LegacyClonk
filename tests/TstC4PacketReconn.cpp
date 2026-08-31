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

// Wire-format round-trip of C4PacketReconn + HandleReconn-returns-null
// contract (mutation 7). Reuses C4ReconnectHarness helpers unchanged.
//
// Spec: .opencode/specs/2026-08-29-2135-live-network-test-harness.md

#include <catch2/catch_all.hpp>

#include "C4ReconnPkt.h"
#include "C4Reconnect.h"
#include "C4ReconnectHarness.hpp"

#include <cstring>

namespace
{
// Binary round-trip: serialise src via StdCompilerBinWrite, deserialise
// into dst via StdCompilerBinRead, return the wire bytes.
StdBuf roundTripPacket(const C4PacketReconn &src, C4PacketReconn &dst)
{
	StdBuf wire = DecompileToBuf<StdCompilerBinWrite>(src);
	CompileFromBuf<StdCompilerBinRead>(dst, wire);
	return wire;
}
}

// W1: A populated C4PacketReconn round-trips byte-for-byte. Closes the
// wire-format residual risk #1 (CompileFunc endianness/layout stability).
TEST_CASE("C4PacketReconn_SerializeRoundTrip", "[reconn][wire]")
{
	C4Reconnect::Token tok = C4ReconnectTest::MakeToken(0xAB);
	C4PacketReconn src{tok, 7, 1234};
	C4PacketReconn dst;
	const StdBuf wire = roundTripPacket(src, dst);

	REQUIRE(dst.GetToken() == tok);
	REQUIRE(dst.GetOriginalClientID() == 7);
	REQUIRE(dst.GetLastConfirmedCtrlTick() == 1234);

	// Re-serialise and assert byte-equality (pins layout/endianness).
	const StdBuf re = DecompileToBuf<StdCompilerBinWrite>(dst);
	REQUIRE(re.getSize() == wire.getSize());
	REQUIRE(std::memcmp(re.getData(), wire.getData(), re.getSize()) == 0);
}

// W2: A default-constructed C4PacketReconn round-trips the defaults
// (originalClientID == -1, lastConfirmedCtrlTick == -1, all-zero token).
TEST_CASE("C4PacketReconn_DefaultConstructIsEmpty", "[reconn][wire]")
{
	C4PacketReconn src;
	C4PacketReconn dst;
	roundTripPacket(src, dst);

	REQUIRE(dst.GetOriginalClientID() == -1);
	REQUIRE(dst.GetLastConfirmedCtrlTick() == -1);
	C4Reconnect::Token zero{};
	REQUIRE(dst.GetToken() == zero);
}

// W3: HandleReconn returns nullptr on token-mismatch; the dormant entry
// remains so a correct retry still re-associates. This is the unit-layer
// contract that mutation 7's pConn->Close()-on-null depends on.
TEST_CASE("HandleReconn_TokenMismatch_ReturnsNull_DormantEntryRemains",
          "[reconn][wire]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{42};
	REQUIRE(r.EnterDormancy(fc.netClient.get(), 0));

	const auto bad = C4ReconnectTest::MakeToken(0xFF);
	REQUIRE(r.HandleReconn(bad, 42, 0, nullptr) == nullptr);
	// Dormant entry remains: a correct retry re-associates.
	REQUIRE(r.HandleReconn(r.GetGameToken(), 42, 0, nullptr) != nullptr);
}

// W4: A successful HandleReconn returns the reassociated client with
// status NCS_Chasing; a replay returns nullptr (dormant entry removed).
TEST_CASE("HandleReconn_ReassociatesAndClearsDormant", "[reconn][wire]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{7};
	REQUIRE(r.EnterDormancy(fc.netClient.get(), 0));

	auto *p = r.HandleReconn(r.GetGameToken(), 7, 0, nullptr);
	REQUIRE(p != nullptr);
	REQUIRE(p == fc.netClient.get());
	REQUIRE(p->getStatus() == NCS_Chasing);
	// Replay: dormant entry gone.
	REQUIRE(r.HandleReconn(r.GetGameToken(), 7, 0, nullptr) == nullptr);
}
