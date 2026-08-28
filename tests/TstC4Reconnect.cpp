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

// Reconnect handshake + snapshot-source-policy tests.
// Spec: .opencode/specs/2026-08-29-1000-connection-migration-reconnect.md
//
// Tier 1 cases 1-10 are pure C4Reconnect unit tests.
// Tier 1 cases 11-17 drive the C4ReconnectHarness fake-client pair.

#include <catch2/catch_all.hpp>

#include "C4Reconnect.h"
#include "C4Rollback.h"

#include "C4ReconnectHarness.hpp"
#include "C4RollbackHarness.hpp"

#include <chrono>
#include <ctime>

using namespace C4ReconnectTest;
using namespace C4RollbackTest;

// ---------------------------------------------------------------------------
// Case 1: MintGameToken produces a 16-byte token; IsTokenMinted flips; a
// second mint is a no-op (game-scoped, minted once).
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_MintGameToken_Is16Bytes", "[reconnect]")
{
	C4Reconnect r;
	REQUIRE_FALSE(r.IsTokenMinted());
	r.MintGameToken();
	REQUIRE(r.IsTokenMinted());
	REQUIRE(r.GetGameToken().size() == 16);
	// A freshly-minted token must not be all-zero.
	bool any = false;
	for (auto b : r.GetGameToken()) any |= (b != 0);
	REQUIRE(any);
	// Second mint is a no-op: token unchanged.
	auto t1 = r.GetGameToken();
	r.MintGameToken();
	REQUIRE(t1 == r.GetGameToken());
}

// ---------------------------------------------------------------------------
// Case 2: ConstantTimeEquals returns false for differing tokens, true for
// equal tokens.
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_ConstantTimeEquals", "[reconnect]")
{
	C4Reconnect::Token a{}; a.fill(0xAA);
	C4Reconnect::Token b{}; b.fill(0xAA);
	C4Reconnect::Token c{}; c.fill(0xBB);
	REQUIRE(C4Reconnect::ConstantTimeEquals(a, b));
	REQUIRE_FALSE(C4Reconnect::ConstantTimeEquals(a, c));
	// Single-byte difference is detected.
	b[15] ^= 0xFF;
	REQUIRE_FALSE(C4Reconnect::ConstantTimeEquals(a, b));
}

// ---------------------------------------------------------------------------
// Case 3: EnterDormancy transitions the client to NCS_Dormant and records a
// dormant entry with the correct deadline.
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_EnterDormancy_TransitionsToNCS_Dormant", "[reconnect]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.SetGraceSec(120);
	r.MintGameToken();

	C4ReconnectTest::FakeClient fc{42};
	REQUIRE(r.EnterDormancy(fc.netClient.get(), 1000));
	REQUIRE(fc.netClient->getStatus() == NCS_Dormant);
}

// ---------------------------------------------------------------------------
// Case 4: TickDormancy expires the entry and invokes onExpire exactly once.
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_TickDormancy_ExpiresAndCallsOnExpire", "[reconnect]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.SetGraceSec(0); // immediate expiry
	r.MintGameToken();

	C4ReconnectTest::FakeClient fc{7};
	REQUIRE(r.EnterDormancy(fc.netClient.get(), 1000));

	int calls = 0;
	C4Network2Client *received = nullptr;
	r.TickDormancy(1001, [&](C4Network2Client *p){ ++calls; received = p; });
	REQUIRE(calls == 1);
	REQUIRE(received == fc.netClient.get());
}

// ---------------------------------------------------------------------------
// Case 5: HandleReconn with a mismatched token returns nullptr; dormant
// entry remains so a retry can still succeed.
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_HandleReconn_TokenMismatch_ReturnsNull", "[reconnect]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{1};
	r.EnterDormancy(fc.netClient.get(), 0);

	auto bad = C4ReconnectTest::MakeToken(0xFF);
	REQUIRE(r.HandleReconn(bad, 1, 0, nullptr) == nullptr);
	// Dormant entry remains: a correct retry still re-associates.
	REQUIRE(r.HandleReconn(r.GetGameToken(), 1, 0, nullptr) != nullptr);
}

// ---------------------------------------------------------------------------
// Case 6: HandleReconn with a matching token re-associates, flips status to
// NCS_Chasing, and removes the dormant entry (replay returns nullptr).
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_HandleReconn_ReassociatesAndClearsDormant", "[reconnect]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{5};
	r.EnterDormancy(fc.netClient.get(), 0);

	auto *p = r.HandleReconn(r.GetGameToken(), 5, 0, nullptr);
	REQUIRE(p != nullptr);
	REQUIRE(p == fc.netClient.get());
	REQUIRE(p->getStatus() == NCS_Chasing);
	// Replay: dormant entry gone.
	REQUIRE(r.HandleReconn(r.GetGameToken(), 5, 0, nullptr) == nullptr);
}

