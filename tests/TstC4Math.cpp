/*
 * LegacyClonk
 *
 * Copyright (c) 2024, The LegacyClonk Team and contributors
 *
 * Distributed under the terms of the ISC license; see accompanying file
 * "COPYING" for details.
 *
 * "Clonk" is a registered trademark of Matthes Bender, used with permission.
 * See accompanying file "TRADEMARK" for details.
 */

#include <catch2/catch_all.hpp>

#include "C4Math.h"

TEST_CASE("Distance computes integer Pythagorean distance", "[C4Math]")
{
	REQUIRE(Distance(0, 0, 0, 0) == 0);
	REQUIRE(Distance(0, 0, 3, 4) == 5);
	REQUIRE(Distance(0, 0, -3, -4) == 5);
}

TEST_CASE("Angle returns compass bearing in degrees", "[C4Math]")
{
	REQUIRE(Angle(0, 0, 1, 0) == 90);   // due east
	REQUIRE(Angle(0, 0, 0, 1) == 181);  // due south (atan2f rounding)
	REQUIRE(Angle(0, 0, -1, 0) == 270); // due west
	REQUIRE(Angle(0, 0, 0, -1) == 359); // due north (atan2f rounding)
}

TEST_CASE("Pow does fast integer exponentiation", "[C4Math]")
{
	REQUIRE(Pow(2, 10) == 1024);
	REQUIRE(Pow(2, 0) == 1);
	REQUIRE(Pow(2, -1) == 0); // negative exponent early-returns 0
}

TEST_CASE("Templated helpers from C4Math.h", "[C4Math]")
{
	REQUIRE(Abs(-5) == 5);
	REQUIRE(BoundBy(15, 0, 10) == 10);
	REQUIRE(Sign(-3) == -1);
	REQUIRE(Inside(5, 1, 10) == true);
}
