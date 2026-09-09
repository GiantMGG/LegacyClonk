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

#include <CSceneShot.h>

bool CSceneShot::ComposeAndWrite(const char *, int32_t, int32_t)
{
	// Plan Task 2 placeholder -- full composer body lands in Task 3.
	// Spec §4.5 failure semantics: return false so the fire site logs the
	// write-failure line and the run continues (never changes exit codes).
	return false;
}
