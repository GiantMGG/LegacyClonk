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

// Slider-contract pinning test — TWO descriptor families (specs
// world-generator-ux-rework + adjustable-winning-conditions):
//
// 1. kSliderDescriptors (cycle 112): every generator slider is
//    data-driven and gated — human label != raw key, Min < Max,
//    default inside the range; count (11) and pairwise uniqueness
//    pinned. Engine-default bounds from C4SLandscape::Default().
//
// 2. kWinConditionDescriptors + kWinTargetDescriptor (cycle 114): the
//    Winning Conditions panel rows + picker count sliders + the four
//    --parameter parity keys, all gated by the same trinity (label !=
//    key, min < max, default in range) plus structural, formula,
//    resolver and codec assertions (spec Data contract 1-5). The codec
//    is the shared seam between the panel and the CLI — the round-trip
//    and family-surgery pins are what keep the two writers identical.

#include <catch2/catch_all.hpp>

#include "C4SliderDescriptors.h"
#include "C4Scenario.h"
#include "C4WinConditionDescriptors.h"

#include <string>

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
			REQUIRE(std::string{Descriptor.szLabel} != std::string{Descriptor.szIniKey});
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
				CHECK(std::string{kSliderDescriptors[i].szLabel} != std::string{kSliderDescriptors[j].szLabel});
				CHECK(std::string{kSliderDescriptors[i].szIniKey} != std::string{kSliderDescriptors[j].szIniKey});
			}
		}
	}
}

