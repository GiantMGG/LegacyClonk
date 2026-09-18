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
#include <C4GuiComboBox.h>
#include <C4GuiResource.h>
#include "C4GuiTabular.h"
#include <C4Log.h>
#include <C4RTF.h>

#include "C4SliderDescriptors.h"
#include "C4WinConditionDescriptors.h"
#include "C4PlrStartDescriptors.h"

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

	// (The per-def picker checkbox + row moved into the nested
	// C4OfflineOptionsDlg::DefPickerRow below: the row needs the dialog's
	// refresh hook, and the dialog needs a row registry for the
	// win-condition refresh — spec adjustable-winning-conditions.)

	// Store-tab section labels: the cycle-137 string keys replace the raw
	// descriptor labels in the section headers (spec pregame-store-tab D4
	// — the last hardcoded-English corner of this dialog). Member-pointer
	// identity pins the section; the descriptor table itself is untouched.
	const char *StoreSectionLabel(const C4PlrStartListDescriptor &rDescriptor)
	{
		if (rDescriptor.pList == &C4SPlrStart::HomeBaseMaterial)
			return LoadResStr(C4ResStrTableKey::IDS_CTL_STOREGOODS);
		if (rDescriptor.pList == &C4SPlrStart::HomeBaseProduction)
			return LoadResStr(C4ResStrTableKey::IDS_CTL_STORERESTOCK);
		return LoadResStr(C4ResStrTableKey::IDS_CTL_BLUEPRINTS);
	}
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

// C4OfflineOptionsDlg::PrimaryButton — the settings-stage Start button:
// base CallbackButton draw (bar + text, font auto-selected for the
// taller bounds, C4GuiButton.cpp:100-107) plus a permanent additive
// fctButtonHighlight glow — the same facet the base draws for
// hover/focus (C4GuiButton.cpp:92-98), here always-on for the one
// primary action per view (spec pregame-start-button-fix). Hover/focus
// brightens further (double additive blit — accepted emphasis cascade).
// Nested so it can reach the dialog's private OnBtnStart (the SeedEdit
// precedent).

class C4OfflineOptionsDlg::PrimaryButton : public C4GUI::CallbackButton<C4OfflineOptionsDlg>
{
public:
	PrimaryButton(const char *szBtnText, const C4Rect &rtBounds, C4GUI::DlgCallback<C4OfflineOptionsDlg>::Func pFn)
		: C4GUI::CallbackButton<C4OfflineOptionsDlg>(szBtnText, rtBounds, pFn) {}

protected:
	virtual void DrawElement(C4FacetEx &cgo) override
	{
		// base draw: bar, hover/focus highlight, text
		C4GUI::CallbackButton<C4OfflineOptionsDlg>::DrawElement(cgo);
		// permanent primary glow (disabled stays plain)
		if (fEnabled)
		{
			int32_t x0 = cgo.TargetX + rcBounds.x, y0 = cgo.TargetY + rcBounds.y;
			lpDDraw->SetBlitMode(C4GFXBLIT_ADDITIVE);
			C4GUI::GetRes()->fctButtonHighlight.DrawX(cgo.Surface, x0 + 5, y0 + 3, rcBounds.Wdt - 10, rcBounds.Hgt - 6);
			lpDDraw->ResetBlitMode();
		}
	}
};

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

// C4OfflineOptionsDlg::DefPickerRow — one picker row: def icon +
// checkbox, PLUS (when the def declares a count channel,
// MaxUserSelect > 1) a count slider + raw-count readout (spec §2.3).
// The checkbox governs membership; the slider the count: re-check adds
// the ID at the slider's current position, uncheck removes the ID;
// slider drags write SetIDCount only while the ID is checked in. Every
// write funnels through the dialog-wide refresh — no cached state.
class C4OfflineOptionsDlg::DefPickerRow : public C4GUI::Window
{
public:
	DefPickerRow(const C4Rect &rcRow, C4Def *pDef, C4IDList *pTargetList,
		const C4CountSliderParams &rCountParams, C4OfflineOptionsDlg *pDlg);

	void UpdateFromLists(); // refresh: checkbox + slider re-derived from the list

private:
	void OnToggle();                            // checkbox: membership write + refresh
	void OnCountSliderChange(int32_t iPosition); // count write + refresh
	void UpdateCountReadout();

	C4OfflineOptionsDlg *pDlg;
	C4IDList *pTargetList;
	C4ID idRowDef;
	C4CountSliderParams CountParams;
	C4GUI::CheckBox *pCheckBox{nullptr};
	C4GUI::ScrollBar *pCountSlider{nullptr};
	C4GUI::Label *pCountReadout{nullptr};
	int32_t iCurrentCount{1};
};

C4OfflineOptionsDlg::DefPickerRow::DefPickerRow(const C4Rect &rcRow, C4Def *pDef, C4IDList *pTargetList,
	const C4CountSliderParams &rCountParams, C4OfflineOptionsDlg *pDlg)
	: pDlg(pDlg), pTargetList(pTargetList), idRowDef(pDef->id), CountParams(rCountParams)
{
	SetBounds(rcRow);

	// pre-checked iff the list contains the ID; the count starts at the
	// authored count (when in the list) or the resolved default (absent)
	const bool fChecked = pTargetList->GetIndex(idRowDef) >= 0;
	iCurrentCount = fChecked
		? std::max(pTargetList->GetIDCount(idRowDef), CountParams.iMin)
		: CountParams.iDefault;

	// checkbox strip — today's 36-px layout (icon + name)
	const C4Rect rcClient = GetContainedClientRect();
	C4GUI::ComponentAligner caTop(C4Rect(rcClient.x, rcClient.y, rcClient.Wdt, 36), 2, 1);
	const int32_t iIconSize = 36 - 4;
	AddElement(new DefIcon(caTop.GetFromLeft(iIconSize, iIconSize), pDef));
	pCheckBox = new C4GUI::CheckBox(caTop.GetAll(), pDef->GetName(), fChecked);
	pCheckBox->SetOnChecked(new C4GUI::CallbackHandlerNoPar<DefPickerRow>(this, &DefPickerRow::OnToggle));
	AddElement(pCheckBox);

	if (CountParams.fEligible)
	{
		// count strip — the lower 16 px (52-px row total): slider + RAW
		// count readout ("15", never an effect — count->effect is
		// script-private and non-linear for WPHT; spec §2.3 count honesty)
		C4GUI::ComponentAligner caCount(C4Rect(rcClient.x, rcClient.y + 36, rcClient.Wdt, rcClient.Hgt - 36), 2, 0);
		pCountReadout = new C4GUI::Label("", caCount.GetFromRight(44), ARight,
			C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont);
		AddElement(pCountReadout);
		auto *pCB = new C4GUI::ParCallbackHandler<DefPickerRow, int32_t>(this, &DefPickerRow::OnCountSliderChange);
		pCountSlider = new C4GUI::ScrollBar(caCount.GetAll(), true, pCB, CountParams.iMax - CountParams.iMin + 1);
		AddElement(pCountSlider);
		// SetScrollPos does NOT fire the callback (direct rescale assign)
		pCountSlider->SetScrollPos(iCurrentCount - CountParams.iMin);
		UpdateCountReadout();
	}
}

