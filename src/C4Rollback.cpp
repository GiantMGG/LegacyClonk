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
}

void C4Rollback::MaybeTakeSnapshot(int32_t iControlTick)
{
	// No-op until Milestone B wires real snapshot logic.
	(void)iControlTick;
}

int32_t C4Rollback::RollbackToTick(int32_t iTick)
{
	// No-op until Milestone B wires real restore logic.
	(void)iTick;
	return -1;
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

bool C4Rollback::TakeSnapshot(int32_t iControlTick)
{
	// Milestone B implements real snapshot capture.
	(void)iControlTick;
	return false;
}

bool C4Rollback::RestoreSnapshot(const Snapshot &snap)
{
	// Milestone B implements real restore.
	(void)snap;
	return false;
}
