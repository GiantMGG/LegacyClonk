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

// IPv6 loopback CI smoke test for C4NetIO.
//
// Exercises:
//   1. The AsIPv4() no-op invariant for pure IPv6 addresses.
//   2. C4Network2EndpointAddress serialization round-trip for pure IPv6.
//   3. UDP loopback on ::1 (two C4NetIOSimpleUDP instances).
//   4. TCP loopback on ::1 (C4NetIOTCP listener + client).
//
// All socket I/O is on the loopback interface (::1). No external network,
// no master server, no netpuncher. Hang protection is provided by the
// CTest TIMEOUT property (see tests/CMakeLists.txt) rather than an
// in-process alarm() watchdog, keeping the test portable to Windows.

#include <catch2/catch_all.hpp>

#include "C4NetIO.h"
#include "C4Network2Address.h"

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

#ifndef _WIN32
	#include <arpa/inet.h>
	#include <netinet/in.h>
	#include <sys/socket.h>
	#include <unistd.h>
#endif

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

namespace
{
	// RAII socket guard: closes the FD on destruction via closesocket()
	// (Windows) or close() (POSIX). Ensures the probe socket in
	// find_free_ipv6_port() is released even when a REQUIRE throws.
	struct SocketGuard
	{
		const int fd;
		explicit SocketGuard(int s) : fd(s) {}
		~SocketGuard()
		{
#ifdef _WIN32
			::closesocket(fd);
#else
			::close(fd);
#endif
		}
		SocketGuard(const SocketGuard &) = delete;
		SocketGuard &operator=(const SocketGuard &) = delete;
	};

	// Find a free ephemeral IPv6 port by binding a temporary TCP socket to
	// ::1:0, calling getsockname, then closing. Avoids hardcoding ports.
	std::uint16_t find_free_ipv6_port()
	{
		const int s = ::socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP);
		REQUIRE(s != INVALID_SOCKET);
		SocketGuard guard{s};

		sockaddr_in6 addr{};
		addr.sin6_family = AF_INET6;
		addr.sin6_port = 0;
		addr.sin6_addr = in6addr_loopback;
		REQUIRE(::bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 0);

		sockaddr_in6 bound{};
		socklen_t len = sizeof(bound);
		REQUIRE(::getsockname(s, reinterpret_cast<sockaddr *>(&bound), &len) == 0);

		return ntohs(bound.sin6_port);
	}
}

// ---------------------------------------------------------------------------
// Recorder: captures received packets and connection events
// ---------------------------------------------------------------------------

struct Recorder : C4NetIO::CBClass
{
	std::vector<StdBuf> received;
	bool connected = false;

	bool OnConn(const C4NetIO::addr_t &AddrPeer, const C4NetIO::addr_t &AddrConnect, const C4NetIO::addr_t *pOwnAddr, C4NetIO *pNetIO) override
	{
		connected = true;
		return true;
	}

	void OnPacket(const C4NetIOPacket &rPacket, C4NetIO *pNetIO) override
	{
		received.push_back(rPacket); // StdBuf slice copy — captures payload data
	}
};

// ---------------------------------------------------------------------------
// 1. AsIPv4() no-op invariant for pure IPv6
// ---------------------------------------------------------------------------

TEST_CASE("AsIPv4() is a no-op for pure IPv6 addresses", "[C4NetIO][IPv6]")
{
	// 2001:db8::1 is a documentation-range pure IPv6 address.
	// ::ffff:1.2.3.4 would be IPv4-mapped, so we avoid that.
	C4Network2EndpointAddress addr{StdStrBuf{"2001:db8::1"}};
	REQUIRE(addr.GetFamily() == C4Network2HostAddress::IPv6);

	const auto as_ipv4 = addr.AsIPv4();

	// The invariant: AsIPv4() returns the address unchanged for pure IPv6.
	REQUIRE(as_ipv4.GetFamily() == C4Network2HostAddress::IPv6);
	REQUIRE(as_ipv4 == addr);
}

// ---------------------------------------------------------------------------
// 2. Endpoint serialization round-trip for pure IPv6
// ---------------------------------------------------------------------------

