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

// Stage 1 unit tests for C4ReplayController — the replay scrub state machine.
//
// The controller uses injectable std::function callbacks (frameProvider,
// softRestart) so the tests can drive it with fake lambdas without booting
// the full engine or synthesizing a C4Playback instance. A non-null sentinel
// pointer stands in for pPlayback_ (the controller only checks non-nullity;
// it never dereferences pPlayback_).

#include <catch2/catch_all.hpp>

#include "C4Replay.h"

#include <cstdint>

// ---------------------------------------------------------------------------
// Test fixture: a controller pre-attached with fake callbacks.
// The fake frame provider returns a mutable counter; the fake soft-restart
// callback records the target and sets the frame to the target (simulating
// a completed soft-restart + fast-forward).
// ---------------------------------------------------------------------------

namespace
{
	struct FakeReplay
	{
		uint32_t currentFrame = 0;
		uint32_t totalFrames  = 100;
		bool     softRestartCalled = false;
		uint32_t softRestartTarget = 0;

		C4ReplayController ctrl;

		// A non-null sentinel for pPlayback_ — the controller never
		// dereferences it; it only checks non-nullity in the guard.
		static C4Playback *sentinel() { return reinterpret_cast<C4Playback *>(0x1); }

		FakeReplay()
		{
			ctrl.Attach(sentinel(), totalFrames,
				[&]() { return currentFrame; },
				[&](uint32_t target) {
					softRestartCalled = true;
					softRestartTarget = target;
					// Simulate the soft-restart fast-forward landing at frame 0.
					currentFrame = 0;
				});
		}
	};
}

// ---------------------------------------------------------------------------
// 1. GetTotalFrames returns zero when Idle
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::GetTotalFrames_returnsZero_whenIdle", "[replay]")
{
	C4ReplayController ctrl;
	CHECK(ctrl.GetTotalFrames() == 0);
	CHECK(ctrl.GetState() == C4ReplayController::State::Idle);
}

// ---------------------------------------------------------------------------
// 2. SetSpeed clamps to [0.25, 8.0]
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::SetSpeed_clampsToRange", "[replay]")
{
	C4ReplayController ctrl;
	ctrl.SetSpeed(20.0f);
	CHECK(ctrl.GetSpeed() == 8.0f);
	ctrl.SetSpeed(0.0f);
	CHECK(ctrl.GetSpeed() == 0.25f);
	ctrl.SetSpeed(2.0f);
	CHECK(ctrl.GetSpeed() == 2.0f);
}

// ---------------------------------------------------------------------------
// 3. Pause / Resume state transitions
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::Pause_Resume_stateTransitions", "[replay]")
{
	FakeReplay fr;
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::Playing);

	fr.ctrl.Pause();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);
	CHECK(fr.ctrl.IsPaused() == true);

	// Pause is idempotent.
	fr.ctrl.Pause();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);

	fr.ctrl.Resume();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Playing);
	CHECK(fr.ctrl.IsPaused() == false);

	// Resume is idempotent.
	fr.ctrl.Resume();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Playing);
}

// ---------------------------------------------------------------------------
// 4. SeekForward sets SeekingForward state
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::SeekForward_setsState", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 0;

	fr.ctrl.SeekToFrame(50);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::SeekingForward);
	CHECK(fr.ctrl.GetSeekTarget() == 50);
	CHECK_FALSE(fr.softRestartCalled);
}

// ---------------------------------------------------------------------------
// 5. SeekBackward sets SeekingBackward and calls softRestart
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::SeekBackward_softRestart", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 80;

	fr.ctrl.SeekToFrame(20);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::SeekingBackward);
	CHECK(fr.ctrl.GetSeekTarget() == 20);
	CHECK(fr.softRestartCalled == true);
	CHECK(fr.softRestartTarget == 20);
}

// ---------------------------------------------------------------------------
// 6. TickSeek forward reaches target
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::TickSeek_forward_reachesTarget", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 0;

	fr.ctrl.SeekToFrame(50);
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::SeekingForward);

	// Simulate the engine's tick loop: advance the frame, then poll TickSeek.
	bool reached = false;
	for (uint32_t i = 0; i < 100; ++i)
	{
		fr.currentFrame++;
		if (fr.ctrl.TickSeek())
		{
			reached = true;
			break;
		}
	}

	CHECK(reached == true);
	CHECK(fr.currentFrame == 50);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);
}

// ---------------------------------------------------------------------------
// 7. TickSeek backward reaches target after soft-restart
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::TickSeek_backward_reachesTarget", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 80;

	// SeekToFrame calls softRestart, which resets currentFrame to 0.
	fr.ctrl.SeekToFrame(20);
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::SeekingBackward);
	REQUIRE(fr.currentFrame == 0); // soft-restart reset to frame 0

	// Simulate fast-forward: advance frame to target.
	fr.currentFrame = 20;

	// TickSeek should detect arrival and transition to Paused.
	CHECK(fr.ctrl.TickSeek() == true);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);
}

// ---------------------------------------------------------------------------
// 8. StepForward advances by one frame
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::StepForward_advancesOne", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 40;

	fr.ctrl.StepForward();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::SeekingForward);
	CHECK(fr.ctrl.GetSeekTarget() == 41);
}

// ---------------------------------------------------------------------------
// 9. StepBackward triggers soft-restart
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::StepBackward_softRestart", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 50;

	fr.ctrl.StepBackward();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::SeekingBackward);
	CHECK(fr.ctrl.GetSeekTarget() == 49);
	CHECK(fr.softRestartCalled == true);
}

