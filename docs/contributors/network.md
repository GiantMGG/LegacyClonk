# Network lockstep deep dive

LegacyClonk's network model is **lockstep with a determinism gate**.
Every client runs the same simulation; the gate
(`C4ControlSyncCheck`) verifies per-tick that all clients reached the
same state by comparing a hash of the game state. A diverging hash is a
desync — fatal. The same control tick runs in `CM_Local`
(single-player), `CM_Network` (online), and `CM_Replay` (playback);
only the input source differs.

```mermaid
sequenceDiagram
    autonumber
    participant C1 as Client A
    participant C2 as Client B
    participant H as Host
    participant Q as C4GameControl queue
    participant Sim as C4Game::Execute (per client)
    C1->>H: DoInput (local input A)
    C2->>H: DoInput (local input B)
    H->>H: DoInput (host's own input)
    H->>Q: Prepare() — wait until all inputs for frame N arrived
    H-->>C1: broadcast ordered input set for frame N
    H-->>C2: broadcast ordered input set for frame N
    par each client runs the same frame
        C1->>Sim: Execute() applies inputs
        C2->>Sim: Execute() applies inputs
        H->>Sim: Execute() applies inputs
    end
    Sim->>Sim: DoSyncCheck() — hash game state
    Note over C1,H: all three hashes must match; mismatch = desync (fatal)
```

---

## Reference walkthrough

### `C4GameControl` modes

`class C4GameControl` (`src/C4GameControl.h:44`) has three modes
selected at startup:

- **`CM_Local`** — single-player or hot-seat; no network, no replay.
  Inputs are applied immediately within the same process.
- **`CM_Network`** — online play; inputs are queued, ordered, and
  broadcast by the host via `C4GameControlNetwork`
  (`src/C4GameControlNetwork.h`). The host decides input ordering.
- **`CM_Replay`** — replay playback; the control queue is fed from
  `C4Record`/`C4Playback` (`src/C4Record.{h,cpp}`). No network and no
  live input; the recorded inputs are replayed deterministically.

### The control tick (in source order)

1. **`DoInput(C4PacketType, C4ControlPacket*, C4ControlDeliveryType)`**
   at `src/C4GameControl.cpp:447` — local input enters the control
   queue as a `C4ControlPacket`. In `CM_Network` the packet is also
   sent to the host.
2. **`Prepare()`** at `src/C4GameControl.cpp:296` — collect inputs from
   all clients for the next frame. Returns `false` if not all inputs
   have arrived yet (the frame waits). This is the lockstep sync
   point.
3. **`Execute()`** at `src/C4GameControl.cpp:336` — apply the queued
   control packets in deterministic order: movement, commands, object
   creation, etc.
4. **`DoSyncCheck()`** at `src/C4GameControl.cpp:506` — emit a
   `C4ControlSyncCheck` packet. Every client computes the same hash;
   if any client's hash differs, the gate fires a fatal log and the
   engine exits non-zero. (`C4ControlSyncCheck::Set` at
   `src/C4Control.cpp:460`; `C4ControlSyncCheck::Execute` at
   `src/C4Control.cpp:493`.)

### Network I/O

`C4Network2` (`src/C4Network2.h:134`) is the network controller: lobby,
league, client/host handshake, reference discovery.
`C4Network2IO` (`src/C4Network2IO.{h,cpp}`) is the low-level I/O layer
(TCP/UDP, packet framing). `C4GameControlNetwork` is the bridge between
`C4GameControl` and `C4Network2`: it serialises `C4ControlPacket`s onto
the wire and deserialises them back into the control queue.

### Determinism gate

`C4ControlSyncCheck` is the determinism gate. Its `Set` method
(`src/C4Control.cpp:460`) builds the sync-check packet by hashing a
fixed set of game-state fields (object count, material counts, score,
etc.). Its `Execute` method (`src/C4Control.cpp:493`) compares the
local hash against the received hash; a mismatch calls `LogFatal` and
the engine exits non-zero. The hash is order-independent (sorted
before hashing) so that the same logical state produces the same hash
on every client regardless of internal iteration order.

### Error and edge cases

- **Client timeout** — `Prepare()` returns `false` until all inputs
  arrive; if a client disconnects, the host removes that client and
  the frame proceeds with the remaining inputs.
- **Desync fatal log + non-zero exit** — `DoSyncCheck` mismatch calls
  `LogFatal`/`LogFatalNTr` and the engine exits non-zero. This is the
  hard failure path; there is no graceful desync recovery.
- **Disconnect handling** — `C4Network2::OnDisconnect` cleans up the
  client's inputs from the control queue so the simulation can
  continue with the remaining clients.

---

## Worked example: Tracing a player's movement input through network lockstep

A player on Client A presses the right arrow key. The trace:

1. **Client A: local input enters the queue.** The keyboard handler
   calls `C4GameControl::DoInput` (`src/C4GameControl.cpp:447`) with a
   `C4ControlPacket` describing "player N moves right". In
   `CM_Network` the packet is also sent to the host via
   `C4GameControlNetwork`.
2. **Host: `Prepare()` waits.** The host's
   `C4GameControl::Prepare()` (`src/C4GameControl.cpp:296`) collects
   inputs from all clients for the next frame. It returns `false`
   until all clients' inputs for this frame have arrived, blocking
   `C4Game::Execute()` in a tight-loop wait.
3. **Host: broadcast ordered input set.** Once all inputs are in, the
   host broadcasts the ordered input set for frame N to all clients
   (including itself).
4. **All clients: `Execute()` applies inputs.** Each client's
   `C4GameControl::Execute()` (`src/C4GameControl.cpp:336`) applies
   the queued control packets in deterministic order. The player's
   movement packet moves the player's `C4Object` right.
5. **All clients: `DoSyncCheck()`.** Each client hashes its game state
   (`C4ControlSyncCheck::Set` at `src/C4Control.cpp:460`) and compares
   hashes (`C4ControlSyncCheck::Execute` at `src/C4Control.cpp:493`).
   If all three clients computed the same hash, the tick is done. A
   mismatch is a desync — fatal.

---

!!! seealso "See also"
    - [C4Aul deep dive](c4aul.md)
    - [Rendering pipeline deep dive](rendering.md)
    - [Engine architecture](architecture.md)
    - [Control callbacks reference](../reference/callbacks/control.md)
    - [Callback convention](../c4script/callbacks-convention.md)
