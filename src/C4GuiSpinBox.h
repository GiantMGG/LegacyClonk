#pragma once

#include "C4Facet.h"
#include "C4Gui.h"
#include "C4GuiEdit.h"
#include "C4GuiResource.h"
#include "C4MouseControl.h"
#include "C4NumberParsing.h"
#include "StdApp.h"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <memory>

/*
 * LegacyClonk
 *
 * Copyright (c) 1998-2000, Matthes Bender (RedWolf Design)
 * Copyright (c) 2017-2023, The LegacyClonk Team and contributors
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

namespace C4GUI
{
template <std::integral T>
class SpinBox : public Edit
{
	using limits = std::numeric_limits<T>;

	static constexpr std::int32_t ArrowHeight{8};
	static constexpr std::int32_t ArrowWidth{13};
	static constexpr std::int32_t ArrowMarginTop{2};
	static constexpr std::int32_t ArrowMarginRight{1};
	static constexpr std::int32_t ArrowMarginLeft{2};

public:
	SpinBox(const C4Rect &bounds, const bool focusEdit = false, const T minimum = limits::min(), const T maximum = limits::max()) : Edit{bounds, focusEdit}, minimum{minimum}, maximum{maximum}
	{
		UpdateSize();

		UpdateMaxText();
		SetValue(T{}, false);

		C4CustomKey::Priority keyPrio = focusEdit ? C4CustomKey::PRIO_FocusCtrl : C4CustomKey::PRIO_Ctrl;
		keyUp = std::make_unique<C4KeyBinding>(C4KeyCodeEx{K_UP}, "GUINumberEditUp", KEYSCOPE_Gui, new ControlKeyCB{*this, &SpinBox::OffsetValueCallback<+1>}, keyPrio);
		keyDown = std::make_unique<C4KeyBinding>(C4KeyCodeEx{K_DOWN}, "GUINumberEditDown", KEYSCOPE_Gui, new ControlKeyCB{*this, &SpinBox::OffsetValueCallback<-1>}, keyPrio);
		keyPageUp = std::make_unique<C4KeyBinding>(C4KeyCodeEx{K_PAGEUP}, "GUINumberEditPageUp", KEYSCOPE_Gui, new ControlKeyCB{*this, &SpinBox::OffsetValueCallback<+10>}, keyPrio);
		keyPageDown = std::make_unique<C4KeyBinding>(C4KeyCodeEx{K_PAGEDOWN}, "GUINumberEditPageDown", KEYSCOPE_Gui, new ControlKeyCB{*this, &SpinBox::OffsetValueCallback<-10>}, keyPrio);
	}

	void SetMinimum(const T newMinimum)
	{
		minimum = newMinimum;
		UpdateMaxText();
	}

	void SetMaximum(const T newMaximum)
	{
		maximum = newMaximum;
		UpdateMaxText();
	}

	// Maximum allowed text length for the given value range. Edit::InsertText
	// checks `iTextLen + iTextEnd <= (iMaxTextLength - 1)`, so the max text
	// length must be one char LARGER than the widest value string of the
	// range, or a full-width value (e.g. the 10-digit default seed
	// "1789962431", or INT32_MIN's "-2147483648") would fill the whole budget
	// and every typed character would be clamped to zero and rejected
	// (the seed-typed-entry defect, C4GuiEdit.cpp InsertText). Public so the
	// char_input_routing test pin can assert the capacity contract directly.
	static unsigned short MaxTextLengthForRange(const T min, const T max)
	{
		return std::max(GetNumberLength(min), GetNumberLength(max)) + 1;
	}

	T GetValue()
	{
		const auto result = [this]
		{
			try
			{
				const std::string_view text{GetText()};
				if (text.empty())
				{
					return T{};
				}
				return ParseNumber<T>(text);
			}
			catch (const NumberRangeError<T> &e)
			{
				return e.AtRangeLimit;
			}
		}();
		return std::clamp(result, minimum, maximum);
	}

	void SetValue(const T value, const bool user)
	{
		const auto clamped = std::clamp(value, minimum, maximum);
		SetText(std::to_string(clamped), user);
	}

protected:
	void OnTextChange() override
	{
		bool changed{false};
		std::string text{GetText()};
		for (std::size_t i = (text.starts_with('-') && minimum < 0) ? 1 : 0; i < text.size();)
		{
			const auto c = text[i];
			if (c < '0' || c > '9')
			{
				text.erase(i, 1);
				if (iCursorPos >= i)
				{
					--iCursorPos;
				}
				changed = true;
				continue;
			}
			++i;
		}
		if (changed)
		{
			const auto cursorPos = iCursorPos;
			SetText(text.c_str(), false);
			iCursorPos = cursorPos;
		}
	}

	InputResult OnFinishInput([[maybe_unused]] const bool pasting, [[maybe_unused]] const bool pastingMore) override
	{
		SetValue(GetValue(), true);
		return IR_None;
	}

	void MouseInput(CMouse &mouse, const std::int32_t button, const std::int32_t x, const std::int32_t y, const std::uint32_t keyParam) override
	{
		// A click that freshly grants focus to the value text must keep the
		// select-all established by Edit::OnGetFocus, so typed characters
		// REPLACE the whole value instead of hitting the length clamp. The
		// base Edit::MouseInput LeftDown handler would otherwise collapse the
		// selection to a caret at the click point; when the value fills the
		// text budget (e.g. the 10-digit default seed "1789962431"), a
		// caret-insert then clamps to zero chars and the character is lost
		// (seed-typed-entry defect, cycle 159).
		const bool fHadFocusBefore = HasFocus();
		switch (button)
		{
			case C4MC_Button_Wheel:
			{
				const auto delta = static_cast<short>(keyParam >> 16);
				OffsetValue(delta < 0 ? -1 : +1, true);
				return;
			}
			case C4MC_Button_LeftDown:
			case C4MC_Button_LeftDouble:
				if (arrowsRect.Wdt <= 0 || !Inside(x, arrowsRect.x - rcBounds.x, rcBounds.Wdt))
				{
					break;
				}
				if (mouse.pDragElement)
				{
					break;
				}
				mouse.pDragElement = this;
				[[fallthrough]];
			case C4MC_Button_LeftUp:
			{
				const auto isDownButton = y > arrowsRect.GetMiddleY() - rcBounds.y;
				const auto prevPressed = upButtonPressed || downButtonPressed;
				if (button == C4MC_Button_LeftUp)
				{
					upButtonPressed = false;
					downButtonPressed = false;
				}
				else
				{
					OffsetValue(isDownButton ? -1 : +1, true);
					(isDownButton ? downButtonPressed : upButtonPressed) = true;
				}
				if ((upButtonPressed || downButtonPressed) != prevPressed)
				{
					GUISound("ArrowHit");
				}
				return;
			}
		}
		Edit::MouseInput(mouse, button, x, y, keyParam);
		if (button == C4MC_Button_LeftDown && !fHadFocusBefore)
		{
			SelectAll();
			// remember that a fresh-focus click granted select-all: the
			// drag-stop on button-up would otherwise collapse it to a caret
			// (Edit::DoDragging sets iSelectionEnd to the click char pos,
			// the click-selection defect, cycle 162). Restored in
			// StopDragging for a plain click; a drag is the user's own
			// selection gesture and is left alone.
			fFreshFocusClickPending = true;
			iFreshFocusClickX = x;
			iFreshFocusClickY = y;
		}
		else if (button == C4MC_Button_LeftDown || button == C4MC_Button_LeftDouble)
		{
			// new gesture without a prior fresh-focus grant (or a
			// word-select double click): nothing to restore at drag stop
			fFreshFocusClickPending = false;
		}
	}

	void DoDragging(CMouse &mouse, const std::int32_t x, const std::int32_t y, const std::uint32_t keyParam) override
	{
		if (!upButtonPressed && !downButtonPressed)
		{
			Edit::DoDragging(mouse, x, y, keyParam);
		}
	}

	void StopDragging(CMouse &mouse, const std::int32_t x, const std::int32_t y, const std::uint32_t keyParam) override
	{
		if (upButtonPressed || downButtonPressed)
		{
			MouseInput(mouse, C4MC_Button_LeftUp, x, y, keyParam);
		}
		else
		{
			Edit::StopDragging(mouse, x, y, keyParam);
			// A fresh-focus click must leave the whole value selected (the
			// contract established by the LeftDown select-all): the
			// drag-stop base path collapses the selection to a caret at the
			// click position, so the first typed char would replace only a
			// prefix (e.g. "178" of the default seed) instead of the whole
			// value. Restore select-all only when the button came up where
			// it went down — a real drag is the user's own selection.
			if (fFreshFocusClickPending)
			{
				fFreshFocusClickPending = false;
				if (x == iFreshFocusClickX && y == iFreshFocusClickY)
				{
					SelectAll();
				}
			}
		}
	}

	void DrawElement(C4FacetEx &cgo) override
	{
		Edit::DrawElement(cgo);
		if (arrowsRect.Wdt > 0)
		{
			static C4DrawTransform flipVerticalTransform = []{
				C4DrawTransform t;
				t.Set(1, 0, 0, 0, -1, 0, 0, 0, 1);
				return t;
			}();

			C4Facet& arrow = GetRes()->fctSpinBoxArrow;

			const auto x0 = cgo.TargetX + arrowsRect.x;
			const auto y0 = cgo.TargetY + arrowsRect.y;
			arrow.DrawT(cgo.Surface, x0 + upButtonPressed, - (y0 + upButtonPressed + arrow.Hgt), 0, 0, &flipVerticalTransform);
			arrow.Draw(cgo.Surface, x0 + downButtonPressed, y0 + arrowsRect.Hgt - arrow.Hgt + downButtonPressed);
		}
	}

	void UpdateSize() override
	{
		if (ResizeToIdealWidth())
		{
			return;
		}

		// reserve space for up-/down arrows
		auto& clientWidth = rcClientRect.Wdt;
		if (clientWidth > 30)
		{
			clientWidth -= ArrowWidth + ArrowMarginLeft + ArrowMarginRight;
			arrowsRect = {rcClientRect.x + clientWidth + ArrowMarginLeft, rcClientRect.y + ArrowMarginTop, ArrowWidth, rcClientRect.Hgt - ArrowMarginTop * 2};
		}
		else
		{
			arrowsRect = {0, 0, 0, 0};
		}
	}

	bool ResizeToIdealWidth()
	{
		const auto digits = std::max(GetNumberLength(minimum), GetNumberLength(maximum));
		const auto idealWidth = pFont->GetTextWidth(std::string(digits, '0').c_str(), false) + C4GUI_ScrollArrowWdt + 2;
		if (idealWidth < rcBounds.Wdt)
		{
			rcBounds.Wdt = idealWidth;
			SetBounds(rcBounds);
			return true;
		}

		return false;
	}

private:
	template <std::make_signed_t<T> change>
	bool OffsetValueCallback()
	{
		OffsetValue(change, true);
		return true;
	}

	void OffsetValue(const std::make_signed_t<T> change, const bool user)
	{
		const auto oldValue = GetValue();
		if (change < 0 && oldValue < limits::min() - change)
		{
			SetValue(limits::min(), user);
		}
		else if (change > 0 && oldValue > limits::max() - change)
		{
			SetValue(limits::max(), user);
		}
		else
		{
			SetValue(oldValue + change, user);
		}
		OnTextChange();
	}

	void UpdateMaxText()
	{
		SetMaxText(MaxTextLengthForRange(minimum, maximum));
	}

	static unsigned short GetNumberLength(T number)
	{
		if (number < 0)
		{
			// avoid overflow
			if (number == limits::min())
			{
				number += 1;
			}
			number = -number;
		}

		if (number == 0)
		{
			return 1;
		}
		return checked_cast<unsigned short>(std::lround(std::log10(number))) + 1 + std::signed_integral<T>;
	}

	C4Rect arrowsRect;

	// fresh-focus click bookkeeping: a LeftDown that newly granted focus
	// selects all and remembers the press position; StopDragging restores
	// the select-all for a plain click (see MouseInput/StopDragging)
	bool fFreshFocusClickPending{false};
	std::int32_t iFreshFocusClickX{0};
	std::int32_t iFreshFocusClickY{0};

	std::unique_ptr<C4KeyBinding> keyUp;
	std::unique_ptr<C4KeyBinding> keyDown;
	std::unique_ptr<C4KeyBinding> keyPageUp;
	std::unique_ptr<C4KeyBinding> keyPageDown;

	T minimum;
	T maximum;

	bool upButtonPressed{false};
	bool downButtonPressed{false};
};
}
