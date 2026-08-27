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

// Replay controller: thin state-machine orchestrator for replay pause /
// speed / seek. Held as a member on C4GameControl. The GUI scrub viewer
// and replay browser talk to this controller; the controller delegates
// frame advancement to C4Playback and soft-restart to C4GameControl via
// callbacks.

#pragma once

#include "C4Record.h" // for C4Playback

#include <cstdint>
#include <functional>

class C4ReplayController
{
public:
	enum class State : uint8_t
	{
		Idle,            // no replay loaded
		Playing,         // normal forward playback
		Paused,          // frozen, world intact
		SeekingBackward, // soft-restart + fast-forward in progress
		SeekingForward,  // tight-loop fast-forward in progress
		Finished,        // RCT_End reached
	};

	C4ReplayController() = default;
	~C4ReplayController() = default;

	// Called by C4GameControl::InitReplay after a successful Open().
	//   totalFrames:    pPlayback->GetTotalFrames() — cached for queries.
	//   frameProvider:  returns current Game.FrameCounter.
	//   softRestart:    calls C4GameControl::SoftRestartForReplaySeek(target).
	void Attach(C4Playback *pPlayback,
	            uint32_t totalFrames,
	            std::function<uint32_t()> frameProvider,
	            std::function<void(uint32_t)> softRestart);
	void Detach();

	uint32_t GetTotalFrames() const { return TotalFrames_; }
	uint32_t GetCurrentFrame() const { return frameProvider_ ? frameProvider_() : 0; }

	void Pause();
	void Resume();
	bool IsPaused() const { return State_ == State::Paused; }

	void SetSpeed(float fMultiplier);
	float GetSpeed() const { return SpeedMultiplier_; }

	void StepForward();
	void StepBackward();

	void SeekToFrame(uint32_t iTargetFrame);

	// Polled by C4Game::Execute when State_ == Seeking*. Returns true
	// when the seek target is reached (transitions to Paused or Finished).
	bool TickSeek();

	// Abort an in-flight seek. Returns to Paused at the current frame.
	void CancelSeek();

	State GetState() const { return State_; }
	uint32_t GetSeekTarget() const { return SeekTarget_; }

	// Update the playback pointer after a soft-restart re-opens the .c4s.
	// Does NOT reset state — used by C4GameControl::SoftRestartForReplaySeek.
	void SetPlayback(C4Playback *pPlayback, uint32_t totalFrames);

private:
	C4Playback *pPlayback_ = nullptr;
	State       State_     = State::Idle;
	float       SpeedMultiplier_ = 1.0f;
	uint32_t    TotalFrames_ = 0;
	uint32_t    SeekTarget_ = 0;

	std::function<uint32_t()> frameProvider_;
	std::function<void(uint32_t)> softRestart_;
};