TEST_CASE("C4Network2EndpointAddress round-trips pure IPv6 through ToString/SetAddress", "[C4NetIO][IPv6][serial]")
{
	C4Network2EndpointAddress original{StdStrBuf{"[2001:db8::1]:1234"}};
	REQUIRE(original.GetFamily() == C4Network2HostAddress::IPv6);
	REQUIRE(original.GetPort() == 1234);

	// CompileFunc serializes via ToString(TSF_SkipZoneId) and deserializes
	// via SetAddress(val). We exercise the same path directly.
	const std::string serialized = original.ToString(C4Network2HostAddress::TSF_SkipZoneId);
	REQUIRE_FALSE(serialized.empty());

	C4Network2EndpointAddress roundtrip;
	roundtrip.SetAddress(StdStrBuf{serialized.c_str()});

	REQUIRE(roundtrip.GetFamily() == C4Network2HostAddress::IPv6);
	REQUIRE(roundtrip.GetPort() == 1234);
	REQUIRE(roundtrip == original);
}

// ---------------------------------------------------------------------------
// 3. UDP IPv6 loopback
// ---------------------------------------------------------------------------

TEST_CASE("C4NetIOSimpleUDP round-trips a packet over IPv6 loopback", "[C4NetIO][IPv6][UDP]")
{
	const std::uint16_t portA = find_free_ipv6_port();
	const std::uint16_t portB = find_free_ipv6_port();

	Recorder recB;
	C4NetIOSimpleUDP udpA, udpB;
	udpB.SetCallback(&recB);
	REQUIRE(udpA.Init(portA));
	REQUIRE(udpB.Init(portB));

	// Build a 50-byte payload with a recognizable pattern (0..49 mod 256).
	StdBuf payload; payload.New(50);
	for (size_t i = 0; i < 50; ++i)
	{
		*payload.getMPtr<uint8_t>(i) = static_cast<uint8_t>(i);
	}

	// A sends to B at ::1:portB.
	const C4NetIO::addr_t destB{C4Network2HostAddress::Loopback, portB};
	REQUIRE(udpA.Send(C4NetIOPacket(payload, destB)));

	// Drive B's event loop until the packet arrives.
	for (int i = 0; i < 100 && recB.received.empty(); ++i)
	{
		udpB.Execute(10);
	}

	REQUIRE_FALSE(recB.received.empty());
	REQUIRE(recB.received[0] == payload);

	udpA.Close();
	udpB.Close();
}

// ---------------------------------------------------------------------------
// 4. TCP IPv6 loopback
// ---------------------------------------------------------------------------

TEST_CASE("C4NetIOTCP round-trips a packet over IPv6 loopback", "[C4NetIO][IPv6][TCP]")
{
	const std::uint16_t port = find_free_ipv6_port();

	Recorder serverRec, clientRec;
	C4NetIOTCP server, client;
	server.SetCallback(&serverRec);
	client.SetCallback(&clientRec);

	// Server listens on the free port.
	REQUIRE(server.Init(port));

	// Client init (no listen socket needed).
	REQUIRE(client.Init());

	// Connect client to ::1:port.
	const C4NetIO::addr_t serverAddr{C4Network2HostAddress::Loopback, port};
	REQUIRE(client.Connect(serverAddr));

	// Drive both sides until the connection is established.
	for (int i = 0; i < 100 && !clientRec.connected; ++i)
	{
		server.Execute(10);
		client.Execute(10);
	}
	REQUIRE(clientRec.connected);

	// Build a 50-byte payload and send from client to server.
	StdBuf payload; payload.New(50);
	for (size_t i = 0; i < 50; ++i)
	{
		*payload.getMPtr<uint8_t>(i) = static_cast<uint8_t>(i);
	}
	REQUIRE(client.Send(C4NetIOPacket(payload, serverAddr)));

	// Drive both sides until the server receives the packet.
	for (int i = 0; i < 100 && serverRec.received.empty(); ++i)
	{
		server.Execute(10);
		client.Execute(10);
	}

	REQUIRE_FALSE(serverRec.received.empty());
	REQUIRE(serverRec.received[0] == payload);

	server.Close();
	client.Close();
}
