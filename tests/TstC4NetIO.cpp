/*
 * LegacyClonk
 *
 * Copyright (c) 2024, The LegacyClonk Team and contributors
 *
 * Distributed under the terms of the ISC license; see accompanying file
 * "COPYING" for details.
 *
 * "Clonk" is a registered trademark of Matthes Bender, used with permission.
 * See accompanying file "TRADEMARK" for details.
 */

// Hang-proof-by-construction network wire-format + fragmentation unit tests.
//
// This test deliberately touches NO socket syscalls, NO threads, NO real-time
// waits, NO RNG, and NO file I/O. It exercises:
//   * C4NetIOTCP::PackPacket / UnpackPacket (TCP framing)
//   * C4NetIOUDP::Packet / PacketList (UDP fragmentation + reassembly)
// through test-only shims that re-expose protected members. See the
// "CI-hang-prevention audit" task in the implementation plan.

#include <catch2/catch_all.hpp>

#include "C4NetIO.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

// ---------------------------------------------------------------------------
// Test shims -- re-expose protected engine members so the test can name them
// without touching engine sources.
// ---------------------------------------------------------------------------

// Exposes C4NetIOTCP::PackPacket / UnpackPacket (protected virtuals).
// Never Init()ed; never opens a socket.
class TcpFramingShim : public C4NetIOTCP
{
public:
	using C4NetIOTCP::PackPacket;
	using C4NetIOTCP::UnpackPacket;
};

// Exposes the protected nested types of C4NetIOUDP so the test can name them
// as UdpShim::Packet etc. Never instantiated.
class UdpShim : public C4NetIOUDP
{
public:
	using C4NetIOUDP::Packet;
	using C4NetIOUDP::PacketList;
	using C4NetIOUDP::DataPacketHdr;
};

// ---------------------------------------------------------------------------
// TCP framing
// ---------------------------------------------------------------------------

TEST_CASE("TCP framing round-trips a 100-byte payload byte-for-byte", "[C4NetIO][TCP]")
{
	TcpFramingShim tcp;

	// Build a 100-byte payload with a recognizable pattern (0..99 mod 256).
	StdBuf payload; payload.New(100);
	for (size_t i = 0; i < 100; ++i)
	{
		*payload.getMPtr<uint8_t>(i) = static_cast<uint8_t>(i);
	}

	SECTION("Pack then unpack a single packet")
	{
		StdBuf out;
		tcp.PackPacket(C4NetIOPacket(payload), out);

		// Wire format: 0xff + uint32 size + payload  => 1 + 4 + 100 == 105
		REQUIRE(out.getSize() == 105);
		REQUIRE(*out.getPtr<uint8_t>(0) == 0xff);
		uint32_t size;
		std::memcpy(&size, out.getPtr(1), sizeof(size));
		REQUIRE(size == 100u);

		// UnpackPacket returns bytes consumed (no callback installed).
		REQUIRE(tcp.UnpackPacket(out, C4NetIO::addr_t{}) == 105);
	}

	SECTION("Back-to-back packets in one buffer")
	{
		StdBuf out;
		tcp.PackPacket(C4NetIOPacket(payload), out);
		tcp.PackPacket(C4NetIOPacket(payload), out); // append again

		REQUIRE(out.getSize() == 210);
		// UnpackPacket consumes only the first packet.
		REQUIRE(tcp.UnpackPacket(out, C4NetIO::addr_t{}) == 105);
	}

	SECTION("OnPacket callback receives the reconstructed payload")
	{
		struct Recorder : C4NetIO::CBClass
		{
			StdBuf received;
			void OnPacket(const C4NetIOPacket &rPacket, C4NetIO *) override
			{
				received = rPacket; // StdBuf slice copy
			}
		} rec;
		tcp.SetCallback(&rec);

		StdBuf out;
		tcp.PackPacket(C4NetIOPacket(payload), out);

		REQUIRE(tcp.UnpackPacket(out, C4NetIO::addr_t{}) == out.getSize());
		REQUIRE(rec.received == payload);
	}
}

