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

// Stage 1+2 unit tests for the stock control-preset registry (spec
// two-hand-control-presets, §3, G1-G5, P1-P5).
//
// G1: every preset's 12 slots are bound to a real key with no duplicates
//     (guards the options-dialog crash invariant,
//     C4StartupOptionsDlg.cpp:254-255), on both locale branches.
// G2: the two-hand tables equal the §2.2 table exactly, on both locale
//     branches, and are fGer-invariant.
// G3: ApplyPreset's restart-survival — a seeded stale KeyConfig.txt delta
//     must not be carried into the resaved file (PRIMARY assert), and layer 1
//     (the config table, re-read by InitKeyboard) carries the binding across
//     the simulated restart (SECONDARY assert).
//     (mutation: removing the ResetKey loop turns the PRIMARY assert RED)
// G4: the Classic One-Hand and Right-Hand registry tables equal the literal
//     pre-flip CompileFunc defaults (C4Config.cpp:345-356 / :371-382), on
//     both locale branches (fGer-variant slots 6/9 classic, 5/8/11 right-hand).
// G5: SetKeyboardControlKey writes BOTH the config table and the live named
//     key (mutation: removing the RebindKey turns this RED).
// P1-P5: the existing KeyConfig.txt delta-form behavior, pinned —
//     never-rebound keys emit no entry (P1), explicitly rebound keys emit
//     theirs (P2), ResetKey-cleared keys emit none (P3), absent entries fall
//     back to DefaultCodes on load (P4), and a one-delta state resaves to an
//     INI containing ONLY the delta entry + ResetKey yields a bare [Keys]
//     section (P5) (mutation: reverting the StdNamingDefaultAdapt write-side
//     skip turns P1/P3/P5 RED).
// L1: the flip wiring — ResetKeys() restores the registry Two-Hand WASD+Mouse
//     table to Kbd1 and the unchanged literal Kbd2-4 defaults.
// L2: registry ↔ CompileFunc legacy parity — the Numpad/Right-Hand/Nav-Cluster
//     presets equal the CompileFunc Kbd2/3/4 defaults read back after
//     ResetKeys(). Both SKIP under USE_CONSOLE: the console engine's
//     CompileFunc key tables are zero-filled (C4Config.cpp:335) and ResetKeys
//     is not defined there.

#include <catch2/catch_all.hpp>

#include "C4ControlPresets.h"
#include "C4Config.h"
#include "C4Game.h"
#include "C4KeyboardInput.h"
#include "C4Wrappers.h"
#include "StdCompiler.h"