// --- Win-condition descriptor contracts (spec adjustable-winning-
// conditions Data contract 1-2) ------------------------------------------
TEST_CASE("WinConditionContractTable", "[slider-contract]")
{
	SECTION("Enum descriptor count is three")
	{
		REQUIRE(std::size(kWinConditionDescriptors) == 3);
	}

	SECTION("Enum rows: label != key, choice structure")
	{
		for (const auto &Descriptor : kWinConditionDescriptors)
		{
			CAPTURE(Descriptor.szLabel, Descriptor.szIniKey);
			REQUIRE(Descriptor.szLabel != nullptr);
			REQUIRE(Descriptor.szLabel[0] != '\0');
			REQUIRE(Descriptor.szIniKey != nullptr);
			REQUIRE(Descriptor.szIniKey[0] != '\0');
			// the trinity gate, row level
			REQUIRE(std::string{Descriptor.szLabel} != std::string{Descriptor.szIniKey});
			// which Parameters list carries the family
			REQUIRE(Descriptor.szIdListKey != nullptr);
			REQUIRE((SEqualNoCase(Descriptor.szIdListKey, "Goals") || SEqualNoCase(Descriptor.szIdListKey, "Rules")));
			// the min<max analogue
			REQUIRE(Descriptor.iChoiceCount >= 2);

			// choice structure (plan correction 2): exactly one no-object
			// choice (the row default); all other choices object-backed with
			// pairwise-unique IDs and pairwise-unique enum + display names
			std::size_t iNoObjectChoices = 0;
			for (std::size_t i = 0; i < Descriptor.iChoiceCount; ++i)
			{
				const C4WinConditionChoice &rChoice = Descriptor.Choices[i];
				CAPTURE(Descriptor.szIniKey, i);
				REQUIRE(rChoice.szEnumName != nullptr);
				REQUIRE(rChoice.szEnumName[0] != '\0');
				REQUIRE(rChoice.szDisplayName != nullptr);
				REQUIRE(rChoice.szDisplayName[0] != '\0');
				if (rChoice.id == C4ID_None)
				{
					++iNoObjectChoices;
					continue;
				}
				for (std::size_t j = 0; j < Descriptor.iChoiceCount; ++j)
				{
					if (j == i) continue;
					CAPTURE(i, j);
					CHECK(std::string{Descriptor.Choices[i].szEnumName} != std::string{Descriptor.Choices[j].szEnumName});
					CHECK(std::string{Descriptor.Choices[i].szDisplayName} != std::string{Descriptor.Choices[j].szDisplayName});
					// object-backed IDs pairwise unique (the ambiguity gate)
					CHECK((Descriptor.Choices[j].id == C4ID_None || Descriptor.Choices[i].id != Descriptor.Choices[j].id));
				}
			}
			REQUIRE(iNoObjectChoices == 1);
		}
	}

	SECTION("Enum keys unique across rows")
	{
		for (std::size_t i = 0; i < std::size(kWinConditionDescriptors); ++i)
		{
			for (std::size_t j = i + 1; j < std::size(kWinConditionDescriptors); ++j)
			{
				CAPTURE(i, j);
				CHECK(std::string{kWinConditionDescriptors[i].szIniKey} != std::string{kWinConditionDescriptors[j].szIniKey});
			}
		}
	}

	SECTION("Target descriptor contract (count pinned == 1)")
	{
		CAPTURE(kWinTargetDescriptor.szLabel, kWinTargetDescriptor.szIniKey);
		REQUIRE(kWinTargetDescriptor.szLabel != nullptr);
		REQUIRE(kWinTargetDescriptor.szLabel[0] != '\0');
		REQUIRE(std::string{kWinTargetDescriptor.szLabel} != std::string{kWinTargetDescriptor.szIniKey}); // "Settlement target" != "ValueGain"
		REQUIRE(kWinTargetDescriptor.id != C4ID_None);
		REQUIRE(kWinTargetDescriptor.iMinCount >= 1);
		REQUIRE(kWinTargetDescriptor.iMaxCount > kWinTargetDescriptor.iMinCount);    // 1 < 50
		REQUIRE(kWinTargetDescriptor.iDefaultCount >= kWinTargetDescriptor.iMinCount); // 15 in [1, 50]
		REQUIRE(kWinTargetDescriptor.iDefaultCount <= kWinTargetDescriptor.iMaxCount);
		REQUIRE(kWinTargetDescriptor.iPointsPerCount >= 1);
		// derived points range + default (spec Data contract 2: 100..5000, 1500)
		REQUIRE(kWinTargetDescriptor.iMinCount * kWinTargetDescriptor.iPointsPerCount == 100);
		REQUIRE(kWinTargetDescriptor.iMaxCount * kWinTargetDescriptor.iPointsPerCount == 5000);
		REQUIRE(kWinTargetDescriptor.iDefaultCount * kWinTargetDescriptor.iPointsPerCount == 1500);
	}

	SECTION("CLI aliases resolve onto canonical choices, never onto panel rows")
	{
		REQUIRE(std::size(kWinConditionAliases) == 2); // MeleeTeamwork + Extended
		for (const auto &Alias : kWinConditionAliases)
		{
			const C4WinConditionDescriptor *pDescriptor = FindWinConditionDescriptor(Alias.szIniKey);
			CAPTURE(Alias.szIniKey, Alias.szAliasEnumName);
			REQUIRE(pDescriptor != nullptr);
			// the canonical target is a real choice of the row...
			REQUIRE(FindWinConditionChoice(pDescriptor, Alias.szEnumName) != nullptr);
			// ...and the alias itself is NOT a panel choice
			REQUIRE(FindWinConditionChoice(pDescriptor, Alias.szAliasEnumName) == nullptr);
		}
	}
}

