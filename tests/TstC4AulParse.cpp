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

// Stage 2 unit tests for the C4Aul parser's bytecode generation.
//
// Feeds C4Script expression snippets through the parser (via ParseFn with
// fExprOnly=true, the same path used by DirectExec) and asserts the emitted
// C4AulBCCType sequence in the script's Code vector.
//
// This test deliberately touches NO network, NO threads, NO file I/O,
// NO RNG, and NO GUI. It exits cleanly.

#include <catch2/catch_all.hpp>

#include "C4Aul.h"

#include <cstddef>
#include <vector>

// ---------------------------------------------------------------------------
// Test-only subclass: re-expose protected C4AulScript members.
//
// This mirrors the protected-member re-exposure pattern already used in
// TstC4NetIO.cpp (TcpFramingShim, UdpShim). No engine sources are modified.
// ---------------------------------------------------------------------------

class TestScript : public C4AulScript
{
public:
	using C4AulScript::Script;
	using C4AulScript::State;
	using C4AulScript::Code;
	using C4AulScript::Preparse;
	using C4AulScript::ParseFn;
	using C4AulScript::Reg2List;
};

// ---------------------------------------------------------------------------
// Helper: parse a bare expression and return the emitted BccType sequence.
//
// Creates a fresh C4AulScriptEngine + TestScript child for each call so
// tests do not leak state into each other. The engine's destructor calls
// Clear() which deletes child scripts (and their owned functions).
// ---------------------------------------------------------------------------

namespace
{
	struct Parsed
	{
		std::vector<C4AulBCCType> types;
		std::vector<std::intptr_t> xs;
	};

	Parsed ParseExpression(const char *src)
	{
		C4AulScriptEngine engine;

		auto *script = new TestScript();
		script->Script.Copy(src);
		script->Strict = C4AulScriptStrict::MAXSTRICT;
		script->State = ASS_LINKED;
		script->Reg2List(&engine, &engine);

		auto *fn = new C4AulScriptFunc(script, "");
		fn->Script = script->Script.getData();
		fn->pOrgScript = script;

		script->ParseFn(fn, true);

		Parsed result;
		for (size_t i = 0; i < script->Code.size(); ++i)
		{
			result.types.push_back(script->Code[i].bccType);
			result.xs.push_back(script->Code[i].bccX);
		}
		return result;
	}
}

// ---------------------------------------------------------------------------
// Tests: arithmetic operator precedence.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: arithmetic operator precedence 2+3*4", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("2+3*4");

	// Expected postfix: AB_INT(2), AB_INT(3), AB_INT(4), AB_Mul, AB_Sum, AB_RETURN
	REQUIRE(parsed.types.size() >= 6);
	REQUIRE(parsed.types[0] == AB_INT);
	REQUIRE(parsed.xs[0] == 2);
	REQUIRE(parsed.types[1] == AB_INT);
	REQUIRE(parsed.xs[1] == 3);
	REQUIRE(parsed.types[2] == AB_INT);
	REQUIRE(parsed.xs[2] == 4);
	REQUIRE(parsed.types[3] == AB_Mul);
	REQUIRE(parsed.types[4] == AB_Sum);
	REQUIRE(parsed.types[5] == AB_RETURN);
}

TEST_CASE("Parser: multiplication before addition 2*3+4", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("2*3+4");

	// Expected: AB_INT(2), AB_INT(3), AB_Mul, AB_INT(4), AB_Sum, AB_RETURN
	REQUIRE(parsed.types.size() >= 6);
	REQUIRE(parsed.types[0] == AB_INT);
	REQUIRE(parsed.types[1] == AB_INT);
	REQUIRE(parsed.types[2] == AB_Mul);
	REQUIRE(parsed.types[3] == AB_INT);
	REQUIRE(parsed.xs[3] == 4);
	REQUIRE(parsed.types[4] == AB_Sum);
	REQUIRE(parsed.types[5] == AB_RETURN);
}

// ---------------------------------------------------------------------------
// Test: string concatenation produces AB_STRING, AB_STRING, AB_Concat.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: string concatenation", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("\"a\"..\"b\"");

	// Expected: AB_STRING, AB_STRING, AB_Concat, AB_RETURN
	REQUIRE(parsed.types.size() >= 4);
	REQUIRE(parsed.types[0] == AB_STRING);
	REQUIRE(parsed.types[1] == AB_STRING);
	REQUIRE(parsed.types[2] == AB_Concat);
	REQUIRE(parsed.types[3] == AB_RETURN);
}

// ---------------------------------------------------------------------------
// Test: nil literal produces AB_NIL.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: nil literal produces AB_NIL", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("nil");

	// Expected: AB_NIL, AB_RETURN
	REQUIRE(parsed.types.size() >= 2);
	REQUIRE(parsed.types[0] == AB_NIL);
	REQUIRE(parsed.types[1] == AB_RETURN);
}

