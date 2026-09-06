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

// Stage 1 unit tests for the stock control-preset registry (spec
// two-hand-control-presets, §3, G1/G2/G4).
//
// G1: every preset's 12 slots are bound to a real key with no duplicates
//     (guards the options-dialog crash invariant,
//     C4StartupOptionsDlg.cpp:254-255), on both locale branches.
// G2: the two-hand tables equal the §2.2 table exactly, on both locale
//     branches, and are fGer-invariant.
// G4: the Classic One-Hand and Right-Hand registry tables equal the literal
//     pre-flip CompileFunc defaults (C4Config.cpp:345-356 / :371-382), on
//     both locale branches (fGer-variant slots 6/9 classic, 5/8 right-hand).

#include <catch2/catch_all.hpp>

#include "C4ControlPresets.h"
#include "C4Config.h"
#include "C4Game.h"
#include "C4KeyboardInput.h"
#include "StdCompiler.h"

// Expectations are platform-resolved with the same triples the registry and
// the pre-flip CompileFunc use (C4Config.cpp:336-341). SDL2 headers ship with
// the project deps on every platform, so <SDL2/SDL.h> resolves even in
// console builds.
#ifdef USE_X11
#include <X11/keysym.h>
#elif !defined(_WIN32)
#include <SDL2/SDL.h>
#endif

#ifdef _WIN32
#define KEY(win, x, sdl) win
#elif defined(USE_X11)
#define KEY(win, x, sdl) x
#else
#define KEY(win, x, sdl) sdl
#endif

namespace
{
	// The §2.2 starter two-hand table.
	const int32_t TwoHandTable[C4MaxKey] =
	{
		KEY('Q', XK_q, SDL_SCANCODE_Q),
		KEY(VK_SPACE, XK_space, SDL_SCANCODE_SPACE),
		KEY('E', XK_e, SDL_SCANCODE_E),
		KEY('J', XK_j, SDL_SCANCODE_J),
		KEY('W', XK_w, SDL_SCANCODE_W),
		KEY('I', XK_i, SDL_SCANCODE_I),
		KEY('A', XK_a, SDL_SCANCODE_A),
		KEY('S', XK_s, SDL_SCANCODE_S),
		KEY('D', XK_d, SDL_SCANCODE_D),
		KEY('K', XK_k, SDL_SCANCODE_K),
		KEY('O', XK_o, SDL_SCANCODE_O),
		KEY('L', XK_l, SDL_SCANCODE_L),
	};

	// Literal pre-flip Kbd1 defaults (C4Config.cpp:345-356); slot 6 (Y/Z) and
	// slot 9 ('<'/R) are the fGer variants.
	const int32_t ClassicTable[C4MaxKey] =
	{
		KEY('Q', XK_q, SDL_SCANCODE_Q),
		KEY('W', XK_w, SDL_SCANCODE_W),
		KEY('E', XK_e, SDL_SCANCODE_E),
		KEY('A', XK_a, SDL_SCANCODE_A),
		KEY('S', XK_s, SDL_SCANCODE_S),
		KEY('D', XK_d, SDL_SCANCODE_D),
		KEY('Z', XK_z, SDL_SCANCODE_Z),
		KEY('X', XK_x, SDL_SCANCODE_X),
		KEY('C', XK_c, SDL_SCANCODE_C),
		KEY('R', XK_r, SDL_SCANCODE_R),
		KEY('V', XK_v, SDL_SCANCODE_V),
		KEY('F', XK_f, SDL_SCANCODE_F),
	};

	const int32_t ClassicGerTable[C4MaxKey] =
	{
		KEY('Q', XK_q, SDL_SCANCODE_Q),
		KEY('W', XK_w, SDL_SCANCODE_W),
		KEY('E', XK_e, SDL_SCANCODE_E),
		KEY('A', XK_a, SDL_SCANCODE_A),
		KEY('S', XK_s, SDL_SCANCODE_S),
		KEY('D', XK_d, SDL_SCANCODE_D),
		KEY('Y', XK_y, SDL_SCANCODE_Z),
		KEY('X', XK_x, SDL_SCANCODE_X),
		KEY('C', XK_c, SDL_SCANCODE_C),
		KEY(226, XK_less, SDL_SCANCODE_NONUSBACKSLASH),
		KEY('V', XK_v, SDL_SCANCODE_V),
		KEY('F', XK_f, SDL_SCANCODE_F),
	};

	// Literal pre-flip Kbd3 defaults (C4Config.cpp:371-382); slot 5 ('ö'/';')
	// and slot 8 ('-'/'/') are the fGer variants.
	const int32_t RightHandTable[C4MaxKey] =
	{
		KEY('I', XK_i,          SDL_SCANCODE_I),
		KEY('O', XK_o,          SDL_SCANCODE_O),
		KEY('P', XK_p,          SDL_SCANCODE_P),
		KEY('K', XK_k,          SDL_SCANCODE_K),
		KEY('L', XK_l,          SDL_SCANCODE_L),
		KEY(0xBA, XK_semicolon, SDL_SCANCODE_SEMICOLON),
		KEY(188, XK_comma,      SDL_SCANCODE_COMMA),
		KEY(190, XK_period,     SDL_SCANCODE_PERIOD),
		KEY(0xBF, XK_slash,     SDL_SCANCODE_SLASH),
		KEY('M', XK_m,          SDL_SCANCODE_M),
		KEY(222, XK_adiaeresis, SDL_SCANCODE_APOSTROPHE),
		KEY(186, XK_udiaeresis, SDL_SCANCODE_LEFTBRACKET),
	};

