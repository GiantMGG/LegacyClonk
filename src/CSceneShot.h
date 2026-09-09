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

#pragma once

// Diagnostic scene shot (spec playtest-vision-tier2 §2C): CPU-composes a
// PNG of the current landscape/view and writes a SceneTruth JSON sidecar.
// Console-safe — no GUI includes. The full composer body lands in Task 3;
// this interface is consumed by the C4Game::Execute fire site.

#include <cstdint>

namespace CSceneShot
{
	bool ComposeAndWrite(const char *szPath, int32_t iWdt, int32_t iHgt);
}