// --- Count-slider resolver + points formula (spec Data contract 3-4) -----
TEST_CASE("WinConditionCountResolver", "[slider-contract]")
{
	SECTION("Eligible def with authored count in range")
	{
		const C4CountSliderParams Params = ResolveCountSliderParams(50, 15); // VALG with authored 15
		REQUIRE(Params.fEligible);
		REQUIRE(Params.iMin == 1);
		REQUIRE(Params.iMax == 50);
		REQUIRE(Params.iDefault == 15);
	}

	SECTION("Authored count above the ceiling stays representable")
	{
		// shipped instance: CoastalHarbor.c4s authors Goals=MONE=100 against
		// Wealth's MaxUserSelect=50 — the slider must not silently rewrite it
		const C4CountSliderParams Params = ResolveCountSliderParams(50, 100);
		REQUIRE(Params.fEligible);
		REQUIRE(Params.iMin == 1);
		REQUIRE(Params.iMax == 100);
		REQUIRE(Params.iDefault == 100);
	}

	SECTION("Ineligible defs: MaxUserSelect <= 1 (covers the parse default 0 and author typos < 0)")
	{
		REQUIRE(!ResolveCountSliderParams(1, 5).fEligible);
		REQUIRE(!ResolveCountSliderParams(0, 5).fEligible);
		REQUIRE(!ResolveCountSliderParams(-5, 5).fEligible);
	}

	SECTION("Negative authored count guarded")
	{
		const C4CountSliderParams Params = ResolveCountSliderParams(50, -3);
		REQUIRE(Params.fEligible);
		REQUIRE(Params.iMin == 1);
		REQUIRE(Params.iMax == 50);
		REQUIRE(Params.iDefault == 1);
	}

	SECTION("ValueGainToCount floors at one (ConvertGoals:601 formula verbatim)")
	{
		REQUIRE(ValueGainToCount(2500) == 25);
		REQUIRE(ValueGainToCount(50) == 1);
		REQUIRE(ValueGainToCount(-300) == 1);
		REQUIRE(ValueGainToCount(0) == 1);
	}
}

