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

// Offline pre-game options dialog (spec world-generator-ux-rework):
// two-stage fullscreen dialog — see the header comment.

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

#include "C4SliderDescriptors.h"

#include <ctime>
#include <format>

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

// C4OfflineOptionsDlg::SliderRow — one generated slider row per
// descriptor (the LandscapeParamEdit precedent): human label + horizontal
// ScrollBar + live numeric readout. The ScrollBar callback writes
// Set(p + Min, 0, Min, Max) through both C4S copies (dual write-through,
// spec §2), updates the readout, and marks the preview dirty (debounced
// to at most one re-render per frame). Scenario-pinned values
// (Max <= Min) render a readout-only row — no degenerate scrollbar.
class C4OfflineOptionsDlg::SliderRow : public C4GUI::Window
{
public:
	SliderRow(const C4Rect &rcRow, const C4SliderDescriptor &Descriptor, C4OfflineOptionsDlg *pDlg);

private:
	void OnSliderChange(int32_t iPosition);
	void UpdateReadout(int32_t iValue);

	C4OfflineOptionsDlg *pDlg;
	C4SVal C4SLandscape::*pField;
	const char *szUnit;
	C4GUI::Label *pReadout{nullptr};
	int32_t iMin{0}, iMax{0};
};

C4OfflineOptionsDlg::SliderRow::SliderRow(const C4Rect &rcRow, const C4SliderDescriptor &Descriptor, C4OfflineOptionsDlg *pDlg)
	: pDlg(pDlg), pField(Descriptor.pField), szUnit(Descriptor.szUnit)
{
	SetBounds(rcRow);
	const C4SVal &rVal = Game.GetActiveSections().front()->C4S.Landscape.*pField;
	iMin = rVal.Min;
	iMax = rVal.Max;

	C4GUI::ComponentAligner caRow(GetContainedClientRect(), 2, 1);
	AddElement(new C4GUI::Label(Descriptor.szLabel,
		caRow.GetFromLeft(rcRow.Wdt * 2 / 5), ALeft, C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont));
	pReadout = new C4GUI::Label("",
		caRow.GetFromRight(56), ARight, C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont);
	AddElement(pReadout);

	// scenario-pinned value (Max <= Min): readout only, no slider
	// (spec edge case 3 — avoids the ScrollBar-with-range-1 degeneracy)
	if (iMax > iMin)
	{
		auto *pCB = new C4GUI::ParCallbackHandler<SliderRow, int32_t>(this, &SliderRow::OnSliderChange);
		auto *pSlider = new C4GUI::ScrollBar(caRow.GetAll(), true, pCB, iMax - iMin + 1);
		AddElement(pSlider);
		// SetScrollPos does NOT fire the callback (direct iScrollPos assign)
		pSlider->SetScrollPos(rVal.Std - iMin);
	}
	UpdateReadout(rVal.Std);
}

void C4OfflineOptionsDlg::SliderRow::OnSliderChange(int32_t iPosition)
{
	// ScrollBar callback: position in [0, iCBMaxRange-1] = [0, iMax-iMin]
	const int32_t iValue = BoundBy(iPosition + iMin, iMin, iMax);

	// dual write-through (spec §2): the section copy the generator reads
	// (C4Landscape.cpp:562) + GameC4S (template consistency)
	C4SVal &rSectionVal = Game.GetActiveSections().front()->C4S.Landscape.*pField;
	rSectionVal.Set(iValue, 0, iMin, iMax);
	C4SVal &rTemplateVal = Game.GameC4S.Landscape.*pField;
	rTemplateVal.Set(iValue, 0, iMin, iMax);

	UpdateReadout(iValue);
	pDlg->MarkPreviewDirty();
}

void C4OfflineOptionsDlg::SliderRow::UpdateReadout(int32_t iValue)
{
	// plain integer + the unit suffix from the descriptor (spec §2)
	StdStrBuf sText;
	if (szUnit && szUnit[0])
		sText.Copy(std::format("{} {}", iValue, szUnit).c_str());
	else
		sText.Copy(std::format("{}", iValue).c_str());
	pReadout->SetText(sText.getData());
}

