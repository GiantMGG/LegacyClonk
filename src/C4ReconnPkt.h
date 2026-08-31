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

// C4PacketReconn: client->host reconnect handshake carrying the game-scoped
// session token, the original client ID, and the client's last confirmed
// control tick. Spec: connection-migration-reconnect.

#pragma once

#include <cstdint>

#include "C4PacketBase.h"
#include "C4Reconnect.h"

class C4PacketReconn : public C4PacketBase
{
public:
	C4PacketReconn() = default;
	C4PacketReconn(C4Reconnect::Token token, int32_t originalClientID, int32_t lastConfirmedCtrlTick)
		: token(std::move(token)), originalClientID(originalClientID), lastConfirmedCtrlTick(lastConfirmedCtrlTick) {}

	const C4Reconnect::Token &GetToken() const { return token; }
	int32_t GetOriginalClientID() const { return originalClientID; }
	int32_t GetLastConfirmedCtrlTick() const { return lastConfirmedCtrlTick; }

	void CompileFunc(StdCompiler *pComp) override;

private:
	C4Reconnect::Token token{};
	int32_t originalClientID{-1};
	int32_t lastConfirmedCtrlTick{-1};
};
