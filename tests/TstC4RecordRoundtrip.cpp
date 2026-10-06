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
#include "C4SyncDigest.h"
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

// 2.1 - SyncCheck digest round-trip (cycle 203): digests ride the packet as
// six TRAILING hi/lo uint32 varint pairs; a zero-digest serialization ends in
// exactly six 0x00 varint bytes; stripping them yields the legacy shape, which
// must decompile without throwing and leave all three digests 0 (EOF-tolerant
// trailing read).
TEST_CASE("C4RecordRoundtrip::SyncCheckDigest", "[record][roundtrip]")
{
	// Leg 1: non-zero digests round-trip byte-exact.
	{
		auto *sc = new C4ControlSyncCheck();
		sc->LandDigest  = 0x0123456789abcdeeull;
		sc->PXSDigest   = 0xfedcba9876543210ull;
		sc->MoverDigest = 0xdeadbeefcafebabeull;
		C4RecordChunk in;
		in.Frame = 33;
		in.Type = RCT_CtrlPkt;
		C4IDPacket pkt(CID_SyncCheck, sc, true);
		in.pPkt = &pkt;

		C4RecordChunk out;
		const RoundTrip r = roundTripChunk(in, out);
		REQUIRE(r.first.getSize() > 0);
		REQUIRE(bufEqual(r.first, r.second));

		const auto *out_sc = static_cast<const C4ControlSyncCheck *>(out.pPkt->getPkt());
		REQUIRE(out_sc->LandDigest  == 0x0123456789abcdeeull);
		REQUIRE(out_sc->PXSDigest   == 0xfedcba9876543210ull);
		REQUIRE(out_sc->MoverDigest == 0xdeadbeefcafebabeull);

		out.Delete();
	}

	// Leg 2: legacy-shaped truncated buffer decompiles with digests 0.
	{
		auto *sc0 = new C4ControlSyncCheck();
		C4RecordChunk in0;
		in0.Frame = 34;
		in0.Type = RCT_CtrlPkt;
		C4IDPacket pkt0(CID_SyncCheck, sc0, true);
		in0.pPkt = &pkt0;

		C4RecordChunk out0;
		const RoundTrip r0 = roundTripChunk(in0, out0);
		REQUIRE(r0.first.getSize() >= 6);
		// Shape pin: the zero-digest serialization's last six bytes are the
		// six 0x00 digest varints (StdIntPackAdapt value-0 → one byte, G9).
		const uint8_t zeros[6]{};
		REQUIRE(std::memcmp(reinterpret_cast<const uint8_t *>(r0.first.getData())
		            + r0.first.getSize() - 6, zeros, 6) == 0);

		StdBuf legacy;
		legacy.Copy(r0.first);
		legacy.SetSize(legacy.getSize() - 6);

		C4RecordChunk out_l;
		bool threw = false;
		try
		{
			CompileFromBuf<StdCompilerBinRead>(out_l, legacy);
		}
		catch (const StdCompiler::Exception &)
		{
			threw = true;
		}
		REQUIRE(!threw);
		const auto *lsc = static_cast<const C4ControlSyncCheck *>(out_l.pPkt->getPkt());
		REQUIRE(lsc->LandDigest == 0);
		REQUIRE(lsc->PXSDigest == 0);
		REQUIRE(lsc->MoverDigest == 0);

		out0.Delete();
		out_l.Delete();
	}
}

// 2.2 - FNV-1a-64 known-answer (cycle 203): fresh digest == offset basis;
// one 'a' byte → the canonical KAT; le16/le32 match explicit LE byte sequences.
TEST_CASE("C4SyncDigest::Fnv1a64_KAT", "[sync][digest]")
{
	C4SyncDigest fresh;
	REQUIRE(fresh.value() == 0xcbf29ce484222325ull);

	C4SyncDigest one_a;
	one_a.update_byte('a');
	REQUIRE(one_a.value() == 0xaf63dc4c8601ec8cull);

	C4SyncDigest via_le16, via_bytes16;
	via_le16.update_le16(0xBEEF);
	via_bytes16.update_byte(0xEF);
	via_bytes16.update_byte(0xBE);
	REQUIRE(via_le16.value() == via_bytes16.value());

	C4SyncDigest via_le32, via_bytes32;
	via_le32.update_le32(0xDEADBEEFu);
	via_bytes32.update_byte(0xEFu);
	via_bytes32.update_byte(0xBEu);
	via_bytes32.update_byte(0xADu);
	via_bytes32.update_byte(0xDEu);
	REQUIRE(via_le32.value() == via_bytes32.value());
}