// --- Codec round-trip + family surgery (spec Data contract 5) ------------
TEST_CASE("WinConditionCodec", "[slider-contract]")
{
	SECTION("Round-trip: Decode(Apply(choice)) == choice for every enum choice")
	{
		for (const auto &Descriptor : kWinConditionDescriptors)
		{
			for (std::size_t i = 0; i < Descriptor.iChoiceCount; ++i)
			{
				const C4WinConditionChoice &rChoice = Descriptor.Choices[i];
				CAPTURE(Descriptor.szIniKey, rChoice.szEnumName);

				// a busy authored state: family members + unrelated survivors
				C4IDList Goals, Rules;
				Goals.SetIDCount(C4Id("MELE"), 1, true);
				Goals.SetIDCount(C4Id("VALG"), 16, true);
				Rules.SetIDCount(C4Id("KILC"), 1, true);
				Rules.SetIDCount(C4Id("FGRV"), 1, true);

				REQUIRE(ApplyWinConditionChoice(Goals, Rules, Descriptor.szIniKey, rChoice.szEnumName, 15));
				const C4WinConditionState State = DecodeWinCondition(Goals, Rules);

				if (SEqualNoCase(Descriptor.szIniKey, "Mode"))
					REQUIRE(State.pModeChoice == &rChoice);
				else if (SEqualNoCase(Descriptor.szIniKey, "Elimination"))
					REQUIRE(State.pEliminationChoice == &rChoice);
				else
				{
					REQUIRE(State.pGoalChoice == &rChoice);
					if (rChoice.id == kWinTargetDescriptor.id)
						REQUIRE(State.iValueGainCount == 15); // aux count honored
				}
			}
		}
	}

	SECTION("Family surgery: only the family swaps, everything else survives")
	{
		C4IDList Goals, Rules;
		Goals.SetIDCount(C4Id("MELE"), 1, true);
		Goals.SetIDCount(C4Id("OILP"), 1, true);
		Goals.SetIDCount(C4Id("VALG"), 16, true);
		Rules.SetIDCount(C4Id("ENRG"), 1, true);
		Rules.SetIDCount(C4Id("FGRV"), 1, true);

		// CooperativeGoal=Goldmine: family swap; MELE, OILP, ENRG, FGRV untouched
		REQUIRE(ApplyWinConditionChoice(Goals, Rules, "CooperativeGoal", "Goldmine", 15));
		REQUIRE(Goals.GetIDCount(C4Id("GLDM")) == 1);
		REQUIRE(Goals.GetIDCount(C4Id("VALG")) == 0);  // MUT-4 pin: the family CLEAR
		REQUIRE(Goals.GetIDCount(C4Id("MNTK")) == 0);
		REQUIRE(Goals.GetIDCount(C4Id("MELE")) == 1);  // coop-goal family never touches melee
		REQUIRE(Goals.GetIDCount(C4Id("OILP")) == 1);  // ...nor unrelated goals
		REQUIRE(Rules.GetIDCount(C4Id("ENRG")) == 1);
		REQUIRE(Rules.GetIDCount(C4Id("FGRV")) == 1);

		// Mode=Melee: additive — authored/anterior goals survive
		REQUIRE(ApplyWinConditionChoice(Goals, Rules, "Mode", "Melee", 0));
		REQUIRE(Goals.GetIDCount(C4Id("MELE")) == 1);
		REQUIRE(Goals.GetIDCount(C4Id("GLDM")) == 1);  // the additive guarantee (smoke-pinned end-to-end)

		// Elimination=CaptureTheFlag: CTFL pulled in WITH FGRV; KILC gone; goals untouched
		REQUIRE(ApplyWinConditionChoice(Goals, Rules, "Elimination", "CaptureTheFlag", 0));
		REQUIRE(Rules.GetIDCount(C4Id("CTFL")) == 1);
		REQUIRE(Rules.GetIDCount(C4Id("KILC")) == 0);
		REQUIRE(Rules.GetIDCount(C4Id("FGRV")) == 1);
		REQUIRE(Rules.GetIDCount(C4Id("ENRG")) == 1);  // elimination family never touches unrelated rules
		REQUIRE(Goals.GetIDCount(C4Id("GLDM")) == 1);
		REQUIRE(Goals.GetIDCount(C4Id("OILP")) == 1);

		// Elimination=EliminateCrew: KILC/CTFL cleared; FGRV SURVIVES (standalone rule)
		REQUIRE(ApplyWinConditionChoice(Goals, Rules, "Elimination", "EliminateCrew", 0));
		REQUIRE(Rules.GetIDCount(C4Id("KILC")) == 0);
		REQUIRE(Rules.GetIDCount(C4Id("CTFL")) == 0);
		REQUIRE(Rules.GetIDCount(C4Id("FGRV")) == 1);  // the CTFL pull is one-way only

		// Mode=Cooperative: MELE (+MEL2) removed; goals otherwise untouched
		REQUIRE(ApplyWinConditionChoice(Goals, Rules, "Mode", "Cooperative", 0));
		REQUIRE(Goals.GetIDCount(C4Id("MELE")) == 0);
		REQUIRE(Goals.GetIDCount(C4Id("GLDM")) == 1);
	}

	SECTION("CLI aliases encode onto their canonical choices")
	{
		C4IDList Goals, Rules;
		REQUIRE(ApplyWinConditionChoice(Goals, Rules, "Mode", "MeleeTeamwork", 0));
		REQUIRE(Goals.GetIDCount(C4Id("MELE")) == 1);

		Goals.Clear();
		Goals.SetIDCount(C4Id("VALG"), 16, true);
		REQUIRE(ApplyWinConditionChoice(Goals, Rules, "CooperativeGoal", "Extended", 0));
		REQUIRE(Goals.GetIDCount(C4Id("GLDM")) == 0);
		REQUIRE(Goals.GetIDCount(C4Id("MNTK")) == 0);
		REQUIRE(Goals.GetIDCount(C4Id("VALG")) == 0); // Extended == NoGoal: family cleared, nothing added
	}

	SECTION("Unknown keys and names are rejected, never partially applied")
	{
		C4IDList Goals, Rules;
		REQUIRE(!ApplyWinConditionChoice(Goals, Rules, "NoSuchKey", "Melee", 0));
		REQUIRE(!ApplyWinConditionChoice(Goals, Rules, "Mode", "Bogus", 0));
		REQUIRE(Goals.GetNumberOfIDs() == 0);
		REQUIRE(Rules.GetNumberOfIDs() == 0);
	}
}