void C4OfflineOptionsDlg::DefPickerRow::OnToggle()
{
	if (pCheckBox->GetChecked())
	{
		// re-check: the slider position IS the count now (spec §2.3)
		pTargetList->SetIDCount(idRowDef, iCurrentCount, true);
	}
	else
	{
		// uncheck: remove the ID from the list again
		const int32_t iIndex = pTargetList->GetIndex(idRowDef);
		if (iIndex >= 0) pTargetList->DeleteItem(static_cast<std::size_t>(iIndex));
	}
	pDlg->OnWinConditionListsChanged();
}

void C4OfflineOptionsDlg::DefPickerRow::OnCountSliderChange(int32_t iPosition)
{
	// slider position p in [0, iMax-iMin] -> count p+iMin
	iCurrentCount = BoundBy(iPosition + CountParams.iMin, CountParams.iMin, CountParams.iMax);
	// membership stays with the checkbox: drags write only checked-in rows
	if (pTargetList->GetIndex(idRowDef) >= 0)
		pTargetList->SetIDCount(idRowDef, iCurrentCount, true);
	UpdateCountReadout();
	pDlg->OnWinConditionListsChanged();
}

void C4OfflineOptionsDlg::DefPickerRow::UpdateFromLists()
{
	// no-fire setters only (CheckBox::SetChecked / ScrollBar::SetScrollPos)
	const bool fPresent = pTargetList->GetIndex(idRowDef) >= 0;
	pCheckBox->SetChecked(fPresent);
	if (fPresent)
	{
		// panel writes (e.g. the settlement slider) reflect here; keep the
		// raw list count so an over-ceiling authored count survives a
		// re-check round-trip (resolver guarantee, spec edge case 3)
		iCurrentCount = std::max(pTargetList->GetIDCount(idRowDef), CountParams.iMin);
		if (pCountSlider)
			pCountSlider->SetScrollPos(BoundBy(iCurrentCount, CountParams.iMin, CountParams.iMax) - CountParams.iMin);
	}
	// absent: slider + readout rest where they were — re-check restores
	// the position (spec edge case 3)
	UpdateCountReadout();
}

void C4OfflineOptionsDlg::DefPickerRow::UpdateCountReadout()
{
	if (!pCountReadout) return;
	StdStrBuf sText;
	sText.Copy(std::format("{}", iCurrentCount).c_str());
	pCountReadout->SetText(sText.getData());
}

// C4OfflineOptionsDlg::PlrStartSectionHeader — one [PlayerN] section
// header: section label (on the cycle-137 string keys, spec D4) + the
// per-section All/None bulk buttons (spec round-setup-parity-complete
// § User-visible behavior). All enters every enumerated def of the
// section into the list — store sections at the descriptor default,
// blueprints at the count-0 presence idiom — unless already present, in
// which case the authored count stands; None removes every enumerated
// def of the section. Both go through the dialog's fan-out write path
// (all four PlrStart slots on both C4S copies).
class C4OfflineOptionsDlg::PlrStartSectionHeader : public C4GUI::Window
{
public:
	PlrStartSectionHeader(const C4Rect &rcRow, const C4PlrStartListDescriptor &rDescriptor,
		const char *szLabel, C4OfflineOptionsDlg *pDlg);

private:
	void OnBtnAll(C4GUI::Control *pBtn);
	void OnBtnNone(C4GUI::Control *pBtn);

	C4OfflineOptionsDlg *pDlg;
	const C4PlrStartListDescriptor *pDescriptor;
};

C4OfflineOptionsDlg::PlrStartSectionHeader::PlrStartSectionHeader(const C4Rect &rcRow,
	const C4PlrStartListDescriptor &rDescriptor, const char *szLabel, C4OfflineOptionsDlg *pDlg)
	: pDlg(pDlg), pDescriptor(&rDescriptor)
{
	SetBounds(rcRow);
	C4GUI::ComponentAligner caRow(GetContainedClientRect(), 2, 1);
	AddElement(new C4GUI::Label(szLabel,
		caRow.GetFromLeft(rcRow.Wdt * 3 / 5), ALeft, C4GUI_CaptionFontClr, &C4GUI::GetRes()->CaptionFont));
	AddElement(new C4GUI::CallbackButtonEx<PlrStartSectionHeader>(LoadResStr(C4ResStrTableKey::IDS_BTN_ALL),
		caRow.GetFromLeft(50), this, &PlrStartSectionHeader::OnBtnAll));
	AddElement(new C4GUI::CallbackButtonEx<PlrStartSectionHeader>(LoadResStr(C4ResStrTableKey::IDS_BTN_NONE),
		caRow.GetFromLeft(50), this, &PlrStartSectionHeader::OnBtnNone));
}

void C4OfflineOptionsDlg::PlrStartSectionHeader::OnBtnAll(C4GUI::Control *pBtn)
{
	// every enumerated def enters the list; present entries keep their
	// authored state (display truth: PlrStart[0] of the section copy)
	for (std::size_t i = 0; C4Def *pDef = Game.Defs.GetDef(i, pDescriptor->dwDefCategory); ++i)
	{
		const C4IDList &rDisplayList = Game.GetActiveSections().front()->C4S.PlrStart[0].*pDescriptor->pList;
		if (rDisplayList.GetIndex(pDef->id) >= 0) continue;
		const int32_t iCount = pDescriptor->fPresenceIdiom ? 0 : pDescriptor->iDefault;
		pDlg->WritePlrStartID(*pDescriptor, pDef->id, iCount, true);
	}
	pDlg->OnPlrStartListsChanged();
}

void C4OfflineOptionsDlg::PlrStartSectionHeader::OnBtnNone(C4GUI::Control *pBtn)
{
	for (std::size_t i = 0; C4Def *pDef = Game.Defs.GetDef(i, pDescriptor->dwDefCategory); ++i)
		pDlg->RemovePlrStartID(*pDescriptor, pDef->id);
	pDlg->OnPlrStartListsChanged();
}

