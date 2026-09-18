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

#pragma once

// Offline pre-game options dialog (spec world-generator-ux-rework):
// two-stage fullscreen dialog. Landing stage: scenario title + the
// [World Settings]/[Quick Start] pair + small Abort. Settings stage:
// the settings body — briefing + pickers + options strip on the left,
// the world block on the right (hero preview + seed row + the 11
// generated slider rows) — plus, offline, a Round/Store tab pair that
// holds the [PlayerN] store sections in a dense grid (spec
// pregame-store-tab). Page-swap via a Stage enum + fVisible; per-stage
// Enter/ESC.

#ifndef USE_CONSOLE

#include "C4Gui.h"
#include "C4GuiDialogs.h"
#include "C4GuiSpinBox.h"
#include "C4GuiTabular.h" // Round/Store sheet pair of the offline settings stage

#include "C4GameOptions.h"

#include <vector>

struct C4PlrStartListDescriptor;

class C4OfflineOptionsDlg : public C4GUI::FullscreenDialog
{
public:
	enum class Stage { Landing, Settings };

	C4OfflineOptionsDlg();

	// create, run modal message loop, destroy; false iff aborted
	static bool Show();

private:
	void OnBtnStart(C4GUI::Control *btn);
	void OnBtnAbort(C4GUI::Control *btn);
	void OnBtnWorldSettings(C4GUI::Control *btn);
	void OnBtnBack(C4GUI::Control *btn);

	// landing stage
	void CreateLandingStage(const C4Rect &rcStage);

	// settings stage
	void CreateSettingsStage(const C4Rect &rcStage);
	void CreateBriefing(const C4Rect &rcBriefing);
	void FillBriefing();
	void CreatePickers(const C4Rect &rcPickers);
	void AddPickerSectionHeader(const char *szSectionLabel);

	// [PlayerN] start-list sections (spec round-setup-parity-complete):
	// three generated picker sections driven by kPlrStartListDescriptors
	// (Store goods / Store restock / Construction blueprints). Writes fan
	// out to all four PlrStart slots on both the active-section C4S and
	// GameC4S (the SliderRow dual write-through extended to the PlrStart
	// array). Offline-only: CreatePlrStartSections renders nothing when
	// Game.NetworkActive — PlrStart edits ride no net sync path, and a
	// host-side edit without sync would desync every joiner.
	void CreatePlrStartSections();
	void WritePlrStartID(const C4PlrStartListDescriptor &rDescriptor, C4ID id, int32_t iCount, bool fAddNew);
	void RemovePlrStartID(const C4PlrStartListDescriptor &rDescriptor, C4ID id);
	void OnPlrStartListsChanged();

	// Store tab (spec pregame-store-tab D2): the three [PlayerN] sections
	// render in a dedicated full-width tab of the offline settings stage as
	// a dense wrapped grid — 24px band rows of K def cells (K from
	// ComputeStoreWrap, C4PlrStartDescriptors.h) — with ONE shared
	// count-editor strip pinned at the sheet bottom (IDS_CTL_COUNT caption
	// + the selected def's name + scroll bar + numeric readout), bound to
	// the last-clicked highlighted cell; blueprint (presence) cells lock
	// the editor. Same offline-only gate as CreatePlrStartSections: the
	// Tabular exists only when the store does (no empty tab on the
	// net-host dialog path, spec D3). All writes keep going through the
	// unchanged WritePlrStartID / RemovePlrStartID / OnPlrStartListsChanged
	// fan-out.
	class StoreCell; // nested (defined in the .cpp): one store-tab grid cell
	void CreateStoreSheet();
	void OnStoreCellClicked(StoreCell *pCell);
	void OnStoreCountSliderChange(int32_t iPosition);
	void UpdateStoreEditor(); // shared editor re-derived from the selected cell

	// Winning Conditions panel + picker-row count sliders (spec
	// adjustable-winning-conditions): the panel rows and the picker
	// checkboxes edit the SAME Parameters lists; every write funnels
	// through OnWinConditionListsChanged -> UpdateWinConditionRows, which
	// re-derives all widget state from the two lists via no-fire setters
	// (CheckBox::SetChecked, ComboBox::SetText, ScrollBar::SetScrollPos).
	void CreateWinConditionPanel();
	void UpdateWinConditionRows();
	void OnWinConditionListsChanged();

