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

// Stage 1 unit tests for C4Value type coercion.
//
// Exercises C4Value::ConvertTo across every (sourceType, targetType, strict)
// triple, cross-referenced against the C4ScriptCnvMap table in C4Value.cpp.
//
// This test deliberately touches NO network, NO threads, NO file I/O,
// NO RNG, and NO GUI. It exits cleanly.

#include <catch2/catch_all.hpp>

#include "C4Value.h"
#include "C4Id.h"
#include "C4StringTable.h"
#include "C4ValueList.h"
#include "C4ValueHash.h"

#include <cstdint>

// ---------------------------------------------------------------------------
// Coercion table encoded as data. Indexed by [sourceType][targetType].
// Each cell is one of: OK, Error, DirectOld, Int2Id, Guess, Deref.
// This mirrors C4ScriptCnvMap in C4Value.cpp:473.
// ---------------------------------------------------------------------------

namespace
{
	enum CnvKind { OK, Error, DirectOld, Int2Id, Guess, Deref };

	// Rows: C4V_Any, C4V_Int, C4V_Bool, C4V_C4ID, C4V_C4Object, C4V_String,
	//       C4V_Array, C4V_Map, C4V_pC4Value
	// Cols: same order.
	const CnvKind CnvTable[9][9] = {
		// tgt:  Any       Int       Bool      C4ID      C4Object  String    Array     Map       pC4Value
		/* Any */      { OK,      Guess,    Guess,    Guess,    Guess,    Guess,    Guess,    Guess,    Error },
		/* Int */      { OK,      OK,       OK,       Int2Id,   Error,    Error,    Error,    Error,    Error },
		/* Bool */     { OK,      OK,       OK,       DirectOld,Error,    Error,    Error,    Error,    Error },
		/* C4ID */     { OK,      DirectOld,OK,       OK,       Error,    Error,    Error,    Error,    Error },
		/* C4Object */ { OK,      DirectOld,OK,       Error,    OK,       Error,    Error,    Error,    Error },
		/* String */   { OK,      DirectOld,OK,       Error,    Error,    OK,       Error,    Error,    Error },
		/* Array */    { OK,      Error,    OK,       Error,    Error,    Error,    OK,       Error,    Error },
		/* Map */      { OK,      Error,    OK,       Error,    Error,    Error,    Error,    OK,       Error },
		/* pC4Value */ { Deref,   Deref,    Deref,    Deref,    Deref,    Deref,    Deref,    Deref,    OK },
	};

	// Expected ConvertTo result for a (source, target, strict, sourceDataIsZero) triple.
	// Returns the expected boolean result.
	bool ExpectedCnvResult(C4V_Type src, C4V_Type tgt, bool strict, bool sourceIsNil)
	{
		CnvKind kind = CnvTable[static_cast<int>(src)][static_cast<int>(tgt)];
		switch (kind)
		{
		case OK:       return true;
		case Error:    return false;
		case DirectOld:return !strict; // false in strict, true in non-strict (no-op)
		case Int2Id:   return true;    // caller must ensure int is in [0, 9999]
		case Guess:    return sourceIsNil ? true : true; // FnCnvGuess returns true for nil
		case Deref:    // FnCnvDeref dereferences (to the pointed-to Int 7) and retries
			return ExpectedCnvResult(C4V_Int, tgt, strict, false);
		}
		return false;
	}

	// Construct a C4Value of the given source type for the matrix sweep.
	// Non-null fixtures are used for every pointer type that can be constructed
	// without engine state (String, Array, Map, pC4Value). C4V_C4Object is the
	// sole exception: a real C4Object requires a live C4Section/Game, so it is
	// constructed with nullptr which collapses to a nil C4V_Any. The sweep uses
	// the value's *actual* type (val.GetType()) for expected-result lookup, so
	// the C4V_C4Object row is effectively tested via the C4V_Any (nil) row.
	C4Value MakeSourceValue(C4V_Type type, C4StringTable &table)
	{
		switch (type)
		{
		case C4V_Any:       return C4Value{};
		case C4V_Int:       return C4Value{C4ValueInt{42}};
		case C4V_Bool:      return C4Value{true};
		case C4V_C4ID:      return C4Value{C4ID{1234}};
		case C4V_C4Object:  return C4Value{static_cast<C4Object *>(nullptr)};
		case C4V_String:    return C4Value{new C4String{"test", &table}};
		case C4V_Array:     return C4Value{new C4ValueArray{}};
		case C4V_Map:       return C4Value{new C4ValueHash{}};
		case C4V_pC4Value:  return C4Value{new C4Value{C4ValueInt{7}}};
		}
		return C4Value{};
	}
}

// ---------------------------------------------------------------------------
// Test: full coercion matrix sweep for constructable source types.
// ---------------------------------------------------------------------------