TEST_CASE("TCP framing rejects malformed input", "[C4NetIO][TCP][fuzz]")
{
	TcpFramingShim tcp;

	SECTION("Truncated header (buffer smaller than 5 bytes)")
	{
		StdBuf shortBuf; shortBuf.New(3);
		*shortBuf.getMPtr<uint8_t>(0) = 0xff; // valid magic, but header truncated
		REQUIRE(tcp.UnpackPacket(shortBuf, C4NetIO::addr_t{}) == 0);
	}

	SECTION("Header claims more payload than buffer holds")
	{
		// 5-byte buffer: 0xff + uint32 size = 100, but 0 payload bytes follow.
		StdBuf buf; buf.New(5);
		*buf.getMPtr<uint8_t>(0) = 0xff;
		uint32_t size = 100u;
		std::memcpy(buf.getMPtr(1), &size, sizeof(size));
		REQUIRE(tcp.UnpackPacket(buf, C4NetIO::addr_t{}) == 0);
	}

	SECTION("Overflow size field (iPos + iPacketSize wraps)")
	{
		// 5-byte buffer with size = 0xFFFFFFFF: must NOT be read as "consume everything".
		// Exercises the integer-overflow guard at C4NetIO.cpp:1312.
		StdBuf buf; buf.New(5);
		*buf.getMPtr<uint8_t>(0) = 0xff;
		uint32_t size = 0xFFFFFFFFu;
		std::memcpy(buf.getMPtr(1), &size, sizeof(size));
		REQUIRE(tcp.UnpackPacket(buf, C4NetIO::addr_t{}) == 0);
	}

	SECTION("First byte is not 0xff (corrupt stream)")
	{
		StdBuf buf; buf.New(5);
		*buf.getMPtr<uint8_t>(0) = 0x00; // wrong magic
		// UnpackPacket returns IBuf.getSize() (==5) to signal "drop the buffer".
		REQUIRE(tcp.UnpackPacket(buf, C4NetIO::addr_t{}) == 5);
	}
}

// ---------------------------------------------------------------------------
// UDP fragmentation / reassembly
// ---------------------------------------------------------------------------

TEST_CASE("UDP single-fragment packet reassembles", "[C4NetIO][UDP]")
{
	using Packet = UdpShim::Packet;

	// Payload small enough to fit in one fragment (< MaxDataSize == 499).
	StdBuf payload; payload.New(50);
	for (size_t i = 0; i < 50; ++i)
	{
		*payload.getMPtr<uint8_t>(i) = static_cast<uint8_t>(i);
	}

	Packet pkt(C4NetIOPacket(payload), /*inNr=*/0);
	REQUIRE(pkt.FragmentCnt() == 1);
	// After the Packet(C4NetIOPacket&&, nr_t) ctor, pFragmentGot is nullptr and
	// Complete() returns !Empty() (FragmentPresent returns true when
	// pFragmentGot is null). This is the observed engine behaviour; if the
	// invariant changes the test will flag it.
	REQUIRE(pkt.Complete() == true);

	// GetFragment(0) produces a wire fragment; feed it back through AddFragment
	// on a fresh Packet.
	C4NetIOPacket frag = pkt.GetFragment(0);
	Packet reassembled;
	REQUIRE(reassembled.AddFragment(frag, frag.getAddr()) == true);
	REQUIRE(reassembled.Complete() == true);
	REQUIRE(reassembled.GetData() == payload);
}

