// Pins for the default gamepad binding table (spec gamepad-defaults §5).
//
// G1 pins the registry layout: every slot of every set bound to a valid
// KEY_Gamepad code with the owning set's pad id embedded, no duplicates,
// and the literal §3.1 face/movement layout respected (mutation: a
// misspelled slot or a lost pad-id embedding turns this RED).
// G2 pins the CompileFunc-default application: Reset() restores the
// table, and the INI load path defaults absent per-slot entries while
// explicitly saved entries keep winning (spec §3.3).
// G3 (SDL builds; appended in Task 2) drives the real
// FeedEvent -> Game.DoKeyboardInput -> named-key path with synthesized
// SDL_CONTROLLER* events: the no-hardware proxy for "press A -> jump
// fires".

#include <catch2/catch_all.hpp>

#include "C4Config.h"
#include "C4Constants.h"
#include "C4Game.h"
#include "C4GamepadDefaults.h"
#include "C4KeyboardInput.h"

#ifdef USE_SDL_FOR_GAMEPAD
#include "C4GamePadCon.h"
#include <SDL2/SDL.h>
#endif

#include <filesystem>
#include <fstream>
#include <set>

namespace
{
	// The literal expected layout (spec §3.1), backend-resolved like the
	// KEY(win, x, sdl) triple (C4Config.cpp:337-341): winmm XInput-facade
	// indices on Windows, SDL_GameController standard-mapping indices
	// elsewhere. CON_* slot order.
	const uint8_t ExpectedLayout[C4MaxKey] =
	{
#ifdef _WIN32
		KEY_JOY_Button(4),      // 0 CursorLeft   - LB
		KEY_JOY_Button(6),      // 1 CursorToggle - Back
		KEY_JOY_Button(5),      // 2 CursorRight  - RB
		KEY_JOY_Button(1),      // 3 Throw        - B
		KEY_JOY_Button(0),      // 4 Up           - A
		KEY_JOY_Button(2),      // 5 Dig          - X
		KEY_JOY_Axis(0, false), // 6 Left  - left stick west
		KEY_JOY_Axis(1, true),  // 7 Down  - left stick south (screen-down = axis max)
		KEY_JOY_Axis(0, true),  // 8 Right - left stick east
		KEY_JOY_Button(7),      // 9 Menu         - Start
		KEY_JOY_Button(3),      // 10 Special     - Y
		KEY_JOY_Button(9),      // 11 Special2    - R3
#else
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
#endif
	};

	// INI fixture writer (TstC4ConfigMigration pattern).
	std::filesystem::path WriteFixture(const std::string &tag, const std::string &contents)
	{
		const auto path = std::filesystem::temp_directory_path()
			/ ("gamepad_defaults_" + tag + ".cfg");
		std::ofstream out{path, std::ios::binary};
		out << contents;
		out.close();
		return path;
	}
}

TEST_CASE("GamepadDefaults.TablePinG1", "[gamepad-defaults]")
{
	for (int32_t iSet = 0; iSet < C4ConfigMaxGamepads; ++iSet)
	{
		std::set<int32_t> codes;
		for (int32_t iSlot = 0; iSlot < C4MaxKey; ++iSlot)
		{
			INFO("set " << iSet << " slot " << iSlot);
			const int32_t code = GetGamepadDefaultButton(iSet, iSlot);
			CHECK(code != -1);                    // bound, not unbound (spec §5 G1)
			CHECK(Key_IsGamepad(code));           // a gamepad keycode
			CHECK(Key_GetGamepad(code) == iSet);  // owning set's pad id embedded
			CHECK(Key_GetGamepadButton(code) == ExpectedLayout[iSlot]); // literal layout
			CHECK(codes.insert(code).second);     // no duplicate codes per set
		}
	}
}

TEST_CASE("GamepadDefaults.ResetRestoresTableG2", "[gamepad-defaults]")
{
	for (int32_t iSet = 0; iSet < C4ConfigMaxGamepads; ++iSet)
	{
		Config.Gamepads[iSet].Reset();
		for (int32_t iSlot = 0; iSlot < C4MaxKey; ++iSlot)
		{
			INFO("set " << iSet << " slot " << iSlot);
			CHECK(Config.Gamepads[iSet].Button[iSlot]
				== KEY_Gamepad(static_cast<uint8_t>(iSet), ExpectedLayout[iSlot]));
		}
	}
}