// C4OfflineOptionsDlg::StoreCell — one store-tab grid cell (spec
// pregame-store-tab D2): 16px def icon + checkbox (def name, truncates)
// + a raw "×n" count label on count-bearing sections, in a 24px cell of
// a dense band row. Writes route through the dialog's fan-out writer
// (all four PlrStart slots on both C4S copies) — the DefPickerRow /
// PlrStartPickerRow write discipline, in cell geometry. Any click binds
// the sheet's ONE shared count editor to this cell (by cell, so the
// binding survives grid scroll and All/None bulk writes — selection is
// never derived from a slider or scroll position).
class C4OfflineOptionsDlg::StoreCell : public C4GUI::Window
{
public:
	StoreCell(const C4Rect &rcCell, C4Def *pDef, const C4PlrStartListDescriptor &rDescriptor,
		const C4PlrStartCountParams &rCountParams, C4OfflineOptionsDlg *pDlg);

	void UpdateFromLists(); // refresh: checkbox + count label re-derived from the lists
	void SetHighlighted(bool fToVal) { fHighlighted = fToVal; } // shared-editor binding marker
	C4ID GetDefID() const { return idCellDef; }
	const char *GetDefName() const { return pCellDef->GetName(); }
	const C4PlrStartListDescriptor &GetDescriptor() const { return *pDescriptor; }
	const C4PlrStartCountParams &GetCountParams() const { return CountParams; }
	int32_t GetCurrentCount() const { return iCurrentCount; }
	// preview channel for unchecked cells: a shared-editor drag on a def
	// that is NOT in the display list lands here, so the count the player
	// settled on is what OnToggle commits when the box gets checked
	void SetPendingCount(int32_t iCount) { iCurrentCount = BoundBy(iCount, CountParams.iMin, CountParams.iMax); }

protected:
	virtual void DrawElement(C4FacetEx &cgo) override; // selection highlight
	virtual void MouseInput(C4GUI::CMouse &rMouse, int32_t iButton, int32_t iX, int32_t iY, uint32_t dwKeyParam) override; // click binds the editor

private:
	void OnToggle(); // checkbox: membership write + editor bind + refresh
	void UpdateCountLabel();

	C4OfflineOptionsDlg *pDlg;
	const C4PlrStartListDescriptor *pDescriptor;
	const C4Def *pCellDef;
	C4ID idCellDef;
	C4PlrStartCountParams CountParams;
	C4GUI::CheckBox *pCheckBox{nullptr};
	C4GUI::Label *pCountLabel{nullptr};
	int32_t iCurrentCount{1};
	bool fHighlighted{false};
};

C4OfflineOptionsDlg::StoreCell::StoreCell(const C4Rect &rcCell, C4Def *pDef,
	const C4PlrStartListDescriptor &rDescriptor, const C4PlrStartCountParams &rCountParams, C4OfflineOptionsDlg *pDlg)
	: pDlg(pDlg), pDescriptor(&rDescriptor), pCellDef(pDef), idCellDef(pDef->id), CountParams(rCountParams)
{
	SetBounds(rcCell);

	// display truth: PlrStart[0] of the active section copy
	const C4IDList &rDisplayList = Game.GetActiveSections().front()->C4S.PlrStart[0].*rDescriptor.pList;
	const bool fChecked = rDisplayList.GetIndex(idCellDef) >= 0;
	iCurrentCount = fChecked
		? std::max(rDisplayList.GetIDCount(idCellDef), CountParams.iMin)
		: CountParams.iDefault;

	// 24px cell (spec D2): 16px def icon + checkbox + raw ×n count label
	// on count-bearing sections
	const C4Rect rcClient = GetContainedClientRect();
	C4GUI::ComponentAligner caCell(C4Rect(rcClient.x + 2, rcClient.y + (rcClient.Hgt - 16) / 2, rcClient.Wdt - 4, 16), 2, 0);
	AddElement(new DefIcon(caCell.GetFromLeft(16, 16), pDef));
	if (CountParams.fEligible)
	{
		pCountLabel = new C4GUI::Label("", caCell.GetFromRight(38), ARight,
			C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont);
		AddElement(pCountLabel);
	}
	pCheckBox = new C4GUI::CheckBox(caCell.GetAll(), pDef->GetName(), fChecked);
	pCheckBox->SetOnChecked(new C4GUI::CallbackHandlerNoPar<StoreCell>(this, &StoreCell::OnToggle));
	AddElement(pCheckBox);
	UpdateCountLabel();
}

void C4OfflineOptionsDlg::StoreCell::OnToggle()
{
	// a checkbox click binds the shared editor to this cell first
	pDlg->OnStoreCellClicked(this);
	if (pCheckBox->GetChecked())
	{
		// re-check: the count is the shared editor's readout value; the
		// blueprints row writes the count-0 presence idiom
		const int32_t iCount = pDescriptor->fPresenceIdiom ? 0 : iCurrentCount;
		pDlg->WritePlrStartID(*pDescriptor, idCellDef, iCount, true);
	}
	else
	{
		// uncheck: remove the ID from every slot again
		pDlg->RemovePlrStartID(*pDescriptor, idCellDef);
	}
	pDlg->OnPlrStartListsChanged();
}

void C4OfflineOptionsDlg::StoreCell::UpdateFromLists()
{
	// no-fire setters only (CheckBox::SetChecked)
	const C4IDList &rDisplayList = Game.GetActiveSections().front()->C4S.PlrStart[0].*pDescriptor->pList;
	const bool fPresent = rDisplayList.GetIndex(idCellDef) >= 0;
	pCheckBox->SetChecked(fPresent);
	if (fPresent)
	{
		// keep the raw list count so an over-ceiling authored count
		// survives a re-check round-trip (the resolver guarantee)
		iCurrentCount = std::max(rDisplayList.GetIDCount(idCellDef), CountParams.iMin);
	}
	UpdateCountLabel();
}

void C4OfflineOptionsDlg::StoreCell::UpdateCountLabel()
{
	if (!pCountLabel) return;
	// raw list count, never an effect (count honesty, spec §2.3); absent
	// defs show no count
	const C4IDList &rDisplayList = Game.GetActiveSections().front()->C4S.PlrStart[0].*pDescriptor->pList;
	const int32_t iCount = rDisplayList.GetIDCount(idCellDef);
	if (iCount > 0)
	{
		StdStrBuf sText;
		sText.Copy(std::format("×{}", iCount).c_str());
		pCountLabel->SetText(sText.getData());
	}
	else
	{
		pCountLabel->SetText("");
	}
}

