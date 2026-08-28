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

// Fake-network harness for the rollback tests.
//
// The harness does NOT open sockets, spawn subprocesses, or boot a full
// scenario. Instead it drives C4GameControl / C4GameControlNetwork with an
// injected fake control stream and asserts the engine's existing
// delay-based lockstep semantics. It mirrors the injectable-callback
// pattern established by tests/TstC4ReplayController.cpp.
//
// The harness is a header-only helper included by TstC4Rollback.cpp.
// Test cases construct a C4RollbackHarness, configure divergence/latency,
// and call Drive() to advance the simulated control stream by one tick.

#ifndef C4ROLLBACK_HARNESS_HPP
#define C4ROLLBACK_HARNESS_HPP

#include <catch2/catch_all.hpp>

#include "C4GameControl.h"
#include "C4GameControlNetwork.h"

#include <cstdint>
#include <functional>
#include <vector>

namespace C4RollbackTest
{
	// A single injected remote control event. The harness calls onRemoteControl
	// for each tick in the queue, allowing the test to simulate divergence
	// (a remote input that differs from what was predicted/queued).
	struct RemoteControlEvent
	{
		int32_t iTick = 0;
		int32_t iByClientID = 0;
		std::function<void()> onRemoteControl; // invoked during Drive()
	};

	// The harness. Construction does not touch the engine; the test calls
	// Init() to wire the harness to the global Game.Control.
	class C4RollbackHarness
	{
	public:
		// Tunables. Defaults match the spec: K=5, W=6, RTT=150 ms.
		int32_t iSnapshotInterval = C4Rollback::DefaultSnapshotInterval;
		int32_t iWindowSnapshots  = C4Rollback::DefaultWindowSnapshots;
		int32_t iSimulatedRTTms   = 150;
		bool    fRollbackEnabled  = false;

		// Recorded trace of ControlTick advances, used by case 8 to assert
		// byte-for-byte identity between RollbackEnabled=true/false runs.
		std::vector<int32_t> controlTickTrace;

		void Init();
		void Drive();       // advance the simulated stream by one control tick
		void InjectRemoteControl(const RemoteControlEvent &evt);

		// Test hooks
		int32_t GetControlReady() const;

	private:
		std::vector<RemoteControlEvent> pendingRemote;
	};

	inline void C4RollbackHarness::Init()
	{
		// Wire the harness to the global Game.Control. The harness does not
		// modify ControlRate or other engine state; it only drives the
		// existing Execute() path with injected remote control.
		if (fRollbackEnabled)
		{
			Game.Control.Rollback.Init(iSnapshotInterval, iWindowSnapshots);
			Game.Control.Rollback.SetEnabled(true);
		}
		controlTickTrace.clear();
	}

	inline void C4RollbackHarness::InjectRemoteControl(const RemoteControlEvent &evt)
	{
		pendingRemote.push_back(evt);
	}

	inline void C4RollbackHarness::Drive()
	{
		// Fire any remote control events scheduled for the next tick.
		// The harness model is wall-clock-free: events fire in injection
		// order during successive Drive() calls.
		for (auto &evt : pendingRemote)
		{
			if (evt.onRemoteControl) evt.onRemoteControl();
		}
		pendingRemote.clear();

		// Advance the engine one control tick.
		Game.Control.Execute();
		controlTickTrace.push_back(Game.Control.ControlTick);
	}

	inline int32_t C4RollbackHarness::GetControlReady() const
	{
		return Game.Control.Network.iControlReady.load();
	}
}

#endif // C4ROLLBACK_HARNESS_HPP
