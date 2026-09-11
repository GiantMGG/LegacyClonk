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

// Winning-condition descriptor tables + shared codec (spec
// adjustable-winning-conditions, cycle 114). The four research §2.1 rows
// tagged 114 ([Game] Mode/Elimination/CooperativeGoal/ValueGain) are
// engine vocabulary: ConvertGoals consumes those enums destructively at
// scenario load (C4Scenario.cpp:96, :583-646) into the [Game]
// Goals/Rules ID lists, so this table encodes/decodes that ID vocabulary
// DIRECTLY against Parameters.Goals/Rules — the runtime truth that
// InitGoals/InitRules (C4Game.cpp:4222-4242), the Parameters.txt savegame
// write, and the cycle-107 JoinData sync already consume. Consumers:
// (1) the Winning Conditions panel + picker count sliders in
// C4OfflineOptionsDlg, (2) the four --parameter parity keys in C4Game.cpp,
// (3) the SliderContract pinning test. No per-ID literals anywhere
// outside this header (the Flash guardrail) — the future DefCore
// [Parameters] grammar refines the eligibility hook without touching the
// dialog.

#pragma once

#include "C4Id.h"
#include "C4IDList.h"
#include "C4Strings.h"

#include <algorithm>
#include <cstddef>
#include <iterator>

// One [Game]-family choice: CLI enum name <-> panel display name <->
// rule/goal object ID. id == C4ID_None marks the row's no-object default
// choice (e.g. "Cooperative"): applying it REMOVES family members
// instead of adding an object.
struct C4WinConditionChoice
{
	const char *szEnumName;    // --parameter/[Game] vocabulary ("ValueGain")
	const char *szDisplayName; // panel vocabulary ("Settlement"); equal to szEnumName where no separate term exists
	C4ID id;                   // family object ID; C4ID_None for the no-object default
};

// One enum-valued [Game] key decoded from / encoded into a Parameters ID list
struct C4WinConditionDescriptor
{
	const char *szIniKey;    // "Mode" | "Elimination" | "CooperativeGoal" (the --parameter key)
	const char *szLabel;     // "Round mode" | "Elimination mode" | "Cooperative goal" (shown)
	const char *szIdListKey; // "Goals" | "Rules" — which Parameters list carries the family
	const C4WinConditionChoice *Choices;
	std::size_t iChoiceCount;
};

// The numeric winning-condition row: [Game] ValueGain <-> VALG count
struct C4WinTargetDescriptor
{
	const char *szIniKey;        // "ValueGain"
	const char *szLabel;         // "Settlement target"
	C4ID id;                     // VALG
	int32_t iPointsPerCount;     // 100 — the ConvertGoals divisor (C4Scenario.cpp:601)
	int32_t iMinCount, iMaxCount, iDefaultCount; // 1, 50 (= VALG MaxUserSelect), 15
	const char *szUnit;          // "points"
};

// The choices the panel offers. MeleeTeamwork/Extended are CLI-only
// deprecated aliases (kWinConditionAliases below) and deliberately NOT
// panel choices: they would promise distinctions the engine no longer
// has (MEL2 self-converts to MELE in its own script; ConvertGoals:591-592
// maps both melee enums to MELE — spec §2 semantics notes).
inline constexpr C4WinConditionChoice kModeChoices[]
{
	{"Cooperative", "Cooperative",    C4ID_None},
	{"Melee",       "Melee",          C4Id("MELE")},
};

inline constexpr C4WinConditionChoice kEliminationChoices[]
{
	{"EliminateCrew",  "Eliminate crew",   C4ID_None},
	{"KillTheCaptain", "Kill the captain", C4Id("KILC")},
	{"CaptureTheFlag", "Capture the flag", C4Id("CTFL")},
};

inline constexpr C4WinConditionChoice kCooperativeGoalChoices[]
{
	{"NoGoal",      "None",       C4ID_None},
	{"Goldmine",    "Goldmine",   C4Id("GLDM")},
	{"Monsterkill", "Monsterkill", C4Id("MNTK")},
	{"ValueGain",   "Settlement", C4Id("VALG")},
};

inline constexpr C4WinConditionDescriptor kWinConditionDescriptors[]
{
	{"Mode",            "Round mode",       "Goals", kModeChoices,            std::size(kModeChoices)},
	{"Elimination",     "Elimination mode", "Rules", kEliminationChoices,     std::size(kEliminationChoices)},
	{"CooperativeGoal", "Cooperative goal", "Goals", kCooperativeGoalChoices, std::size(kCooperativeGoalChoices)},
};

inline constexpr C4WinTargetDescriptor kWinTargetDescriptor
{
	"ValueGain", "Settlement target", C4Id("VALG"), 100, 1, 50, 15, "points",
};

// CLI-only deprecated aliases accepted by --parameter, never offered by
// the panel (spec §3: Melee and MeleeTeamwork both encode to MELE;
// Extended ~= NoGoal — both fall through ConvertGoals:597-602 with no
// goal ID).
struct C4WinConditionAlias
{
	const char *szIniKey;        // owning descriptor key
	const char *szEnumName;      // canonical choice the alias resolves to
	const char *szAliasEnumName; // the deprecated alias
};

