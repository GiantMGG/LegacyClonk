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

/* Stock keyboard control presets (spec two-hand-control-presets, §2.1/§2.2) */

#include "C4ControlPresets.h"

#include <cstring>

// Keysym/scancode declarations, platform-resolved exactly like the
// C4Config.cpp:336-341 precedent. SDL2 headers ship with the project deps on
// every platform, so <SDL2/SDL.h> resolves even in console builds; X11 builds
// get their keysyms from the system X11 headers.
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
	// Per-preset storage: the base (non-German) table plus the German variant
	// (identical to the base table for locale-neutral presets). Tables are in
	// CON_* slot order (C4Constants.h): CursorLeft, CursorToggle, CursorRight,
	// Throw, Up, Dig, Left, Down, Right, Menu, Special, Special2.
	struct PresetTable
	{
		const char *szID;
		const char *szName;
		const char *szDescription;
		int32_t Keys[C4MaxKey];
		int32_t KeysGer[C4MaxKey];
		int32_t MouseMode;

		constexpr PresetTable(const char *pID, const char *pName, const char *pDescription,
		                      const int32_t (&rKeys)[C4MaxKey], const int32_t (&rKeysGer)[C4MaxKey],
		                      int32_t iMouseMode)
			: szID(pID), szName(pName), szDescription(pDescription), MouseMode(iMouseMode)
		{
			for (int32_t i = 0; i < C4MaxKey; ++i)
			{
				Keys[i] = rKeys[i];
				KeysGer[i] = rKeysGer[i];
			}
		}
	};

	// The starter two-hand table (spec §2.2): shared by C4PR_TwoHandIJKL and
	// C4PR_TwoHandMouse — they differ ONLY in MouseMode. Locale-neutral by
	// construction (no Y/Z, '<', ';', no umlaut dependencies).
	constexpr int32_t TwoHandKeys[C4MaxKey] =
	{
		KEY('Q', XK_q, SDL_SCANCODE_Q),               // CursorLeft
		KEY(VK_SPACE, XK_space, SDL_SCANCODE_SPACE),  // CursorToggle
		KEY('E', XK_e, SDL_SCANCODE_E),               // CursorRight
		KEY('J', XK_j, SDL_SCANCODE_J),               // Throw
		KEY('W', XK_w, SDL_SCANCODE_W),               // Up
		KEY('I', XK_i, SDL_SCANCODE_I),               // Dig
		KEY('A', XK_a, SDL_SCANCODE_A),               // Left
		KEY('S', XK_s, SDL_SCANCODE_S),               // Down
		KEY('D', XK_d, SDL_SCANCODE_D),               // Right
		KEY('K', XK_k, SDL_SCANCODE_K),               // Menu
		KEY('O', XK_o, SDL_SCANCODE_O),               // Special
		KEY('L', XK_l, SDL_SCANCODE_L),               // Special2
	};

	// Legacy presets transcribed line-for-line from the pre-flip CompileFunc
	// defaults (spec §2.2): Classic = Kbd1 (C4Config.cpp:345-356, fGer-variant
	// slots 6 and 9), Numpad = Kbd2 (:358-369), Right-Hand = Kbd3 (:371-382,
	// fGer-variant slots 5 and 8), Nav Cluster = Kbd4 (:384-395).
	constexpr int32_t ClassicKeys[C4MaxKey] =
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

	constexpr int32_t ClassicKeysGer[C4MaxKey] =
	{
		KEY('Q', XK_q, SDL_SCANCODE_Q),
		KEY('W', XK_w, SDL_SCANCODE_W),
		KEY('E', XK_e, SDL_SCANCODE_E),
		KEY('A', XK_a, SDL_SCANCODE_A),
		KEY('S', XK_s, SDL_SCANCODE_S),
		KEY('D', XK_d, SDL_SCANCODE_D),
		KEY('Y', XK_y, SDL_SCANCODE_Z),               // QWERTZ: Y/Z slot
		KEY('X', XK_x, SDL_SCANCODE_X),
		KEY('C', XK_c, SDL_SCANCODE_C),
		KEY(226, XK_less, SDL_SCANCODE_NONUSBACKSLASH), // QWERTZ: '<' next to shift
		KEY('V', XK_v, SDL_SCANCODE_V),
		KEY('F', XK_f, SDL_SCANCODE_F),
	};

	constexpr int32_t NumpadKeys[C4MaxKey] =
	{
		KEY(103, XK_KP_Home,      SDL_SCANCODE_KP_7),
		KEY(104, XK_KP_Up,        SDL_SCANCODE_KP_8),
		KEY(105, XK_KP_Page_Up,   SDL_SCANCODE_KP_9),
		KEY(100, XK_KP_Left,      SDL_SCANCODE_KP_4),
		KEY(101, XK_KP_Begin,     SDL_SCANCODE_KP_5),
		KEY(102, XK_KP_Right,     SDL_SCANCODE_KP_6),
		KEY( 97, XK_KP_End,       SDL_SCANCODE_KP_1),
		KEY( 98, XK_KP_Down,      SDL_SCANCODE_KP_2),
		KEY( 99, XK_KP_Page_Down, SDL_SCANCODE_KP_3),
		KEY( 96, XK_KP_Insert,    SDL_SCANCODE_KP_0),
		KEY(110, XK_KP_Delete,    SDL_SCANCODE_KP_PERIOD),
		KEY(107, XK_KP_Add,       SDL_SCANCODE_KP_PLUS),
	};

	constexpr int32_t RightHandKeys[C4MaxKey] =
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

	constexpr int32_t RightHandKeysGer[C4MaxKey] =
	{
		KEY('I', XK_i,          SDL_SCANCODE_I),
		KEY('O', XK_o,          SDL_SCANCODE_O),
		KEY('P', XK_p,          SDL_SCANCODE_P),
		KEY('K', XK_k,          SDL_SCANCODE_K),
		KEY('L', XK_l,          SDL_SCANCODE_L),
		KEY(192, XK_odiaeresis, SDL_SCANCODE_SEMICOLON), // QWERTZ: 'ö'
		KEY(188, XK_comma,      SDL_SCANCODE_COMMA),
		KEY(190, XK_period,     SDL_SCANCODE_PERIOD),
		KEY(189, XK_minus,      SDL_SCANCODE_SLASH),     // QWERTZ: '-' on the slash slot
		KEY('M', XK_m,          SDL_SCANCODE_M),
		KEY(222, XK_adiaeresis, SDL_SCANCODE_APOSTROPHE),
		KEY(186, XK_udiaeresis, SDL_SCANCODE_LEFTBRACKET),
	};

	constexpr int32_t NavClusterKeys[C4MaxKey] =
	{
		KEY(VK_INSERT, XK_Insert,    SDL_SCANCODE_INSERT),
		KEY(VK_HOME,   XK_Home,      SDL_SCANCODE_HOME),
		KEY(VK_PRIOR,  XK_Page_Up,   SDL_SCANCODE_PAGEUP),
		KEY(VK_DELETE, XK_Delete,    SDL_SCANCODE_DELETE),
		KEY(VK_UP,     XK_Up,        SDL_SCANCODE_UP),
		KEY(VK_NEXT,   XK_Page_Down, SDL_SCANCODE_PAGEDOWN),
		KEY(VK_LEFT,   XK_Left,      SDL_SCANCODE_LEFT),
		KEY(VK_DOWN,   XK_Down,      SDL_SCANCODE_DOWN),
		KEY(VK_RIGHT,  XK_Right,     SDL_SCANCODE_RIGHT),
		KEY(VK_END,    XK_End,       SDL_SCANCODE_END),
		KEY(VK_RETURN, XK_Return,    SDL_SCANCODE_RETURN),
		KEY(VK_BACK,   XK_BackSpace, SDL_SCANCODE_BACKSPACE),
	};

	constexpr PresetTable PresetTables[C4PR_Max] =
	{
		{
			"Classic", "Classic One-Hand",
			"The traditional single-hand Clonk layout (QWERTZ-aware)",
			ClassicKeys, ClassicKeysGer, -1
		},
		{
			"Numpad", "Numpad",
			"Full control from the numpad, right hand",
			NumpadKeys, NumpadKeys, -1
		},
		{
			"RightHand", "Right-Hand",
			"Action cluster on the right hand (QWERTZ-aware)",
			RightHandKeys, RightHandKeysGer, -1
		},
		{
			"NavCluster", "Nav Cluster",
			"Navigation-cluster keys (Insert/Home/Delete/arrows)",
			NavClusterKeys, NavClusterKeys, -1
		},
		{
			"TwoHandIJKL", "Two-Hand WASD+IJKL",
			"WASD movement with an IJKL+O action cluster",
			TwoHandKeys, TwoHandKeys, -1
		},
		{
			"TwoHandMouse", "Two-Hand WASD+Mouse",
			"WASD movement, right-hand action keys, mouse aiming enabled",
			TwoHandKeys, TwoHandKeys, 1
		},
	};
}

int32_t GetPresetCount()
{
	return C4PR_Max;
}

C4ControlPreset GetPreset(int32_t iIndex, bool fGer)
{
	if (iIndex < 0 || iIndex >= C4PR_Max) return {};
	const PresetTable &rTable = PresetTables[iIndex];
	C4ControlPreset preset;
	preset.szID = rTable.szID;
	preset.szName = rTable.szName;
	preset.szDescription = rTable.szDescription;
	preset.MouseMode = rTable.MouseMode;
	std::memcpy(preset.Keys, fGer ? rTable.KeysGer : rTable.Keys, sizeof(preset.Keys));
	return preset;
}

#undef KEY