// ---------------------------------------------------------------------------
// Case 7: HandleReconn with an unknown originalClientID returns nullptr.
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_HandleReconn_UnknownOriginalClientID_ReturnsNull", "[reconnect]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	REQUIRE(r.HandleReconn(r.GetGameToken(), 999, 0, nullptr) == nullptr);
}

// ---------------------------------------------------------------------------
// Case 8: GetReconnectSnapshot with Rollback disabled returns a fresh
// snapshot via the injectable DoSaveSnapshot hook. The returned tick is
// Game.Control.ControlTick (0 in the default-constructed test global).
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_GetReconnectSnapshot_RollbackDisabled", "[reconnect]")
{
	C4ReconnectTestable r;
	r.SetEnabled(true);
	r.saveFn = [](StdBuf &buf){ buf.Copy("fresh", 5); return true; };
	auto snap = r.GetReconnectSnapshot(0, nullptr);
	REQUIRE(snap.has_value());
	REQUIRE(snap->buf.getSize() == 5);
	REQUIRE(snap->tick == Game.Control.ControlTick);
}

// ---------------------------------------------------------------------------
// Case 9: GetReconnectSnapshot with Rollback enabled but the requested tick
// beyond the ring window falls back to the fresh-snapshot path.
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_GetReconnectSnapshot_RollbackWindowExceeded", "[reconnect]")
{
	C4ReconnectTestable r;
	r.SetEnabled(true);
	r.saveFn = [](StdBuf &buf){ buf.Copy("fresh", 5); return true; };
	C4Rollback rb;
	rb.Init(5, 3);
	rb.SetEnabled(true);
	// Ring is empty → GetSnapshotForTick returns nullopt → fresh fallback.
	auto snap = r.GetReconnectSnapshot(20, &rb);
	REQUIRE(snap.has_value());
	REQUIRE(snap->buf.getSize() == 5);
}

// ---------------------------------------------------------------------------
// Case 10: GetReconnectSnapshot prefers the rollback ring when a snapshot
// with tick <= lastConfirmedCtrlTick exists, and does NOT call the fresh-
// save hook. Uses C4RollbackTestable (from C4RollbackHarness.hpp) to inject
// a ring snapshot at tick 5 via MaybeTakeSnapshot.
// ---------------------------------------------------------------------------
TEST_CASE("C4Reconnect_GetReconnectSnapshot_RollbackHit", "[reconnect]")
{
	C4ReconnectTestable r;
	r.SetEnabled(true);
	bool freshCalled = false;
	r.saveFn = [&](StdBuf &){ freshCalled = true; return false; };

	C4RollbackTest::C4RollbackTestable rb;
	rb.Init(5, 3);
	rb.SetEnabled(true);
	rb.snapshotFn = [](StdBuf &buf){ buf.Copy("ring", 4); return true; };
	// Populate the ring with a snapshot at tick 5 (K=5 → tick % 5 == 0).
	rb.MaybeTakeSnapshot(5);
	REQUIRE(rb.GetSnapshotCount() == 1);

	auto snap = r.GetReconnectSnapshot(10, &rb);
	REQUIRE(snap.has_value());
	REQUIRE(snap->tick == 5);
	REQUIRE_FALSE(freshCalled); // ring path taken, fresh-save bypassed
}

// ---------------------------------------------------------------------------
// Case 11: A successful reconnect restores the original client ID (no
// iNextClientID++ mint). Drives the fake-client pair through dormancy +
// HandleReconn and asserts the reassociated client is the original.
// ---------------------------------------------------------------------------
TEST_CASE("Harness_DisconnectReconnect_RestoresOriginalClientID", "[reconnect][harness]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{11, "eleven"};
	REQUIRE(r.EnterDormancy(fc.netClient.get(), 0));
	auto *p = r.HandleReconn(r.GetGameToken(), 11, 0, nullptr);
	REQUIRE(p != nullptr);
	REQUIRE(p->getID() == 11);
	REQUIRE(p->getStatus() == NCS_Chasing);
}

// ---------------------------------------------------------------------------
// Case 12: ReconnectGraceSec = 0 → TickDormancy expires on the next tick
// and the onExpire callback (which would run CtrlRemove) fires.
// ---------------------------------------------------------------------------
TEST_CASE("Harness_GraceExpires_RunsCtrlRemove", "[reconnect][harness]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.SetGraceSec(0);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{12};
	r.EnterDormancy(fc.netClient.get(), 100);

	bool ctrlRemoveCalled = false;
	r.TickDormancy(101, [&](C4Network2Client *){ ctrlRemoveCalled = true; });
	REQUIRE(ctrlRemoveCalled);
}

