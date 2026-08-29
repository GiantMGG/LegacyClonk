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

#include <C4Id.h>

#include <string_view>

TEST_CASE("C4IdText formats literal IDs", "[C4IdText]")
{
	REQUIRE(std::string_view{C4IdText(C4Id("BLZD"))} == "BLZD");
	REQUIRE(std::string_view{C4IdText(C4Id("STRM"))} == "STRM");
	REQUIRE(std::string_view{C4IdText(C4Id("NONE"))} == "NONE");
}

TEST_CASE("C4IdText formats numerical IDs", "[C4IdText]")
{
	REQUIRE(std::string_view{C4IdText(C4Id("1337"))} == "1337");
}
