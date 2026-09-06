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
// two-pane rebuild — briefing + pickers left, options list right.

#include "C4OfflineOptionsDlg.h"

#ifndef USE_CONSOLE

#include <C4Application.h>
#include <C4ComponentHost.h>
#include <C4Components.h>
#include <C4Config.h>
#include <C4Game.h>
#include <C4GameLobby.h>
#include <C4GuiResource.h>
#include <C4Log.h>
#include <C4RTF.h>

C4OfflineOptionsDlg::C4OfflineOptionsDlg()
	: C4GUI::FullscreenDialog(LoadResStr(C4ResStrTableKey::IDS_DLG_OPTIONS), Game.Parameters.ScenarioTitle.getData()),
	pBriefing(nullptr), pOptionsList(nullptr), pBtnStart(nullptr), pBtnAbort(nullptr)
{
	// layout (spec §2.3): bottom button strip carved first, then a left
	// briefing/picker pane (~55%) and a right options pane (~45%)
	C4GUI::ComponentAligner caMain(GetClientRect(), 10, 10, true);
	// bottom button area
	C4GUI::ComponentAligner caBottom(caMain.GetFromBottom(C4GUI_ButtonHgt + 8), 10, 4);
	// left pane: briefing on top (~45% of the pane); pickers land below (task 6)
	const int32_t iLeftWdt = caMain.GetWidth() * 55 / 100;
	C4GUI::ComponentAligner caLeft(caMain.GetFromLeft(iLeftWdt), 6, 4);
	CreateBriefing(caLeft.GetFromTop(caLeft.GetHeight() * 45 / 100));
	// right pane: options list (pre-game mode, same sheet as the network lobby)
	pOptionsList = new C4GameOptionsList(caMain.GetAll(), true, false);
	AddElement(pOptionsList);
	// buttons (unchanged from cycle 84)
	pBtnStart = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_DLG_GAMEGO), caBottom.GetFromLeft(110), &C4OfflineOptionsDlg::OnBtnStart);
	pBtnAbort = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_DLG_ABORT), caBottom.GetFromLeft(110), &C4OfflineOptionsDlg::OnBtnAbort);
	AddElement(pBtnStart);
	AddElement(pBtnAbort);
}

void C4OfflineOptionsDlg::CreateBriefing(const C4Rect &rcBriefing)
{
	// briefing text window (ScenDesc pattern, C4GameLobby.cpp:63-72)
	pBriefing = new C4GUI::TextWindow(rcBriefing, 0, 0, 0, 100, 4096, "", true);
	pBriefing->SetDecoration(false, false, nullptr, true);
	AddElement(pBriefing);
	FillBriefing();
}

void C4OfflineOptionsDlg::FillBriefing()
{
	// scenario title + plain-text RTF description, loaded exactly like the
	// net lobby's ScenDesc (C4GameLobby.cpp:74-116): C4ComponentHost::LoadEx
	// on the open ScenarioFile group + C4RTFFile plain-text conversion.
	CStdFont &rTitleFont = C4GUI::GetRes()->CaptionFont;
	CStdFont &rTextFont = C4GUI::GetRes()->TextFont;
	pBriefing->ClearText(false);
	StdStrBuf sDesc;
	C4ComponentHost DefDesc;
	if (DefDesc.LoadEx("Desc", Game.ScenarioFile, C4CFN_ScenarioDesc, Config.General.LanguageEx))
	{
		C4RTFFile rtf;
		rtf.Load(StdBuf::MakeRef(DefDesc.GetData(), SLen(DefDesc.GetData())));
		sDesc.Take(rtf.GetPlainText());
	}
	DefDesc.Close();
	pBriefing->AddTextLine(Game.Parameters.ScenarioTitle.getData(), &rTitleFont, C4GUI_CaptionFontClr, false, true);
	if (!!sDesc)
		pBriefing->AddTextLine(sDesc.getData(), &rTextFont, C4GUI_MessageFontClr, false, true);
	pBriefing->UpdateHeight();
}

void C4OfflineOptionsDlg::OnBtnStart(C4GUI::Control *btn)
{
	// start the game
	Close(true);
}

void C4OfflineOptionsDlg::OnBtnAbort(C4GUI::Control *btn)
{
	// abort: same semantics as a network lobby abort
	C4GameLobby::UserAbort = true;
	Close(false);
}

bool C4OfflineOptionsDlg::Show()
{
	if (!Game.pGUI) return true;  // belt and braces: no GUI -> skip
	auto *pDlg = new C4OfflineOptionsDlg();
	if (!pDlg->FadeIn(Game.pGUI))
	{
		delete pDlg;
		return false;
	}
	// caller-owned message loop (mirrors C4Network2::DoLobby)
	while (Game.pGUI && pDlg->IsShown())
	{
		if (Application.HandleMessage() == HR_Failure)
		{
			delete pDlg;
			return false;
		}
	}
	const bool fStarted = !pDlg->IsAborted();
	if (pDlg->IsShown()) pDlg->Close(true);
	delete pDlg;
	if (Game.pGUI) Game.pGUI->CloseAllDialogs(false);
	return fStarted;
}

#endif
