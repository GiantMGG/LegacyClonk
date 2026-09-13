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

// In-game replay scrub viewer overlay.
//
// A non-modal HUD (~64px tall) anchored to the bottom of the screen. Does
// NOT pause the game on open — it is a HUD, not a modal dialog. Exposes:
//   - Horizontal timeline bar with draggable playhead.
//   - Play / Pause toggle (also Space).
//   - Step-frame buttons (also , / .).
//   - Speed presets (0.25x, 0.5x, 1x, 2x, 4x, 8x).
//   - Close button (also Esc).
//
// Reads/writes state via Game.Control.ReplayController (C4ReplayController).
//
// Shown automatically when a replay attaches (EnsureShown, called from
// C4GameControl::InitReplay) and toggled with the Ctrl+R "ReplayViewerToggle"
// key. Singleton lifetime follows the C4Network2ClientListDlg pattern
// (ShowRemoveDlg self-delete; pInstance cleared in the destructor).
//
// This is a GUI-only file. Under USE_CONSOLE=ON the entire .cpp body is
// compiled out via #ifndef USE_CONSOLE.

#pragma once

#include "C4Gui.h"
#include "C4GuiDialogs.h"
#include "C4Replay.h"

class C4ReplayViewerDlg : public C4GUI::Dialog
{
public:
	C4ReplayViewerDlg();
	~C4ReplayViewerDlg() override;

	// overlay singleton control (the C4Network2ClientListDlg::Toggle pattern)
	static bool Toggle();      // toggle overlay visibility; no-op unless a replay is running
	static void EnsureShown(); // show the overlay if it is not up yet (replay start)

	// C4GUI callbacks (DlgCallback<...>::Func signature: Control* parameter)
	void OnPlayPause(C4GUI::Control *pButton);
	void OnStepForward(C4GUI::Control *pButton);
	void OnStepBackward(C4GUI::Control *pButton);
	void OnSpeedPreset(float fSpeed);
	void OnTimelineDrag(uint32_t iTargetFrame);
	void OnClose(C4GUI::Control *pButton);

	void Draw(C4FacetEx &cgo) override;

	// dock at the bottom of the screen instead of letting Screen::ShowDialog
	// re-center the overlay (DoPlacement returning true keeps our placement)
	bool DoPlacement(C4GUI::Screen *pOnScreen, const C4Rect &rPreferredDlgRect) override
	{
		SetPos(0, C4GUI::GetScreenHgt() - kOverlayHeight);
		return true;
	}

private:
	C4ReplayController &GetController() const;

	// Timeline bar geometry
	static constexpr int32_t kOverlayHeight = 64;
	static constexpr int32_t kTimelineBarY  = 32;
	static constexpr int32_t kTimelineBarH  = 8;

	void DrawTimelineBar(C4FacetEx &cgo);

	static C4ReplayViewerDlg *pInstance; // current overlay instance, if shown
};
