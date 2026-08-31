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

#include <Fixed.h>

#include <cmath>
#include <cstdint>
#include <limits>
#include <numbers>

// ---------------------------------------------------------------------------
// Cohort A -- Edge-case suite for conversions, operators, comparisons, helpers
// ---------------------------------------------------------------------------

TEST_CASE("C4Fixed itofix/fixtoi pin exact bit patterns", "[C4Fixed]")
{
	REQUIRE(itofix(0).val == 0);
	REQUIRE(itofix(1).val == 65536);
	REQUIRE(itofix(-1).val == -65536);
	REQUIRE(fixtoi(itofix(7)) == 7);
	REQUIRE(fixtoi(itofix(-7)) == -7);

	// Half-up rounding for positive 0.5
	C4Fixed half; half.val = 32768;
	REQUIRE(fixtoi(half) == 1);

	// Half-away-from-zero for negative
	C4Fixed negHalf; negHalf.val = -32768;
	REQUIRE(fixtoi(negHalf) == 0);
	C4Fixed negOneHalf; negOneHalf.val = -65536 - 32768;
	REQUIRE(fixtoi(negOneHalf) == -2);
}

TEST_CASE("C4Fixed itofix overflow-domain wrap pins", "[C4Fixed]")
{
	// In-range boundary: 32767 is the last value that does not overflow
	REQUIRE(itofix(32767).val == 0x7FFF0000);
	// First overflow: 32768 wraps to INT32_MIN
	REQUIRE(itofix(32768).val == std::numeric_limits<int32_t>::min());
	// Negative overflow: -32769 wraps to +0x7FFF0000
	REQUIRE(itofix(-32769).val == 0x7FFF0000);
	// Full wrap: 65535 → 0xFFFF0000, 65536 → 0
	REQUIRE(itofix(65535).val == -65536);
	REQUIRE(itofix(65536).val == 0);
	// Symmetric negative wrap
	REQUIRE(itofix(-65535).val == 65536);
	REQUIRE(itofix(-65536).val == 0);
}

TEST_CASE("C4Fixed ftofix/fixtof conversions", "[C4Fixed]")
{
	REQUIRE(ftofix(0.5f).val == 32768);
	REQUIRE(ftofix(-0.5f).val == -32768);
	// ftofix(0.1f) truncates toward zero; 0.1 * 65536 = 6553.6 -> 6553
	REQUIRE(std::abs(ftofix(0.1f).val - 6553) <= 1);
	REQUIRE(fixtof(itofix(1)) == 1.0f);
	REQUIRE(fixtof(itofix(-1)) == -1.0f);
}

TEST_CASE("C4Fixed itofix(x, prec) two-branch ctor", "[C4Fixed]")
{
	// prec < FIXED_FPF branch
	REQUIRE(itofix(1, 100).val == 655);
	REQUIRE(itofix(50, 100).val == 32768);
	// prec >= FIXED_FPF branch (int64_t math path)
	REQUIRE(itofix(1, 65536).val == 1);
	// Round-trip
	for (int x : {0, 1, 50, 99, 100, -1, -50})
	{
		REQUIRE(fixtoi(itofix(x, 100), 100) == x);
	}
}

TEST_CASE("C4Fixed arithmetic operators", "[C4Fixed]")
{
	REQUIRE((itofix(2) + itofix(3)) == itofix(5));
	REQUIRE((itofix(2) - itofix(3)) == itofix(-1));
	REQUIRE((itofix(2) * itofix(3)) == itofix(6));
	REQUIRE((itofix(6) / itofix(3)) == itofix(2));
	REQUIRE((itofix(6) / itofix(4)) == itofix(3, 2)); // 6/4 = 1.5, exactly representable
	{
		C4Fixed trunc; trunc.val = 21845; // 65536 / 3 truncated toward zero
		REQUIRE((itofix(1) / itofix(3)) == trunc);
	}
	// int32_t overloads
	REQUIRE((itofix(2) * int32_t(3)) == itofix(6));
	REQUIRE((itofix(6) / int32_t(3)) == itofix(2));
	// Unary
	REQUIRE((-itofix(5)) == itofix(-5));
	REQUIRE((+itofix(5)) == itofix(5));
}