void C4OfflineOptionsDlg::StoreCell::DrawElement(C4FacetEx &cgo)
{
	// selection highlight marking the shared-editor binding (the grid's
	// ListBox item bar is disabled — the bar would span the whole band)
	if (fHighlighted)
		lpDDraw->DrawBoxDw(cgo.Surface, cgo.TargetX + rcBounds.x, cgo.TargetY + rcBounds.y,
			cgo.TargetX + rcBounds.x + rcBounds.Wdt - 1, cgo.TargetY + rcBounds.y + rcBounds.Hgt - 1,
			C4GUI_ListBoxSelColor);
}

void C4OfflineOptionsDlg::StoreCell::MouseInput(C4GUI::CMouse &rMouse, int32_t iButton, int32_t iX, int32_t iY, uint32_t dwKeyParam)
{
	// any left click reaching the cell (icon / empty space) binds the
	// shared count editor; checkbox clicks go through OnToggle instead
	if (iButton == C4MC_Button_LeftDown)
		pDlg->OnStoreCellClicked(this);
	Window::MouseInput(rMouse, iButton, iX, iY, dwKeyParam);
}

// C4OfflineOptionsDlg::WinComboRow — one Winning Conditions ComboBox
// row (the C4StartupPlrPropertiesDlg fill-callback pattern): human
// label + ComboBox; a selection encodes through the shared codec into
// Parameters.Goals/Rules, then the dialog-wide refresh re-derives
// every other row. SetText is the no-fire display setter used by the
// refresh (C4GuiComboBox.cpp:224 — plain copy, no callback).
class C4OfflineOptionsDlg::WinComboRow : public C4GUI::Window
{
public:
	WinComboRow(const C4Rect &rcRow, const C4WinConditionDescriptor &rDescriptor, C4OfflineOptionsDlg *pDlg);

	void UpdateFromLists(const C4WinConditionState &rState); // decode -> no-fire display

private:
	void OnComboFill(C4GUI::ComboBox_FillCB *pFiller);
	bool OnComboSelChange(C4GUI::ComboBox *pForCombo, int32_t idNewSelection);

	C4OfflineOptionsDlg *pDlg;
	const C4WinConditionDescriptor *pDescriptor;
	C4GUI::ComboBox *pComboBox{nullptr};
};

C4OfflineOptionsDlg::WinComboRow::WinComboRow(const C4Rect &rcRow, const C4WinConditionDescriptor &rDescriptor, C4OfflineOptionsDlg *pDlg)
	: pDlg(pDlg), pDescriptor(&rDescriptor)
{
	SetBounds(rcRow);
	C4GUI::ComponentAligner caRow(GetContainedClientRect(), 2, 1);
	AddElement(new C4GUI::Label(rDescriptor.szLabel,
		caRow.GetFromLeft(rcRow.Wdt * 2 / 5), ALeft, C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont));
	pComboBox = new C4GUI::ComboBox(caRow.GetAll());
	pComboBox->SetComboCB(new C4GUI::ComboBox_FillCallback<WinComboRow>(this, &WinComboRow::OnComboFill, &WinComboRow::OnComboSelChange));
	pComboBox->SetFont(&C4GUI::GetRes()->TextFont);
	AddElement(pComboBox);
	// initial state: decode-only (opening the dialog writes nothing)
	const C4WinConditionState State = DecodeWinCondition(Game.Parameters.Goals, Game.Parameters.Rules);
	UpdateFromLists(State);
}

void C4OfflineOptionsDlg::WinComboRow::OnComboFill(C4GUI::ComboBox_FillCB *pFiller)
{
	// the panel vocabulary: display names; id = choice index
	for (std::size_t i = 0; i < pDescriptor->iChoiceCount; ++i)
		pFiller->AddEntry(pDescriptor->Choices[i].szDisplayName, static_cast<int32_t>(i));
}

bool C4OfflineOptionsDlg::WinComboRow::OnComboSelChange(C4GUI::ComboBox *pForCombo, int32_t idNewSelection)
{
	if (idNewSelection >= 0 && static_cast<std::size_t>(idNewSelection) < pDescriptor->iChoiceCount)
	{
		const C4WinConditionChoice &rChoice = pDescriptor->Choices[idNewSelection];
		// panel aux: keep the current settlement count when the row stays
		// on Settlement; a newly-selected Settlement starts at the
		// descriptor default (15 -> 1500 points, spec decision (c))
		const int32_t iCurrentValG = Game.Parameters.Goals.GetIDCount(kWinTargetDescriptor.id);
		const int32_t iAuxCount = (iCurrentValG > 0) ? iCurrentValG : kWinTargetDescriptor.iDefaultCount;
		ApplyWinConditionChoice(Game.Parameters.Goals, Game.Parameters.Rules,
			pDescriptor->szIniKey, rChoice.szEnumName, iAuxCount);
		pDlg->OnWinConditionListsChanged();
	}
	// false: default behaviour displays the selected entry text
	return false;
}

void C4OfflineOptionsDlg::WinComboRow::UpdateFromLists(const C4WinConditionState &rState)
{
	const C4WinConditionChoice *pChoice = nullptr;
	if (SEqualNoCase(pDescriptor->szIniKey, "Mode")) pChoice = rState.pModeChoice;
	else if (SEqualNoCase(pDescriptor->szIniKey, "Elimination")) pChoice = rState.pEliminationChoice;
	else pChoice = rState.pGoalChoice;
	// no-fire display setter — the refresh never re-fires selections
	if (pChoice) pComboBox->SetText(pChoice->szDisplayName);
}

// C4OfflineOptionsDlg::SettlementRow — the ValueGain row: label +
// horizontal ScrollBar in the points domain (positions 0..iMax-iMin map
// to counts iMin..iMax, shown as count*100 points) + live readout.
// Dragging writes Goals.SetIDCount(VALG, count, true) — one gesture, no
// disabled controls: interacting with the slider IMPLICITLY selects the
// Settlement cooperative goal (the refresh decodes VALG presence).
class C4OfflineOptionsDlg::SettlementRow : public C4GUI::Window
{
public:
	SettlementRow(const C4Rect &rcRow, C4OfflineOptionsDlg *pDlg);

	void UpdateFromLists(const C4IDList &rGoals); // decode -> no-fire reposition

private:
	void OnSliderChange(int32_t iPosition);
	void UpdateReadout(int32_t iCount);

	C4OfflineOptionsDlg *pDlg;
	C4GUI::ScrollBar *pSlider{nullptr};
	C4GUI::Label *pReadout{nullptr};
	int32_t iMin{1}, iMax{1};
};

