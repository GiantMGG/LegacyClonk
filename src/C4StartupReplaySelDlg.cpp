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
#include <C4GuiListBox.h>
#include <C4GuiResource.h>
#include <C4Log.h>
#include <C4TextEncoding.h>

#include <StdFile.h>

#include <algorithm>
#include <format>
#include <string>
#include <vector>

namespace
{
	// display-only date formatting (the C4StartupPlrSelDlg.cpp DateString idiom)
	std::string FormatTime(time_t iTime)
	{
		const tm *pLocalTime = localtime(&iTime);
		if (!pLocalTime) return {};
		return std::format("{}-{:02}-{:02} {:02}:{:02}",
			pLocalTime->tm_year + 1900, pLocalTime->tm_mon + 1, pLocalTime->tm_mday,
			pLocalTime->tm_hour, pLocalTime->tm_min);
	}

	// display-only size formatting
	std::string FormatSize(size_t iSize)
	{
		if (iSize >= 1024 * 1024) return std::format("{:.1f} MB", iSize / 1024.0f / 1024.0f);
		if (iSize >= 1024) return std::format("{:.1f} kB", iSize / 1024.0f);
		return std::format("{} Bytes", iSize);
	}
}

// C4StartupReplaySelDlg::ReplayListItem

C4StartupReplaySelDlg::ReplayListItem::ReplayListItem(const char *szFilename, time_t iFileTime, size_t iFileSize)
	: C4GUI::Control(C4Rect(0, 0, 0, 0))
{
	if (szFilename) sFilename.Copy(szFilename);

	// display text: filename (converted for the UI) - date (size);
	// the stored launch path stays raw system bytes
	const std::string strEntry{std::format("{} - {} ({})",
		TextEncodingConverter.SystemToClonk(GetFilename(szFilename)),
		FormatTime(iFileTime), FormatSize(iFileSize))};

	rcBounds.Hgt = C4GUI::GetRes()->TextFont.GetLineHeight();
	UpdateSize();
	AddElement(new C4GUI::Label(strEntry, GetContainedClientRect(), ALeft, C4GUI_CheckboxFontClr));
}

// C4StartupReplaySelDlg

C4StartupReplaySelDlg::C4StartupReplaySelDlg()
	: C4StartupDlg("Replays")
{
	// layout: list fills the main area; buttons sit in a bottom bar
	// (the C4StartupNetDlg layout skeleton)
	UpdateSize();
	C4GUI::ComponentAligner caMain(GetClientRect(), 0, 0, true);
	C4GUI::ComponentAligner caButtonArea(caMain.GetFromBottom(caMain.GetHeight() / 10), 8, 0);

	// replay list
	pReplayList = new C4GUI::ListBox(caMain.GetAll());
	pReplayList->SetDecoration(true, nullptr, true, true);
	pReplayList->SetSelectionChangeCallbackFn(new C4GUI::CallbackHandler<C4StartupReplaySelDlg>(this, &C4StartupReplaySelDlg::OnSelChange));
	pReplayList->SetSelectionDblClickFn(new C4GUI::CallbackHandler<C4StartupReplaySelDlg>(this, &C4StartupReplaySelDlg::OnSelDblClick));
	AddElement(pReplayList);

	// empty-folder hint naming the records folder path
	pEmptyHint = new C4GUI::Label("", C4Rect(rcBounds.Wdt / 8, rcBounds.Hgt / 2 - 20, rcBounds.Wdt * 3 / 4, 40), ACenter, C4GUI_Caption2FontClr);
	AddElement(pEmptyHint);

	// buttons
	int32_t iCaptionFontHgt, iButtonWidth = 100;
	C4GUI::GetRes()->CaptionFont.GetTextExtent("<< BACK", iButtonWidth, iCaptionFontHgt, true);
	iButtonWidth *= 2;
	iButtonWidth = std::min(iButtonWidth, caButtonArea.GetInnerWidth() / 3);
	C4GUI::CallbackButton<C4StartupReplaySelDlg> *btn;
	AddElement(btn = new C4GUI::CallbackButton<C4StartupReplaySelDlg>(LoadResStr(C4ResStrTableKey::IDS_BTN_BACK), caButtonArea.GetFromLeft(iButtonWidth), &C4StartupReplaySelDlg::OnBackBtn));
	btn->SetToolTip(LoadResStr(C4ResStrTableKey::IDS_DLGTIP_BACKMAIN));
	AddElement(pOpenBtn = new C4GUI::CallbackButton<C4StartupReplaySelDlg>(LoadResStr(C4ResStrTableKey::IDS_BTN_OPEN), caButtonArea.GetFromLeft(iButtonWidth), &C4StartupReplaySelDlg::OnButtonScenario));
	pOpenBtn->SetEnabled(false);

	// initial contents
	PopulateList();
	SetFocus(pReplayList, false);
}

