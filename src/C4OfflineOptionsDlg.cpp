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

#include <ctime>

namespace
{
	// Def icon: buffered def picture, drawn per frame — the GoalPicture
	// buffered-draw pattern (C4GameOverDlg.cpp:51-59).
	class DefIcon : public C4GUI::Window
	{
	public:
		DefIcon(const C4Rect &rcBounds, C4Def *pDef)
		{
			SetBounds(rcBounds);
			if (pDef)
			{
				Picture.Create(rcBounds.Wdt, rcBounds.Hgt);
				pDef->Draw(Picture, false, 0, nullptr);
			}
		}

	protected:
		virtual void DrawElement(C4FacetEx &cgo) override
		{
			C4Facet cgoDraw;
			cgoDraw.Set(cgo.Surface, cgo.X + rcBounds.x + cgo.TargetX, cgo.Y + rcBounds.y + cgo.TargetY, rcBounds.Wdt, rcBounds.Hgt);
			Picture.Draw(cgoDraw);
		}

	private:
		C4FacetExSurface Picture;
	};

	// Per-def picker checkbox (spec §2.3): toggling writes through to the
	// target C4IDList immediately — check on re-adds the ID with its initial
	// count clamped >= 1; check off removes the ID from the list again.
	class PickerCheckBox : public C4GUI::CheckBox
	{
	public:
		PickerCheckBox(const C4Rect &rcBounds, const std::string &szCaption, bool fChecked,
			C4IDList *pTargetList, C4ID idDef, int32_t iInitialCount)
			: C4GUI::CheckBox(rcBounds, szCaption, fChecked)
			, pTargetList(pTargetList), idDef(idDef), iInitialCount(iInitialCount)
		{
			SetOnChecked(new C4GUI::CallbackHandlerNoPar<PickerCheckBox>(this, &PickerCheckBox::OnToggle));
		}

	private:
		void OnToggle()
		{
			if (GetChecked())
			{
				// re-check: restore the initial count, clamped >= 1 (spec §4.7)
				pTargetList->SetIDCount(idDef, std::max(iInitialCount, 1), true);
			}
			else
			{
				// uncheck: remove the ID from the list again
				const int32_t iIndex = pTargetList->GetIndex(idDef);
				if (iIndex >= 0) pTargetList->DeleteItem(static_cast<std::size_t>(iIndex));
			}
		}

		C4IDList *pTargetList;
		C4ID idDef;
		int32_t iInitialCount;
	};

	// One picker row: def icon left, checkbox right (spec §1: icon + name).
	class DefPickerRow : public C4GUI::Window
	{
	public:
		DefPickerRow(const C4Rect &rcRow, C4Def *pDef, C4IDList *pTargetList)
		{
			SetBounds(rcRow);
			const C4ID idDef = pDef->id;
			// pre-checked iff the list contains the ID (spec §1)
			const bool fChecked = pTargetList->GetIndex(idDef) >= 0;
			const int32_t iInitialCount = pTargetList->GetIDCount(idDef);
			C4GUI::ComponentAligner caRow(GetContainedClientRect(), 2, 1);
			const int32_t iIconSize = rcRow.Hgt - 4;
			AddElement(new DefIcon(caRow.GetFromLeft(iIconSize, iIconSize), pDef));
			AddElement(new PickerCheckBox(caRow.GetAll(), pDef->GetName(), fChecked, pTargetList, idDef, iInitialCount));
		}
	};
}

// C4OfflineOptionsDlg::SeedEdit — nested so it can reach the dialog's
// private OnSeedChanged (the ScaleEdit precedent).

class C4OfflineOptionsDlg::SeedEdit : public C4GUI::SpinBox<int32_t>
{
public:
	SeedEdit(const C4Rect &rcBounds, C4OfflineOptionsDlg *pDlg);

protected:
	virtual void OnTextChange() override;

private:
	C4OfflineOptionsDlg *pDlg;
};

C4OfflineOptionsDlg::SeedEdit::SeedEdit(const C4Rect &rcBounds, C4OfflineOptionsDlg *pDlg)
	: C4GUI::SpinBox<int32_t>{rcBounds, true}
	, pDlg(pDlg)
{
}

void C4OfflineOptionsDlg::SeedEdit::OnTextChange()
{
	C4GUI::SpinBox<int32_t>::OnTextChange();
	pDlg->OnSeedChanged();
}