C4OfflineOptionsDlg::SettlementRow::SettlementRow(const C4Rect &rcRow, C4OfflineOptionsDlg *pDlg)
	: pDlg(pDlg)
{
	SetBounds(rcRow);
	iMin = kWinTargetDescriptor.iMinCount;
	iMax = kWinTargetDescriptor.iMaxCount;

	C4GUI::ComponentAligner caRow(GetContainedClientRect(), 2, 1);
	AddElement(new C4GUI::Label(kWinTargetDescriptor.szLabel,
		caRow.GetFromLeft(rcRow.Wdt * 2 / 5), ALeft, C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont));
	pReadout = new C4GUI::Label("", caRow.GetFromRight(64), ARight,
		C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont);
	AddElement(pReadout);
	auto *pCB = new C4GUI::ParCallbackHandler<SettlementRow, int32_t>(this, &SettlementRow::OnSliderChange);
	pSlider = new C4GUI::ScrollBar(caRow.GetAll(), true, pCB, iMax - iMin + 1);
	AddElement(pSlider);

	// initial state: decode-only — absent VALG rests at the default
	// (15 -> 1500 points) and does nothing until dragged (spec edge case 1)
	UpdateFromLists(Game.Parameters.Goals);
}

void C4OfflineOptionsDlg::SettlementRow::OnSliderChange(int32_t iPosition)
{
	// position p in [0, iMax-iMin] -> count p+iMin (clamped defensively)
	const int32_t iCount = BoundBy(iPosition + iMin, iMin, iMax);
	// write-through: the implicit Settlement selection (VALG enters the list)
	Game.Parameters.Goals.SetIDCount(kWinTargetDescriptor.id, iCount, true);
	UpdateReadout(iCount);
	pDlg->OnWinConditionListsChanged();
}

void C4OfflineOptionsDlg::SettlementRow::UpdateFromLists(const C4IDList &rGoals)
{
	const int32_t iListCount = rGoals.GetIDCount(kWinTargetDescriptor.id);
	// display-only clamp: the list count is the truth; a count this panel
	// cannot produce shows pinned at the top end
	const int32_t iCount = (iListCount > 0)
		? BoundBy(iListCount, iMin, iMax)
		: kWinTargetDescriptor.iDefaultCount;
	pSlider->SetScrollPos(iCount - iMin); // no callback fire
	UpdateReadout(iCount);
}

void C4OfflineOptionsDlg::SettlementRow::UpdateReadout(int32_t iCount)
{
	StdStrBuf sText;
	sText.Copy(std::format("{} {}", iCount * kWinTargetDescriptor.iPointsPerCount, kWinTargetDescriptor.szUnit).c_str());
	pReadout->SetText(sText.getData());
}

C4OfflineOptionsDlg::C4OfflineOptionsDlg()
	: C4GUI::FullscreenDialog(LoadResStr(C4ResStrTableKey::IDS_DLG_OPTIONS), Game.Parameters.ScenarioTitle.getData())
{
	// Child bounds are relative to the client area: Window::Draw already
	// offsets children by the client margins, so the stages must start at
	// 0,0. Using GetClientRect() here shifted both stages down/right by the
	// margins and pushed the bottom button row (Start/Back/Abort) below the
	// screen edge.
	const C4Rect rcStage = GetContainedClientRect();

	// both stage windows cover the full client area; page-swap via fVisible
	pLandingStage = new C4GUI::Window();
	pLandingStage->SetBounds(rcStage);
	AddElement(pLandingStage);
	pSettingsStage = new C4GUI::Window();
	pSettingsStage->SetBounds(rcStage);
	AddElement(pSettingsStage);

	CreateLandingStage(rcStage);
	CreateSettingsStage(rcStage);

	// Free Game (roadmap free-game-menu-entry): rounds started via the
	// main-menu Free Game button open straight onto the world-settings
	// stage. One-shot: consumed here so the next normal start lands on
	// the landing stage again.
	SetStage(Game.fFreeGameStart ? Stage::Settings : Stage::Landing);
	Game.fFreeGameStart = false;
}

