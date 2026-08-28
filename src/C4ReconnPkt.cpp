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

#include "C4ReconnPkt.h"

#include <cstring>

void C4PacketReconn::CompileFunc(StdCompiler *pComp)
{
	// Serialise the 128-bit token as two uint64s so the on-wire format is
	// explicit and endianness-stable via mkNamingAdapt's int handling.
	uint64_t lo = 0, hi = 0;
	if (pComp->isDecompiler())
	{
		std::memcpy(&lo, token.data(),     sizeof(uint64_t));
		std::memcpy(&hi, token.data() + 8, sizeof(uint64_t));
	}
	pComp->Value(mkNamingAdapt(lo, "TokenLo", 0ull));
	pComp->Value(mkNamingAdapt(hi, "TokenHi", 0ull));
	if (pComp->isCompiler())
	{
		std::memcpy(token.data(),     &lo, sizeof(uint64_t));
		std::memcpy(token.data() + 8, &hi, sizeof(uint64_t));
	}
	pComp->Value(mkNamingAdapt(originalClientID,     "OriginalClientID",     -1));
	pComp->Value(mkNamingAdapt(lastConfirmedCtrlTick, "LastConfirmedCtrlTick", -1));
}
