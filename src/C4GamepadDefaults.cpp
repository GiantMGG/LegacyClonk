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

/* Xbox-style default gamepad binding table (spec gamepad-defaults §3.1). */

#include "C4GamepadDefaults.h" // self-include canary (rules/pch-off-compile-gate.md)

#include "C4Constants.h"   // C4MaxKey
#include "C4KeyboardInput.h" // KEY_JOY_* / KEY_Gamepad

#include <cassert>

namespace
{
	// The 12-slot layout in CON_* order (C4Constants.h:213-224):
	// CursorLeft, CursorToggle, CursorRight, Throw, Up, Dig, Left, Down,
	// Right, Menu, Special, Special2.
	//
	// Backend resolution mirrors the KEY(win, x, sdl) triple precedent
	// (C4Config.cpp:337-341): the winmm path on Windows reports the XInput
	// facade's bitmask order; every other backend feeds SDL_GameController
	// standard-mapping indices. Face buttons A/B/X/Y share indices across
	// backends; shoulders, Back/Start and R3 differ (spec §3.1).
#ifdef _WIN32
	const uint8_t GamepadDefaultLayout[C4MaxKey] =
	{
		KEY_JOY_Button(4),      // 0 CursorLeft   - LB
		KEY_JOY_Button(6),      // 1 CursorToggle - Back
		KEY_JOY_Button(5),      // 2 CursorRight  - RB
		KEY_JOY_Button(1),      // 3 Throw        - B
		KEY_JOY_Button(0),      // 4 Up           - A
		KEY_JOY_Button(2),      // 5 Dig          - X
		KEY_JOY_Axis(0, false), // 6 Left  - left stick west
		KEY_JOY_Axis(1, true),  // 7 Down  - left stick south
		KEY_JOY_Axis(0, true),  // 8 Right - left stick east
		KEY_JOY_Button(7),      // 9 Menu         - Start
		KEY_JOY_Button(3),      // 10 Special     - Y
		KEY_JOY_Button(9),      // 11 Special2    - R3
	};
#else
	const uint8_t GamepadDefaultLayout[C4MaxKey] =
	{
		KEY_JOY_Button(9),      // 0 CursorLeft   - LB
		KEY_JOY_Button(4),      // 1 CursorToggle - Back
		KEY_JOY_Button(10),     // 2 CursorRight  - RB
		KEY_JOY_Button(1),      // 3 Throw        - B
		KEY_JOY_Button(0),      // 4 Up           - A
		KEY_JOY_Button(2),      // 5 Dig          - X
		KEY_JOY_Axis(0, false), // 6 Left  - left stick west
		KEY_JOY_Axis(1, true),  // 7 Down  - left stick south
		KEY_JOY_Axis(0, true),  // 8 Right - left stick east
		KEY_JOY_Button(6),      // 9 Menu         - Start
		KEY_JOY_Button(3),      // 10 Special     - Y
		KEY_JOY_Button(8),      // 11 Special2    - R3
	};
#endif
}

int32_t GetGamepadDefaultButton(int32_t iGamepadSet, int32_t iCtrlSlot)
{
	assert(iCtrlSlot >= 0 && iCtrlSlot < C4MaxKey);
	// Compose the full keycode so each gamepad set's defaults embed its
	// own pad id (KEY_Gamepad): the winmm/SDL backends then fire matching
	// codes back through the event layer.
	return KEY_Gamepad(static_cast<uint8_t>(iGamepadSet), GamepadDefaultLayout[iCtrlSlot]);
}