inline constexpr C4WinConditionAlias kWinConditionAliases[]
{
	{"Mode",            "Melee",  "MeleeTeamwork"},
	{"CooperativeGoal", "NoGoal", "Extended"},
};

// Family members cleared when a row's selection changes (the surgical
// exclusivity vocabulary). MEL2 is the obsolete alias OBJECT — cleared
// with MELE but never a panel choice. FGRV is deliberately NOT in
// kEliminationFamilyIDs: it is a standalone rule that SURVIVES
// elimination switches (ConvertGoals:634-635 only ADDS it for CTFL).
inline constexpr C4ID kModeFamilyIDs[]            {C4Id("MELE"), C4Id("MEL2")};
inline constexpr C4ID kEliminationFamilyIDs[]     {C4Id("KILC"), C4Id("CTFL")};
inline constexpr C4ID kCooperativeGoalFamilyIDs[] {C4Id("GLDM"), C4Id("MNTK"), C4Id("VALG")};

// Count-slider eligibility/range for one picker row (spec decision (c)):
// eligible iff MaxUserSelect > 1; the ceiling covers authored counts
// above it (shipped instance: CoastalHarbor.c4d authors Goals=MONE=100
// against Wealth's MaxUserSelect=50 — never silently rewrite an authored
// count); default = authored count, floored at 1.
struct C4CountSliderParams
{
	bool fEligible;
	int32_t iMin, iMax, iDefault;
};

constexpr C4CountSliderParams ResolveCountSliderParams(int32_t iMaxUserSelect, int32_t iAuthoredCount)
{
	if (iMaxUserSelect <= 1) return {false, 1, 1, 1};
	return {true, 1,
		(std::max)((std::max)(iMaxUserSelect, iAuthoredCount), 1),
		(std::max)(iAuthoredCount, 1)};
}

// [Game] ValueGain points -> VALG count, floored at one — the
// ConvertGoals:601 formula verbatim ((std::max)(ValueGain / 100, 1)).
constexpr int32_t ValueGainToCount(int32_t iPoints)
{
	return (std::max)(iPoints / 100, 1);
}

// --- lookup helpers --------------------------------------------------------

inline const C4WinConditionDescriptor *FindWinConditionDescriptor(const char *szIniKey)
{
	for (const auto &Descriptor : kWinConditionDescriptors)
		if (SEqualNoCase(szIniKey, Descriptor.szIniKey)) return &Descriptor;
	return nullptr;
}

inline const C4WinConditionChoice *FindWinConditionChoice(const C4WinConditionDescriptor *pDescriptor, const char *szEnumName)
{
	if (!pDescriptor) return nullptr;
	for (std::size_t i = 0; i < pDescriptor->iChoiceCount; ++i)
		if (SEqualNoCase(szEnumName, pDescriptor->Choices[i].szEnumName)) return &pDescriptor->Choices[i];
	return nullptr;
}

inline const C4WinConditionChoice *FindChoiceByID(const C4WinConditionDescriptor *pDescriptor, C4ID id)
{
	if (!pDescriptor) return nullptr;
	for (std::size_t i = 0; i < pDescriptor->iChoiceCount; ++i)
		if (pDescriptor->Choices[i].id == id) return &pDescriptor->Choices[i];
	return nullptr;
}

// Resolve a CLI alias (MeleeTeamwork -> Melee, Extended -> NoGoal);
// non-aliases pass through unchanged.
inline const char *ResolveWinConditionAlias(const char *szIniKey, const char *szEnumName)
{
	for (const auto &Alias : kWinConditionAliases)
		if (SEqualNoCase(szIniKey, Alias.szIniKey) && SEqualNoCase(szEnumName, Alias.szAliasEnumName))
			return Alias.szEnumName;
	return szEnumName;
}

// --- encode ----------------------------------------------------------------

// Remove every family member from rList (index re-queried per ID — safe
// against the DeleteItem index shift).
inline void RemoveFamilyIDs(C4IDList &rList, const C4ID *pIDs, std::size_t iCount)
{
	for (std::size_t i = 0; i < iCount; ++i)
	{
		const int32_t iIndex = rList.GetIndex(pIDs[i]);
		if (iIndex >= 0) rList.DeleteItem(static_cast<std::size_t>(iIndex));
	}
}