TEST_CASE("GamepadDefaults.IniLoadSideDefaultsG2", "[gamepad-defaults]")
{
	// Absent entries load the new defaults; an explicitly saved entry wins
	// per-slot (spec §3.3). The fixture covers both: [Gamepad0] entirely
	// absent (whole-table defaulting), [Gamepad1] with one explicit save.
	const auto path = WriteFixture("g2",
		"[Gamepad1]\n"
		"Button5=12345\n");
	REQUIRE(Config.Load(false, path.string().c_str()));

	// Gamepad0: section absent -> every slot loads its default, pad 0 embedded.
	for (int32_t iSlot = 0; iSlot < C4MaxKey; ++iSlot)
	{
		INFO("Gamepad0 slot " << iSlot);
		CHECK(Config.Gamepads[0].Button[iSlot] == KEY_Gamepad(0, ExpectedLayout[iSlot]));
	}

	// Gamepad1: slot 4 ("Button5") explicitly saved -> wins over the default.
	CHECK(Config.Gamepads[1].Button[4] == 12345);

	// Every other slot defaulted with pad 1's id embedded (pins the
	// pad-index threading; a lost index turns sets 1-3 into pad-0 copies).
	for (int32_t iSlot = 0; iSlot < C4MaxKey; ++iSlot)
	{
		if (iSlot == 4) continue;
		INFO("Gamepad1 slot " << iSlot);
		CHECK(Config.Gamepads[1].Button[iSlot] == KEY_Gamepad(1, ExpectedLayout[iSlot]));
	}
}

TEST_CASE("GamepadDefaults.IniLoadMigratesExplicitMinusOneG2", "[gamepad-defaults]")
{
	// Upgrade path (cycle-148 review B1): configs written before the
	// default table existed saved an explicit -1 ("unbound") for every
	// untouched slot (the v370-and-earlier writer had no default filter,
	// and the pre-cycle defaults were all -1). A present `ButtonN=-1` key
	// beats the CompileFunc default, so without a migration upgrading
	// players would never see the new table. The migration replaces a
	// loaded -1 with the registry default (pad id embedded); an explicitly
	// saved non--1 value still wins.
	const auto path = WriteFixture("g2m1",
		"[Gamepad1]\n"
		"Button3=-1\n"
		"Button5=12345\n");
	REQUIRE(Config.Load(false, path.string().c_str()));

	// Gamepad0: section absent -> every slot loads its default, pad 0 embedded.
	for (int32_t iSlot = 0; iSlot < C4MaxKey; ++iSlot)
	{
		INFO("Gamepad0 slot " << iSlot);
		CHECK(Config.Gamepads[0].Button[iSlot] == KEY_Gamepad(0, ExpectedLayout[iSlot]));
	}

	// Gamepad1 slot 2 ("Button3"): explicitly saved -1 -> migrates to the
	// registry default with pad 1's id embedded (the upgrade path).
	CHECK(Config.Gamepads[1].Button[2] == KEY_Gamepad(1, ExpectedLayout[2]));

	// Gamepad1 slot 4 ("Button5"): explicitly saved non--1 -> still wins.
	CHECK(Config.Gamepads[1].Button[4] == 12345);

	// Every other slot defaulted with pad 1's id embedded.
	for (int32_t iSlot = 0; iSlot < C4MaxKey; ++iSlot)
	{
		if (iSlot == 2 || iSlot == 4) continue;
		INFO("Gamepad1 slot " << iSlot);
		CHECK(Config.Gamepads[1].Button[iSlot] == KEY_Gamepad(1, ExpectedLayout[iSlot]));
	}
}

