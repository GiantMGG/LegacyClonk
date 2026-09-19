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

/* Xbox-style default gamepad binding table (spec gamepad-defaults §3.1).
 * One layout, two backend-resolved variants: SDL_GameController
 * standard-mapping indices (Linux/macOS) and the winmm XInput-facade
 * bitmask order (Windows). Console-safe: pure integer tables. */

#ifndef INC_C4GamepadDefaults
#define INC_C4GamepadDefaults

#include <cstdint>

// The full KEY_Gamepad keycode for control slot iCtrlSlot of gamepad set
// iGamepadSet (0..C4ConfigMaxGamepads-1): the CompileFunc INI default for
// Config.Gamepads[iGamepadSet].Button[iCtrlSlot].
int32_t GetGamepadDefaultButton(int32_t iGamepadSet, int32_t iCtrlSlot);

#endif
