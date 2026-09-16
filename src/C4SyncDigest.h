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

#pragma once

#include <cstdint>

// FNV-1a-64 rolling digest (cycle 130, spec pxs-network-determinism-gate
// §6.1). Integer-only and order-sensitive: allocation/divergence in
// iteration order IS divergence. Used by C4ControlSyncCheck::Set() to
// build the three position-resolved state digests compared client-side
// in Execute(). Header-only so the Catch2 round-trip tests can exercise
// it without engine globals.
class C4SyncDigest
{
public:
	C4SyncDigest() = default;

	void update_byte(uint8_t b)
	{
		state ^= b;
		state *= FNVPrime;
	}

	void update_le16(uint16_t v)
	{
		update_byte(static_cast<uint8_t>(v & 0xff));
		update_byte(static_cast<uint8_t>((v >> 8) & 0xff));
	}

	void update_le32(uint32_t v)
	{
		update_byte(static_cast<uint8_t>(v & 0xff));
		update_byte(static_cast<uint8_t>((v >> 8) & 0xff));
		update_byte(static_cast<uint8_t>((v >> 16) & 0xff));
		update_byte(static_cast<uint8_t>((v >> 24) & 0xff));
	}

	uint64_t value() const { return state; }

private:
	static constexpr uint64_t FNVOffsetBasis = 0xcbf29ce484222325ull;
	static constexpr uint64_t FNVPrime = 0x100000001b3ull;
	uint64_t state = FNVOffsetBasis;
};