C4OfflineOptionsDlg::C4OfflineOptionsDlg()
	: C4GUI::FullscreenDialog(LoadResStr(C4ResStrTableKey::IDS_DLG_OPTIONS), Game.Parameters.ScenarioTitle.getData())
{
	const C4Rect rcClient = GetClientRect();

	// both stage windows cover the full client rect; page-swap via fVisible
	pLandingStage = new C4GUI::Window();
	pLandingStage->SetBounds(rcClient);
	AddElement(pLandingStage);
	pSettingsStage = new C4GUI::Window();
	pSettingsStage->SetBounds(rcClient);
	AddElement(pSettingsStage);

	CreateLandingStage(rcClient);
	CreateSettingsStage(rcClient);

	// land on the landing stage (spec §2: the dialog opens on landing)
	SetStage(Stage::Landing);
}

void C4OfflineOptionsDlg::CreateLandingStage(const C4Rect &rcStage)
{
	C4GUI::ComponentAligner caStage(rcStage, 10, 10, true);

	// scenario title, centered, caption font
	pLandingStage->AddElement(new C4GUI::Label(Game.Parameters.ScenarioTitle.getData(),
		caStage.GetFromTop(60), ACenter, C4GUI_CaptionFontClr, &C4GUI::GetRes()->CaptionFont));

	// the equal-size [World Settings][Quick Start] pair, centered
	C4GUI::ComponentAligner caPair(caStage.GetCentered(caStage.GetInnerWidth() * 3 / 4, C4GUI_ButtonHgt + 8), 10, 4);
	pBtnWorldSettings = new C4GUI::CallbackButton<C4OfflineOptionsDlg>("World Settings",
		caPair.GetFromLeft(caPair.GetInnerWidth() / 2), &C4OfflineOptionsDlg::OnBtnWorldSettings);
	pLandingStage->AddElement(pBtnWorldSettings);
	pBtnQuickStart = new C4GUI::CallbackButton<C4OfflineOptionsDlg>("Quick Start",
		caPair.GetAll(), &C4OfflineOptionsDlg::OnBtnStart);
	pLandingStage->AddElement(pBtnQuickStart);

	// small Abort affordance, bottom center
	C4GUI::ComponentAligner caAbort(caStage.GetFromBottom(C4GUI_ButtonHgt), 10, 4);
	pLandingStage->AddElement(new C4GUI::CallbackButton<C4OfflineOptionsDlg>(
		LoadResStr(C4ResStrTableKey::IDS_DLG_ABORT), caAbort.GetCentered(110, C4GUI_ButtonHgt),
		&C4OfflineOptionsDlg::OnBtnAbort));
}

void C4OfflineOptionsDlg::CreateSettingsStage(const C4Rect &rcStage)
{
	C4GUI::ComponentAligner caMain(rcStage, 10, 10, true);

	// bottom strip: [Back][Start][Abort]
	C4GUI::ComponentAligner caBottom(caMain.GetFromBottom(C4GUI_ButtonHgt + 8), 10, 4);
	pBtnBack = new C4GUI::CallbackButton<C4OfflineOptionsDlg>("Back",
		caBottom.GetFromLeft(110), &C4OfflineOptionsDlg::OnBtnBack);
	pSettingsStage->AddElement(pBtnBack);
	pBtnStart = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_DLG_GAMEGO),
		caBottom.GetFromLeft(110), &C4OfflineOptionsDlg::OnBtnStart);
	pSettingsStage->AddElement(pBtnStart);
	pBtnAbort = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_DLG_ABORT),
		caBottom.GetAll(), &C4OfflineOptionsDlg::OnBtnAbort);
	pSettingsStage->AddElement(pBtnAbort);

	// left pane (~55%): briefing top, pickers middle, options strip bottom
	const int32_t iLeftWdt = caMain.GetInnerWidth() * 55 / 100;
	C4GUI::ComponentAligner caLeft(caMain.GetFromLeft(iLeftWdt), 6, 4);
	CreateBriefing(caLeft.GetFromTop(caLeft.GetInnerHeight() * 40 / 100));
	if (LandscapePanelVisible())
	{
		// compact options strip at the bottom of the left pane
		pOptionsList = new C4GameOptionsList(caLeft.GetFromBottom(caLeft.GetInnerHeight() * 32 / 100), true, false);
		pSettingsStage->AddElement(pOptionsList);
	}
	CreatePickers(caLeft.GetAll());

	// right pane (~45%): the world block — or, for resumes/exact/static
	// maps, the full-height options list (the pre-rework resume layout)
	if (LandscapePanelVisible())
	{
		CreateLandscapePanel(caMain.GetAll());
	}
	else
	{
		pOptionsList = new C4GameOptionsList(caMain.GetAll(), true, false);
		pSettingsStage->AddElement(pOptionsList);
	}
}

