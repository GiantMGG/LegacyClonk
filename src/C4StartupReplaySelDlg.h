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

// Replay browser startup dialog — lists .c4s replay files from
// Config.General.SaveDemoFolder with per-entry metadata (title, players,
// frame count, date, size). Double-click launches a replay via the existing
// C4Game::InitControl() -> C4GameControl::InitReplay() path.
//
// This is a GUI-only file. Under USE_CONSOLE=ON the entire .cpp body is
// compiled out via #ifndef USE_CONSOLE, so the console build is unaffected.

#pragma once

#include "C4Gui.h"
#include "C4Startup.h"
#include "C4Scenario.h"
#include "C4Folder.h"

#include <memory>

class C4StartupReplaySelDlg : public C4StartupDlg
{
public:
	C4StartupReplaySelDlg();
	~C4StartupReplaySelDlg() override;

	// C4GUI callbacks
	void OnButtonScenario(C4GUI::Control *pBtn);
	void OnClosed(bool fFadeOK) override;

	// C4StartupDlg
	bool DoStart() { return true; }

private:
	// The replay list — reuses the C4ScenarioListLoader infrastructure
	// scoped to Config.General.SaveDemoFolder.
	void PopulateList();
	void OpenSelectedReplay();

	C4GUI::ListBox *pReplayList{nullptr};
	C4GUI::CallbackButton<C4StartupReplaySelDlg> *pOpenBtn{nullptr};
};
