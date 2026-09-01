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

// In-game replay scrub viewer overlay implementation.
//
// This file is compiled out under USE_CONSOLE=ON. The entire body is wrapped
// in #ifndef USE_CONSOLE so the console build never sees this file's symbols.

#ifndef USE_CONSOLE

#include <C4ReplayViewerDlg.h>

#include <C4Game.h>
#include <C4GameControl.h>
#include <C4GuiResource.h>
#include <C4Log.h>

C4ReplayViewerDlg::C4ReplayViewerDlg()
	: C4GUI::Dialog(C4GUI::GetScreenWdt(), C4ReplayViewerDlg::kOverlayHeight, "Replay Viewer", false)
{
	// The overlay is anchored to the bottom of the screen, full width.
	// Controls: play/pause, step, speed presets, close.
	//
	// For the MVP, the dialog is created with a minimal set of buttons.
	// Full timeline bar drawing and playhead dragging are implemented below
	// but may need adjustment once the GUI build is unblocked for testing.

	// Play/Pause button
	auto *pBtnPlay = new C4GUI::CallbackButton<C4ReplayViewerDlg>(
		"Play/Pause", C4Rect(0, 4, 24, 24), &C4ReplayViewerDlg::OnPlayPause, this);
	AddElement(pBtnPlay);

	// Step backward
	auto *pBtnStepBack = new C4GUI::CallbackButton<C4ReplayViewerDlg>(
		"Step Back", C4Rect(28, 4, 24, 24), &C4ReplayViewerDlg::OnStepBackward, this);
	AddElement(pBtnStepBack);

	// Step forward
	auto *pBtnStepFwd = new C4GUI::CallbackButton<C4ReplayViewerDlg>(
		"Step Fwd", C4Rect(56, 4, 24, 24), &C4ReplayViewerDlg::OnStepForward, this);
	AddElement(pBtnStepFwd);

	// Close button (right-aligned)
	auto *pBtnClose = new C4GUI::CallbackButton<C4ReplayViewerDlg>(
		"Close", C4Rect(0, 4, 24, 24), &C4ReplayViewerDlg::OnClose, this);
	AddElement(pBtnClose);
}

C4ReplayController &C4ReplayViewerDlg::GetController() const
{
	return Game.Control.ReplayController;
}

void C4ReplayViewerDlg::OnPlayPause(C4GUI::Control *pButton)
{
	auto &ctrl = GetController();
	if (ctrl.IsPaused())
		ctrl.Resume();
	else
		ctrl.Pause();
}

void C4ReplayViewerDlg::OnStepForward(C4GUI::Control *pButton)
{
	GetController().StepForward();
}

void C4ReplayViewerDlg::OnStepBackward(C4GUI::Control *pButton)
{
	GetController().StepBackward();
}

void C4ReplayViewerDlg::OnSpeedPreset(float fSpeed)
{
	GetController().SetSpeed(fSpeed);
}

void C4ReplayViewerDlg::OnTimelineDrag(uint32_t iTargetFrame)
{
	GetController().SeekToFrame(iTargetFrame);
}

void C4ReplayViewerDlg::OnClose(C4GUI::Control *pButton)
{
	Close(false);
}

void C4ReplayViewerDlg::Draw(C4FacetEx &cgo)
{
	C4GUI::Dialog::Draw(cgo);
	DrawTimelineBar(cgo);
}

void C4ReplayViewerDlg::DrawTimelineBar(C4Facet &cgo)
{
	auto &ctrl = GetController();
	const uint32_t total  = ctrl.GetTotalFrames();
	const uint32_t cur    = ctrl.GetCurrentFrame();
	const float    fFill  = total > 0 ? static_cast<float>(cur) / static_cast<float>(total) : 0.0f;

	// Draw the timeline bar background.
	const int32_t barX = 100;
	const int32_t barW = cgo.Wdt - 200;
	const int32_t barY = kTimelineBarY;
	const int32_t barH = kTimelineBarH;

	// Background
	Application.DDraw->DrawBoxDw(cgo.Surface, barX, barY, barX + barW, barY + barH, 0xff404040);
	// Filled portion
	const int32_t fillW = static_cast<int32_t>(barW * fFill);
	Application.DDraw->DrawBoxDw(cgo.Surface, barX, barY, barX + fillW, barY + barH, 0xff00ff00);

	// Tick marks at every 10% of total frames.
	for (int32_t pct = 10; pct < 100; pct += 10)
	{
		const int32_t tickX = barX + (barW * pct) / 100;
		Application.DDraw->DrawBoxDw(cgo.Surface, tickX, barY, tickX + 1, barY + barH, 0xff808080);
	}

	// Playhead
	const int32_t headX = barX + fillW;
	Application.DDraw->DrawBoxDw(cgo.Surface, headX - 1, barY - 2, headX + 2, barY + barH + 2, 0xffffffff);
}

#endif // !USE_CONSOLE
