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

#include "StdBuf.h"

#include <cstring>

TEST_CASE("StdBuf default construction is an empty ref", "[StdBuf]")
{
	StdBuf b;
	REQUIRE(b.getSize() == 0);
	REQUIRE(b.isRef() == true);
}

TEST_CASE("StdBuf owning copy from raw data", "[StdBuf]")
{
	const char data[] = "hello";
	StdBuf b(data, 5);
	REQUIRE(b.isRef() == false);
	REQUIRE(b.getSize() == 5);
	REQUIRE(std::memcmp(b.getData(), "hello", 5) == 0);
}

TEST_CASE("StdBuf non-owning ref from raw data", "[StdBuf]")
{
	const char data[] = "hello";
	StdBuf b(data, 5, false);
	REQUIRE(b.isRef() == true);
	REQUIRE(b.getSize() == 5);
}

TEST_CASE("StdBuf copy constructor produces an equal independent buffer", "[StdBuf]")
{
	const char data[] = "hello";
	StdBuf original(data, 5);
	StdBuf copy(original);
	REQUIRE(copy.isRef() == false);
	REQUIRE(copy.getSize() == 5);
	REQUIRE(std::memcmp(copy.getData(), "hello", 5) == 0);
}

TEST_CASE("StdBuf move constructor transfers ownership to the destination", "[StdBuf]")
{
	const char data[] = "hello";
	StdBuf original(data, 5);
	StdBuf moved(std::move(original));
	REQUIRE(moved.isRef() == false);
	REQUIRE(moved.getSize() == 5);
	REQUIRE(original.isRef() == true);
}