void C4OfflineOptionsDlg::CreateLandingStage(const C4Rect &rcStage)
{
	C4GUI::ComponentAligner caStage(rcStage, 10, 10, true);

	// scenario title, centered, caption font
	pLandingStage->AddElement(new C4GUI::Label(Game.Parameters.ScenarioTitle.getData(),
		caStage.GetFromTop(60), ACenter, C4GUI_CaptionFontClr, &C4GUI::GetRes()->CaptionFont));

	// the equal-size [World Settings][Quick Start] pair, centered
	C4GUI::ComponentAligner caPair(caStage.GetCentered(caStage.GetInnerWidth() * 3 / 4, C4GUI_ButtonHgt + 8), 10, 4);
	pBtnWorldSettings = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_BTN_WORLDSETTINGS),
		caPair.GetFromLeft(caPair.GetInnerWidth() / 2), &C4OfflineOptionsDlg::OnBtnWorldSettings);
	pLandingStage->AddElement(pBtnWorldSettings);
	pBtnQuickStart = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_BTN_QUICKSTART),
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

	// bottom strip: [Back][Abort] ... [Start Game] (spec pregame-start-
	// button-fix): small cluster bottom-left (110x32 centered in 120px
	// cells — the landing Abort's centering idiom), the primary Start
	// bottom-right in big-button geometry (170x40) with a permanent glow;
	// Abort's GetAll() mega-width bug is dead (no GetAll consumer
	// remains in the strip)
	C4GUI::ComponentAligner caBottom(caMain.GetFromBottom(C4GUI_BigButtonHgt + 8), 10, 4);
	C4GUI::ComponentAligner caBackCell(caBottom.GetFromLeft(120), 10, 4);
	pBtnBack = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_BTN_BACK),
		caBackCell.GetCentered(110, C4GUI_ButtonHgt), &C4OfflineOptionsDlg::OnBtnBack);
	pSettingsStage->AddElement(pBtnBack);
	C4GUI::ComponentAligner caAbortCell(caBottom.GetFromLeft(120), 10, 4);
	pBtnAbort = new C4GUI::CallbackButton<C4OfflineOptionsDlg>(LoadResStr(C4ResStrTableKey::IDS_DLG_ABORT),
		caAbortCell.GetCentered(110, C4GUI_ButtonHgt), &C4OfflineOptionsDlg::OnBtnAbort);
	pSettingsStage->AddElement(pBtnAbort);
	pBtnStart = new PrimaryButton(LoadResStr(C4ResStrTableKey::IDS_DLG_STARTGAME),
		caBottom.GetFromRight(170), &C4OfflineOptionsDlg::OnBtnStart);
	pBtnStart->SetToolTip(LoadResStr(C4ResStrTableKey::IDS_DLGTIP_GAMEGO));
	pSettingsStage->AddElement(pBtnStart);

	// The settings body goes into a Round/Store tab pair on the offline
	// path — the [PlayerN] store sections move to a dedicated full-width
	// Store tab so the whole Knights store surface fits at 1080p without
	// scrolling (spec pregame-store-tab D1). The bottom strip above stays
	// a direct child of the stage on BOTH paths, outside the tabbed area.
	//
	// The Tabular is gated on the same condition CreatePlrStartSections
	// uses (Game.NetworkActive): the net-host dialog (C4Game.cpp:677
	// reaches this class too) renders today's layout verbatim with no
	// Store tab — no empty tab can ever appear on the net path (spec D3).
	// The Round sheet gets today's entire settings body (briefing +
	// pickers + landscape panel / options strip), re-parented via
	// pSettingsBody.
	if (!Game.NetworkActive)
	{
		pStageTabs = new C4GUI::Tabular(caMain.GetAll(), C4GUI::Tabular::tbTop);
		pSettingsStage->AddElement(pStageTabs);
		// Round is added first, so it is the active sheet on open
		pRoundSheet = pStageTabs->AddSheet(LoadResStr(C4ResStrTableKey::IDS_CTL_TAB_ROUND));
		pStoreSheet = pStageTabs->AddSheet(LoadResStr(C4ResStrTableKey::IDS_CTL_TAB_STORE));
		pSettingsBody = pRoundSheet;
		// the store sheet must exist before the pickers build the PlrStart
		// sections (CreatePickers -> CreatePlrStartSections)
		CreateStoreSheet();
	}
	else
	{
		pSettingsBody = pSettingsStage;
	}

	// The options list only has rows for network games and team scenarios
	// (C4GameOptionsList::InitOptions); in a plain offline round it would be
	// an empty framed box, so it is left out and its space goes to the pickers.
	const bool fHaveOptions = Game.Network.isEnabled() || Game.Control.isNetwork()
		|| Game.Teams.HasTeamDistOptions() || Game.Teams.IsMultiTeams();

	if (!LandscapePanelVisible() && !fHaveOptions)
	{
		// nothing for a right pane: briefing on top, pickers use the full width
		C4GUI::ComponentAligner caAll(caMain.GetAll(), 6, 4);
		CreateBriefing(caAll.GetFromTop(caAll.GetInnerHeight() * 25 / 100));
		CreatePickers(caAll.GetAll());
		return;
	}

	// left pane (~55%): briefing top, pickers middle, options strip bottom
	const int32_t iLeftWdt = caMain.GetInnerWidth() * 55 / 100;
	C4GUI::ComponentAligner caLeft(caMain.GetFromLeft(iLeftWdt), 6, 4);
	CreateBriefing(caLeft.GetFromTop(caLeft.GetInnerHeight() * 25 / 100));
	if (LandscapePanelVisible() && fHaveOptions)
	{
		// compact options strip at the bottom of the left pane
		pOptionsList = new C4GameOptionsList(caLeft.GetFromBottom(caLeft.GetInnerHeight() * 25 / 100), true, false);
		pSettingsBody->AddElement(pOptionsList);
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
		pSettingsBody->AddElement(pOptionsList);
	}
}

void C4OfflineOptionsDlg::CreateBriefing(const C4Rect &rcBriefing)
{
	// briefing text window (ScenDesc pattern, C4GameLobby.cpp:63-72)
	pBriefing = new C4GUI::TextWindow(rcBriefing, 0, 0, 0, 100, 4096, "", true);
	pBriefing->SetDecoration(false, false, nullptr, true);
	pSettingsBody->AddElement(pBriefing);
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
	pSettingsBody->AddElement(pPickerList);
	const int32_t iListWdt = pPickerList->GetItemWidth();

	// Winning Conditions — the four §2.1 acceptance rows atop the pickers
	CreateWinConditionPanel();

	// objectives — one checkbox row per loaded C4D_Goal def (spec §2.3;
	// the enum constraint: ONLY C4D_Goal/C4D_Rule defs are enumerated);
	// defs that declare a count channel (MaxUserSelect > 1, resolved —
	// never per-ID literals) grow a count slider (52-px row)
	AddPickerSectionHeader(LoadResStr(C4ResStrTableKey::IDS_CTL_OBJECTIVES));
	for (std::size_t i = 0; C4Def *pDef = Game.Defs.GetDef(i, C4D_Goal); ++i)
	{
		const C4CountSliderParams CountParams = ResolveCountSliderParams(
			pDef->MaxUserSelect, Game.Parameters.Goals.GetIDCount(pDef->id));
		auto *pRow = new DefPickerRow(C4Rect(0, 0, iListWdt, CountParams.fEligible ? 52 : 36),
			pDef, &Game.Parameters.Goals, CountParams, this);
		pPickerList->AddElement(pRow);
		pPickerRows.push_back(pRow);
	}

	// Rules — one checkbox row per loaded C4D_Rule def (same eligibility)
	AddPickerSectionHeader(LoadResStr(C4ResStrTableKey::IDS_CTL_RULES));
	for (std::size_t i = 0; C4Def *pDef = Game.Defs.GetDef(i, C4D_Rule); ++i)
	{
		const C4CountSliderParams CountParams = ResolveCountSliderParams(
			pDef->MaxUserSelect, Game.Parameters.Rules.GetIDCount(pDef->id));
		auto *pRow = new DefPickerRow(C4Rect(0, 0, iListWdt, CountParams.fEligible ? 52 : 36),
			pDef, &Game.Parameters.Rules, CountParams, this);
		pPickerList->AddElement(pRow);
		pPickerRows.push_back(pRow);
	}

	// [PlayerN] start-list sections (spec round-setup-parity-complete +
	// pregame-store-tab): Store goods / Store restock / Construction
	// blueprints. They live in the Store tab's dense grid, NOT this picker
	// list. Offline-only (the !Game.NetworkActive gate inside).
	CreatePlrStartSections();
}

void C4OfflineOptionsDlg::CreateWinConditionPanel()
{
	// the four research §2.1 acceptance rows: three ComboBox rows driven
	// by kWinConditionDescriptors + the settlement-target slider
	// (kWinTargetDescriptor). Lives at the top of the picker ListBox,
	// inside the same savegame gate as the pickers (resume rounds never
	// re-run InitGoals/InitRules — spec edge case 6).
	static_assert(std::size(kWinConditionDescriptors) == 3); // pWinComboRows bound
	AddPickerSectionHeader(LoadResStr(C4ResStrTableKey::IDS_CTL_WINNINGCONDITIONS));
	const int32_t iListWdt = pPickerList->GetItemWidth();
	for (std::size_t i = 0; i < std::size(kWinConditionDescriptors); ++i)
	{
		pWinComboRows[i] = new WinComboRow(C4Rect(0, 0, iListWdt, 36), kWinConditionDescriptors[i], this);
		pPickerList->AddElement(pWinComboRows[i]);
	}
	pSettlementRow = new SettlementRow(C4Rect(0, 0, iListWdt, 24), this);
	pPickerList->AddElement(pSettlementRow);
}

