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
#include "C4PlrStartDescriptors.h"
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

// --- PlrStart list descriptor contract (spec round-setup-parity-complete) --
TEST_CASE("PlrStartListContractTable", "[slider-contract]")
{
	SECTION("Table count is three")
	{
		REQUIRE(std::size(kPlrStartListDescriptors) == 3);
	}

	SECTION("Identity pins: pList members are the named C4SPlrStart lists")
	{
		// mutation M1's catcher: named-member pins, not just non-null
		REQUIRE(kPlrStartListDescriptors[0].pList == &C4SPlrStart::HomeBaseMaterial);
		REQUIRE(kPlrStartListDescriptors[1].pList == &C4SPlrStart::HomeBaseProduction);
		REQUIRE(kPlrStartListDescriptors[2].pList == &C4SPlrStart::BuildKnowledge);
	}

	SECTION("Row structure: label != key, both non-empty (the research §8 gate)")
	{
		for (const auto &Descriptor : kPlrStartListDescriptors)
		{
			CAPTURE(Descriptor.szLabel, Descriptor.szIniKey);
			REQUIRE(Descriptor.szLabel != nullptr);
			REQUIRE(Descriptor.szLabel[0] != '\0');
			REQUIRE(Descriptor.szIniKey != nullptr);
			REQUIRE(Descriptor.szIniKey[0] != '\0');
			REQUIRE(std::string{Descriptor.szLabel} != std::string{Descriptor.szIniKey});
		}
	}

	SECTION("Labels and keys are pairwise unique")
	{
		for (std::size_t i = 0; i < std::size(kPlrStartListDescriptors); ++i)
			for (std::size_t j = i + 1; j < std::size(kPlrStartListDescriptors); ++j)
			{
				CAPTURE(i, j);
				CHECK(std::string{kPlrStartListDescriptors[i].szLabel} != std::string{kPlrStartListDescriptors[j].szLabel});
				CHECK(std::string{kPlrStartListDescriptors[i].szIniKey} != std::string{kPlrStartListDescriptors[j].szIniKey});
			}
	}

	SECTION("Category-filter pins")
	{
		REQUIRE(kPlrStartListDescriptors[0].dwDefCategory == C4D_SelectHomebase);
		REQUIRE(kPlrStartListDescriptors[1].dwDefCategory == C4D_SelectHomebase);
		REQUIRE(kPlrStartListDescriptors[2].dwDefCategory == C4D_SelectKnowledge);
	}

	SECTION("Count-channel rows: stock {1,25,5}, rate {1,10,1}, blueprints presence")
	{
		REQUIRE(kPlrStartListDescriptors[0].fCountChannel);
		REQUIRE(kPlrStartListDescriptors[0].iCountMin == 1);
		REQUIRE(kPlrStartListDescriptors[0].iCountMax == 25);
		REQUIRE(kPlrStartListDescriptors[0].iDefault == 5);
		REQUIRE(kPlrStartListDescriptors[1].fCountChannel);
		REQUIRE(kPlrStartListDescriptors[1].iCountMin == 1);
		REQUIRE(kPlrStartListDescriptors[1].iCountMax == 10);
		REQUIRE(kPlrStartListDescriptors[1].iDefault == 1);
		REQUIRE(!kPlrStartListDescriptors[2].fCountChannel);
		REQUIRE(kPlrStartListDescriptors[2].fPresenceIdiom);
	}

	SECTION("Range-validity trinity per count row (min < max, default in range)")
	{
		for (const auto &Descriptor : kPlrStartListDescriptors)
		{
			if (!Descriptor.fCountChannel) continue;
			CAPTURE(Descriptor.szIniKey);
			REQUIRE(Descriptor.iCountMin < Descriptor.iCountMax);
			REQUIRE(Descriptor.iDefault >= Descriptor.iCountMin);
			REQUIRE(Descriptor.iDefault <= Descriptor.iCountMax);
		}
	}
}

TEST_CASE("PlrStartCountResolver", "[slider-contract]")
{
	const C4PlrStartListDescriptor &rStock = kPlrStartListDescriptors[0];
	const C4PlrStartListDescriptor &rRestock = kPlrStartListDescriptors[1];
	const C4PlrStartListDescriptor &rKnowledge = kPlrStartListDescriptors[2];

	SECTION("Authored count in range becomes the default")
	{
		const C4PlrStartCountParams Params = ResolvePlrStartCountParams(rStock, 7);
		REQUIRE(Params.fEligible);
		REQUIRE(Params.iMin == 1);
		REQUIRE(Params.iMax == 25);
		REQUIRE(Params.iDefault == 7);
	}

	SECTION("Over-ceiling authored count pins for display without expanding the range")
	{
		// FIXED range — the contrast to the win-condition resolver, whose
		// ceiling grows to cover the authored count (shipped instance:
		// authored 30 stock pins at 25 for display, the list keeps 30)
		const C4PlrStartCountParams Params = ResolvePlrStartCountParams(rStock, 30);
		REQUIRE(Params.fEligible);
		REQUIRE(Params.iMin == 1);
		REQUIRE(Params.iMax == 25);
		REQUIRE(Params.iDefault == 25);
	}

	SECTION("Absent rows floor at the descriptor default")
	{
		const C4PlrStartCountParams ParamsStock = ResolvePlrStartCountParams(rStock, 0);
		REQUIRE(ParamsStock.fEligible);
		REQUIRE(ParamsStock.iDefault == 5);
		const C4PlrStartCountParams ParamsRestock = ResolvePlrStartCountParams(rRestock, 0);
		REQUIRE(ParamsRestock.fEligible);
		REQUIRE(ParamsRestock.iDefault == 1);
	}

	SECTION("Presence rows are ineligible (no count slider)")
	{
		const C4PlrStartCountParams Params = ResolvePlrStartCountParams(rKnowledge, 5);
		REQUIRE(!Params.fEligible);
	}
}