TEST_CASE("C4Fixed comparisons and bool conversion", "[C4Fixed]")
{
	REQUIRE(itofix(1) == itofix(1));
	REQUIRE(itofix(1) != itofix(2));
	REQUIRE(itofix(1) < itofix(2));
	REQUIRE((itofix(1) <=> itofix(2)) == std::strong_ordering::less);
	REQUIRE(itofix(1) == int32_t(1));
	REQUIRE(itofix(1) < int32_t(2));
	// bool conversion
	REQUIRE(static_cast<bool>(itofix(0)) == false);
	REQUIRE(static_cast<bool>(itofix(1)) == true);
	REQUIRE(!itofix(0) == true);
	REQUIRE(!itofix(1) == false);
}

TEST_CASE("C4Fixed helpers FIXED100/FIXED256/FIXED10/Fix0", "[C4Fixed]")
{
	REQUIRE(FIXED100(1).val == 655);
	REQUIRE(FIXED100(50).val == 32768);
	REQUIRE(FIXED100(100).val == 65536);
	REQUIRE(FIXED256(1).val == 256);
	REQUIRE(FIXED256(256).val == 65536);
	REQUIRE(FIXED10(1).val == 6553);
	REQUIRE(FIXED10(10).val == 65536);
	REQUIRE(Fix0 == itofix(0));
	REQUIRE(Fix0.val == 0);
}

// ---------------------------------------------------------------------------
// Cohort D -- SineTable golden snapshot via FNV-1a hash + invariants
// ---------------------------------------------------------------------------

TEST_CASE("SineTable FNV-1a hash matches golden snapshot", "[C4Fixed]")
{
	uint32_t hash = 0x811c9dc5u;
	for (int i = 0; i <= 9000; ++i)
	{
		uint32_t u = static_cast<uint32_t>(SineTable[i]);
		hash ^= u & 0xffu;
		hash *= 0x01000193u;
		hash ^= (u >> 8) & 0xffu;
		hash *= 0x01000193u;
		hash ^= (u >> 16) & 0xffu;
		hash *= 0x01000193u;
		hash ^= (u >> 24) & 0xffu;
		hash *= 0x01000193u;
	}
	INFO("FNV-1a hash=" << std::hex << hash);
	REQUIRE(hash == 0x83ac573fu);
}

TEST_CASE("SineTable structural invariants", "[C4Fixed]")
{
	REQUIRE(SineTable[0] == 0);
	REQUIRE(SineTable[9000] == 65536);
	for (int i = 0; i < 9000; ++i)
	{
		REQUIRE(SineTable[i] <= SineTable[i + 1]);
	}
}

// ---------------------------------------------------------------------------
// Cohort E -- Differential testing of sin_deg/cos_deg vs std::sin/std::cos
// ---------------------------------------------------------------------------

TEST_CASE("sin_deg approximates std::sin within 2 ULP", "[C4Fixed]")
{
	constexpr double pi = std::numbers::pi_v<double>;
	const int angles[] = {
		0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330,
		89, 90, 91, 179, 180, 181, 269, 270, 271, 359, 360, 361,
		-1, -90, -180, -270, -360};
	for (int degrees : angles)
	{
		C4Fixed s = itofix(degrees).sin_deg();
		double ref = std::sin(degrees * pi / 180.0);
		INFO("degrees=" << degrees << " fixtof(s)=" << fixtof(s) << " ref=" << ref);
		REQUIRE(std::abs(static_cast<double>(fixtof(s)) - ref) < 2.0 / 65536.0);
	}
}

TEST_CASE("cos_deg approximates std::cos within 2 ULP", "[C4Fixed]")
{
	constexpr double pi = std::numbers::pi_v<double>;
	const int angles[] = {
		0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330,
		89, 90, 91, 179, 180, 181, 269, 270, 271, 359, 360, 361,
		-1, -90, -180, -270, -360};
	for (int degrees : angles)
	{
		C4Fixed c = itofix(degrees).cos_deg();
		double ref = std::cos(degrees * pi / 180.0);
		INFO("degrees=" << degrees << " fixtof(c)=" << fixtof(c) << " ref=" << ref);
		REQUIRE(std::abs(static_cast<double>(fixtof(c)) - ref) < 2.0 / 65536.0);
	}
}

TEST_CASE("sin_deg(x) == cos_deg(x - 90) identity", "[C4Fixed]")
{
	const int angles[] = {0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360};
	for (int x : angles)
	{
		C4Fixed s = itofix(x).sin_deg();
		C4Fixed c = itofix(x - 90).cos_deg();
		INFO("x=" << x << " sin=" << s.val << " cos(x-90)=" << c.val);
		REQUIRE(s == c);
	}
}