void C4OfflineOptionsDlg::UpdateWinConditionRows()
{
	// read-only derive: every widget state comes from the two lists
	// (spec risk-1 mitigation — nothing cached, no firing setters);
	// null-guards keep this safe during dialog construction
	const C4WinConditionState State = DecodeWinCondition(Game.Parameters.Goals, Game.Parameters.Rules);
	for (C4OfflineOptionsDlg::WinComboRow *pRow : pWinComboRows)
		if (pRow) pRow->UpdateFromLists(State);
	if (pSettlementRow) pSettlementRow->UpdateFromLists(Game.Parameters.Goals);
	for (DefPickerRow *pRow : pPickerRows)
		pRow->UpdateFromLists();
}

void C4OfflineOptionsDlg::OnWinConditionListsChanged()
{
	// writer hook: every picker/slider/panel write calls this after its
	// list write; the guard breaks any re-entrancy
	if (fUpdatingWinRows) return;
	fUpdatingWinRows = true;
	UpdateWinConditionRows();
	fUpdatingWinRows = false;
}

void C4OfflineOptionsDlg::CreatePlrStartSections()
{
	// desync gate (spec round-setup-parity-complete): PlrStart edits
	// ride no net sync path — the sections must not exist on the
	// net-host dialog path. Offline rounds (Game.NetworkActive == false)
	// get the full surface.
	if (Game.NetworkActive) return;

	// emit into the Store sheet's dense grid (spec pregame-store-tab D2),
	// not the shared picker list: per-section 20px header with the All/None
	// bulk buttons and the cycle-137 section label, then 24px band rows of
	// iColumns def cells (K from ComputeStoreWrap — full store surface
	// visible without scrolling at 1080p = the player check)
	const int32_t iListWdt = pStoreList->GetItemWidth();
	const int32_t iColumns = ComputeStoreWrapColumns(iListWdt);
	for (const auto &Descriptor : kPlrStartListDescriptors)
	{
		pStoreList->AddElement(new PlrStartSectionHeader(
			C4Rect(0, 0, iListWdt, kStoreWrapHeaderHeight), Descriptor, StoreSectionLabel(Descriptor), this));
		// one cell per loaded def matching the descriptor's picker filter
		// (the Objectives/Rules GetDef bitmask-AND filter, C4Def.cpp:1000),
		// wrapped into band rows of iColumns cells
		int32_t iCell = 0;
		C4GUI::Window *pBand = nullptr;
		for (std::size_t i = 0; C4Def *pDef = Game.Defs.GetDef(i, Descriptor.dwDefCategory); ++i)
		{
			if (iCell == 0)
			{
				pBand = new C4GUI::Window();
				pBand->SetBounds(C4Rect(0, 0, iListWdt, kStoreWrapBandHeight));
				pStoreList->AddElement(pBand);
			}
			const C4IDList &rDisplayList = Game.GetActiveSections().front()->C4S.PlrStart[0].*Descriptor.pList;
			const C4PlrStartCountParams CountParams = ResolvePlrStartCountParams(Descriptor, rDisplayList.GetIDCount(pDef->id));
			auto *pCell = new StoreCell(C4Rect(iCell * kStoreWrapCellWidth, 0, kStoreWrapCellWidth, kStoreWrapBandHeight),
				pDef, Descriptor, CountParams, this);
			pBand->AddElement(pCell);
			pStoreCells.push_back(pCell);
			iCell = (iCell + 1) % iColumns;
		}
	}
}

void C4OfflineOptionsDlg::WritePlrStartID(const C4PlrStartListDescriptor &rDescriptor, C4ID id, int32_t iCount, bool fAddNew)
{
	// fan-out write: all four [PlayerN] slots, both C4S copies (the
	// SliderRow dual write-through, C4OfflineOptionsDlg.cpp:189-192,
	// extended to the PlrStart array). Offline-solo context: a
	// single-player round reads PlrStart[0]
	// (PlrStartIndex = Number % C4S_MaxPlayer, C4Player.cpp:685).
	for (int32_t iSlot = 0; iSlot < C4S_MaxPlayer; ++iSlot)
	{
		(Game.GameC4S.PlrStart[iSlot].*rDescriptor.pList).SetIDCount(id, iCount, fAddNew);
		(Game.GetActiveSections().front()->C4S.PlrStart[iSlot].*rDescriptor.pList).SetIDCount(id, iCount, fAddNew);
	}
}

void C4OfflineOptionsDlg::RemovePlrStartID(const C4PlrStartListDescriptor &rDescriptor, C4ID id)
{
	// fan-out removal: index re-queried per list — safe against the
	// DeleteItem index shift
	for (int32_t iSlot = 0; iSlot < C4S_MaxPlayer; ++iSlot)
	{
		{
			C4IDList &rList = Game.GameC4S.PlrStart[iSlot].*rDescriptor.pList;
			const int32_t iIndex = rList.GetIndex(id);
			if (iIndex >= 0) rList.DeleteItem(static_cast<std::size_t>(iIndex));
		}
		{
			C4IDList &rList = Game.GetActiveSections().front()->C4S.PlrStart[iSlot].*rDescriptor.pList;
			const int32_t iIndex = rList.GetIndex(id);
			if (iIndex >= 0) rList.DeleteItem(static_cast<std::size_t>(iIndex));
		}
	}
}

void C4OfflineOptionsDlg::OnPlrStartListsChanged()
{
	// PlrStart twin of OnWinConditionListsChanged: re-derive every
	// [PlayerN] cell (and the shared count editor) from the lists via
	// no-fire setters; the guard breaks any re-entrancy
	if (fUpdatingPlrStartRows) return;
	fUpdatingPlrStartRows = true;
	for (StoreCell *pCell : pStoreCells)
		pCell->UpdateFromLists();
	fUpdatingPlrStartRows = false;
	// the shared editor's slider + readout are list-derived too (e.g. an
	// All/None bulk write may have changed the bound cell's count)
	UpdateStoreEditor();
}

