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

// Replay controller implementation — see C4Replay.h for design notes.

#include "C4Replay.h"

#include <algorithm>

void C4ReplayController::Attach(C4Playback *pPlayback,
                                uint32_t totalFrames,
                                std::function<uint32_t()> frameProvider,
                                std::function<void(uint32_t)> softRestart)
{
	pPlayback_     = pPlayback;
	TotalFrames_   = totalFrames;
	frameProvider_ = std::move(frameProvider);
	softRestart_   = std::move(softRestart);
	State_         = State::Playing;
	SeekTarget_    = 0;
}

void C4ReplayController::Detach()
{
	pPlayback_   = nullptr;
	TotalFrames_ = 0;
	State_       = State::Idle;
	SeekTarget_  = 0;
	frameProvider_ = nullptr;
	softRestart_   = nullptr;
}

void C4ReplayController::Pause()
{
	if (State_ == State::Playing)
		State_ = State::Paused;
}

void C4ReplayController::Resume()
{
	if (State_ == State::Paused)
		State_ = State::Playing;
}

void C4ReplayController::SetSpeed(float fMultiplier)
{
	SpeedMultiplier_ = std::clamp(fMultiplier, 0.25f, 8.0f);
}

void C4ReplayController::StepForward()
{
	if (!pPlayback_) return;
	SeekToFrame(GetCurrentFrame() + 1);
}

void C4ReplayController::StepBackward()
{
	if (!pPlayback_) return;
	const uint32_t cur = GetCurrentFrame();
	if (cur > 0)
		SeekToFrame(cur - 1);
}

void C4ReplayController::SeekToFrame(uint32_t iTargetFrame)
{
	if (!pPlayback_) return;

	// Clamp to [0, TotalFrames_].
	if (iTargetFrame > TotalFrames_)
		iTargetFrame = TotalFrames_;

	const uint32_t iCurrent = GetCurrentFrame();
	if (iTargetFrame == iCurrent) return;

	if (iTargetFrame > iCurrent)
	{
		State_      = State::SeekingForward;
		SeekTarget_ = iTargetFrame;
		return;
	}

	// Backward: must soft-restart. Set state, then invoke the callback
	// which re-opens the .c4s, re-initializes game state, and fast-forwards.
	State_      = State::SeekingBackward;
	SeekTarget_ = iTargetFrame;
	if (softRestart_)
		softRestart_(iTargetFrame);
}

bool C4ReplayController::TickSeek()
{
	if (State_ != State::SeekingForward && State_ != State::SeekingBackward)
		return false;

	if (GetCurrentFrame() >= SeekTarget_)
	{
		// Reached the target. Transition to Paused (or Finished if at end).
		if (SeekTarget_ >= TotalFrames_)
			State_ = State::Finished;
		else
			State_ = State::Paused;
		return true;
	}
	return false;
}

void C4ReplayController::CancelSeek()
{
	if (State_ == State::SeekingForward || State_ == State::SeekingBackward)
		State_ = State::Paused;
}

void C4ReplayController::SetPlayback(C4Playback *pPlayback, uint32_t totalFrames)
{
	pPlayback_   = pPlayback;
	TotalFrames_ = totalFrames;
}
