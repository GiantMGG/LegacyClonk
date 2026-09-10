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
// two-stage fullscreen dialog. Landing stage: scenario title + the
// [World Settings]/[Quick Start] pair + small Abort. Settings stage:
// briefing + pickers + options strip on the left, the world block on
// the right (hero preview + seed row + the 11 generated slider rows).
// Page-swap via a Stage enum + fVisible; per-stage Enter/ESC.

#ifndef USE_CONSOLE

#include "C4Gui.h"
#include "C4GuiDialogs.h"
#include "C4GuiSpinBox.h"

#include "C4GameOptions.h"

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

	class SeedEdit;  // nested: needs OnSeedChanged (the ScaleEdit precedent)
	class SliderRow; // nested: one generated row per descriptor

	C4GUI::Window *pLandingStage{nullptr};
	C4GUI::Window *pSettingsStage{nullptr};
	Stage eStage{Stage::Landing};

	C4GUI::TextWindow *pBriefing{nullptr};
	C4GUI::ListBox *pPickerList{nullptr};
	C4GUI::Window *pLandscapePanel{nullptr};
	C4GUI::ListBox *pSliderList{nullptr};
	C4GUI::Picture *pPreviewPicture{nullptr};
	SeedEdit *pSeedEdit{nullptr};
	C4GameOptionsList *pOptionsList{nullptr};

	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnQuickStart{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnWorldSettings{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnStart{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnBack{nullptr};
	C4GUI::CallbackButton<C4OfflineOptionsDlg> *pBtnAbort{nullptr};

	bool fPreviewDirty{false};
};

#endif