TEST_CASE("UDP multi-fragment packet reassembles out-of-order", "[C4NetIO][UDP][frag]")
{
	using Packet = UdpShim::Packet;

	// Pick a payload size > MaxDataSize (499) so we get >= 2 fragments.
	// 1000 bytes -> ceil(1000/499) == 3 fragments.
	constexpr size_t kPayloadSize = 1000;
	StdBuf payload; payload.New(kPayloadSize);
	for (size_t i = 0; i < kPayloadSize; ++i)
	{
		*payload.getMPtr<uint8_t>(i) = static_cast<uint8_t>(i);
	}

	Packet pkt(C4NetIOPacket(payload), /*inNr=*/0);
	REQUIRE(pkt.FragmentCnt() == 3);

	// Generate all three fragments.
	std::array<C4NetIOPacket, 3> frags{
		pkt.GetFragment(0), pkt.GetFragment(1), pkt.GetFragment(2)};

	SECTION("In-order delivery completes")
	{
		Packet reassembled;
		for (auto &f : frags)
		{
			REQUIRE(reassembled.AddFragment(f, f.getAddr()));
		}
		REQUIRE(reassembled.Complete());
		REQUIRE(reassembled.GetData() == payload);
	}

	SECTION("Out-of-order delivery still completes")
	{
		Packet reassembled;
		// Feed frag 2, then 0, then 1.
		REQUIRE(reassembled.AddFragment(frags[2], frags[2].getAddr()));
		REQUIRE(reassembled.AddFragment(frags[0], frags[0].getAddr()));
		REQUIRE(reassembled.AddFragment(frags[1], frags[1].getAddr()));
		REQUIRE(reassembled.Complete());
		REQUIRE(reassembled.GetData() == payload);
	}

	SECTION("Matching duplicate fragment is accepted as an idempotent no-op")
	{
		Packet reassembled;
		REQUIRE(reassembled.AddFragment(frags[0], frags[0].getAddr()));
		REQUIRE(reassembled.AddFragment(frags[1], frags[1].getAddr()));
		// Re-send fragment 0: bytes already present -> AddFragment returns true
		// (engine only rejects a re-send whose bytes DIFFER; see next SECTION).
		REQUIRE(reassembled.AddFragment(frags[0], frags[0].getAddr()) == true);
		REQUIRE(reassembled.AddFragment(frags[2], frags[2].getAddr()));
		REQUIRE(reassembled.Complete());
		REQUIRE(reassembled.GetData() == payload);
	}

	SECTION("Mismatched re-send of a present fragment is rejected")
	{
		Packet reassembled;
		REQUIRE(reassembled.AddFragment(frags[0], frags[0].getAddr()));
		REQUIRE(reassembled.AddFragment(frags[1], frags[1].getAddr()));
		// frag1 is now present; a re-send with a flipped payload byte must be
		// rejected (Data.Compare returns nonzero -> AddFragment returns false).
		C4NetIOPacket bad = frags[1];
		// sizeof(DataPacketHdr) == 13 (packed: 1+4+4+4), but the struct is only
		// forward-declared in the header, so we use the literal.
		*bad.getMPtr<uint8_t>(13u) ^= 0xff;
		REQUIRE(reassembled.AddFragment(bad, bad.getAddr()) == false);
		// State is uncorrupted: completing with frag2 still yields the payload.
		REQUIRE(reassembled.AddFragment(frags[2], frags[2].getAddr()));
		REQUIRE(reassembled.Complete());
		REQUIRE(reassembled.GetData() == payload);
	}

	SECTION("Missing fragment: Packet not Complete; PacketList.GetFirstPacketComplete null")
	{
		using PacketList = UdpShim::PacketList;

		// Heap-allocate so PacketList can take ownership and delete it on
		// destruction (avoids a risky move-construct of Packet).
		Packet *reassembled = new Packet();
		REQUIRE(reassembled->AddFragment(frags[0], frags[0].getAddr()));
		REQUIRE(reassembled->AddFragment(frags[2], frags[2].getAddr()));
		REQUIRE_FALSE(reassembled->Complete());
		REQUIRE_FALSE(reassembled->FragmentPresent(1));
		REQUIRE(reassembled->FragmentPresent(0));
		REQUIRE(reassembled->FragmentPresent(2));

		PacketList list; // default iMaxPacketCnt == ~0u
		REQUIRE(list.AddPacket(reassembled));
		REQUIRE(list.GetFirstPacketComplete() == nullptr);

		// Late-arriving frag 1 completes the packet.
		REQUIRE(reassembled->AddFragment(frags[1], frags[1].getAddr()));
		REQUIRE(reassembled->Complete());
		REQUIRE(list.GetFirstPacketComplete() == reassembled);
		// list's destructor deletes reassembled.
	}

	SECTION("Wrong-FNr fragment is rejected")
	{
		Packet reassembled;
		REQUIRE(reassembled.AddFragment(frags[0], frags[0].getAddr()));
		// Construct a fragment whose header FNr doesn't match iNr (0).
		// Easiest: build a second source Packet with inNr=10 and feed its
		// fragment 0 in. AddFragment checks pHdr->FNr != iNr -> returns false.
		Packet otherPkt(C4NetIOPacket(payload), /*inNr=*/10);
		C4NetIOPacket otherFrag = otherPkt.GetFragment(0);
		REQUIRE(reassembled.AddFragment(otherFrag, otherFrag.getAddr()) == false);
	}

	SECTION("Wire-fragment smaller than sizeof(DataPacketHdr) is rejected")
	{
		StdBuf tiny; tiny.New(2); // smaller than 13-byte DataPacketHdr
		Packet reassembled;
		C4NetIOPacket tinyPkt{tiny, C4NetIO::addr_t{}};
		REQUIRE(reassembled.AddFragment(tinyPkt, tinyPkt.getAddr()) == false);
	}
}

TEST_CASE("UDP zero-byte payload packet", "[C4NetIO][UDP][edge]")
{
	using Packet = UdpShim::Packet;

	StdBuf empty;
	Packet pkt(C4NetIOPacket(empty), /*inNr=*/0);
	// FragmentCnt(): Data.getSize()==0 -> the formula returns 1 anyway.
	REQUIRE(pkt.FragmentCnt() == 1);
	REQUIRE(pkt.Empty());
	// Complete() returns !Empty() check first -> false for empty.
	REQUIRE_FALSE(pkt.Complete());
}