	// world block (settings stage right pane)
	bool LandscapePanelVisible() const;
	void CreateLandscapePanel(const C4Rect &rcPanel);
	void BuildPreviewPalette(uint32_t dwPalette[256]) const;
	void RenderLandscapePreview();
	void OnSeedChanged();
	void OnBtnNewSeed(C4GUI::Control *btn);

	void SetStage(Stage eToStage);

	// per-stage key semantics (spec §2): Enter = Quick Start on the
	// landing stage, Start on the settings stage; ESC = Abort on the
	// landing stage, Back-to-landing on the settings stage. Abort is
	// always an explicit click.
	virtual bool OnEnter() override;
	virtual bool OnEscape() override;
	virtual class C4GUI::Control *GetDefaultControl() override;

	// preview dirty-flag debounce: slider drags fire many callbacks, so
	// the slider handler only marks the preview dirty; the dialog's
	// Draw flushes it — at most one re-render per frame.
	virtual void Draw(C4FacetEx &cgo) override;
	void MarkPreviewDirty() { fPreviewDirty = true; }

	class SeedEdit;      // nested: needs OnSeedChanged (the ScaleEdit precedent)
	class SliderRow;     // nested: one generated row per descriptor
	class DefPickerRow;  // nested: one picker row (checkbox + optional count slider)
	class PlrStartSectionHeader; // nested: one [PlayerN] section header (All/None bulk buttons)
	class StoreCell;     // nested: one store-tab grid cell (icon + checkbox + count label + selection)
	class WinComboRow;   // nested: one panel ComboBox row per enum descriptor
	class SettlementRow; // nested: the settlement-target points slider
	class PrimaryButton; // nested: the settings-stage Start (styled primary action)

	C4GUI::Window *pLandingStage{nullptr};
	C4GUI::Window *pSettingsStage{nullptr};
	Stage eStage{Stage::Landing};

	C4GUI::TextWindow *pBriefing{nullptr};
	C4GUI::ListBox *pPickerList{nullptr};
	std::vector<DefPickerRow *> pPickerRows; // picker-row registry for the win-condition refresh
	std::vector<StoreCell *> pStoreCells;    // store-cell registry for the PlrStart refresh
	WinComboRow *pWinComboRows[3]{nullptr, nullptr, nullptr}; // Mode/Elimination/CooperativeGoal
	SettlementRow *pSettlementRow{nullptr};
	C4GUI::Window *pLandscapePanel{nullptr};
	C4GUI::ListBox *pSliderList{nullptr};
	C4GUI::Picture *pPreviewPicture{nullptr};
	SeedEdit *pSeedEdit{nullptr};
	C4GameOptionsList *pOptionsList{nullptr};

	// settings-stage tab set (offline only; the net-host dialog keeps
	// today's direct layout — the Tabular exists only when the store does)
	C4GUI::Tabular *pStageTabs{nullptr};
	C4GUI::Tabular::Sheet *pRoundSheet{nullptr};
	C4GUI::Tabular::Sheet *pStoreSheet{nullptr};
	C4GUI::Window *pSettingsBody{nullptr}; // settings-body parent: stage (net) / Round sheet (offline)

	// store tab widgets (spec pregame-store-tab D2)
	C4GUI::ListBox *pStoreList{nullptr};       // the dense wrapped grid
	StoreCell *pSelectedStoreCell{nullptr};    // last-clicked highlighted cell (editor binding)
	C4GUI::Window *pStoreEditorStrip{nullptr}; // shared count-editor strip container
	C4GUI::Label *pStoreEditorName{nullptr};   // strip: the selected def's name
	C4GUI::ScrollBar *pStoreEditorSlider{nullptr};
	C4GUI::Label *pStoreEditorReadout{nullptr};
	C4Rect rcStoreEditorSlider{};                    // fixed slider rect within the strip
	int32_t iStoreEditorMin{1}, iStoreEditorMax{1};  // slider domain of the bound cell

	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnQuickStart{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnWorldSettings{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnStart{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnBack{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnAbort{nullptr};

	bool fPreviewDirty{false};
	bool fUpdatingWinRows{false}; // refresh re-entrancy guard (spec risk 1)
	bool fUpdatingPlrStartRows{false}; // PlrStart refresh re-entrancy guard
};

#endif