TEST_CASE("C4Value coercion matrix covers all type pairs", "[C4Value][Coercion]")
{
	// Sweep all 9 source types. Non-null fixtures are used for every pointer
	// type that can be constructed without engine state (String, Array, Map,
	// pC4Value). C4V_C4Object is constructed with nullptr (collapses to nil
	// C4V_Any) because a real C4Object requires a live C4Section/Game.
	const C4V_Type allSourceTypes[] = {
		C4V_Any, C4V_Int, C4V_Bool, C4V_C4ID,
		C4V_C4Object, C4V_String, C4V_Array, C4V_Map, C4V_pC4Value
	};
	const C4V_Type allTargetTypes[] = {
		C4V_Any, C4V_Int, C4V_Bool, C4V_C4ID,
		C4V_C4Object, C4V_String, C4V_Array, C4V_Map, C4V_pC4Value
	};

	C4StringTable table;

	for (C4V_Type src : allSourceTypes)
	{
		for (C4V_Type tgt : allTargetTypes)
		{
			for (bool strict : {false, true})
			{
				C4Value val = MakeSourceValue(src, table);
				bool sourceIsNil = val.IsNil();
				bool result = val.ConvertTo(tgt, strict);
				// ConvertTo indexes C4ScriptCnvMap by the value's *raw* Type
				// field, not the dereferenced type reported by GetType().
				// C4V_C4Object is constructed with nullptr which collapses to
				// a nil C4V_Any, so its expected results come from the
				// C4V_Any row. Every other source type retains its raw Type,
				// so the requested `src` is the correct table row.
				C4V_Type tableSrc = (src == C4V_C4Object) ? C4V_Any : src;
				bool expected = ExpectedCnvResult(tableSrc, tgt, strict, sourceIsNil);

				INFO("src=" << GetC4VName(src) << " tgt=" << GetC4VName(tgt)
				     << " strict=" << strict << " => got=" << result
				     << " expected=" << expected);
				REQUIRE(result == expected);
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Test: FnCnvInt2Id range boundary [0, 9999].
// ---------------------------------------------------------------------------

TEST_CASE("FnCnvInt2Id range boundary", "[C4Value][Coercion]")
{
	struct Case { C4ValueInt value; bool shouldSucceed; };
	const Case cases[] = {
		{-1,    false},
		{0,     true},
		{9999,  true},
		{10000, false},
	};

	for (const auto &c : cases)
	{
		C4Value val{c.value};
		bool result = val.ConvertTo(C4V_C4ID, false);
		INFO("int=" << c.value << " => C4ID result=" << result);
		REQUIRE(result == c.shouldSucceed);
		if (c.shouldSucceed)
		{
			REQUIRE(val.GetType() == C4V_C4ID);
			REQUIRE(val._getC4ID() == static_cast<C4ID>(c.value));
		}
	}
}

// ---------------------------------------------------------------------------
// Test: strict mode rejects FnCnvDirectOld cross-type coercions.
// ---------------------------------------------------------------------------

TEST_CASE("Strict mode rejects CnvDirectOld cross-type coercions", "[C4Value][Coercion]")
{
	// C4V_Bool → C4V_C4ID uses CnvDirectOld.
	SECTION("Bool to C4ID")
	{
		C4Value val{true};
		REQUIRE_FALSE(val.ConvertTo(C4V_C4ID, true));   // strict: reject
		REQUIRE(val.ConvertTo(C4V_C4ID, false));        // non-strict: allow (no-op)
	}

	// C4V_C4ID → C4V_Int uses CnvDirectOld.
	SECTION("C4ID to Int")
	{
		C4Value val{C4ID{1234}};
		REQUIRE_FALSE(val.ConvertTo(C4V_Int, true));    // strict: reject
		REQUIRE(val.ConvertTo(C4V_Int, false));         // non-strict: allow (no-op)
	}
}

// ---------------------------------------------------------------------------
// Test: nil (C4V_Any with Data.Raw == 0) converts to every non-pC4Value type.
// ---------------------------------------------------------------------------

TEST_CASE("Nil converts to every type except pC4Value", "[C4Value][Coercion]")
{
	const C4V_Type allTypes[] = {
		C4V_Any, C4V_Int, C4V_Bool, C4V_C4ID,
		C4V_C4Object, C4V_String, C4V_Array, C4V_Map, C4V_pC4Value
	};

	for (C4V_Type tgt : allTypes)
	{
		C4Value nil{};
		REQUIRE(nil.IsNil());
		bool result = nil.ConvertTo(tgt, false);

		if (tgt == C4V_pC4Value)
		{
			INFO("nil → pC4Value should fail");
			REQUIRE_FALSE(result);
		}
		else
		{
			INFO("nil → " << GetC4VName(tgt) << " should succeed");
			REQUIRE(result);
		}
	}
}

// ---------------------------------------------------------------------------
// Test: idempotence — converting an already-converted value is a no-op.
// ---------------------------------------------------------------------------

TEST_CASE("Coercion idempotence for identity conversions", "[C4Value][Coercion]")
{
	SECTION("Int to Int")
	{
		C4Value val{C4ValueInt{42}};
		REQUIRE(val.ConvertTo(C4V_Int));
		REQUIRE(val.GetType() == C4V_Int);
		REQUIRE(val._getInt() == 42);
		// Second conversion is a no-op.
		REQUIRE(val.ConvertTo(C4V_Int));
		REQUIRE(val._getInt() == 42);
	}

	SECTION("Bool to Bool")
	{
		C4Value val{true};
		REQUIRE(val.ConvertTo(C4V_Bool));
		REQUIRE(val.GetType() == C4V_Bool);
		REQUIRE(val._getBool() == true);
	}

	SECTION("C4ID to C4ID")
	{
		C4Value val{C4ID{1234}};
		REQUIRE(val.ConvertTo(C4V_C4ID));
		REQUIRE(val.GetType() == C4V_C4ID);
		REQUIRE(val._getC4ID() == C4ID{1234});
	}
}

// ---------------------------------------------------------------------------
// Test: rejected coercions leave the value's type unchanged.
// ---------------------------------------------------------------------------

TEST_CASE("Rejected coercions leave source type unchanged", "[C4Value][Coercion]")
{
	// C4V_Int → C4V_C4Object is CnvError.
	C4Value val{C4ValueInt{42}};
	REQUIRE_FALSE(val.ConvertTo(C4V_C4Object, false));
	REQUIRE(val.GetType() == C4V_Int);
	REQUIRE(val._getInt() == 42);
}