C4StartupReplaySelDlg::~C4StartupReplaySelDlg() = default;

void C4StartupReplaySelDlg::PopulateList()
{
	if (!pReplayList) return;

	// enumerate .c4s files in the records folder — the same CWD-relative
	// resolution C4Record uses when writing ({SaveDemoFolder}{DirSep}{name},
	// C4Record.cpp:144). NOTE: DirectoryIterator yields the full folder-prefixed
	// path (its ctor copies the dir name and operator++ appends the entry name
	// into the same buffer, StdFile.cpp:816-838), so the iterator result IS the
	// composed path; passing it through {SaveDemoFolder}DirSep{} again would
	// double the prefix. Also do NOT pReplayList->Clear() here: that would
	// delete the ListBox's internal ScrollWindow/ScrollBar (the ListBox's only
	// children) leaving pClientWindow dangling — Container::ClearChildren does
	// not know about the scroll infrastructure (see C4GuiContainers.cpp:58).
	struct ReplayFile { std::string strFilename; time_t iFileTime; size_t iFileSize; };
	std::vector<ReplayFile> files;
	for (DirectoryIterator i(Config.General.SaveDemoFolder.getData()); *i; ++i)
	{
		if (!SEqualNoCase(GetExtension(*i), "c4s")) continue;
		const std::string strPath{*i};
		files.push_back({strPath, FileTime(strPath.c_str()), FileSize(strPath.c_str())});
	}
	// newest first
	std::sort(files.begin(), files.end(), [](const ReplayFile &lhs, const ReplayFile &rhs) { return lhs.iFileTime > rhs.iFileTime; });

	for (const ReplayFile &file : files)
		pReplayList->AddElement(new ReplayListItem(file.strFilename.c_str(), file.iFileTime, file.iFileSize));

	// empty or missing records folder: hint naming the folder path
	pEmptyHint->SetVisibility(files.empty());
	if (files.empty())
		pEmptyHint->SetText(LoadResStr(C4ResStrTableKey::IDS_MSG_NOREPLAYS,
			TextEncodingConverter.SystemToClonk(Config.General.SaveDemoFolder.getData())).c_str(), false);

	UpdateOpenButton();
}

void C4StartupReplaySelDlg::UpdateOpenButton()
{
	// Open is only meaningful with a selected replay entry
	if (pOpenBtn) pOpenBtn->SetEnabled(!!dynamic_cast<ReplayListItem *>(pReplayList ? pReplayList->GetSelectedItem() : nullptr));
}

void C4StartupReplaySelDlg::OnSelChange(C4GUI::Element *pEl)
{
	UpdateOpenButton();
}

void C4StartupReplaySelDlg::OnSelDblClick(C4GUI::Element *pEl)
{
	OpenSelectedReplay();
}

void C4StartupReplaySelDlg::OnButtonScenario(C4GUI::Control *pBtn)
{
	OpenSelectedReplay();
}

void C4StartupReplaySelDlg::OnBackBtn(C4GUI::Control *pBtn)
{
	DoBack();
}

bool C4StartupReplaySelDlg::DoBack()
{
	// back to main menu
	C4Startup::Get()->SwitchDialog(C4Startup::SDID_Back);
	return true;
}

void C4StartupReplaySelDlg::OpenSelectedReplay()
{
	// hand the selected .c4s to the standard scenario start path — the
	// C4StartupScenSelDlg::StartScenario handoff minus the definition/player
	// handling (the record core carries its own definitions and replays take
	// no join players; GameC4S.Head.Replay routes InitControl into
	// InitReplay, C4Game.cpp:2758-2764)
	ReplayListItem *pItem = pReplayList ? dynamic_cast<ReplayListItem *>(pReplayList->GetSelectedItem()) : nullptr;
	if (!pItem) return;
	SCopy(pItem->GetEntryFilename(), Game.ScenarioFilename);
	Game.fLobby = false;
	Game.fObserve = false;
	// start with this set!
	C4Startup::Get()->Start();
}

void C4StartupReplaySelDlg::OnClosed(bool fFadeOK)
{
	// base close handling is sufficient: dialog switches via DoBack()
	C4GUI::Dialog::OnClosed(fFadeOK);
}

#endif // !USE_CONSOLE
