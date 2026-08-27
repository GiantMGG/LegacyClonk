/*
 * LegacyClonk
 *
 * Copyright (c) RedWolf Design
 * Copyright (c) 2017-2026, The LegacyClonk Team and contributors
 *
 * Distributed under the terms of the ISC license; see accompanying file
 * "COPYING" for details.
 *
 * "Clonk" is a registered trademark of Matthes Bender, used with permission.
 * See accompanying file "TRADEMARK" for details.
 *
 * To redistribute this file separately, substitute the full license texts
 * for the above references.
 */

// First-run welcome dialog shown once when Config.General.FirstStart is true.
// Offers "Play tutorial" (auto-launches Tutorial01) or "Skip for now".

#pragma once

#include "C4Gui.h"
#include "C4GuiDialogs.h"

class C4StartupWelcomeDlg : public C4GUI::Dialog
{
public:
	C4StartupWelcomeDlg();
	~C4StartupWelcomeDlg() override = default;

protected:
	virtual const char *GetID() override { return "StartupWelcomeDlg"; }

private:
	void OnPlayTutorialBtn(C4GUI::Control *btn);
	void OnSkipBtn(C4GUI::Control *btn);
	void OnReadGuideBtn(C4GUI::Control *btn);
};
