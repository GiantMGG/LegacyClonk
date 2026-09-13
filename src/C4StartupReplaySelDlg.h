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
// Config.General.SaveDemoFolder with per-entry date and size. Open or
// double-click launches the replay via the C4Startup::Start() handoff;
// GameC4S.Head.Replay routes C4Game::InitControl() into
// C4GameControl::InitReplay() (the C4StartupScenSelDlg::StartScenario path).
//
// This is a GUI-only file. Under USE_CONSOLE=ON the entire .cpp body is
// compiled out via #ifndef USE_CONSOLE, so the console build is unaffected.

#pragma once

#include "C4Gui.h"
#include "C4Startup.h"

#include <ctime>

class C4StartupReplaySelDlg : public C4StartupDlg
{
public:
	// one list entry per .c4s; carries the full launch path so selection
	// never needs path reconstruction (the C4FileSelDlg::ListItem pattern)
	class ReplayListItem : public C4GUI::Control
	{
	private:
		StdStrBuf sFilename; // full path to the .c4s (launch path, raw system bytes)

	protected:
		virtual bool IsFocusOnClick() override { return false; } // keep focus on the list box

	public:
		ReplayListItem(const char *szFilename, time_t iFileTime, size_t iFileSize);

		const char *GetEntryFilename() const { return sFilename.getData(); }
	};

	C4StartupReplaySelDlg();
	~C4StartupReplaySelDlg() override;

	// C4GUI callbacks
	void OnButtonScenario(C4GUI::Control *pBtn); // Open button
	void OnBackBtn(C4GUI::Control *pBtn);
	void OnSelChange(C4GUI::Element *pEl);
	void OnSelDblClick(C4GUI::Element *pEl);
	void OnClosed(bool fFadeOK) override;
	virtual bool OnEscape() override { DoBack(); return true; }

	// C4StartupDlg
	bool DoStart() { return true; }

private:
	void PopulateList();
	void UpdateOpenButton();
	void OpenSelectedReplay();
	bool DoBack();

	C4GUI::ListBox *pReplayList{nullptr};
	C4GUI::CallbackButton<C4StartupReplaySelDlg> *pOpenBtn{nullptr};
	C4GUI::Label *pEmptyHint{nullptr};
};
