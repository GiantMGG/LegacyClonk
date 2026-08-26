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

// Test-only translation unit that provides the engine globals normally
// defined in src/C4WinMain.cpp (Game, Application, Console, FullScreen,
// Config). C4WinMain.cpp is excluded from the clonk_engine OBJECT library
// because it also defines main(), which would clash with Catch2's main()
// on macOS and Windows. Test binaries link this TU instead so the engine
// objects can resolve the global singleton symbols without pulling in
// main().

#include <C4Application.h>
#include <C4Console.h>
#include <C4FullScreen.h>
#include <C4Game.h>
#include <C4Config.h>

C4Application Application;
C4Console Console;
C4FullScreen FullScreen;
C4Game Game;
C4Config Config;