// --- PlrStart INI-name round-trip (spec § Test plan T2; mutation M2's
// catcher — a symmetric rename round-trips clean, so the textual pins
// below are what actually break under the mutation) ----------------------
TEST_CASE("PlrStartCompileFuncRoundTrip", "[slider-contract]")
{
	C4SPlrStart Authored;
	Authored.Default();
	Authored.BuildKnowledge.SetIDCount(C4Id("HUT2"), 0, true);
	Authored.BuildKnowledge.SetIDCount(C4Id("WMIL"), 0, true);
	Authored.HomeBaseMaterial.SetIDCount(C4Id("CNKT"), 3, true);
	Authored.HomeBaseMaterial.SetIDCount(C4Id("LOAM"), 5, true);
	Authored.HomeBaseProduction.SetIDCount(C4Id("CNKT"), 3, true);
	Authored.HomeBaseProduction.SetIDCount(C4Id("LOAM"), 5, true);

	// T2a — write pin: the serialized [Player1] section carries the three
	// canonical INI names (C4Scenario.cpp:278-280)
	const std::string sSerialized = DecompileToBuf<StdCompilerINIWrite>(mkNamingAdapt(Authored, "Player1"));
	CAPTURE(sSerialized);
	REQUIRE(sSerialized.find("Knowledge=") != std::string::npos);
	REQUIRE(sSerialized.find("HomeBaseMaterial=") != std::string::npos);
	REQUIRE(sSerialized.find("HomeBaseProduction=") != std::string::npos);

	// T2b — read pin: a canonical authored [Player1] section repopulates
	// the lists (the count-0 knowledge idiom survives: GetIDCount(id,1))
	{
		C4SPlrStart ReParsed;
		ReParsed.Default();
		CompileFromBuf<StdCompilerINIRead>(mkNamingAdapt(ReParsed, "Player1"),
			StdStrBuf{"[Player1]\nKnowledge=HUT2=0;WMIL=0\nHomeBaseMaterial=CNKT=3;LOAM=5\nHomeBaseProduction=CNKT=3;LOAM=5\n"});
		REQUIRE(ReParsed.BuildKnowledge.GetIDCount(C4Id("HUT2"), 1) == 1);
		REQUIRE(ReParsed.BuildKnowledge.GetIndex(C4Id("WMIL")) >= 0);
		REQUIRE(ReParsed.HomeBaseMaterial.GetIDCount(C4Id("CNKT")) == 3);
		REQUIRE(ReParsed.HomeBaseMaterial.GetIDCount(C4Id("LOAM")) == 5);
		REQUIRE(ReParsed.HomeBaseProduction.GetIDCount(C4Id("CNKT")) == 3);
	}

	// T2c — round-trip: decompile -> parse == original, list by list
	{
		C4SPlrStart RoundTripped;
		RoundTripped.Default();
		CompileFromBuf<StdCompilerINIRead>(mkNamingAdapt(RoundTripped, "Player1"),
			StdStrBuf{DecompileToBuf<StdCompilerINIWrite>(mkNamingAdapt(Authored, "Player1")).c_str()});
		REQUIRE(RoundTripped.HomeBaseMaterial == Authored.HomeBaseMaterial);
		REQUIRE(RoundTripped.HomeBaseProduction == Authored.HomeBaseProduction);
		REQUIRE(RoundTripped.BuildKnowledge == Authored.BuildKnowledge);
	}
}

// --- Store-tab wrap geometry (spec pregame-store-tab D2) ------------------
// Pure-geometry pins for the dense Store sheet grid. The arithmetic is the
// unit half of the binding player check ("all store rows visible at 1080p
// without scrolling"): the helper family must not regress the wrap math the
// dialog renders with. Integer-only operands throughout.
TEST_CASE("ComputeStoreWrapContract", "[slider-contract]")
{
	SECTION("Columns-from-width: K = max(4, floor(width / 170))")
	{
		REQUIRE(ComputeStoreWrapColumns(1788) == 10);  // measured 1080p Store-list item width (cycle 138 Task 4)
		REQUIRE(ComputeStoreWrapColumns(1174) == 6);   // measured 720p Store-list item width (cycle 138 Task 4)
		REQUIRE(ComputeStoreWrapColumns(600) == 4);    // min-clamp dominates
	}

	SECTION("Bands-from-count: ceil(N / K)")
	{
		REQUIRE(ComputeStoreWrapBands(75, 10) == 8);    // store goods @ K=10
		REQUIRE(ComputeStoreWrapBands(115, 10) == 12);  // blueprints @ K=10
		REQUIRE(ComputeStoreWrapBands(75, 6) == 13);    // store goods @ K=6 (measured 720p)
		REQUIRE(ComputeStoreWrapBands(115, 6) == 20);   // blueprints @ K=6 (measured 720p)
	}

	SECTION("Knights fit budget at 1080p: content 768px <= 810px viewport")
	{
		// Worst measured Knights census (75 store goods + 75 restock + 115
		// blueprint defs across content/Objects.c4d + Knights.c4d):
		// 28 bands*24 + 3*20 headers + 36 editor strip = 768px (formula model).
		REQUIRE(ComputeStoreWrapContentHeight(75, 75, 115, 10) == 768);
		// Cycle-138 Task-4 measurement: the Store list's item width is 1788px
		// and its viewport is 810px tall at 1920x1080 (list bounds 1810x810).
		// 768px of content fits the 810px viewport — no scrollbar on the 1080p
		// Store tab (the player check's no-scroll budget; if these pins fail,
		// K=10 no longer fits and the spec risk-1 fallback applies).
		REQUIRE(768 <= 810);
	}
}
