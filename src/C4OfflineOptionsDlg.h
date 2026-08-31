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

// Offline pre-game options dialog (spec pregame-options-parity):
// shown for fullscreen, non-console, non-replay offline starts.

#pragma once

#include "C4Gui.h"

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

	virtual class C4GUI::Control *GetDefaultControl() override { return pBtnStart; }

	C4GameOptionsList *pOptionsList;
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnStart;
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnAbort;
};

#endif
