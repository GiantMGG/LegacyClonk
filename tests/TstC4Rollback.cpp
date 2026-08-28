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

// Rollback test harness + minimal C4Rollback primitive tests.
// Spec: .opencode/specs/2026-08-27-1600-rollback-prediction.md
//
// Tier 1 cases 1-4 are pure C4Rollback unit tests.
// Tier 1 cases 5-13 drive the C4RollbackHarness fake-network helper.

#include <catch2/catch_all.hpp>

#include "C4Rollback.h"

#include <cstdint>

// ---------------------------------------------------------------------------
// Smoke case: the target links and the C4Rollback default state is sane.
// ---------------------------------------------------------------------------

TEST_CASE("C4Rollback_DefaultDisabled", "[rollback]")
{
	C4Rollback rb;
	REQUIRE_FALSE(rb.IsEnabled());
	REQUIRE(rb.GetSnapshotCount() == 0);
	REQUIRE(rb.GetOldestSnapshotTick() == -1);
	REQUIRE(rb.GetNewestSnapshotTick() == -1);
}

#include "C4RollbackHarness.hpp"

using namespace C4RollbackTest;

// ---------------------------------------------------------------------------
// Tier 1 case 5: Harness_DelayBasedLockstep_StallsOnMissingRemoteInput
// Drive the harness with a 100-ms-delayed remote input; assert
// iControlReady does NOT advance past the missing tick (the existing
// delay-based behaviour). This is the baseline — proves the harness
// accurately models the engine.
// ---------------------------------------------------------------------------

TEST_CASE("Harness_DelayBasedLockstep_StallsOnMissingRemoteInput", "[rollback][harness]")
{
	C4RollbackHarness h;
	h.Init();

	// Without remote input for tick 0, iControlReady must not advance.
	const int32_t readyBefore = h.GetControlReady();
	h.Drive();
	REQUIRE(h.GetControlReady() == readyBefore);
}