void C4OfflineOptionsDlg::CreateStoreSheet()
{
	if (!pStoreSheet) return;
	C4GUI::ComponentAligner caSheet(pStoreSheet->GetContainedClientRect(), 3, 3);

	// shared count-editor strip pinned at the sheet bottom (~36px, spec
	// D2); it sits OUTSIDE the grid ListBox, so a wheel over the grid
	// scrolls the list, never scrubs the shared slider (spec risk 4)
	pStoreEditorStrip = new C4GUI::Window();
	pStoreEditorStrip->SetBounds(caSheet.GetFromBottom(kStoreWrapEditorStrip));
	pStoreSheet->AddElement(pStoreEditorStrip);

	// [Count] <selected def name> [≈slider≈] [#readout] — the slider is
	// (re)created on demand for the bound cell's count domain (one range
	// per descriptor: 1..25 goods, 1..10 restock); the name label spans
	// the strip and the editor widgets just overdraw its right end, which
	// keeps the layout stable when the editor is locked for a blueprint
	C4GUI::ComponentAligner caStrip(pStoreEditorStrip->GetContainedClientRect(), 2, 1);
	pStoreEditorStrip->AddElement(new C4GUI::Label(LoadResStr(C4ResStrTableKey::IDS_CTL_COUNT),
		caStrip.GetFromLeft(64), ALeft, C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont));
	pStoreEditorName = new C4GUI::Label("", caStrip.GetAll(), ALeft,
		C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont);
	pStoreEditorStrip->AddElement(pStoreEditorName);
	pStoreEditorReadout = new C4GUI::Label("", caStrip.GetFromRight(44), ARight,
		C4GUI_MessageFontClr, &C4GUI::GetRes()->TextFont);
	pStoreEditorStrip->AddElement(pStoreEditorReadout);
	rcStoreEditorSlider = caStrip.GetAll();

	// the dense grid: 24px band rows of K cells (spec D2)
	pStoreList = new C4GUI::ListBox(caSheet.GetAll());
	pStoreSheet->AddElement(pStoreList);
	// cells draw their own selection highlight; the list's own item
	// selection bar would span a whole band row, so it stays off
	pStoreList->SetSelectionDiabled(true);

	// no selection yet: the editor is locked
	UpdateStoreEditor();
}

void C4OfflineOptionsDlg::OnStoreCellClicked(C4OfflineOptionsDlg::StoreCell *pCell)
{
	// move the highlight and rebind the shared editor — the last-clicked
	// cell wins (spec D2); selection is by cell/id, so it survives grid
	// scroll and All/None bulk writes
	if (pSelectedStoreCell == pCell)
	{
		UpdateStoreEditor();
		return;
	}
	if (pSelectedStoreCell) pSelectedStoreCell->SetHighlighted(false);
	pSelectedStoreCell = pCell;
	pCell->SetHighlighted(true);
	UpdateStoreEditor();
}

void C4OfflineOptionsDlg::OnStoreCountSliderChange(int32_t iPosition)
{
	// shared-editor drag: position p in [0, iCBMaxRange-1] -> count
	// iMin+p, written through the unchanged fan-out (the old row slider
	// discipline, in the shared strip)
	if (!pSelectedStoreCell) return;
	const C4PlrStartCountParams &rParams = pSelectedStoreCell->GetCountParams();
	if (!rParams.fEligible) return; // blueprint (presence) cells are locked
	const int32_t iCount = BoundBy(iPosition + iStoreEditorMin, iStoreEditorMin, iStoreEditorMax);
	// two paths (membership stays with the cell checkbox): a present def
	// (already checked) writes through the fan-out immediately — the old
	// row-slider discipline, in the shared strip; an absent def (still
	// unchecked) only updates the pending preview so the drag doesn't
	// snap back — the checkbox click commits it via OnToggle
	const C4IDList &rDisplayList = Game.GetActiveSections().front()->C4S.PlrStart[0]
		.*pSelectedStoreCell->GetDescriptor().pList;
	if (rDisplayList.GetIndex(pSelectedStoreCell->GetDefID()) >= 0)
		WritePlrStartID(pSelectedStoreCell->GetDescriptor(), pSelectedStoreCell->GetDefID(), iCount, true);
	else
		pSelectedStoreCell->SetPendingCount(iCount);
	OnPlrStartListsChanged();
	UpdateStoreEditor();
}

void C4OfflineOptionsDlg::UpdateStoreEditor()
{
	// re-derive the shared strip from the selected cell; no-fire setters
	// only. Blueprint cells (presence semantics — no count channel) lock
	// the editor: slider concealed, readout empty (spec D2).
	if (!pStoreEditorStrip) return;
	const bool fValid = pSelectedStoreCell != nullptr;
	const bool fCount = fValid && pSelectedStoreCell->GetCountParams().fEligible;

	pStoreEditorName->SetText(fValid ? pSelectedStoreCell->GetDefName() : "");
	if (!fCount)
	{
		if (pStoreEditorSlider) pStoreEditorSlider->SetVisibility(false);
		pStoreEditorReadout->SetVisibility(false);
		return;
	}
	pStoreEditorReadout->SetVisibility(true);

	const C4PlrStartCountParams &rParams = pSelectedStoreCell->GetCountParams();
	if (!pStoreEditorSlider || iStoreEditorMin != rParams.iMin || iStoreEditorMax != rParams.iMax)
	{
		// (re)create the slider for the bound cell's count domain
		if (pStoreEditorSlider) delete pStoreEditorSlider;
		iStoreEditorMin = rParams.iMin;
		iStoreEditorMax = rParams.iMax;
		pStoreEditorSlider = new C4GUI::ScrollBar(rcStoreEditorSlider, true,
			new C4GUI::ParCallbackHandler<C4OfflineOptionsDlg, int32_t>(this, &C4OfflineOptionsDlg::OnStoreCountSliderChange),
			iStoreEditorMax - iStoreEditorMin + 1);
		pStoreEditorStrip->AddElement(pStoreEditorSlider);
	}
	pStoreEditorSlider->SetVisibility(true);

	// slider position + raw readout from the cell's current count
	// (SetScrollPos does NOT fire the callback)
	pStoreEditorSlider->SetScrollPos(BoundBy(pSelectedStoreCell->GetCurrentCount(), iStoreEditorMin, iStoreEditorMax) - iStoreEditorMin);
	StdStrBuf sText;
	sText.Copy(std::format("{}", pSelectedStoreCell->GetCurrentCount()).c_str());
	pStoreEditorReadout->SetText(sText.getData());
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
	pSettingsBody->AddElement(pLandscapePanel);

	// children are laid out in the panel's own coordinate space
	C4GUI::ComponentAligner caPanel(C4Rect(0, 0, rcPanel.Wdt, rcPanel.Hgt), 6, 3, true);

	// header
	pLandscapePanel->AddElement(new C4GUI::Label(LoadResStr(C4ResStrTableKey::IDS_DLG_LANDSCAPE),
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