	const int32_t RightHandGerTable[C4MaxKey] =
	{
		KEY('I', XK_i,          SDL_SCANCODE_I),
		KEY('O', XK_o,          SDL_SCANCODE_O),
		KEY('P', XK_p,          SDL_SCANCODE_P),
		KEY('K', XK_k,          SDL_SCANCODE_K),
		KEY('L', XK_l,          SDL_SCANCODE_L),
		KEY(192, XK_odiaeresis, SDL_SCANCODE_SEMICOLON),
		KEY(188, XK_comma,      SDL_SCANCODE_COMMA),
		KEY(190, XK_period,     SDL_SCANCODE_PERIOD),
		KEY(189, XK_minus,      SDL_SCANCODE_SLASH),
		KEY('M', XK_m,          SDL_SCANCODE_M),
		KEY(222, XK_adiaeresis, SDL_SCANCODE_APOSTROPHE),
		KEY(186, XK_udiaeresis, SDL_SCANCODE_LEFTBRACKET),
	};

	bool KeysEqual(const C4ControlPreset &lhs, const C4ControlPreset &rhs)
	{
		for (int32_t i = 0; i < C4MaxKey; ++i)
			if (lhs.Keys[i] != rhs.Keys[i]) return false;
		return true;
	}
}

TEST_CASE("PresetRegistry.AllSlotsBoundNoDupes", "[control-presets]")
{
	// G1: every slot's code is a real key (not KEY_Default/0/KEY_Undefined)
	// and no code appears twice within one preset. Guards the options-dialog
	// crash invariant: "every key from 0 to C4MaxKey-1 MUST BE present here,
	// or the engine will crash" (C4StartupOptionsDlg.cpp:254-255).
	for (int32_t iPreset = 0; iPreset < C4PR_Max; ++iPreset)
	{
		for (bool fGer : { false, true })
		{
			const C4ControlPreset preset = GetPreset(iPreset, fGer);
			for (int32_t iKey = 0; iKey < C4MaxKey; ++iKey)
			{
				INFO("preset " << iPreset << " fGer " << fGer << " slot " << iKey);
				CHECK(preset.Keys[iKey] != static_cast<int32_t>(KEY_Default));
				CHECK(preset.Keys[iKey] != 0);
				CHECK(preset.Keys[iKey] != static_cast<int32_t>(KEY_Undefined));
				for (int32_t iOther = 0; iOther < iKey; ++iOther)
				{
					INFO("preset " << iPreset << " fGer " << fGer << " slots " << iOther << " vs " << iKey);
					CHECK(preset.Keys[iKey] != preset.Keys[iOther]);
				}
			}
		}
	}
}

TEST_CASE("PresetRegistry.TwoHandTablePin", "[control-presets]")
{
	// G2: C4PR_TwoHandIJKL and C4PR_TwoHandMouse both equal the §2.2 table
	// exactly (12 codes, platform-resolved), on both locale branches, and
	// differ only in MouseMode (-1 keep vs +1 force on).
	for (int32_t iPreset : { C4PR_TwoHandIJKL, C4PR_TwoHandMouse })
	{
		for (bool fGer : { false, true })
		{
			const C4ControlPreset preset = GetPreset(iPreset, fGer);
			for (int32_t iKey = 0; iKey < C4MaxKey; ++iKey)
			{
				INFO("preset " << iPreset << " fGer " << fGer << " slot " << iKey);
				CHECK(preset.Keys[iKey] == TwoHandTable[iKey]);
			}
		}
		INFO("preset " << iPreset);
		CHECK(GetPreset(iPreset, false).MouseMode == GetPreset(iPreset, true).MouseMode);
	}
	CHECK(GetPreset(C4PR_TwoHandIJKL, false).MouseMode == -1);
	CHECK(GetPreset(C4PR_TwoHandMouse, false).MouseMode == 1);

	// The two-hand table is locale-neutral: the fGer branch resolves
	// identically (locale-invariance pinned — risk R6).
	CHECK(KeysEqual(GetPreset(C4PR_TwoHandIJKL, false), GetPreset(C4PR_TwoHandIJKL, true)));
	CHECK(KeysEqual(GetPreset(C4PR_TwoHandMouse, false), GetPreset(C4PR_TwoHandMouse, true)));
}

TEST_CASE("PresetRegistry.LegacyGerParity", "[control-presets]")
{
	// G4: Classic One-Hand == the literal C4Config.cpp:345-356 transcription
	// and Right-Hand == the literal :371-382 transcription, on fGer=false AND
	// fGer=true (fGer-variant slots 6/9 classic, 5/8 right-hand). German
	// veterans keep their Y/'<' and 'ö'/'-' keys.
	const C4ControlPreset classic = GetPreset(C4PR_Classic, false);
	const C4ControlPreset classicGer = GetPreset(C4PR_Classic, true);
	for (int32_t iKey = 0; iKey < C4MaxKey; ++iKey)
	{
		INFO("classic non-German slot " << iKey);
		CHECK(classic.Keys[iKey] == ClassicTable[iKey]);
		INFO("classic German slot " << iKey);
		CHECK(classicGer.Keys[iKey] == ClassicGerTable[iKey]);
	}

	const C4ControlPreset rightHand = GetPreset(C4PR_RightHand, false);
	const C4ControlPreset rightHandGer = GetPreset(C4PR_RightHand, true);
	for (int32_t iKey = 0; iKey < C4MaxKey; ++iKey)
	{
		INFO("right-hand non-German slot " << iKey);
		CHECK(rightHand.Keys[iKey] == RightHandTable[iKey]);
		INFO("right-hand German slot " << iKey);
		CHECK(rightHandGer.Keys[iKey] == RightHandGerTable[iKey]);
	}
}

#undef KEY
