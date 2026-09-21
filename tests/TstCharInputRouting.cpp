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

// char_input_routing — pin for the SeedEdit typed-entry defect (cycle 159).
//
// Empirical failure (reproduced twice in cycle 158, u-series): typed chars
// did NOT insert into the seed spinbox while the SAME synthetic input does
// echo in the PlrSel rename edit. Arrows/wheel/"New" all work — only typed
// entry vanishes.
//
// Root cause (cycle-159 [CHARTRACE] diff of the two flows):
//   Flow A (SeedEdit):  '5' → Screen::CharIn → Dialog::CharIn (pActiveCtrl
//     == SeedEdit) → Edit::CharIn → InsertText REJECTS:
//       fBufferOK = (iTextLen + iTextEnd <= (iMaxTextLength - 1))
//       = (1 + 10 <= 11 - 1) = false  → iTextLen clamps to 0 → return false
//     The seed edit was initialised with a 10-digit time-based seed
//     ("1789962431"); SpinBox::UpdateMaxText sized the text field to
//     GetNumberLength(INT32_MIN/MAX) = 11, and Edit::InsertText only allows
//     iMaxTextLength - 1 = 10 characters total — so the current value itself
//     ALREADY fills the entire buffer, and any typed character is clamped
//     away. The click into the field had additionally collapsed the
//     OnGetFocus select-all to a caret (Edit::MouseInput LeftDown), so no
//     selection existed to delete-and-replace either; and because
//     Edit::CharIn returned false, Dialog::CharIn's fallback re-focused the
//     dialog's DEFAULT control, sending every subsequent typed char to the
//     wrong control (trace shows pActiveCtrl changing).
//   Flow B (rename edit): Text='Neuling' cur=7 sel=0/7 — the select-all from
//     focus SURVIVED (open-by-keyboard, no click into the field after), so
//     InsertText deleted the selection first and every typed char landed.
//
// Fix (both in C4GuiSpinBox.h):
//   1. SpinBox::UpdateMaxText now derives the edit capacity via
//      MaxTextLengthForRange(min, max) = GetNumberLength(...) + 1, because
//      Edit::InsertText enforces (iMaxTextLength - 1). The +1 gives the
//      max value string itself room AND lets a caret-insert land when the
//      field shows a full-width value (the seed at its digit cap could
//      previously never be typed into).
//   2. SpinBox::MouseInput no longer lets a click that freshly grants focus
//      collapse the OnGetFocus select-all: typed input REPLACES the value,
//      exactly like the working rename path (mouse focus behaves like
//      keyboard focus again).
//
// This pin asserts the pure capacity contract behind fix 1 (the arithmetic
// the defect reduces to), without needing the GUI resource system: the
// InsertText length check `iTextLen + iTextEnd <= iMaxTextLength - 1` is
// replayed verbatim against the spinbox-derived max text length.

#include <catch2/catch_all.hpp>

#include "C4GuiSpinBox.h"

#include <cstdint>
#include <limits>
#include <string>

namespace
{
	// Verbatim replay of Edit::InsertText's buffer check (C4GuiEdit.cpp):
	// number of insertable characters, given the current text length, the
	// incoming text length and the edit's configured max text length.
	std::size_t InsertableChars(const std::size_t iTextLen, const std::size_t iTextEnd, const std::int32_t iMaxTextLength)
	{
		auto InsertLen = iTextLen;
		const bool fBufferOK = (InsertLen + iTextEnd <= static_cast<std::size_t>(iMaxTextLength - 1));
		if (!fBufferOK) InsertLen -= iTextEnd + InsertLen - static_cast<std::size_t>(iMaxTextLength - 1);
		return InsertLen;
	}
}

TEST_CASE("CharInputRouting_SpinBoxMaxTextHeadroom", "[char-input-routing]")
{
	// The default SeedEdit/ScaleEdit spinbox range is the full int32 span.
	// The widest value string is INT32_MIN's "-2147483648" (11 chars).
	constexpr auto minInt = std::numeric_limits<std::int32_t>::min();
	constexpr auto maxInt = std::numeric_limits<std::int32_t>::max();
	REQUIRE(std::to_string(minInt).size() == 11);

	const auto maxTextLen = C4GUI::SpinBox<std::int32_t>::MaxTextLengthForRange(minInt, maxInt);

	// InsertText enforces (iMaxTextLength - 1) total characters. The max
	// value string itself must fit inside that budget (cycle 159: the
	// spinbox derived maxlen=11, InsertText allowed 10, and a 10-digit seed
	// saturated the buffer so every typed char was clamped to zero).
	REQUIRE(static_cast<std::size_t>(maxTextLen - 1) >= std::to_string(minInt).size());
	REQUIRE(static_cast<std::size_t>(maxTextLen - 1) >= std::to_string(maxInt).size());

	// Typed-entry regression, verbatim InsertText arithmetic: the observed
	// Flow-A failure was '5' into "1789962431" (10 chars) at maxlen 11 →
	// 0 insertable chars. With the headroom fix a caret-insert lands again.
	REQUIRE(InsertableChars(1, 10, maxTextLen) >= 1);       // '5' into the 10-digit seed
	REQUIRE(InsertableChars(1, 10, maxTextLen - 1) == 0);   // pre-fix sizing rejects it

	// Replacement path (select-all → DeleteSelection empties the field
	// first, i.e. iTextEnd == 0): a full-width typed value still lands —
	// this is how "55" replaces "1789962431" once focus keeps the select-all.
	REQUIRE(InsertableChars(2, 0, maxTextLen) == 2);
	REQUIRE(InsertableChars(std::to_string(minInt).size(), 0, maxTextLen) == std::to_string(minInt).size());
}

TEST_CASE("CharInputRouting_SpinBoxMaxTextSmallRanges", "[char-input-routing]")
{
	// ScaleEdit (C4StartupOptionsDlg): 100..300, three digits.
	const auto scaleTextLen = C4GUI::SpinBox<std::int32_t>::MaxTextLengthForRange(100, 300);
	REQUIRE(static_cast<std::size_t>(scaleTextLen - 1) >= 3);
	REQUIRE(InsertableChars(1, 3, scaleTextLen) >= 1);  // typing at a full 3-digit value lands

	// Port edit (C4StartupOptionsDlg) uses SetMaxText(10) explicitly after
	// construction, so the derivation result below is only the constructor
	// default; assert it stays a pure int32-style derivation (65535 is 5
	// digits → GetNumberLength = 7 → MaxTextLengthForRange = 8).
	const auto portTextLen = C4GUI::SpinBox<std::int32_t>::MaxTextLengthForRange(0, 65535);
	REQUIRE(portTextLen == 8);
	REQUIRE(InsertableChars(1, 5, portTextLen) >= 1);
}