#include <format>
#include <string>

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

	// Literal pre-flip Kbd3 defaults (C4Config.cpp:371-382); slots 5 ('ö'/';'),
	// 8 ('-'/'/') and 11 ('ü'/'[') are the fGer variants.
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
		KEY(0xDB, XK_udiaeresis, SDL_SCANCODE_LEFTBRACKET),
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

	// Literal Kbd2 defaults (C4Config.cpp:363-374) — locale-neutral.
	const int32_t NumpadTable[C4MaxKey] =
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

	// Literal Kbd4 defaults (C4Config.cpp:389-400) — locale-neutral.
	const int32_t NavClusterTable[C4MaxKey] =
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

	bool KeysEqual(const C4ControlPreset &lhs, const C4ControlPreset &rhs)
	{
		for (int32_t i = 0; i < C4MaxKey; ++i)
			if (lhs.Keys[i] != rhs.Keys[i]) return false;
		return true;
	}

	// Registers the 12 named keys of keyboard set iSet, mirroring the
	// C4Game.cpp:3285-3294 registration loop (nullptr callback is fine — the
	// C4CustomKey ctor guards it, C4KeyboardInput.cpp:484-489). Used both for
	// "classic registration" and the simulated-restart re-registration.
	void RegisterKbdSet(C4KeyboardInput &rInput, int32_t iSet, const int32_t (&rCodes)[C4MaxKey])
	{
		for (int32_t i = 0; i < C4MaxKey; ++i)
		{
			const std::string name = std::format("Kbd{}Key{}", iSet + 1, i + 1);
			rInput.RegisterKey(new C4CustomKey(C4KeyCodeEx(rCodes[i]), name.c_str(),
				KEYSCOPE_Control, nullptr, C4CustomKey::PRIO_PlrControl));
		}
	}

	// The exact serialization SaveCustomConfig performs (C4KeyboardInput.cpp:
	// 678-680): decompile the input to an INI string, no disk involved.
	std::string ResaveToIni(C4KeyboardInput &rInput)
	{
		StdCompilerINIWrite iniWrite;
		iniWrite.Decompile(rInput);
		return iniWrite.getOutput();
	}

	// The exact deserialization LoadCustomConfig performs (C4KeyboardInput.cpp:
	// 866): compile the INI string back into the input.
	bool LoadFromIni(C4KeyboardInput &rInput, const std::string &rIni)
	{
		return CompileFromBuf_LogWarn<StdCompilerINIRead>(rInput, StdStrBuf(rIni), "test");
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
	// fGer=true (fGer-variant slots 6/9 classic, 5/8/11 right-hand). German
	// veterans keep their Y/'<', 'ö'/'-' and 'ü'/'[' keys.
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

TEST_CASE("ApplyPreset.RestartSurvival", "[control-presets]")
{
	// G3: ApplyPreset's restart-survival — a seeded stale KeyConfig.txt delta
	// must not be carried into the resaved file, and layer 1 (the config
	// table, re-read by InitKeyboard at startup) must carry the applied
	// binding across the simulated restart. The six steps follow the plan:
	// mutation, removing the ResetKey loop from ApplyPreset, turns this RED
	// on the step-5 PRIMARY assert.
	//
	// NOTE: a real C4KeyCodeEx delta is written quoted (RCT_Escaped) but read
	// back via RCT_Idtf, which cannot consume a leading '"' — so a delta does
	// not survive a load; the effective key falls back to its default. Layer 1
	// is therefore what carries the applied preset across a restart. The
	// ResetKey loop guarantees the resaved KeyConfig.txt carries NO stale
	// delta, which is the property pinned in step 5.

	// A code in neither the classic nor the two-hand table: seeds the stale delta.
	const int32_t staleCode = KEY('T', XK_t, SDL_SCANCODE_T);
	const C4ControlPreset twoHand = GetPreset(C4PR_TwoHandMouse, false);
	const C4ControlPreset classic = GetPreset(C4PR_Classic, false);

	// (1) Fresh global input, registered with the classic table.
	Game.KeyboardInput.Clear();
	RegisterKbdSet(Game.KeyboardInput, 0, classic.Keys);

	// (2) Seed a stale delta on Kbd1Key7.
	C4CustomKey *pKey7 = Game.KeyboardInput.GetKeyByName("Kbd1Key7");
	REQUIRE(pKey7);
	C4CustomKey::CodeList staleCodes;
	staleCodes.push_back(C4KeyCodeEx(staleCode));
	Game.KeyboardInput.RebindKey(pKey7, staleCodes);

	// (3) Apply the two-hand preset to keyboard set 0 (table write + ResetKey x 12).
	REQUIRE(ApplyPreset(0, twoHand));

	// (4) Resave: SaveCustomConfig-shaped decompile, no disk.
	const std::string saved = ResaveToIni(Game.KeyboardInput);

	// (5) PRIMARY ASSERT (mutation discriminator): the resave contains NO
	// Kbd1Key7 entry — after ResetKey, Codes == {} and the writer drops
	// empty-Codes entries. Without the ResetKey loop the stale delta would
	// survive the resave (Kbd1Key7="t") and this assert goes RED.
	CHECK(saved.find("Kbd1Key7") == std::string::npos);
	CHECK(saved.find('=') == std::string::npos);

	// (6) SECONDARY (documents the truthful end state): simulate restart —
	// re-register the 12 keys from the NEW table (what InitKeyboard does,
	// C4Game.cpp:3289-3293), then load the saved INI back. All 12 effective
	// codes must equal the applied two-hand table.
	Game.KeyboardInput.Clear();
	RegisterKbdSet(Game.KeyboardInput, 0, Config.Controls.Keyboard[0]);
	REQUIRE(LoadFromIni(Game.KeyboardInput, saved));
	for (int32_t i = 0; i < C4MaxKey; ++i)
	{
		INFO("slot " << i);
		C4CustomKey *pKey = Game.KeyboardInput.GetKeyByName(std::format("Kbd1Key{}", i + 1).c_str());
		REQUIRE(pKey);
		CHECK(pKey->GetCodes().front().Key == static_cast<C4KeyCode>(twoHand.Keys[i]));
	}
}

TEST_CASE("KeyConfigDeltaForm.NeverReboundWritesNothing", "[control-presets]")
{
	// P1: a never-rebound key (Codes == DefaultCodes — the post-load
	// fallback state, StdAdaptors.h:126) emits no INI entry. The empty-[Keys]
	// load puts every key into that default-equal state (what LoadCustomConfig
	// does for absent entries). Mutation: reverting the
	// StdNamingDefaultAdapt write-side skip turns this RED.
	C4KeyboardInput input;
	RegisterKbdSet(input, 0, ClassicTable);
	REQUIRE(LoadFromIni(input, "[Keys]\r\n"));

	const std::string out = ResaveToIni(input);
	CHECK(out.find('=') == std::string::npos); // no entries at all
}

TEST_CASE("KeyConfigDeltaForm.ReboundKeyEmitsEntry", "[control-presets]")
{
	// P2: an explicitly rebound key (Codes != DefaultCodes) emits its entry.
	C4KeyboardInput input;
	RegisterKbdSet(input, 0, ClassicTable);

	C4CustomKey *pKey = input.GetKeyByName("Kbd1Key2");
	REQUIRE(pKey);
	C4CustomKey::CodeList codes;
	codes.push_back(C4KeyCodeEx(KEY('T', XK_t, SDL_SCANCODE_T)));
	input.RebindKey(pKey, codes);

	const std::string out = ResaveToIni(input);
	CHECK(out.find("Kbd1Key2=") != std::string::npos);
}

TEST_CASE("KeyConfigDeltaForm.ResetKeyedWritesNothing", "[control-presets]")
{
	// P3: a ResetKey-cleared key (Codes == {}) emits nothing, even after a
	// previous rebind created a delta. The sibling keys stay default-equal
	// (post-load fallback) so the write-side skip must silence them.
	// Mutation: reverting the write-side default skip turns this RED (the
	// default-equal sibling keys then write).
	C4KeyboardInput input;
	RegisterKbdSet(input, 0, ClassicTable);
	REQUIRE(LoadFromIni(input, "[Keys]\r\n"));

	C4CustomKey *pKey = input.GetKeyByName("Kbd1Key2");
	REQUIRE(pKey);
	C4CustomKey::CodeList codes;
	codes.push_back(C4KeyCodeEx(KEY('T', XK_t, SDL_SCANCODE_T)));
	input.RebindKey(pKey, codes);

	input.ResetKey(input.GetKeyByName("Kbd1Key2"));

	const std::string out = ResaveToIni(input);
	CHECK(out.find('=') == std::string::npos);
	CHECK(out.find("Kbd1Key2") == std::string::npos);
}

TEST_CASE("KeyConfigDeltaForm.AbsentEntryFallsBackToDefault", "[control-presets]")
{
	// P4: on load, an absent entry falls back to Codes = DefaultCodes
	// (StdAdaptors.h:126) — the key keeps working with its registered
	// default, and a later save still skips it as default-equal.
	C4KeyboardInput input;
	RegisterKbdSet(input, 0, ClassicTable);

	REQUIRE(LoadFromIni(input, "[Keys]\r\n"));

	for (int32_t i = 0; i < C4MaxKey; ++i)
	{
		INFO("slot " << i);
		C4CustomKey *pKey = input.GetKeyByName(std::format("Kbd1Key{}", i + 1).c_str());
		REQUIRE(pKey);
		CHECK(pKey->GetCodes().front().Key == static_cast<C4KeyCode>(ClassicTable[i]));
	}

	// The loaded-in fallback state is default-equal: a resave emits no entries.
	const std::string out = ResaveToIni(input);
	CHECK(out.find('=') == std::string::npos);
}

TEST_CASE("KeyConfigDeltaForm.OneDeltaStateResavesToDeltaOnly", "[control-presets]")
{
	// P5 (a): a one-delta state resaves to an INI containing ONLY the delta
	// entry — the 11 default-equal siblings are skipped by the write-side
	// default check (StdAdaptors.h:109-115). Mutation: reverting the
	// write-side skip turns this RED (the sibling keys then leak entries).
	//
	// NOTE: the written delta does NOT survive a load — the value is written
	// quoted (RCT_Escaped) but read back via RCT_Idtf, which cannot consume
	// a leading '"', so the entry is dropped at load (and the effective key
	// falls back to its default). Therefore a load->save byte-identity is
	// mechanically impossible and is deliberately NOT asserted here (plan
	// amendment, 2026-09-06).
	C4KeyboardInput input;
	RegisterKbdSet(input, 0, ClassicTable);
	REQUIRE(LoadFromIni(input, "[Keys]\r\n")); // siblings -> default-equal

	C4CustomKey *pKey = input.GetKeyByName("Kbd1Key2");
	REQUIRE(pKey);
	C4CustomKey::CodeList codes;
	codes.push_back(C4KeyCodeEx(KEY('T', XK_t, SDL_SCANCODE_T)));
	input.RebindKey(pKey, codes);

	const std::string s1 = ResaveToIni(input);
	CHECK(s1.find("Kbd1Key2=") != std::string::npos); // the delta entry
	for (int32_t i = 0; i < C4MaxKey; ++i)
	{
		if (i == 1) continue; // slot 1 (Kbd1Key2) is the one delta
		INFO("sibling slot " << i);
		CHECK(s1.find(std::format("Kbd1Key{}=", i + 1)) == std::string::npos);
	}
}

TEST_CASE("KeyConfigDeltaForm.ResetYieldsBareKeysSection", "[control-presets]")
{
	// P5 (b): after ResetKey on the rebound key + resave, the file is just
	// the [Keys] section — the stale delta entry is dropped. Mutation:
	// reverting the write-side skip turns this RED (the still-default
	// sibling keys write their entries).
	C4KeyboardInput input;
	RegisterKbdSet(input, 0, ClassicTable);
	REQUIRE(LoadFromIni(input, "[Keys]\r\n")); // siblings -> default-equal

	C4CustomKey *pKey = input.GetKeyByName("Kbd1Key2");
	REQUIRE(pKey);
	C4CustomKey::CodeList codes;
	codes.push_back(C4KeyCodeEx(KEY('T', XK_t, SDL_SCANCODE_T)));
	input.RebindKey(pKey, codes);
	input.ResetKey(input.GetKeyByName("Kbd1Key2"));

	const std::string out = ResaveToIni(input);
	CHECK(out.find('=') == std::string::npos);
	CHECK(out.find("Kbd1Key2") == std::string::npos);
}

// --- R-series: the KeyConfig.txt round trip (spec
// bindings-persistence-roundtrip-fix, cycle 116) --------------------------
//
// SaveCustomConfig writes every [Keys] delta token quoted (RCT_Escaped);
// the read side consumed bare identifiers only (RCT_Idtf) — a quoted token
// threw NotFound at the '"', the container adapt swallowed it per-element,
// and the delta silently dropped (the key fell back to its default). The
// fix (C4KeyCodeEx::CompileFunc) retries the quoted form. The expected
// code is the PLATFORM round-trip String2KeyCode(KeyCode2String(code)) —
// the console build's stub resolves both sides to KEY_Default, so the
// pins hold there by construction.

TEST_CASE("KeyConfigRoundtrip.RebindSurvivesRestart", "[control-presets]")
{
	// R1 (RED-first discriminator): rebind -> save -> fresh registration ->
	// load -> assert code identity. RED on the unfixed tree: the load
	// returns true but the quoted delta is dropped per-element and the key
	// falls back to its registered default (probe, spec §0.3). The
	// register -> load-empty-[Keys] -> rebind sequence is the exact P5(a)
	// state machine: it puts the 11 siblings into the default-equal
	// post-load state so the save emits ONLY the one delta (production
	// shape — SaveCustomConfig always runs after a LoadCustomConfig).
	C4KeyboardInput input;
	RegisterKbdSet(input, 0, ClassicTable);
	REQUIRE(LoadFromIni(input, "[Keys]\r\n")); // siblings -> default-equal

	C4CustomKey *pKey = input.GetKeyByName("Kbd1Key2");
	REQUIRE(pKey);
	C4CustomKey::CodeList codes;
	codes.push_back(C4KeyCodeEx(KEY('T', XK_t, SDL_SCANCODE_T)));
	input.RebindKey(pKey, codes);

	const std::string saved = ResaveToIni(input);

	C4KeyboardInput input2;
	RegisterKbdSet(input2, 0, ClassicTable);
	REQUIRE(LoadFromIni(input2, saved));

	C4CustomKey *pKey2 = input2.GetKeyByName("Kbd1Key2");
	REQUIRE(pKey2);
	REQUIRE_FALSE(pKey2->GetCodes().empty());
	const C4KeyCode expected = C4KeyCodeEx::String2KeyCode(
		StdStrBuf(C4KeyCodeEx::KeyCode2String(KEY('T', XK_t, SDL_SCANCODE_T), false, false)));
	CHECK(pKey2->GetCodes().front().Key == expected);
}

TEST_CASE("SetKeyboardControlKey.WritesBothLayers", "[control-presets]")
{
	// G5: the old-editor fix primitive must write the config-table slot AND
	// rebind the live named key. Mutation: removing the RebindKey call turns
	// this RED (the named key keeps its stale codes — the old-editor bug).
	Game.KeyboardInput.Clear();

	const int32_t code = KEY('T', XK_t, SDL_SCANCODE_T);
	C4CustomKey::CodeList defCodes;
	defCodes.push_back(C4KeyCodeEx(ClassicTable[2]));
	Game.KeyboardInput.RegisterKey(new C4CustomKey(defCodes, "Kbd2Key3",
		KEYSCOPE_Control, nullptr, C4CustomKey::PRIO_PlrControl));

	SetKeyboardControlKey(1, 2, code);

	// (a) Layer 1: the config-table write.
	CHECK(Config.Controls.Keyboard[1][2] == code);
	// (b) Layer 2: the live named key carries the new code.
	C4CustomKey *pKey = Game.KeyboardInput.GetKeyByName("Kbd2Key3");
	REQUIRE(pKey);
	REQUIRE_FALSE(pKey->GetCodes().empty());
	CHECK(pKey->GetCodes().front().Key == static_cast<C4KeyCode>(code));
}

TEST_CASE("FreshDefaults.FlipWiringL1", "[control-presets]")
{
	// L1 (the flip wiring, spec §3): Config.Controls.ResetKeys() restores
	// the CompileFunc defaults — which after the flip are the single-sourced
	// registry Two-Hand WASD+Mouse table for Kbd1 (spec §2.7) and the
	// unchanged literal Kbd2-4 defaults. A hand-duplicated Kbd1 default that
	// drifts from the registry fails here. (See §4.7: resetting now flips a
	// classic Kbd1 to two-hand.)
#ifdef USE_CONSOLE
	SKIP("console build: CompileFunc key tables are zero-filled (F5)");
#else
	Config.Controls.ResetKeys();

	// Kbd1 == C4PR_TwoHandMouse on both locale branches (the two-hand table
	// is locale-neutral by construction — no QWERTZ variants).
	for (bool fGer : { false, true })
	{
		const C4ControlPreset twoHand = GetPreset(C4PR_TwoHandMouse, fGer);
		for (int32_t iKey = 0; iKey < C4MaxKey; ++iKey)
		{
			INFO("Kbd1 fGer " << fGer << " slot " << iKey);
			CHECK(Config.Controls.Keyboard[0][iKey] == twoHand.Keys[iKey]);
		}
	}

	// Kbd2-4 == the literal CompileFunc defaults, resolved the same way
	// CompileFunc does for the fGer-sensitive Kbd3 slots 5/8/11.
	const int32_t (&rKbd3)[C4MaxKey] = isGermanSystem() ? RightHandGerTable : RightHandTable;
	for (int32_t iKey = 0; iKey < C4MaxKey; ++iKey)
	{
		INFO("Kbd2 slot " << iKey);
		CHECK(Config.Controls.Keyboard[1][iKey] == NumpadTable[iKey]);
		INFO("Kbd3 slot " << iKey);
		CHECK(Config.Controls.Keyboard[2][iKey] == rKbd3[iKey]);
		INFO("Kbd4 slot " << iKey);
		CHECK(Config.Controls.Keyboard[3][iKey] == NavClusterTable[iKey]);
	}
#endif
}

TEST_CASE("FreshDefaults.LegacyParityL2", "[control-presets]")
{
	// L2 (registry ↔ CompileFunc legacy parity, spec §3): the registry
	// Numpad/Right-Hand/Nav-Cluster presets equal the CompileFunc Kbd2/3/4
	// defaults read back after ResetKeys(). A registry transcription that
	// drifts from the CompileFunc literals (or a CompileFunc change left
	// unmirrored in the registry) fails here.
#ifdef USE_CONSOLE
	SKIP("console build: CompileFunc key tables are zero-filled (F5)");
#else
	const bool fGer = isGermanSystem(); // what CompileFunc resolved during ResetKeys()
	Config.Controls.ResetKeys();

	for (int32_t iPreset : { C4PR_Numpad, C4PR_RightHand, C4PR_NavCluster })
	{
		const C4ControlPreset preset = GetPreset(iPreset, fGer);
		for (int32_t iKey = 0; iKey < C4MaxKey; ++iKey)
		{
			INFO("preset " << iPreset << " slot " << iKey);
			CHECK(preset.Keys[iKey] == Config.Controls.Keyboard[iPreset][iKey]);
		}
	}
#endif
}

#undef KEY
