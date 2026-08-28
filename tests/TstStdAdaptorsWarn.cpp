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

// Focused regression test for the StdAdaptors unknown-value-name Warn
// format-string fix (spec defcore-format-compat-fix, root cause D).
//
// C4EnumAdaptWithInfo::CompileFunc calls pComp->Warn("Unknown value name: %s",
// name.c_str()) at StdAdaptors.h:931 when a serialized enum value does not
// match any registered name. StdCompiler::Warn (StdCompiler.h:312) is a
// std::format_string variadic template, so the printf-style "%s" was printed
// literally and the offending name was silently dropped.
//
// This test drives the C4EnumAdapt reading path with a minimal StdCompiler
// test double that forces the not-an-int / read-as-string fallback, feeds an
// unregistered name, and asserts the captured Warn message names the value
// legibly.

#include <catch2/catch_all.hpp>

#include "StdAdaptors.h"

#include <string>

enum class TestColor { Red, Green, Blue };

template<>
struct C4EnumInfo<TestColor>
{
	static constexpr auto data = mkEnumInfo<TestColor>("TestColor", {
		{TestColor::Red,   "Red"},
		{TestColor::Green, "Green"},
		{TestColor::Blue,  "Blue"},
	});
};

namespace
{
	// Minimal StdCompiler reading-mode double. DWord throws NotFoundException
	// to force the C4EnumAdapt read-as-string fallback (StdAdaptors.h:915-919);
	// String injects the candidate name that CompileFunc will check against the
	// registered enum names.
	class TestCompiler : public StdCompiler
	{
	public:
		std::string nextString{"Bogus"};

		bool isCompiler() override { return true; }
		bool hasNaming() override { return true; }

		void DWord(int32_t &) override { excNotFound("not an int"); }
		void String(std::string &str, RawCompileType) override { str = nextString; }

		void QWord(int64_t &) override {}
		void QWord(uint64_t &) override {}
		void DWord(uint32_t &) override {}
		void Word(int16_t &) override {}
		void Word(uint16_t &) override {}
		void Byte(int8_t &) override {}
		void Byte(uint8_t &) override {}
		void Boolean(bool &) override {}
		void Character(char &) override {}
		void String(char *, size_t, RawCompileType) override {}
		void Raw(void *, size_t, RawCompileType) override {}
	};

	struct WarnCapture
	{
		std::string lastMessage;
		static void callback(void *data, const char *, const char *msg)
		{
			static_cast<WarnCapture *>(data)->lastMessage = msg;
		}
	};
}

TEST_CASE("C4EnumAdapt unknown value name produces legible Warn", "[StdAdaptors]")
{
	TestCompiler compiler;
	WarnCapture capture;
	compiler.setWarnCallback(&WarnCapture::callback, &capture);

	TestColor value{TestColor::Red};
	auto adapt = mkEnumAdapt(value, C4EnumAdaptPrefixMode::None);
	adapt.CompileFunc(&compiler);

	REQUIRE(capture.lastMessage.find("Bogus") != std::string::npos);
	REQUIRE(capture.lastMessage.find("%s") == std::string::npos);
	REQUIRE(capture.lastMessage == "Unknown value name: Bogus");
}
