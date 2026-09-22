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

// Pins the two mouse-selection caps raised in spec mouse-selection-limits
// (cycle 165). Red if anyone reverts either constant.

#include <catch2/catch_all.hpp>

#include "C4Constants.h"

TEST_CASE("SelectionLimits pin the raised caps", "[engine][selection]")
{
	REQUIRE(C4MaxObjectSelection == 100);
	REQUIRE(C4MaxCommandStack == 200);
	REQUIRE(C4MaxObjectSelection >= 50);
	REQUIRE(C4MaxCommandStack >= 50);
}