void C4OfflineOptionsDlg::CreateBriefing(const C4Rect &rcBriefing)
{
	// briefing text window (ScenDesc pattern, C4GameLobby.cpp:63-72)
	pBriefing = new C4GUI::TextWindow(rcBriefing, 0, 0, 0, 100, 4096, "", true);
	pBriefing->SetDecoration(false, false, nullptr, true);
	pSettingsStage->AddElement(pBriefing);
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
	pSettingsStage->AddElement(pPickerList);
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
	pSettingsStage->AddElement(pLandscapePanel);

	// children are laid out in the panel's own coordinate space
	C4GUI::ComponentAligner caPanel(C4Rect(0, 0, rcPanel.Wdt, rcPanel.Hgt), 6, 3, true);

	// header (hardcoded-English precedent: the picker section headers)
	pLandscapePanel->AddElement(new C4GUI::Label("Landscape",
		caPanel.GetFromTop(16), ALeft, C4GUI_CaptionFontClr, &C4GUI::GetRes()->CaptionFont));

	// hero preview (spec §2: aspect-fit, ~40% of the pane height —
	// ~3-4x the old 64px strip; renders the exact 8-bit map the round
	// will get, on demand only)
	const int32_t iPreviewHgt = std::max<int32_t>(caPanel.GetInnerHeight() * 40 / 100, 96);
	pPreviewPicture = new C4GUI::Picture(caPanel.GetFromTop(iPreviewHgt), true);
	pLandscapePanel->AddElement(pPreviewPicture);

	// seed row directly beneath the preview
	C4GUI::ComponentAligner caSeed(caPanel.GetFromTop(C4GUI_ButtonHgt), 4, 2);
	pLandscapePanel->AddElement(new C4GUI::Label("Seed", caSeed.GetFromLeft(50), ALeft,
		C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont));
	pSeedEdit = new SeedEdit(caSeed.GetFromLeft(110), this);
	pSeedEdit->SetValue(Game.Parameters.RandomSeed, false);
	pLandscapePanel->AddElement(pSeedEdit);
	pLandscapePanel->AddElement(new C4GUI::CallbackButton<C4OfflineOptionsDlg>(
		"New", caSeed.GetFromLeft(60), &C4OfflineOptionsDlg::OnBtnNewSeed));

	// slider list: one generated row per descriptor (spec §2), inside a
	// ListBox so the rows scroll if the pane is short
	pSliderList = new C4GUI::ListBox(caPanel.GetAll());
	pLandscapePanel->AddElement(pSliderList);
	if (!Game.ScenarioFile.AccessEntry(C4CFN_DynLandscape))
	{
		const int32_t iListWdt = pSliderList->GetItemWidth();
		for (const auto &Descriptor : kSliderDescriptors)
			pSliderList->AddElement(new SliderRow(C4Rect(0, 0, iListWdt, 20), Descriptor, this));
	}

	// render the preview for the current seed once, on panel creation
	RenderLandscapePreview();
}

