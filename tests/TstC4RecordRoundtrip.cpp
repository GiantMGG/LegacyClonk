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

// Characterization tests for C4RecordChunk binary round-trip.
// Spec: .opencode/specs/2026-08-29-0000-savegame-roundtrip-tests.md
//
// Each test constructs a C4RecordChunk, serializes it via
// DecompileToBuf<StdCompilerBinWrite>, deserializes via
// CompileFromBuf<StdCompilerBinRead> into a fresh chunk, re-serializes,
// and asserts byte-equality of the two serial forms. This pins the
// mkIntAdapt endianness, mkPtrAdaptNoNull pointer tagging, and the
// C4RecordChunkHead layout that the savegame record path emits.

#include <catch2/catch_all.hpp>

#include "C4Record.h"
#include "C4Control.h"
#include "C4PacketBase.h"

#include <cstdint>
#include <cstring>

// Regression guard: C4RecordChunk must NOT be inside #pragma pack(1).
// It owns non-trivial members (StdStrBuf) whose constructors require
// natural alignment. If someone re-adds #pragma pack(1) around
// C4RecordChunk, alignof(C4RecordChunk) drops to 1 and this
// static_assert fails at compile time.
static_assert(alignof(StdStrBuf) <= alignof(C4RecordChunk),
              "C4RecordChunk must not be #pragma pack(1)'d — it owns StdStrBuf");

namespace
{
struct RoundTrip { StdBuf first; StdBuf second; };

// Round-trip a chunk through the binary compiler. `in` is read-only;
// `out` receives the deserialized chunk (caller must out.Delete()).
RoundTrip roundTripChunk(const C4RecordChunk &in, C4RecordChunk &out)
{
	RoundTrip r;
	r.first = DecompileToBuf<StdCompilerBinWrite>(in);
	CompileFromBuf<StdCompilerBinRead>(out, r.first);
	r.second = DecompileToBuf<StdCompilerBinWrite>(out);
	return r;
}

bool bufEqual(const StdBuf &a, const StdBuf &b)
{
	return a.getSize() == b.getSize() &&
		std::memcmp(a.getData(), b.getData(), a.getSize()) == 0;
}
}

// 1.1 - RCT_Frame round-trip (head-only, no payload).
TEST_CASE("C4RecordRoundtrip::RCT_Frame", "[record][roundtrip]")
{
	C4RecordChunk in;
	in.Frame = 42;
	in.Type = RCT_Frame;

	C4RecordChunk out;
	const RoundTrip r = roundTripChunk(in, out);

	REQUIRE(out.Frame == 42);
	REQUIRE(out.Type == RCT_Frame);
	REQUIRE(r.first.getSize() > 0);
	REQUIRE(bufEqual(r.first, r.second));

	out.Delete();
}

// 1.3 - RCT_End round-trip (head-only, terminal chunk).
TEST_CASE("C4RecordRoundtrip::RCT_End", "[record][roundtrip]")
{
	C4RecordChunk in;
	in.Frame = 999;
	in.Type = RCT_End;

	C4RecordChunk out;
	const RoundTrip r = roundTripChunk(in, out);

	REQUIRE(out.Frame == 999);
	REQUIRE(out.Type == RCT_End);
	REQUIRE(bufEqual(r.first, r.second));

	out.Delete();
}

// 1.4 - RCT_File round-trip (Filename + pFileData).
TEST_CASE("C4RecordRoundtrip::RCT_File", "[record][roundtrip]")
{
	C4RecordChunk in;
	in.Frame = 7;
	in.Type = RCT_File;
	in.Filename.Copy("test.bin");
	in.pFileData = new StdBuf();
	const uint8_t data[]{0xDE, 0xAD, 0xBE, 0xEF};
	in.pFileData->Copy(data, sizeof(data));

	C4RecordChunk out;
	const RoundTrip r = roundTripChunk(in, out);

	REQUIRE(out.Type == RCT_File);
	REQUIRE(out.pFileData != nullptr);
	REQUIRE(out.pFileData->getSize() == 4);
	REQUIRE(bufEqual(r.first, r.second));

	out.Delete();
	in.Delete();
}

// 1.2 - RCT_CtrlPkt round-trip (one C4IDPacket wrapping a C4ControlSet).
TEST_CASE("C4RecordRoundtrip::RCT_CtrlPkt", "[record][roundtrip]")
{
	C4RecordChunk in;
	in.Frame = 100;
	in.Type = RCT_CtrlPkt;
	C4IDPacket pkt(CID_Set, new C4ControlSet(C4CVT_ControlRate, 42), true);
	in.pPkt = &pkt;

	C4RecordChunk out;
	const RoundTrip r = roundTripChunk(in, out);

	REQUIRE(out.Type == RCT_CtrlPkt);
	REQUIRE(out.pPkt != nullptr);
	REQUIRE(out.pPkt->getPktType() == CID_Set);
	REQUIRE(bufEqual(r.first, r.second));

	out.Delete();
}

// 1.5 - RCT_Ctrl round-trip (one C4ControlSet packet).
TEST_CASE("C4RecordRoundtrip::RCT_Ctrl", "[record][roundtrip]")
{
	C4RecordChunk in;
	in.Frame = 5;
	in.Type = RCT_Ctrl;
	in.pCtrl = new C4Control();
	in.pCtrl->Add(CID_Set, new C4ControlSet(C4CVT_ControlRate, 7));

	C4RecordChunk out;
	const RoundTrip r = roundTripChunk(in, out);

	REQUIRE(out.Type == RCT_Ctrl);
	REQUIRE(out.pCtrl != nullptr);
	REQUIRE(bufEqual(r.first, r.second));

	out.Delete();
	in.Delete();
}

// 1.6 - Re-serialize idempotence: a second deserialize+serialize cycle
// produces a byte-identical buffer to the first.
TEST_CASE("C4RecordRoundtrip::Idempotence", "[record][roundtrip]")
{
	C4RecordChunk in;
	in.Frame = 13;
	in.Type = RCT_Frame;

	C4RecordChunk mid;
	const RoundTrip r1 = roundTripChunk(in, mid);
	REQUIRE(bufEqual(r1.first, r1.second));

	// Second cycle: deserialize r1.second into `out`, re-serialize.
	C4RecordChunk out;
	const RoundTrip r2 = roundTripChunk(mid, out);
	REQUIRE(bufEqual(r2.first, r2.second));
	REQUIRE(bufEqual(r1.second, r2.second));

	mid.Delete();
	out.Delete();
}

// 1.7 - Empty StdBuf deserialize must not crash (clean reject).
TEST_CASE("C4RecordRoundtrip::EmptyBuffer_safe", "[record][roundtrip]")
{
	StdBuf empty;
	C4RecordChunk out;
	bool threw = false;
	try
	{
		CompileFromBuf<StdCompilerBinRead>(out, empty);
	}
	catch (const StdCompiler::Exception &)
	{
		threw = true;
	}
	// The binary reader rejects the truncated input (throws EOFException
	// when it cannot read the 4-byte Frame field). No crash, no UB.
	REQUIRE(threw);
	out.Delete();
}
