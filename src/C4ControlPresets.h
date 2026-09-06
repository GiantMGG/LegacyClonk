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
 *
 * To redistribute this file separately, substitute the full license texts
 * for the above references.
 */

/* Stock keyboard control presets (spec two-hand-control-presets, §2.1) */

#ifndef INC_C4ControlPresets
#define INC_C4ControlPresets

#include "C4Constants.h"

#include <cstdint>

// One stock control preset: a full 12-slot key table + a mouse recommendation.
struct C4ControlPreset
{
	const char *szID;          // stable registry identifier
	const char *szName;        // picker caption
	const char *szDescription; // picker tooltip
	int32_t Keys[C4MaxKey];    // per-slot key codes (platform + locale resolved)
	int32_t MouseMode;         // -1 keep player's setting, 0 force off, 1 force on
};

// Stable indices (the flip and the tests address presets by these).
enum C4ControlPresetId
{
	C4PR_None         = -1, // "keep current" placeholder for pickers
	C4PR_Classic      = 0,  // Classic One-Hand (pre-flip Kbd1, fGer-aware)
	C4PR_Numpad       = 1,  // Numpad (Kbd2)
	C4PR_RightHand    = 2,  // Right-Hand (Kbd3, fGer-aware)
	C4PR_NavCluster   = 3,  // Nav Cluster (Kbd4)
	C4PR_TwoHandIJKL  = 4,  // Two-Hand WASD+IJKL
	C4PR_TwoHandMouse = 5,  // Two-Hand WASD+Mouse (the fresh-install default)
	C4PR_Max          = 6
};

// isGermanSystem() is defined in C4Config.cpp; forward-declared here so the
// default argument of GetPreset resolves. Definition stays in C4Config.cpp.
bool isGermanSystem();

int32_t GetPresetCount();                       // == C4PR_Max
C4ControlPreset GetPreset(int32_t iIndex, bool fGer = isGermanSystem());

// Writes BOTH in-memory layers for keyboard set iSet (0..C4MaxKeyboardSet-1):
// 1. the config table  Config.Controls.Keyboard[iSet][0..11]
// 2. the named-key registry: ResetKey on each Kbd{iSet+1}Key{1..12} live named key,
//    which drops their KeyConfig.txt override deltas on the next SaveCustomConfig.
// Disk persistence is the call-site's job (Options tail / properties-dialog saves).
bool ApplyPreset(int32_t iSet, const C4ControlPreset &rPreset);

// The old-editor fix primitive: writes the config-table slot AND RebindKeys the
// live named key (mirrors what the BindingsTab rebind does).
void SetKeyboardControlKey(int32_t iSet, int32_t iKey, int32_t iKeyCode);

#endif
