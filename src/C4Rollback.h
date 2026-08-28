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

// In-memory rollback primitive: ring buffer of full-state snapshots taken
// every K control ticks, restored on remote-input divergence and re-executed
// forward via C4GameControl::FastForwardToFrame.
//
// Spec: .opencode/specs/2026-08-27-1600-rollback-prediction.md
//
// Default behaviour (Config.Network.RollbackEnabled = false): every method
// is a no-op or returns a sentinel; the default game is byte-for-byte
// identical to the pre-rollback engine.

#pragma once

#include <cstdint>
#include <functional>
#include <vector>

#include "StdBuf.h"

class C4Rollback
{
public:
	static constexpr int32_t DefaultSnapshotInterval = 5; // K: control ticks
	static constexpr int32_t DefaultWindowSnapshots  = 6; // W: ring size
	static constexpr int32_t MaxWindowSnapshots      = 32;

	C4Rollback();
	~C4Rollback();

	void Init(int32_t iSnapshotInterval, int32_t iWindowSnapshots);
	void Clear();

	// Called from C4GameControl::Execute after each control tick.
	void MaybeTakeSnapshot(int32_t iControlTick);

	// Called from C4GameControlNetwork::HandleControl when a remote input
	// for tick T arrives that differs from the predicted/queued input.
	// Returns the tick restored to (== nearest snapshot tick), or -1 on
	// failure (snapshot outside window, corrupt, etc.).
	int32_t RollbackToTick(int32_t iTick);

	bool IsEnabled() const { return fEnabled; }
	void SetEnabled(bool fnEnabled) { fEnabled = fnEnabled; }

	// Test introspection
	int32_t GetSnapshotCount() const;
	int32_t GetOldestSnapshotTick() const;
	int32_t GetNewestSnapshotTick() const;

	// Injectable snapshot/restore functions for testing. When set,
	// TakeSnapshot/RestoreSnapshot call these instead of the default
	// C4GameSaveSavegame helpers. Pass nullptr to revert to the default.
	void SetSnapshotFunction(std::function<bool(StdBuf &)> fn) { snapshotFn = std::move(fn); }
	void SetRestoreFunction(std::function<bool(const StdBuf &)> fn) { restoreFn = std::move(fn); }

private:
	struct Snapshot
	{
		int32_t iControlTick = -1;
		std::vector<uint8_t> serializedState;
		bool fValid = false;
	};

	bool fEnabled = false;
	bool fRollbackInProgress = false;
	int32_t iSnapshotInterval = DefaultSnapshotInterval;
	int32_t iWindowSnapshots  = DefaultWindowSnapshots;
	int32_t iHead = 0; // next slot to write
	std::vector<Snapshot> ring;

	std::function<bool(StdBuf &)> snapshotFn;
	std::function<bool(const StdBuf &)> restoreFn;

	bool TakeSnapshot(int32_t iControlTick);
	bool RestoreSnapshot(const Snapshot &snap);
};
