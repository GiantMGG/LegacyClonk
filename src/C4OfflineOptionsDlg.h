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

// Offline pre-game options dialog (spec pregame-options-parity-2):
// two-pane pre-game screen — briefing (+ objectives/rules pickers) on the
// left, the game options list on the right, Start/Abort at the bottom.
// Shown for fullscreen, non-console, non-replay OFFLINE starts, after
// InitGameFirstPart (definitions loaded — see the call site in C4Game.cpp).

#pragma once

#include "C4Gui.h"
#include "C4GuiDialogs.h"

#ifndef USE_CONSOLE

#include "C4GameOptions.h"

class C4OfflineOptionsDlg : public C4GUI::FullscreenDialog
{
public:
	C4OfflineOptionsDlg();

	// create, run modal message loop, destroy; false iff aborted
	static bool Show();

private:
	void OnBtnStart(C4GUI::Control *btn);
	void OnBtnAbort(C4GUI::Control *btn);

	// left pane top: scenario title + RTF description (ScenDesc pattern)
	void CreateBriefing(const C4Rect &rcBriefing);
	void FillBriefing();

	// left pane bottom: objectives/rules checkbox rows (spec §2.3)
	void CreatePickers(const C4Rect &rcPickers);
	void AddPickerSectionHeader(const char *szSectionLabel);

	virtual class C4GUI::Control *GetDefaultControl() override { return pBtnStart; }

	C4GUI::TextWindow *pBriefing;
	C4GUI::ListBox *pPickerList{nullptr};
	C4GameOptionsList *pOptionsList;
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnStart;
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnAbort;
};

#endif