void C4OfflineOptionsDlg::BuildPreviewPalette(uint32_t dwPalette[256]) const
{
	// Preview palette (spec §2.3, cosmetic latitude): map pixel 0 = sky;
	// material pixels are texture-map index + MapIFT(128); liquid pixels
	// are the raw texture-map index (C4Map.cpp:92,133-141). Colors come
	// from the material's base color (C4MaterialCore::GetDWordColor).
	const C4Section &rSection = *Game.GetActiveSections().front();
	for (int32_t i = 0; i < 256; ++i) dwPalette[i] = 0xff7f7f7f; // fallback grey
	dwPalette[0] = 0xffbf5f1f; // sky blue (0xAABBGGRR)
	for (int32_t iTex = 1; iTex < C4M_MaxTexIndex; ++iTex)
	{
		const C4TexMapEntry *pEntry = rSection.TextureMap.GetEntry(iTex);
		if (!pEntry || pEntry->isNull()) continue;
		C4Material *pMaterial = pEntry->GetMaterial();
		if (!pMaterial) continue;
		const uint32_t dwClr = pMaterial->GetDWordColor(0);
		dwPalette[iTex] = dwClr;        // liquid pixel (raw tex index)
		dwPalette[iTex + 128] = dwClr;  // material pixel (tex index + MapIFT)
	}
}

void C4OfflineOptionsDlg::RenderLandscapePreview()
{
	// on-demand re-render only (spec §2.3): per-frame cost is one buffered
	// facet blit; the generation runs on a private seeded RNG inside
	// C4Landscape::CreatePreviewMap (C4Random::Default untouched).
	if (!pPreviewPicture) return;
	auto sfcMap = Game.GetActiveSections().front()->Landscape.CreatePreviewMap(Game.Parameters.RandomSeed);
	if (!sfcMap) return;

	uint32_t dwPalette[256];
	BuildPreviewPalette(dwPalette);

	auto &facet = pPreviewPicture->GetMFacet();
	if (!facet.Create(sfcMap->Wdt, sfcMap->Hgt)) return;
	C4Surface *pSfc = facet.Surface;
	if (!pSfc || !pSfc->Lock()) return;
	for (int32_t y = 0; y < sfcMap->Hgt; ++y)
		for (int32_t x = 0; x < sfcMap->Wdt; ++x)
			pSfc->SetPixDw(x, y, dwPalette[sfcMap->_GetPix(x, y)]);
	pSfc->Unlock();
}

void C4OfflineOptionsDlg::OnSeedChanged()
{
	// immediate write-through: the displayed seed IS the round seed
	// (FixRandom consumes Parameters.RandomSeed, C4Game.cpp:2500)
	Game.Parameters.RandomSeed = pSeedEdit->GetValue();
	MarkPreviewDirty();
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

void C4OfflineOptionsDlg::OnBtnWorldSettings(C4GUI::Control *btn)
{
	SetStage(Stage::Settings);
}

void C4OfflineOptionsDlg::OnBtnBack(C4GUI::Control *btn)
{
	SetStage(Stage::Landing);
}

void C4OfflineOptionsDlg::SetStage(Stage eToStage)
{
	eStage = eToStage;
	pLandingStage->fVisible = (eToStage == Stage::Landing);
	pSettingsStage->fVisible = (eToStage == Stage::Settings);
	SetFocus(GetDefaultControl(), false);
}

bool C4OfflineOptionsDlg::OnEnter()
{
	// per-stage Enter (spec §2): Quick Start on the landing stage,
	// Start on the settings stage — both close the dialog with OK
	Close(true);
	return true;
}

bool C4OfflineOptionsDlg::OnEscape()
{
	if (eStage == Stage::Settings)
	{
		// settings: ESC = Back to the landing stage (the cheap exit for
		// the player who wandered in by accident)
		SetStage(Stage::Landing);
		return true;
	}
	// landing: ESC = Abort
	C4GameLobby::UserAbort = true;
	Close(false);
	return true;
}

C4GUI::Control *C4OfflineOptionsDlg::GetDefaultControl()
{
	return eStage == Stage::Settings ? pBtnStart : pBtnQuickStart;
}

void C4OfflineOptionsDlg::Draw(C4FacetEx &cgo)
{
	// dirty-flag debounce (spec "Preview behavior"): slider drags fire
	// many callbacks; re-render at most once per frame
	if (fPreviewDirty)
	{
		fPreviewDirty = false;
		RenderLandscapePreview();
	}
	C4GUI::FullscreenDialog::Draw(cgo);
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
