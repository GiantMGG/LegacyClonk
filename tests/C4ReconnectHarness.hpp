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

// Fake-network harness for the reconnect tests.
//
// Drives C4Reconnect directly with in-process fake C4Network2Client
// objects (built from real C4Client instances). No sockets, no full
// C4Network2 handshake. Mirrors the injectable-hook pattern in
// tests/C4RollbackHarness.hpp.
//
// Spec: .opencode/specs/2026-08-29-1000-connection-migration-reconnect.md

#ifndef C4RECONNECT_HARNESS_HPP
#define C4RECONNECT_HARNESS_HPP

#include <catch2/catch_all.hpp>

#include <spdlog/spdlog.h>

#include "C4Client.h"
#include "C4Network2Client.h"
#include "C4Reconnect.h"
#include "C4Rollback.h"

#include <memory>
#include <string>

namespace C4ReconnectTest
{
	// Test-only subclass exposing injectable save/load hooks so the
	// snapshot-source policy can be exercised without a live game save.
	// Mirrors C4RollbackTestable in tests/C4RollbackHarness.hpp.
	class C4ReconnectTestable : public C4Reconnect
	{
	public:
		std::function<bool(StdBuf &)> saveFn;
		std::function<bool(const StdBuf &)> loadFn;

	protected:
		bool DoSaveSnapshot(StdBuf &outBuf) override
		{
			if (saveFn) return saveFn(outBuf);
			return false;
		}
		bool DoLoadSnapshot(const StdBuf &inBuf) override
		{
			if (loadFn) return loadFn(inBuf);
			return false;
		}
	};

	// A fake C4Network2Client backed by a real C4Client with a set ID.
	// Owns its C4Client + C4Network2Client. The C4Network2Client is
	// constructed with a dummy spdlog logger so no global logger is
	// required.
	struct FakeClient
	{
		std::shared_ptr<spdlog::logger> logger;
		std::unique_ptr<C4Client> client;
		std::unique_ptr<C4Network2Client> netClient;

		explicit FakeClient(int32_t id, const std::string & /*name*/ = "fake")
		{
			logger = spdlog::default_logger();
			client = std::make_unique<C4Client>();
			client->SetID(id);
			// Note: the core name is left at its default. C4Client::getCore()
			// returns a const ref, so it cannot be mutated post-construction
			// without going through C4ClientList. The reconnect tests do not
			// assert on the client name, so this is fine.
			netClient = std::make_unique<C4Network2Client>(logger, client.get());
		}
	};

	// Build a token filled with a repeating byte pattern (deterministic).
	inline C4Reconnect::Token MakeToken(uint8_t fill)
	{
		C4Reconnect::Token t{};
		t.fill(fill);
		return t;
	}
}

#endif // C4RECONNECT_HARNESS_HPP
