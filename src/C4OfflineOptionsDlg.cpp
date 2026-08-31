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

// Offline pre-game options dialog (spec pregame-options-parity)

#include "C4OfflineOptionsDlg.h"

#ifndef USE_CONSOLE

#include <C4Application.h>
#include <C4Game.h>
#include <C4GameLobby.h>
#include <C4Log.h>

C4OfflineOptionsDlg::C4OfflineOptionsDlg()
	: C4GUI::FullscreenDialog(LoadResStr(C4ResStrTableKey::IDS_DLG_OPTIONS), Game.Parameters.ScenarioTitle.getData()),
	pOptionsList(nullptr), pBtnStart(nullptr), pBtnAbort(nullptr)
{
	// layout
	C4GUI::ComponentAligner caMain(GetClientRect(), 10, 10, true);
	// options list (pre-game mode, same sheet as the network lobby)
	pOptionsList = new C4GameOptionsList(caMain.GetAll(), true, false);
	AddElement(pOptionsList);
	// lower button area
	C4GUI::ComponentAligner caBottom(caMain.GetFromBottom(C4GUI_ButtonHgt + 8), 10, 4);
	pBtnStart = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_DLG_GAMEGO), caBottom.GetFromLeft(110), &C4OfflineOptionsDlg::OnBtnStart);
	pBtnAbort = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_DLG_ABORT), caBottom.GetFromLeft(110), &C4OfflineOptionsDlg::OnBtnAbort);
	AddElement(pBtnStart);
	AddElement(pBtnAbort);
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
