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
//     both locale branches (fGer-variant slots 6/9 classic, 5/8 right-hand).
// G5: SetKeyboardControlKey writes BOTH the config table and the live named
//     key (mutation: removing the RebindKey turns this RED).
// P1-P5: the existing KeyConfig.txt delta-form behavior, pinned —
//     never-rebound keys emit no entry (P1), explicitly rebound keys emit
//     theirs (P2), ResetKey-cleared keys emit none (P3), absent entries fall
//     back to DefaultCodes on load (P4), and a one-delta state resaves to an
//     INI containing ONLY the delta entry + ResetKey yields a bare [Keys]
//     section (P5) (mutation: reverting the StdNamingDefaultAdapt write-side
//     skip turns P1/P3/P5 RED).

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

#undef KEY
