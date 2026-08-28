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

#include "C4Rollback.h"

#include "C4GameSave.h"
#include "C4Log.h"
#include "StdBuf.h"

#include <algorithm>

C4Rollback::C4Rollback() = default;
C4Rollback::~C4Rollback() = default;

void C4Rollback::Init(int32_t iSnapshotInterval, int32_t iWindowSnapshots)
{
	// Clamp K to [1, C4ControlBacklog=100] and W to [1, MaxWindowSnapshots].
	// C4ControlBacklog (100) is hard-coded here to avoid pulling
	// C4GameControlNetwork.h into the header.
	iSnapshotInterval = std::clamp(iSnapshotInterval, 1, 100);
	iWindowSnapshots  = std::clamp(iWindowSnapshots,  1, MaxWindowSnapshots);
	this->iSnapshotInterval = iSnapshotInterval;
	this->iWindowSnapshots  = iWindowSnapshots;
	iHead = 0;
	ring.assign(static_cast<size_t>(iWindowSnapshots), Snapshot{});
}

void C4Rollback::Clear()
{
	ring.clear();
	iHead = 0;
	fEnabled = false;
	fRollbackInProgress = false;
	iSnapshotInterval = DefaultSnapshotInterval;
	iWindowSnapshots  = DefaultWindowSnapshots;
}

void C4Rollback::MaybeTakeSnapshot(int32_t iControlTick)
{
	if (!fEnabled) return;
	if (iControlTick % iSnapshotInterval != 0) return;
	TakeSnapshot(iControlTick);
}

int32_t C4Rollback::RollbackToTick(int32_t iTick)
{
	if (!fEnabled) return -1;
	if (fRollbackInProgress) return -1;

	// Find the nearest valid snapshot with tick <= iTick.
	const Snapshot *best = nullptr;
	for (const auto &s : ring)
	{
		if (!s.fValid) continue;
		if (s.iControlTick > iTick) continue;
		if (!best || s.iControlTick > best->iControlTick) best = &s;
	}
	if (!best)
	{
		// Spec edge cases #2 and #5: log a fatal error when the rollback
		// window is exceeded — no snapshot <= iTick exists, so the engine
		// cannot recover via rollback. The caller falls back to the
		// existing delay-based lockstep behaviour.
		LogFatalNTr("Rollback window exceeded for tick {}; cannot recover", iTick);
		return -1;
	}

	fRollbackInProgress = true;
	bool ok = RestoreSnapshot(*best);
	fRollbackInProgress = false;
	if (!ok) return -1;

	// Re-execute forward to iTick. The C4GameControl caller is responsible
	// for driving FastForwardToFrame; RollbackToTick just restores state
	// and reports the restored tick.
	return best->iControlTick;
}

int32_t C4Rollback::GetSnapshotCount() const
{
	int32_t count = 0;
	for (const auto &s : ring) if (s.fValid) ++count;
	return count;
}

int32_t C4Rollback::GetOldestSnapshotTick() const
{
	int32_t oldest = -1;
	for (const auto &s : ring) if (s.fValid && (oldest == -1 || s.iControlTick < oldest)) oldest = s.iControlTick;
	return oldest;
}

int32_t C4Rollback::GetNewestSnapshotTick() const
{
	int32_t newest = -1;
	for (const auto &s : ring) if (s.fValid && (newest == -1 || s.iControlTick > newest)) newest = s.iControlTick;
	return newest;
}

std::optional<std::pair<StdBuf, int32_t>> C4Rollback::GetSnapshotForTick(int32_t iTick) const
{
	const Snapshot *best = nullptr;
	for (const auto &s : ring)
	{
		if (!s.fValid) continue;
		if (s.iControlTick > iTick) continue;
		if (!best || s.iControlTick > best->iControlTick) best = &s;
	}
	if (!best) return std::nullopt;
	StdBuf buf;
	buf.Copy(best->serializedState.data(), best->serializedState.size());
	return std::make_pair(std::move(buf), best->iControlTick);
}

bool C4Rollback::DoSaveRuntimeData(StdBuf &outBuf)
{
	C4GameSaveSavegame save;
	return save.SaveRuntimeDataToBuffer(outBuf);
}

bool C4Rollback::DoLoadRuntimeData(const StdBuf &inBuf)
{
	C4GameSaveSavegame save;
	return save.LoadRuntimeDataFromBuffer(inBuf);
}

bool C4Rollback::TakeSnapshot(int32_t iControlTick)
{
	StdBuf buf;
	if (!DoSaveRuntimeData(buf)) return false;

	Snapshot &slot = ring[iHead];
	slot.iControlTick = iControlTick;
	slot.serializedState.assign(static_cast<const uint8_t *>(buf.getData()),
	                           static_cast<const uint8_t *>(buf.getData()) + buf.getSize());
	slot.fValid = true;

	iHead = (iHead + 1) % iWindowSnapshots;
	return true;
}

bool C4Rollback::RestoreSnapshot(const Snapshot &snap)
{
	if (!snap.fValid) return false;
	StdBuf buf;
	buf.Copy(snap.serializedState.data(), snap.serializedState.size());
	return DoLoadRuntimeData(buf);
}
