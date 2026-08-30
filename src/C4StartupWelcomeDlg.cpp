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

// First-run welcome dialog implementation.

#include "C4StartupWelcomeDlg.h"

#include "C4Game.h"
#include "C4GuiResource.h"
#include "C4OpenURL.h"
#include "C4Startup.h"
#include "C4Gui.h"

namespace
{
// Dialog dimensions in user units (matches the look of other startup dialogs).
constexpr int32_t kWelcomeDlgWdt = 400;
constexpr int32_t kWelcomeDlgHgt = 300;

constexpr int32_t kWelcomeBtnHgt = C4GUI_BigButtonHgt;
constexpr int32_t kWelcomeBtnWdt = 160;
constexpr int32_t kWelcomeBtnGap = 20;

// TODO(legacyclonk/LegacyClonk#000): Hardcoded English strings for now; follow-up
// wires these through LoadResStr + the engine string table for DE/other locales.
constexpr const char *kWelcomeTitle = "Welcome to LegacyClonk";
constexpr const char *kWelcomeBody =
	"Clonk is a tactical action game of digging, building and commanding.\n"
	"Would you like to play the voiced tutorial?";
constexpr const char *kWelcomePlayBtn = "Play tutorial";
constexpr const char *kWelcomeSkipBtn = "Skip for now";
constexpr const char *kWelcomeReadGuideBtn = "Read the 5-minute quickstart";
constexpr const char *kFirstGameGuideURL =
	"https://legacyclonk.github.io/LegacyClonk/players/first-game/";

// Hardcoded scenario path for the first tutorial.
constexpr const char *kTutorial01Path = "Tutorial.c4f\\Tutorial01.c4s";
} // namespace

C4StartupWelcomeDlg::C4StartupWelcomeDlg()
	: C4GUI::Dialog(kWelcomeDlgWdt, kWelcomeDlgHgt, kWelcomeTitle, false)
{
	// Body text label across the top of the dialog.
	C4GUI::ComponentAligner caBody(GetClientRect(), 10, 10, false);
	const C4Rect rcBody = caBody.GetFromTop(120);
	C4GUI::Label *pBody = new C4GUI::Label(kWelcomeBody, rcBody, ALeft, C4StartupFontClr, &C4GUI::GetRes()->TextFont, false, false);
	AddElement(pBody);

	// Two buttons centered at the bottom, plus a third "Read the 5-minute
	// quickstart" button stacked above them.
	const int32_t iTotalBtnWdt = 2 * kWelcomeBtnWdt + kWelcomeBtnGap;
	const int32_t iBtnY = GetClientRect().Hgt - kWelcomeBtnHgt - 20;

	C4GUI::CallbackButton<C4StartupWelcomeDlg> *pBtn;

	// Guide button: full dialog width, stacked above the play/skip pair.
	const int32_t iGuideBtnY = iBtnY - kWelcomeBtnHgt - 10;
	const C4Rect rcGuideBtn(
		GetClientRect().Wdt / 2 - kWelcomeBtnWdt / 2,
		iGuideBtnY,
		kWelcomeBtnWdt,
		kWelcomeBtnHgt);
	pBtn = new C4GUI::CallbackButton<C4StartupWelcomeDlg>(
		kWelcomeReadGuideBtn, rcGuideBtn,
		&C4StartupWelcomeDlg::OnReadGuideBtn);
	AddElement(pBtn);
	const C4Rect rcPlayBtn(GetClientRect().Wdt / 2 - iTotalBtnWdt / 2, iBtnY, kWelcomeBtnWdt, kWelcomeBtnHgt);
	pBtn = new C4GUI::CallbackButton<C4StartupWelcomeDlg>(kWelcomePlayBtn, rcPlayBtn, &C4StartupWelcomeDlg::OnPlayTutorialBtn);
	AddElement(pBtn);
	SetFocus(pBtn, false); // "Play tutorial" is the default focus

	const C4Rect rcSkipBtn(GetClientRect().Wdt / 2 + iTotalBtnWdt / 2 - kWelcomeBtnWdt, iBtnY, kWelcomeBtnWdt, kWelcomeBtnHgt);
	pBtn = new C4GUI::CallbackButton<C4StartupWelcomeDlg>(kWelcomeSkipBtn, rcSkipBtn, &C4StartupWelcomeDlg::OnSkipBtn);
	AddElement(pBtn);
}

void C4StartupWelcomeDlg::OnPlayTutorialBtn(C4GUI::Control *btn)
{
	// Launch Tutorial01 directly, mirroring C4StartupScenSelDlg::StartScenario.
	(void)btn;
	SCopy(kTutorial01Path, Game.ScenarioFilename);
	Game.fLobby = false;
	Game.fObserve = false;
	Game.DefinitionFilenames.clear();
	Game.DefinitionFilenames.push_back("Objects.c4d");
	C4Startup::Get()->Start();
	// Close(false) dismisses this modal dialog (and triggers fDelOnClose
	// cleanup since ShowModalDlg(..., true) was used). C4Startup::Start()
	// only flips fInStartup/fAborted; it does not touch the dialog stack.
	Close(false);
}

void C4StartupWelcomeDlg::OnSkipBtn(C4GUI::Control *btn)
{
	// Dismiss the dialog; main menu remains.
	(void)btn;
	Close(false);
}

void C4StartupWelcomeDlg::OnReadGuideBtn(C4GUI::Control *btn)
{
	// Open the published first-game guide in the player's default browser,
	// then dismiss the welcome dialog so the player lands on the main menu.
	// Mirrors the label-hyperlink precedent at C4GuiLabels.cpp:89.
	(void)btn;
	OpenURL(kFirstGameGuideURL);
	Close(false);
}
