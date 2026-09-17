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

// Language-table regression test (spec translate-new-dialogs).
//
// Parses the actual shipped string tables (planet/System.c4g/LanguageUS.txt
// and LanguageDE.txt) through the real C4ResStrTable parser and asserts:
//
//  1. FULL COVERAGE — for every C4ResStrTableKey 0..NumberOfEntries-1 the
//     entry resolves in BOTH tables (no "[Undefined: ...]" fallback). The
//     engine fills every missing key with "[Undefined: KEY]" plus a spdlog
//     warning, so this is a hard gate that any future key added to
//     src/C4ResStrTable.txt must also be added to the language tables here.
//
//  2. SPOT CHECKS — the dialogs that moved to the string table this cycle
//     (welcome dialog + pre-game options dialog) must read back byte-exact.
//     German values are asserted as raw Latin-1 bytes (the table files are
//     ISO-8859-1), e.g. "Zur\xFCck".
//
// The parser converts "\n" escapes in values to CRLF; expected values below
// use "\r\n" where the shipped table contains the backslash-n escape.

#include <catch2/catch_all.hpp>

#include "C4ResStrTable.h"

#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>
#include <string_view>

#ifndef LANG_SRC_DIR
#error "LANG_SRC_DIR must be defined (see tests/CMakeLists.txt)"
#endif

namespace
{
	std::string ReadTableFile(const char *szName)
	{
		std::ifstream f(
			std::string{LANG_SRC_DIR} + "/planet/System.c4g/" + szName,
			std::ios::binary);
		REQUIRE(f.good());
		std::ostringstream ss;
		ss << f.rdbuf();
		return ss.str();
	}

	TEST_CASE("LanguageTables_FullCoverage_NoUndefinedEntries", "[language-tables]")
	{
		const auto usText = ReadTableFile("LanguageUS.txt");
		const auto deText = ReadTableFile("LanguageDE.txt");
		const C4ResStrTable us{"US", usText};
		const C4ResStrTable de{"DE", deText};

		for (std::uint16_t i = 0; i < std::to_underlying(C4ResStrTableKey::NumberOfEntries); ++i)
		{
			const auto key = static_cast<C4ResStrTableKey>(i);
			CAPTURE(i);
			INFO("US entry for key");
			REQUIRE_FALSE(us.GetEntry(key).starts_with("[Undefined:"));
			INFO("DE entry for key");
			REQUIRE_FALSE(de.GetEntry(key).starts_with("[Undefined:"));
		}
	}

	TEST_CASE("LanguageTables_WelcomeDialog_SpotChecks", "[language-tables]")
	{
		const auto usText = ReadTableFile("LanguageUS.txt");
		const auto deText = ReadTableFile("LanguageDE.txt");
		const C4ResStrTable us{"US", usText};
		const C4ResStrTable de{"DE", deText};

		// GetEntry returns std::string_view; assertion operands must be wrapped in
		// std::string because the MSVC prebuilt deps Catch2 lib lacks the
		// StringMaker<std::string_view> definition (CATCH_CONFIG_CPP17_STRING_VIEW).

		// --- English (welcome dialog, C4StartupWelcomeDlg.cpp) ------------
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_WELCOME_TITLE)} == "Welcome to LegacyClonk");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_WELCOME_PLAYTUTORIAL)} == "Play tutorial");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_WELCOME_SKIP)} == "Skip for now");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_WELCOME_READGUIDE)} == "Read the 5-minute quickstart");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_WELCOME_BODY)}
			== "Clonk is a tactical action game of digging, building and commanding.\r\n"
			   "Would you like to play the voiced tutorial?");

		// --- German (welcome dialog), byte-exact Latin-1 -------------
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_WELCOME_TITLE)} == "Willkommen bei LegacyClonk");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_WELCOME_PLAYTUTORIAL)} == "Tutorial spielen");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_WELCOME_SKIP)} == "Vorerst \xFC" "berspringen");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_WELCOME_READGUIDE)} == "5-Minuten-Kurzanleitung lesen");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_WELCOME_BODY)}
			== "Clonk ist ein taktisches Actionspiel: Du gr\xE4" "bst, baust und befehligst.\r\n"
			   "M\xF6" "chtest du das vertonte Tutorial spielen?");
	}

	TEST_CASE("LanguageTables_PreGameDialog_SpotChecks", "[language-tables]")
	{
		const auto usText = ReadTableFile("LanguageUS.txt");
		const auto deText = ReadTableFile("LanguageDE.txt");
		const C4ResStrTable us{"US", usText};
		const C4ResStrTable de{"DE", deText};

		// GetEntry returns std::string_view; assertion operands must be wrapped in
		// std::string because the MSVC prebuilt deps Catch2 lib lacks the
		// StringMaker<std::string_view> definition (CATCH_CONFIG_CPP17_STRING_VIEW).

		// --- English (pre-game options dialog, C4OfflineOptionsDlg.cpp) ---
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_BTN_WORLDSETTINGS)} == "World Settings");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_BTN_QUICKSTART)} == "Quick Start");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_BTN_BACK)} == "Back");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_CTL_OBJECTIVES)} == "Objectives");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_CTL_RULES)} == "Rules");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_CTL_WINNINGCONDITIONS)} == "Winning Conditions");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_DLG_LANDSCAPE)} == "Landscape");

		// --- German (pre-game options dialog), byte-exact Latin-1 -----
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_BTN_WORLDSETTINGS)} == "Welteinstellungen");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_BTN_QUICKSTART)} == "Schnellstart");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_BTN_BACK)} == "Zur\xFC" "ck");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_CTL_OBJECTIVES)} == "Ziele");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_CTL_RULES)} == "Regeln");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_CTL_WINNINGCONDITIONS)} == "Siegbedingungen");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_DLG_LANDSCAPE)} == "Landschaft");

		// --- pre-existing gap fixes (engine-referenced, tables missed) ---
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_ERR_SECTION)} == "Error loading section.");
		REQUIRE(std::string{us.GetEntry(C4ResStrTableKey::IDS_MSG_VOTE_ENABLED_DESC)} == "Voting is enabled.");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_ERR_SECTION)} == "Fehler beim Laden der Sektion.");
		REQUIRE(std::string{de.GetEntry(C4ResStrTableKey::IDS_MSG_VOTE_ENABLED_DESC)} == "Es wird abgestimmt.");
	}
}
