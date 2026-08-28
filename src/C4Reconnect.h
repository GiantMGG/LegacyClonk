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

// Reconnect handshake: session-token + grace-window dormancy for dropped
// clients, with a rollback-ring snapshot source when RollbackEnabled.
//
// Spec: .opencode/specs/2026-08-29-1000-connection-migration-reconnect.md
//
// Default behaviour (Config.Network.ReconnectEnabled = false): EnterDormancy
// returns false, HandleReconn returns nullptr, GetReconnectSnapshot returns
// std::nullopt on the rollback path; the default game is byte-for-byte
// identical to the pre-reconnect engine.

#pragma once

#include <array>
#include <cstdint>
#include <ctime>
#include <functional>
#include <optional>
#include <vector>

#include "StdBuf.h"

class C4Network2Client;
class C4Network2IOConnection;
class C4Rollback;

class C4Reconnect
{
public:
	static constexpr uint32_t DefaultGraceSec = 120;
	using Token = std::array<uint8_t, 16>; // 128-bit

	C4Reconnect() = default;
	~C4Reconnect() = default;

	void Clear();

	// Game-scoped token, minted lazily on first Join(). Rotated on Clear().
	const Token &GetGameToken() const { return gameToken; }
	bool         IsTokenMinted() const { return tokenMinted; }
	void         MintGameToken();

	// Constant-time compare. Both tokens are always 16 bytes.
	static bool ConstantTimeEquals(const Token &a, const Token &b);

	// Host-side dormancy. Transitions pClient to NCS_Dormant and arms a
	// grace timer. Returns false if disabled (caller should CtrlRemove).
	bool EnterDormancy(C4Network2Client *pClient, time_t now);

	// Host-side per-tick expiry. Invokes onExpire outside the dormant list
	// so the callback may mutate the client list (e.g. CtrlRemove).
	void TickDormancy(time_t now, const std::function<void(C4Network2Client *)> &onExpire);

	// Host-side reconnect handshake. Looks up the dormant client by
	// originalClientID, constant-time-compares the token, re-associates
	// pNewConn with the dormant client (restoring the original client ID),
	// flips status to NCS_Chasing, and removes the dormant entry. Returns
	// nullptr on lookup-miss or token-mismatch (caller closes pNewConn).
	C4Network2Client *HandleReconn(const Token &token, int32_t originalClientID,
	                               int32_t lastConfirmedCtrlTick,
	                               C4Network2IOConnection *pNewConn);

	// Snapshot-source policy. Prefers the rollback ring when RollbackEnabled
	// and a snapshot with tick <= lastConfirmedCtrlTick exists; else falls
	// back to a fresh SaveRuntimeDataToBuffer. Returns std::nullopt on
	// failure (ring miss AND fresh-save failed).
	struct Snapshot { StdBuf buf; int32_t tick; };
	std::optional<Snapshot> GetReconnectSnapshot(int32_t lastConfirmedCtrlTick, C4Rollback *pRollback);

	bool     IsEnabled() const { return enabled; }
	void     SetEnabled(bool e) { enabled = e; }
	void     SetGraceSec(uint32_t s) { graceSec = s; }
	uint32_t GetGraceSec() const { return graceSec; }

private:
	struct Dormant
	{
		int32_t  originalClientID{-1};
		Token    token{};
		time_t   deadline{0};
		C4Network2Client *pClient{nullptr};
	};

	bool     enabled{false};
	uint32_t graceSec{DefaultGraceSec};
	Token    gameToken{};
	bool     tokenMinted{false};
	std::vector<Dormant> dormant;

	// Serialization hooks for the fresh-snapshot fallback path. The default
	// implementation delegates to C4GameSaveSavegame. Test doubles override
	// these to inject fake serialization without a live game — mirrors the
	// C4Rollback::DoSaveRuntimeData / DoLoadRuntimeData pattern.
	virtual bool DoSaveSnapshot(StdBuf &outBuf);
	virtual bool DoLoadSnapshot(const StdBuf &inBuf);
};