C4OfflineOptionsDlg::C4OfflineOptionsDlg()
	: C4GUI::FullscreenDialog(LoadResStr(C4ResStrTableKey::IDS_DLG_OPTIONS), Game.Parameters.ScenarioTitle.getData()),
	pBriefing(nullptr), pOptionsList(nullptr), pBtnStart(nullptr), pBtnAbort(nullptr)
{
	// layout (spec §2.3): bottom button strip carved first, then a left
	// briefing/picker pane (~55%) and a right options pane (~45%)
	C4GUI::ComponentAligner caMain(GetClientRect(), 10, 10, true);
	// bottom button area
	C4GUI::ComponentAligner caBottom(caMain.GetFromBottom(C4GUI_ButtonHgt + 8), 10, 4);
	// left pane: briefing on top (~45% of the pane), pickers in the middle,
	// landscape panel carved from the bottom (spec landscape-generator-research §2.2)
	const int32_t iLeftWdt = caMain.GetWidth() * 55 / 100;
	C4GUI::ComponentAligner caLeft(caMain.GetFromLeft(iLeftWdt), 6, 4);
	CreateBriefing(caLeft.GetFromTop(caLeft.GetHeight() * 45 / 100));
	const bool fLandscapePanel = LandscapePanelVisible();
	const C4Rect rcLandscape = fLandscapePanel ? caLeft.GetFromBottom(128) : C4Rect{};
	CreatePickers(caLeft.GetAll());
	if (fLandscapePanel) CreateLandscapePanel(rcLandscape);
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

void C4OfflineOptionsDlg::CreatePickers(const C4Rect &rcPickers)
{
	// Savegame resume (spec §1 + §4.3): InitRules/InitGoals are gated on
	// LandscapeLoaded (C4Game.cpp:2358) and don't run for savegame resumes,
	// so picker writes would be inert — the pickers are skipped and the
	// briefing is shown read-only.
	if (Game.GameC4S.Head.SaveGame) return;

	pPickerList = new C4GUI::ListBox(rcPickers);
	AddElement(pPickerList);
	const int32_t iListWdt = pPickerList->GetItemWidth();

	// Objectives — one checkbox row per loaded C4D_Goal def (spec §2.3;
	// the enum constraint: ONLY C4D_Goal/C4D_Rule defs are enumerated)
	AddPickerSectionHeader("Objectives");
	for (std::size_t i = 0; C4Def *pDef = Game.Defs.GetDef(i, C4D_Goal); ++i)
	{
		pPickerList->AddElement(new DefPickerRow(C4Rect(0, 0, iListWdt, 36), pDef, &Game.Parameters.Goals));
	}

	// Rules — one checkbox row per loaded C4D_Rule def
	AddPickerSectionHeader("Rules");
	for (std::size_t i = 0; C4Def *pDef = Game.Defs.GetDef(i, C4D_Rule); ++i)
	{
		pPickerList->AddElement(new DefPickerRow(C4Rect(0, 0, iListWdt, 36), pDef, &Game.Parameters.Rules));
	}
}

void C4OfflineOptionsDlg::AddPickerSectionHeader(const char *szSectionLabel)
{
	pPickerList->AddElement(new C4GUI::Label(szSectionLabel,
		C4Rect(0, 0, pPickerList->GetItemWidth(), 20), ALeft,
		C4GUI_CaptionFontClr, &C4GUI::GetRes()->CaptionFont));
}

bool C4OfflineOptionsDlg::LandscapePanelVisible() const
{
	// Panel self-hides (spec §2.2 + §4.2/§4.3): savegame resumes (the
	// landscape loads from the saved surface, C4Landscape.cpp:863-884),
	// exact landscapes, and static maps (Map.bmp/Landscape.bmp in the
	// scenario group — the same entries C4Landscape::Init's static-map
	// branch reads, C4Landscape.cpp:808-831).
	const C4SLandscape &rLS = Game.GameC4S.Landscape;
	if (Game.GameC4S.Head.SaveGame || rLS.ExactLandscape) return false;
	return !Game.ScenarioFile.AccessEntry(C4CFN_Map)
		&& !Game.ScenarioFile.AccessEntry(C4CFN_Landscape);
}

void C4OfflineOptionsDlg::CreateLandscapePanel(const C4Rect &rcPanel)
{
	pLandscapePanel = new C4GUI::Window();
	pLandscapePanel->SetBounds(rcPanel);
	AddElement(pLandscapePanel);

	// children are laid out in the panel's own coordinate space
	// (the DefPickerRow GetContainedClientRect discipline)
	C4GUI::ComponentAligner caPanel(C4Rect(0, 0, rcPanel.Wdt, rcPanel.Hgt), 6, 3, true);

	// header (hardcoded-English precedent: the picker section headers)
	pLandscapePanel->AddElement(new C4GUI::Label("Landscape",
		caPanel.GetFromTop(16), ALeft, C4GUI_CaptionFontClr, &C4GUI::GetRes()->CaptionFont));

	// seed row at the bottom of the panel: label + stepper + reroll button
	C4GUI::ComponentAligner caSeed(caPanel.GetFromBottom(C4GUI_ButtonHgt), 4, 2);
	pLandscapePanel->AddElement(new C4GUI::Label("Seed", caSeed.GetFromLeft(70), ALeft,
		C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont));
	pSeedEdit = new SeedEdit(caSeed.GetFromLeft(120), this);
	pSeedEdit->SetValue(Game.Parameters.RandomSeed, false);
	pLandscapePanel->AddElement(pSeedEdit);
	pLandscapePanel->AddElement(new C4GUI::CallbackButton<C4OfflineOptionsDlg>(
		"New", caSeed.GetFromLeft(70), &C4OfflineOptionsDlg::OnBtnNewSeed));
}

void C4OfflineOptionsDlg::OnSeedChanged()
{
	// immediate write-through: the displayed seed IS the round seed
	// (FixRandom consumes Parameters.RandomSeed, C4Game.cpp:2500)
	Game.Parameters.RandomSeed = pSeedEdit->GetValue();
}

void C4OfflineOptionsDlg::OnBtnNewSeed(C4GUI::Control *btn)
{
	// fresh seed: the engine's own default-seed source
	// (C4GameParameters.cpp:424) + a salt so double-clicks within one
	// second differ. SafeRandom is NOT usable here: pre-dialog rand() is
	// unseeded; FixedRandom's srand(time) runs only later (C4Game.cpp:2500).
	// SetValue fires OnTextChange -> OnSeedChanged: single write path.
	static int32_t iRerollSalt = 0;
	const int32_t iNewSeed = static_cast<int32_t>(time(nullptr)) + ++iRerollSalt;
	pSeedEdit->SetValue(iNewSeed, false);
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
