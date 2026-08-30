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

#include "C4Reconnect.h"

#include "C4Game.h"
#include "C4GameSave.h"
#include "C4Network2Client.h"
#include "C4Rollback.h"

#include <algorithm>
#include <cstring>
#include <random>

void C4Reconnect::Clear()
{
	enabled = false;
	graceSec = DefaultGraceSec;
	gameToken.fill(0);
	tokenMinted = false;
	dormant.clear();
}

void C4Reconnect::MintGameToken()
{
	if (tokenMinted) return;
	std::random_device rd;
	for (size_t i = 0; i < gameToken.size();)
	{
		unsigned int v = rd();
		size_t n = std::min(sizeof(v), gameToken.size() - i);
		std::memcpy(gameToken.data() + i, &v, n);
		i += n;
	}
	tokenMinted = true;
}

bool C4Reconnect::ConstantTimeEquals(const Token &a, const Token &b)
{
	uint8_t diff = 0;
	for (size_t i = 0; i < a.size(); ++i) diff |= a[i] ^ b[i];
	return diff == 0;
}

bool C4Reconnect::EnterDormancy(C4Network2Client *pClient, time_t now)
{
	if (!enabled || !pClient) return false;
	// Idempotent per client: a drop tears down several conns in a burst,
	// each firing OnClientDisconnect. Refresh the existing entry's
	// deadline instead of stacking duplicates -- stale duplicates would
	// later expire and CtrlRemove a freshly reassociated client.
	for (auto &d : dormant)
	{
		if (d.pClient == pClient)
		{
			d.deadline = now + static_cast<time_t>(graceSec);
			return true;
		}
	}
	pClient->SetStatus(NCS_Dormant);
	Dormant d;
	d.originalClientID = pClient->getID();
	d.token = gameToken;
	d.deadline = now + static_cast<time_t>(graceSec);
	d.pClient = pClient;
	dormant.push_back(std::move(d));
	return true;
}

void C4Reconnect::TickDormancy(time_t now, const std::function<void(C4Network2Client *)> &onExpire)
{
	if (dormant.empty()) return;
	std::vector<C4Network2Client *> expired;
	for (auto it = dormant.begin(); it != dormant.end();)
	{
		if (it->deadline <= now)
		{
			if (it->pClient) expired.push_back(it->pClient);
			it = dormant.erase(it);
		}
		else ++it;
	}
	for (C4Network2Client *p : expired) onExpire(p);
}

C4Network2Client *C4Reconnect::HandleReconn(const Token &token, int32_t originalClientID,
                                            int32_t /*lastConfirmedCtrlTick*/,
                                            C4Network2IOConnection *pNewConn)
{
	if (!enabled) return nullptr;
	auto it = std::find_if(dormant.begin(), dormant.end(),
	                       [&](const Dormant &d){ return d.originalClientID == originalClientID; });
	if (it == dormant.end()) return nullptr;
	if (!ConstantTimeEquals(token, it->token)) return nullptr;
	C4Network2Client *pClient = it->pClient;
	// Tear down any stale half-open connections before re-associating.
	// The handshake conn may already be among them (the host's own
	// re-dial of the dormant client's addresses lands as the client
	// entry's msg conn) -- detach it first so the teardown cannot close
	// the conn the reconnect join data must travel on.
	if (pNewConn && pClient->hasConn(pNewConn)) pClient->RemoveConn(pNewConn);
	pClient->CloseConns("reconnect");
	if (pNewConn) pClient->SetMsgConn(pNewConn);
	pClient->SetStatus(NCS_Chasing);
	dormant.erase(it);
	return pClient;
}

std::optional<C4Reconnect::Snapshot> C4Reconnect::GetReconnectSnapshot(int32_t lastConfirmedCtrlTick, C4Rollback *pRollback)
{
	// Idea 2: prefer the rollback ring when enabled and a snapshot exists.
	if (pRollback && pRollback->IsEnabled())
	{
		auto snap = pRollback->GetSnapshotForTick(lastConfirmedCtrlTick);
		if (snap) return Snapshot{std::move(snap->first), snap->second};
	}
	// Idea 1 fallback: fresh full-state snapshot via the injectable hook.
	StdBuf buf;
	if (!DoSaveSnapshot(buf)) return std::nullopt;
	return Snapshot{std::move(buf), Game.Control.ControlTick};
}

bool C4Reconnect::DoSaveSnapshot(StdBuf &outBuf)
{
	C4GameSaveSavegame save;
	return save.SaveRuntimeDataToBuffer(outBuf);
}

bool C4Reconnect::DoLoadSnapshot(const StdBuf &inBuf)
{
	C4GameSaveSavegame save;
	return save.LoadRuntimeDataFromBuffer(inBuf);
}
