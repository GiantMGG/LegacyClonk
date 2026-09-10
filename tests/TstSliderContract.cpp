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

// Slider-contract pinning test (spec world-generator-ux-rework; the
// roadmap Flash-merged gate). The descriptor table behind every generator
// slider is data-driven and gated: every row must carry a human label
// distinct from its raw --parameter key, a range with Min < Max, and a
// default (Std) inside that range. The count (11) and the pairwise
// uniqueness of labels and keys are pinned so rows can neither vanish
// nor duplicate silently. Engine-default bounds come from
// C4SLandscape::Default() (research §8: the deterministic base).

#include <catch2/catch_all.hpp>

#include "C4SliderDescriptors.h"
#include "C4Scenario.h"

#include <string_view>

TEST_CASE("SliderContractTable", "[slider-contract]")
{
	C4SLandscape Landscape;
	Landscape.Default();

	SECTION("Row count is eleven")
	{
		REQUIRE(std::size(kSliderDescriptors) == 11);
	}

	SECTION("Human labels differ from raw keys")
	{
		for (const auto &Descriptor : kSliderDescriptors)
		{
			CAPTURE(Descriptor.szLabel, Descriptor.szIniKey);
			REQUIRE(Descriptor.szLabel != nullptr);
			REQUIRE(Descriptor.szLabel[0] != '\0');
			REQUIRE(Descriptor.szIniKey != nullptr);
			REQUIRE(Descriptor.szIniKey[0] != '\0');
			// exact string inequality — the research §8 gate
			REQUIRE(std::string_view{Descriptor.szLabel} != std::string_view{Descriptor.szIniKey});
		}
	}

	SECTION("Engine-default bounds are valid")
	{
		for (const auto &Descriptor : kSliderDescriptors)
		{
			const C4SVal &rVal = Landscape.*Descriptor.pField;
			CAPTURE(Descriptor.szIniKey, rVal.Min, rVal.Max, rVal.Std);
			REQUIRE(rVal.Min < rVal.Max);
			REQUIRE(rVal.Std >= rVal.Min);
			REQUIRE(rVal.Std <= rVal.Max);
		}
	}

	SECTION("Labels and keys are pairwise unique")
	{
		for (std::size_t i = 0; i < std::size(kSliderDescriptors); ++i)
		{
			for (std::size_t j = i + 1; j < std::size(kSliderDescriptors); ++j)
			{
				CAPTURE(i, j);
				CHECK(std::string_view{kSliderDescriptors[i].szLabel} != std::string_view{kSliderDescriptors[j].szLabel});
				CHECK(std::string_view{kSliderDescriptors[i].szIniKey} != std::string_view{kSliderDescriptors[j].szIniKey});
			}
		}
	}
}