// ---------------------------------------------------------------------------
// Test: int literal + return produces AB_INT(42), AB_RETURN.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: int literal produces AB_INT and AB_RETURN", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("42");

	// Expected: AB_INT(42), AB_RETURN
	REQUIRE(parsed.types.size() >= 2);
	REQUIRE(parsed.types[0] == AB_INT);
	REQUIRE(parsed.xs[0] == 42);
	REQUIRE(parsed.types[1] == AB_RETURN);
}

// ---------------------------------------------------------------------------
// Test: simple addition 1+2 produces AB_INT, AB_INT, AB_Sum.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: simple addition 1+2", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("1+2");

	// Expected: AB_INT(1), AB_INT(2), AB_Sum, AB_RETURN
	REQUIRE(parsed.types.size() >= 4);
	REQUIRE(parsed.types[0] == AB_INT);
	REQUIRE(parsed.xs[0] == 1);
	REQUIRE(parsed.types[1] == AB_INT);
	REQUIRE(parsed.xs[1] == 2);
	REQUIRE(parsed.types[2] == AB_Sum);
	REQUIRE(parsed.types[3] == AB_RETURN);
}

// ---------------------------------------------------------------------------
// Test: subtraction produces AB_Sub.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: subtraction 10-3", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("10-3");

	// Expected: AB_INT(10), AB_INT(3), AB_Sub, AB_RETURN
	REQUIRE(parsed.types.size() >= 4);
	REQUIRE(parsed.types[0] == AB_INT);
	REQUIRE(parsed.xs[0] == 10);
	REQUIRE(parsed.types[1] == AB_INT);
	REQUIRE(parsed.xs[1] == 3);
	REQUIRE(parsed.types[2] == AB_Sub);
	REQUIRE(parsed.types[3] == AB_RETURN);
}

// ---------------------------------------------------------------------------
// Test: parenthesised expression overrides precedence.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: parenthesised (2+3)*4", "[C4Aul][Parser]")
{
	auto parsed = ParseExpression("(2+3)*4");

	// Expected: AB_INT(2), AB_INT(3), AB_Sum, AB_INT(4), AB_Mul, AB_RETURN
	REQUIRE(parsed.types.size() >= 6);
	REQUIRE(parsed.types[0] == AB_INT);
	REQUIRE(parsed.types[1] == AB_INT);
	REQUIRE(parsed.types[2] == AB_Sum);
	REQUIRE(parsed.types[3] == AB_INT);
	REQUIRE(parsed.xs[3] == 4);
	REQUIRE(parsed.types[4] == AB_Mul);
	REQUIRE(parsed.types[5] == AB_RETURN);
}

// ---------------------------------------------------------------------------
// Test: empty script Preparse succeeds.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: empty script Preparse succeeds", "[C4Aul][Parser]")
{
	C4AulScriptEngine engine;

	auto *script = new TestScript();
	script->Script.Copy("");
	script->Reg2List(&engine, &engine);

	REQUIRE(script->Preparse());
	// Preparse sets State to ASS_PREPARSED on success.
	REQUIRE(script->State == ASS_PREPARSED);
	// An empty script produces no bytecode.
	REQUIRE(script->Code.empty());
}

// ---------------------------------------------------------------------------
// Regression (cycle 78): Parse_Function's ATT_BLCLOSE case computed the
// previous bytecode element as GetCodeByPos(max(GetCodePos(), 1) - 1).
// When Code is empty — the close of the first new-format function of any
// script — the clamp yields index 0 and GetCodeByPos does &Code[0] on an
// empty std::vector: an out-of-bounds read that assert-aborts every
// Debug/ASan-Debug build via _GLIBCXX_ASSERTIONS.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: preparse of script with first new-format function", "[C4Aul][Parser]")
{
	C4AulScriptEngine engine;

	auto *script = new TestScript();
	script->Script.Copy("#strict 2\nfunc Foo() {}");
	script->Reg2List(&engine, &engine);

	REQUIRE(script->Preparse());
	REQUIRE(script->State == ASS_PREPARSED);
}

// ---------------------------------------------------------------------------
// PARSER-mode leg: an empty-body first function must get the implicit
// AB_NIL, AB_RETURN pair (CPos == nullptr -> !CPos branch). Exact-shape
// assertions so any regression of the !CPos branch fails loudly instead
// of re-introducing silent UB.
// ---------------------------------------------------------------------------

TEST_CASE("Parser: empty-body first function gets implicit return", "[C4Aul][Parser]")
{
	C4AulScriptEngine engine;

	auto *script = new TestScript();
	script->Strict = C4AulScriptStrict::MAXSTRICT;
	script->State = ASS_LINKED;
	script->Reg2List(&engine, &engine);

	auto *fn = new C4AulScriptFunc(script, "Foo");
	fn->Script = "}";
	fn->bNewFormat = true;
	fn->pOrgScript = script;

	script->ParseFn(fn, false);

	REQUIRE(script->Code.size() == 2);
	REQUIRE(script->Code[0].bccType == AB_NIL);
	REQUIRE(script->Code[1].bccType == AB_RETURN);
}