#ifdef USE_SDL_FOR_GAMEPAD
TEST_CASE("GamepadDefaults.SyntheticDispatchG3", "[gamepad-defaults]")
{
	// G3 (spec §5): synthesize SDL_CONTROLLER* events and drive the REAL
	// FeedEvent -> Game.DoKeyboardInput -> named-key path with no hardware.
	// This is the strongest in-loop proxy for "press A -> jump fires".
	Game.KeyboardInput.Clear();

	struct Probe { int fired = 0; bool Fire() { ++fired; return true; } };
	Probe probeA, probeLeft;

	const int32_t codeA = GetGamepadDefaultButton(0, CON_Up);     // A button
	const int32_t codeLeft = GetGamepadDefaultButton(0, CON_Left); // lstick west
	REQUIRE(Key_GetGamepad(codeA) == 0);
	REQUIRE(Key_GetGamepadButton(codeA) == KEY_JOY_Button(0));

	Game.KeyboardInput.RegisterKey(new C4CustomKey(C4KeyCodeEx(codeA), "JoyProbeA",
		KEYSCOPE_Control, new C4KeyCB<Probe>(probeA, &Probe::Fire, &Probe::Fire), C4CustomKey::PRIO_PlrControl));
	Game.KeyboardInput.RegisterKey(new C4CustomKey(C4KeyCodeEx(codeLeft), "JoyProbeLeft",
		KEYSCOPE_Control, new C4KeyCB<Probe>(probeLeft, &Probe::Fire, &Probe::Fire), C4CustomKey::PRIO_PlrControl));

	C4GamePadControl control;
	constexpr SDL_JoystickID kFakeInstance = 42;
	control.RegisterGCInstance(kFakeInstance, 0);

	// 1. GC A-press fires the bound named key exactly once.
	SDL_Event ev{}; ev.type = SDL_CONTROLLERBUTTONDOWN;
	ev.cbutton.which = kFakeInstance;
	ev.cbutton.button = SDL_CONTROLLER_BUTTON_A;
	control.FeedEvent(ev);
	CHECK(probeA.fired == 1);

	// 2. Double-fire guard: the raw JOY event of the same physical press
	//    (GC-opened pads still emit both families) is dropped.
	SDL_Event raw{}; raw.type = SDL_JOYBUTTONDOWN;
	raw.jbutton.which = kFakeInstance;
	raw.jbutton.button = SDL_CONTROLLER_BUTTON_A;
	control.FeedEvent(raw);
	CHECK(probeA.fired == 1);

	// 3. Left-stick west through the GC axis path fires the movement binding.
	SDL_Event ax{}; ax.type = SDL_CONTROLLERAXISMOTION;
	ax.caxis.which = kFakeInstance;
	ax.caxis.axis = SDL_CONTROLLER_AXIS_LEFTX;
	ax.caxis.value = -20000;
	control.FeedEvent(ax);
	CHECK(probeLeft.fired == 1);

	// 4. Releasing the stick fires the matching Up (dedupe bookkeeping).
	ax.caxis.value = 0;
	control.FeedEvent(ax);
	CHECK(probeLeft.fired == 2);

	// 5. Dpad alias: a GC dpad-left press ALSO drives the movement axis.
	SDL_Event dp{}; dp.type = SDL_CONTROLLERBUTTONDOWN;
	dp.cbutton.which = kFakeInstance;
	dp.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_LEFT;
	control.FeedEvent(dp);
	CHECK(probeLeft.fired == 3);

#ifndef USE_SDL_MAINLOOP
	// 6. Pump path (review B1): on an X11 build Execute() is the ONLY SDL
	//    event pump, and it must forward SDL_CONTROLLER* events to FeedEvent
	//    the way the SDL-mainloop funnel (C4FullScreen.cpp) does. Push a GC
	//    A-press onto the real SDL queue, let Execute() poll it, and require
	//    the bound named key to fire exactly once more. SDL-mainloop builds
	//    compile this out: Execute() is a no-op there, and this queue is not
	//    what feeds the game.
	SDL_Event pushed{};
	pushed.type = SDL_CONTROLLERBUTTONDOWN;
	pushed.cbutton.which = kFakeInstance;
	pushed.cbutton.button = SDL_CONTROLLER_BUTTON_A;
	REQUIRE(SDL_PushEvent(&pushed) == 1);
	control.Execute();
	CHECK(probeA.fired == 2);
#endif
}
#endif