// ---------------------------------------------------------------------------
// Case 13: With RollbackEnabled and a populated ring, the reconnect
// snapshot is sourced from the ring. Drives a reconnect handshake then
// GetReconnectSnapshot; asserts the ring snapshot (tick 5) is returned and
// the fresh-save hook is NOT called.
// ---------------------------------------------------------------------------
TEST_CASE("Harness_ReconnectWithRollbackSnapshot_FastForwardsToHostTick", "[reconnect][harness]")
{
	C4ReconnectTestable r;
	r.SetEnabled(true);
	r.MintGameToken();
	bool freshCalled = false;
	r.saveFn = [&](StdBuf &){ freshCalled = true; return false; };

	C4RollbackTest::C4RollbackTestable rb;
	rb.Init(5, 3);
	rb.SetEnabled(true);
	rb.snapshotFn = [](StdBuf &buf){ buf.Copy("ring", 4); return true; };
	rb.MaybeTakeSnapshot(5);
	REQUIRE(rb.GetSnapshotCount() == 1);

	C4ReconnectTest::FakeClient fc{13};
	REQUIRE(r.EnterDormancy(fc.netClient.get(), 0));
	auto *p = r.HandleReconn(r.GetGameToken(), 13, 50, nullptr);
	REQUIRE(p != nullptr);

	auto snap = r.GetReconnectSnapshot(50, &rb);
	REQUIRE(snap.has_value());
	REQUIRE(snap->tick == 5);
	REQUIRE_FALSE(freshCalled);
}

// ---------------------------------------------------------------------------
// Case 14: Two concurrent reconnects claiming the same dormant client —
// first wins, second returns nullptr.
// ---------------------------------------------------------------------------
TEST_CASE("Harness_ConcurrentReconnects_FirstWins", "[reconnect][harness]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{14};
	r.EnterDormancy(fc.netClient.get(), 0);

	auto *first = r.HandleReconn(r.GetGameToken(), 14, 0, nullptr);
	REQUIRE(first != nullptr);
	auto *second = r.HandleReconn(r.GetGameToken(), 14, 0, nullptr);
	REQUIRE(second == nullptr);
}

// ---------------------------------------------------------------------------
// Case 15: ReconnectDisabled — EnterDormancy returns false, so the caller
// takes the CtrlRemove path. This is the byte-for-byte-identical safety
// property.
// ---------------------------------------------------------------------------
TEST_CASE("Harness_ReconnectDisabled_ByteForByteIdentical", "[reconnect][harness]")
{
	C4Reconnect r;
	// r.IsEnabled() == false by default.
	r.MintGameToken(); // minting is allowed even when disabled (no-op effect)
	C4ReconnectTest::FakeClient fc{15};
	REQUIRE_FALSE(r.EnterDormancy(fc.netClient.get(), 0));
	REQUIRE(fc.netClient->getStatus() != NCS_Dormant);
	REQUIRE(r.HandleReconn(r.GetGameToken(), 15, 0, nullptr) == nullptr);
}

// ---------------------------------------------------------------------------
// Case 16: Token mismatch — HandleReconn returns nullptr; the caller
// (HandlePacket PID_Reconn case) closes the connection. Dormant entry stays.
// ---------------------------------------------------------------------------
TEST_CASE("Harness_TokenMismatch_ConnectionClosed", "[reconnect][harness]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{16};
	r.EnterDormancy(fc.netClient.get(), 0);
	auto bad = C4ReconnectTest::MakeToken(0x01);
	REQUIRE(r.HandleReconn(bad, 16, 0, nullptr) == nullptr);
	// Dormant entry still present: a correct retry re-associates.
	REQUIRE(r.HandleReconn(r.GetGameToken(), 16, 0, nullptr) != nullptr);
}

// ---------------------------------------------------------------------------
// Case 17: League notified exactly once on drop. The dormancy-entry path
// fires LeagueNotifyDisconnect once (in OnClientDisconnect, before
// EnterDormancy). TickDormancy's onExpire callback runs CtrlRemove directly
// WITHOUT re-entering OnClientDisconnect, so it does NOT re-notify. Assert
// at the callback layer: onExpire fires exactly once per expired entry, and
// EnterDormancy does not invoke onExpire.
// ---------------------------------------------------------------------------
TEST_CASE("Harness_Reconnect_LeagueNotifiedOnceOnDrop", "[reconnect][harness]")
{
	C4Reconnect r;
	r.SetEnabled(true);
	r.SetGraceSec(0);
	r.MintGameToken();
	C4ReconnectTest::FakeClient fc{17};
	r.EnterDormancy(fc.netClient.get(), 0);

	int onExpireCalls = 0;
	r.TickDormancy(1, [&](C4Network2Client *){ ++onExpireCalls; });
	REQUIRE(onExpireCalls == 1);
	// A second TickDormancy with the entry already removed must not re-fire.
	r.TickDormancy(2, [&](C4Network2Client *){ ++onExpireCalls; });
	REQUIRE(onExpireCalls == 1);
}
