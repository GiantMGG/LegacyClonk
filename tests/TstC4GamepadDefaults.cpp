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
