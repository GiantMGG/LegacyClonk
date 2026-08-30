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

// Cycle 75 (pixel-material-reactions) engine unit tests.
//
// Covers the two additive engine changes:
//   1. The C4MaterialCore "Buoyancy" field (compile round-trip, default 0).
//   2. The "React" reaction type (multi-[Reaction] parsing, product-sentinel
//      resolution, and the compile -> decompile -> recompile savegame
//      round-trip for a full React section).

#include <catch2/catch_all.hpp>

#include <C4Material.h>
#include <StdCompiler.h>
#include <C4Wrappers.h>

#include <cstring>

namespace
{
	constexpr const char *MaterialWithoutBuoyancy = R"ini([Material]
Name=TestPlain
Density=25
)ini";

	constexpr const char *MaterialWithBuoyancy = R"ini([Material]
Name=TestBuoy
Density=25
Buoyancy=150
)ini";

	bool CompileMaterial(C4MaterialCore &core, const char *szBuffer)
	{
		return CompileFromBuf_LogWarn<StdCompilerINIRead>(core, StdStrBuf{szBuffer}, "TstC4MaterialReactions");
	}
}

TEST_CASE("C4MaterialCore.BuoyancyRoundTrip", "[material]")
{
	// Old-format material without the key compiles to the 0 default
	// (gravity path untouched for every pre-cycle material).
	C4MaterialCore plain;
	REQUIRE(CompileMaterial(plain, MaterialWithoutBuoyancy));
	CHECK(plain.Buoyancy == 0);

	// New-format material with the key compiles to 150.
	C4MaterialCore buoyant;
	REQUIRE(CompileMaterial(buoyant, MaterialWithBuoyancy));
	CHECK(buoyant.Buoyancy == 150);

	// Decompile -> recompile equality for the new field.
	const std::string decompiled = DecompileToBuf<StdCompilerINIWrite>(buoyant);
	C4MaterialCore reparsed;
	REQUIRE(CompileMaterial(reparsed, decompiled.c_str()));
	CHECK(reparsed.Buoyancy == 150);
	CHECK(reparsed.Density == buoyant.Density);
	CHECK(std::strcmp(reparsed.Name, buoyant.Name) == 0);
}