// Encode one [Game]-family selection into the Parameters lists (the
// spec's encode columns — the ConvertGoals vocabulary):
//   Mode=Melee        additive: Goals MELE=1, nothing else cleared
//                     (ConvertGoals:591-594 parity — authored goals
//                     survive a mode switch)
//   Mode=Cooperative  Goals: MELE and the obsolete MEL2 removed
//   Elimination       Rules: KILC/CTFL family swap; CaptureTheFlag ALSO
//                     adds FGRV (ConvertGoals:634-635 parity); FGRV is
//                     never removed by this family
//   CooperativeGoal   Goals: GLDM/MNTK/VALG family swap; the chosen
//                     object enters at iAuxCount (floored at 1) iff it
//                     is the target descriptor's ID (VALG), else at 1
// Returns false iff szIniKey/szEnumName name no descriptor/choice —
// unknown names are never partially applied (callers log + skip).
inline bool ApplyWinConditionChoice(C4IDList &rGoals, C4IDList &rRules,
	const char *szIniKey, const char *szEnumName, int32_t iAuxCount)
{
	const C4WinConditionDescriptor *pDescriptor = FindWinConditionDescriptor(szIniKey);
	const C4WinConditionChoice *pChoice =
		FindWinConditionChoice(pDescriptor, ResolveWinConditionAlias(szIniKey, szEnumName));
	if (!pChoice) return false;

	C4IDList &rPrimaryList = SEqualNoCase(pDescriptor->szIdListKey, "Rules") ? rRules : rGoals;

	if (SEqualNoCase(szIniKey, "Mode"))
	{
		if (pChoice->id == C4ID_None)
			RemoveFamilyIDs(rPrimaryList, kModeFamilyIDs, std::size(kModeFamilyIDs));
		else
			rPrimaryList.SetIDCount(pChoice->id, 1, true); // additive — nothing else cleared
	}
	else if (SEqualNoCase(szIniKey, "Elimination"))
	{
		RemoveFamilyIDs(rPrimaryList, kEliminationFamilyIDs, std::size(kEliminationFamilyIDs));
		if (pChoice->id != C4ID_None)
		{
			rPrimaryList.SetIDCount(pChoice->id, 1, true);
			if (pChoice->id == kEliminationFamilyIDs[1]) // CTFL requires FlagRemoveable
				rRules.SetIDCount(C4Id("FGRV"), 1, true);
		}
	}
	else // CooperativeGoal
	{
		RemoveFamilyIDs(rPrimaryList, kCooperativeGoalFamilyIDs, std::size(kCooperativeGoalFamilyIDs));
		if (pChoice->id != C4ID_None)
		{
			const int32_t iCount = (pChoice->id == kWinTargetDescriptor.id)
				? (std::max)(iAuxCount, 1)
				: 1;
			rPrimaryList.SetIDCount(pChoice->id, iCount, true);
		}
	}
	return true;
}

// --- decode ----------------------------------------------------------------

// Decoded panel state (the spec's decode columns). Choice pointers are
// never null: each row falls back to its no-object default when no
// family member is present.
struct C4WinConditionState
{
	const C4WinConditionChoice *pModeChoice;
	const C4WinConditionChoice *pEliminationChoice;
	const C4WinConditionChoice *pGoalChoice;
	int32_t iValueGainCount; // current VALG count (0 if absent)
};

inline C4WinConditionState DecodeWinCondition(const C4IDList &rGoals, const C4IDList &rRules)
{
	const C4WinConditionDescriptor *pModeDescriptor = FindWinConditionDescriptor("Mode");
	const C4WinConditionDescriptor *pEliminationDescriptor = FindWinConditionDescriptor("Elimination");
	const C4WinConditionDescriptor *pGoalDescriptor = FindWinConditionDescriptor("CooperativeGoal");

	C4WinConditionState State{};

	// Mode: MELE — or the obsolete MEL2 alias object — present means melee
	// (the IsMelee vocabulary, C4Scenario.cpp:644-646)
	const C4ID idMelee = kModeFamilyIDs[0], idMeleeObsolete = kModeFamilyIDs[1];
	State.pModeChoice = FindChoiceByID(pModeDescriptor,
		(rGoals.GetIDCount(idMelee) > 0 || rGoals.GetIDCount(idMeleeObsolete) > 0) ? idMelee : C4ID_None);

	// Elimination: KILC wins over CTFL (the combo is single-select anyway);
	// none -> the no-rule-object engine default (Eliminate crew)
	const C4ID idKillCaptain = kEliminationFamilyIDs[0], idCaptureFlag = kEliminationFamilyIDs[1];
	State.pEliminationChoice = FindChoiceByID(pEliminationDescriptor,
		(rRules.GetIDCount(idKillCaptain) > 0) ? idKillCaptain
		: (rRules.GetIDCount(idCaptureFlag) > 0) ? idCaptureFlag : C4ID_None);

	// Cooperative goal: first family member present wins (family order =
	// the ConvertGoals conversion order), none -> NoGoal
	const C4ID idGoldmine = kCooperativeGoalFamilyIDs[0],
		idMonsterkill = kCooperativeGoalFamilyIDs[1],
		idValueGain = kCooperativeGoalFamilyIDs[2];
	State.pGoalChoice = FindChoiceByID(pGoalDescriptor,
		(rGoals.GetIDCount(idGoldmine) > 0) ? idGoldmine
		: (rGoals.GetIDCount(idMonsterkill) > 0) ? idMonsterkill
		: (rGoals.GetIDCount(idValueGain) > 0) ? idValueGain : C4ID_None);

	State.iValueGainCount = rGoals.GetIDCount(kWinTargetDescriptor.id);
	return State;
}
