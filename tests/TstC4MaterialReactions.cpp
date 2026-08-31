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

// Cycle 75 (pixel-material-reactions) / cycle 80 (sand-drift-dune-mechanic)
// engine unit tests.
//
// Cycle 75 covers the two additive engine changes:
//   1. The C4MaterialCore "Buoyancy" field (compile round-trip, default 0).
//   2. The "React" reaction type (multi-[Reaction] parsing, product-sentinel
//      resolution, and the compile -> decompile -> recompile savegame
//      round-trip for a full React section).
//
// Cycle 80 adds:
//   3. The C4MaterialCore "Saltation" field (compile round-trip, default 0).

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

namespace
{
	constexpr const char *SteamLikeMaterial = R"ini([Material]
Name=TestSteam
Density=1
Buoyancy=150
WindDrift=60

[Reaction]
Type=React
TargetSpec=All
CheckSlide=0
PXSProduct=Water
Rate=20

[Reaction]
Type=React
TargetSpec=Sky
CheckSlide=0
PXSProduct=Water
Rate=5
)ini";

	constexpr const char *FullReactReaction = R"ini([Reaction]
Type=React
TargetSpec=Lava
CheckSlide=0
LSProduct=Rock
PXSProduct=Steam
ByProduct=Water
ByProductRate=50
Rate=100
)ini";
}

TEST_CASE("C4MaterialCore.MultiReactionParsing", "[material]")
{
	// Design question (c): one .c4m with TWO [Reaction] sections parses
	// into a two-element CustomReactionList; both resolve to mrfReact and
	// keep their per-section fields. (The same repeated-section mechanism
	// already carries [Rec] chunks in C4Record.) The last-section-wins
	// composition is exercised end-to-end by SteamBuoyancySmoke.
	C4MaterialCore core;
	REQUIRE(CompileMaterial(core, SteamLikeMaterial));

	REQUIRE(core.CustomReactionList.size() == 2);

	const C4MaterialReaction &all = core.CustomReactionList[0];
	CHECK(all.pFunc == &C4MaterialMap::mrfReact);
	CHECK(all.TargetSpec == "All");
	CHECK(all.fInsertionCheck == false); // CheckSlide=0
	CHECK(all.sPXSProduct == "Water");
	CHECK(all.iRate == 20);

	const C4MaterialReaction &sky = core.CustomReactionList[1];
	CHECK(sky.pFunc == &C4MaterialMap::mrfReact);
	CHECK(sky.TargetSpec == "Sky");
	CHECK(sky.fInsertionCheck == false);
	CHECK(sky.sPXSProduct == "Water");
	CHECK(sky.iRate == 5);
}

TEST_CASE("C4MaterialReaction.ResolveReactProductSentinels", "[material]")
{
	// Sentinel convention shared by mrfReact and CrossMapMaterials:
	//   omitted key -> -2 (no-op); "Sky" -> MNone (vanish);
	//   valid name -> resolved index; unknown name -> warn + no-op (-2).
	CHECK(ResolveReactProduct(StdStrBuf{}, MNone) == -2);
	CHECK(ResolveReactProduct(StdStrBuf{"Sky"}, MNone) == MNone);
	CHECK(ResolveReactProduct(StdStrBuf{"Water"}, 5) == 5);
	CHECK(ResolveReactProduct(StdStrBuf{"Bogus"}, MNone) == -2);
}

TEST_CASE("C4MaterialReaction.ReactRoundTrip", "[material]")
{
	// Savegame contract: a full React section (all five new keys set)
	// survives compile -> decompile -> recompile with every field equal.
	C4MaterialReaction first;
	REQUIRE(CompileFromBuf_LogWarn<StdCompilerINIRead>(
		mkNamingAdapt(first, "Reaction"),
		StdStrBuf{FullReactReaction},
		"TstC4MaterialReactions"));

	REQUIRE(first.pFunc == &C4MaterialMap::mrfReact);
	CHECK(first.TargetSpec == "Lava");
	CHECK(first.fInsertionCheck == false);
	CHECK(first.sLSProduct == "Rock");
	CHECK(first.sPXSProduct == "Steam");
	CHECK(first.sByProduct == "Water");
	CHECK(first.iByProductRate == 50);
	CHECK(first.iRate == 100);

	const std::string decompiled = DecompileToBuf<StdCompilerINIWrite>(
		mkNamingAdapt(first, "Reaction"));
	C4MaterialReaction second;
	REQUIRE(CompileFromBuf_LogWarn<StdCompilerINIRead>(
		mkNamingAdapt(second, "Reaction"),
		StdStrBuf{decompiled.c_str()},
		"TstC4MaterialReactions"));

	CHECK(second.pFunc == &C4MaterialMap::mrfReact);
	CHECK(second.TargetSpec == first.TargetSpec);
	CHECK(second.fInsertionCheck == first.fInsertionCheck);
	CHECK(second.sLSProduct == first.sLSProduct);
	CHECK(second.sPXSProduct == first.sPXSProduct);
	CHECK(second.sByProduct == first.sByProduct);
	CHECK(second.iByProductRate == first.iByProductRate);
	CHECK(second.iRate == first.iRate);
}

namespace
{
	constexpr const char *MaterialWithoutSaltation = R"ini([Material]
Name=TestSaltPlain
Density=50
)ini";

	constexpr const char *MaterialWithSaltation = R"ini([Material]
Name=TestSaltation
Density=50
Saltation=30
)ini";
}

TEST_CASE("C4MaterialCore.SaltationRoundTrip", "[material]")
{
	// Old-format material without the key compiles to the 0 default
	// (saltation branch never runs for every pre-cycle material).
	C4MaterialCore plain;
	REQUIRE(CompileMaterial(plain, MaterialWithoutSaltation));
	CHECK(plain.Saltation == 0);

	// New-format material with the key compiles to 30.
	C4MaterialCore saltating;
	REQUIRE(CompileMaterial(saltating, MaterialWithSaltation));
	CHECK(saltating.Saltation == 30);

	// Decompile -> recompile equality for the new field.
	const std::string decompiled = DecompileToBuf<StdCompilerINIWrite>(saltating);
	C4MaterialCore reparsed;
	REQUIRE(CompileMaterial(reparsed, decompiled.c_str()));
	CHECK(reparsed.Saltation == 30);
	CHECK(reparsed.Density == saltating.Density);
	CHECK(std::strcmp(reparsed.Name, saltating.Name) == 0);
}
