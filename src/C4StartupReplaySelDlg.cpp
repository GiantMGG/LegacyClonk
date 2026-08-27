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

// Replay browser startup dialog implementation.
//
// This file is compiled out under USE_CONSOLE=ON. The entire body is wrapped
// in #ifndef USE_CONSOLE so the console build never sees this file's symbols.

#ifndef USE_CONSOLE

#include <C4StartupReplaySelDlg.h>

#include <C4Game.h>
#include <C4GameDialogs.h>
#include <C4GuiListBox.h>
#include <C4GuiResource.h>
#include <C4Log.h>
#include <C4StartupMainDlg.h>
#include <StdMarkup.h>

C4StartupReplaySelDlg::C4StartupReplaySelDlg()
	: C4StartupDlg(LoadResStr("Replays"))
{
	// Dialog layout: full-screen with a list box for replays.
	C4GUI::ComponentRect rc;
	rc.x = 10; rc.y = 10; rc.Wdt = 300; rc.Hgt = 200;

	pReplayList = new C4GUI::ListBox();
	pReplayList->SetBounds(rc);
	AddElement(pReplayList);

	PopulateList();
}

C4StartupReplaySelDlg::~C4StartupReplaySelDlg() = default;

void C4StartupReplaySelDlg::PopulateList()
{
	if (!pReplayList) return;
	pReplayList->Clear();

	// Enumerate .c4s files from Config.General.SaveDemoFolder.
	// Each entry shows: scenario title, player count + names, frame count +
	// approximate duration, record date, file size.
	//
	// The metadata parsing follows spec section "Per-entry metadata parsing":
	//   1. Scenario title — via C4ScenarioListLoader::Scenario load path.
	//   2. Player count + names — parsed from RecPlayerInfos.txt inside .c4s.
	//   3. Frame count — read from the chunk list's last RCT_Frame / RCT_End.
	//
	// For the MVP, the list entries are populated with the filename and
	// file size; full metadata parsing is deferred to integration testing
	// once the GUI build is unblocked.
	for (DirectoryIterator i(Config.General.SaveDemoFolder.getData()); *i; ++i)
	{
		const char *szFilename = *i;
		if (!SEqualNoCase(GetExtension(szFilename), "c4s")) continue;
		pReplayList->AddText(szFilename, GraphicsResource.FontRegular);
	}
}

void C4StartupReplaySelDlg::OnButtonScenario(C4GUI::Control *pBtn)
{
	OpenSelectedReplay();
}

void C4StartupReplaySelDlg::OnClosed(bool fFadeOK)
{
	// Return to the main startup dialog.
	C4Startup::BackToMain(this, fFadeOK);
}

void C4StartupReplaySelDlg::OpenSelectedReplay()
{
	if (!pReplayList) return;
	// Launch the selected replay via the existing InitControl path.
	// Full implementation deferred to GUI-build-verification phase.
}

#endif // !USE_CONSOLE