// ---------------------------------------------------------------------------
// 10. CancelSeek returns to Paused
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::CancelSeek_returnsToPaused", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 80;

	fr.ctrl.SeekToFrame(20);
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::SeekingBackward);

	fr.ctrl.CancelSeek();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);

	// Also test forward cancel.
	fr.ctrl.SeekToFrame(90);
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::SeekingForward);
	fr.ctrl.CancelSeek();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);
}

// ---------------------------------------------------------------------------
// 11. SeekToFrame clamps to total frames
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::SeekToFrame_clampsToTotal", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 0;
	fr.totalFrames = 100;

	// Seek way past the end.
	fr.ctrl.SeekToFrame(500);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::SeekingForward);
	CHECK(fr.ctrl.GetSeekTarget() == 100); // clamped
}

// ---------------------------------------------------------------------------
// 12. SeekToFrame to end transitions to Finished via TickSeek
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::SeekToFrame_end_transitionsToFinished", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 0;
	fr.totalFrames = 100;

	fr.ctrl.SeekToFrame(100);
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::SeekingForward);

	// Advance to frame 100.
	fr.currentFrame = 100;
	CHECK(fr.ctrl.TickSeek() == true);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Finished);
}

// ---------------------------------------------------------------------------
// 13. Speed multiplier round-trip (M-1)
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::SetSpeed_roundTrip", "[replay]")
{
	C4ReplayController ctrl;

	// Default speed is 1.0x.
	CHECK(ctrl.GetSpeed() == 1.0f);

	// Mid-range value passes through unchanged.
	ctrl.SetSpeed(2.5f);
	CHECK(ctrl.GetSpeed() == 2.5f);

	// Boundary values.
	ctrl.SetSpeed(0.25f);
	CHECK(ctrl.GetSpeed() == 0.25f);
	ctrl.SetSpeed(8.0f);
	CHECK(ctrl.GetSpeed() == 8.0f);

	// Out-of-range values are clamped, not rejected.
	ctrl.SetSpeed(0.0f);
	CHECK(ctrl.GetSpeed() == 0.25f);
	ctrl.SetSpeed(100.0f);
	CHECK(ctrl.GetSpeed() == 8.0f);

	// Negative values clamp to the low end.
	ctrl.SetSpeed(-5.0f);
	CHECK(ctrl.GetSpeed() == 0.25f);
}

// ---------------------------------------------------------------------------
// 14. Forward seek leaves no Seeking state after TickSeek (M-3)
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::ForwardSeek_notStuckInSeeking", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 10;

	// Initiate a forward seek.
	fr.ctrl.SeekToFrame(50);
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::SeekingForward);
	REQUIRE(fr.ctrl.GetSeekTarget() == 50);

	// Simulate the engine's tight-loop advancing to the target, polling
	// TickSeek each frame as C4Game::Execute() now does.
	while (fr.currentFrame < 50)
	{
		++fr.currentFrame;
		if (fr.ctrl.TickSeek())
			break;
	}

	// The controller must have transitioned OUT of SeekingForward.
	CHECK(fr.ctrl.GetState() != C4ReplayController::State::SeekingForward);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);
}

// ---------------------------------------------------------------------------
// 15. Backward seek leaves no Seeking state after TickSeek (M-3)
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::BackwardSeek_notStuckInSeeking", "[replay]")
{
	FakeReplay fr;
	fr.currentFrame = 80;

	// SeekToFrame triggers the soft-restart callback, which in the real
	// engine fast-forwards to the target. The fake callback records the
	// target and resets the frame to 0 (simulating soft-restart).
	fr.ctrl.SeekToFrame(20);
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::SeekingBackward);
	REQUIRE(fr.softRestartCalled == true);
	REQUIRE(fr.currentFrame == 0);

	// Simulate the fast-forward landing at the target frame.
	fr.currentFrame = 20;

	// TickSeek is polled by the engine (and explicitly by
	// SoftRestartForReplaySeek after FastForwardToFrame) to transition
	// out of the SeekingBackward state.
	CHECK(fr.ctrl.TickSeek() == true);
	CHECK(fr.ctrl.GetState() != C4ReplayController::State::SeekingBackward);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Paused);
}

// ---------------------------------------------------------------------------
// 16. Detach resets the controller to Idle (covers M-2's Detach call)
// ---------------------------------------------------------------------------

TEST_CASE("C4ReplayController::Detach_resetsToIdle", "[replay]")
{
	FakeReplay fr;
	REQUIRE(fr.ctrl.GetState() == C4ReplayController::State::Playing);
	REQUIRE(fr.ctrl.GetTotalFrames() == 100);

	fr.ctrl.Detach();

	// After Detach, the controller is safely idle — no dangling playback
	// pointer, no callbacks, zero total frames. This is the state the
	// engine relies on after a corrupt-replay soft-restart failure (M-2).
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Idle);
	CHECK(fr.ctrl.GetTotalFrames() == 0);
	CHECK(fr.ctrl.GetCurrentFrame() == 0);

	// Operations on a detached controller are safe no-ops.
	fr.ctrl.SeekToFrame(50);
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Idle);
	fr.ctrl.StepForward();
	CHECK(fr.ctrl.GetState() == C4ReplayController::State::Idle);
}
