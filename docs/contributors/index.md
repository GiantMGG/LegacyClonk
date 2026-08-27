# Contributors

LegacyClonk is a C++23 fan-made continuation of the Clonk Rage engine. The
engine source lives in `LegacyClonk/src/` as a flat tree of `C4*`-prefixed
classes sitting on top of a `Std*` utility layer (`StdApp`, `StdBuf`,
`StdDDraw2`, …). New contributors should read
[Engine architecture](architecture.md) first — it walks through the
`C4*` subsystem layout, the main loop in `C4Game::Execute()`, the C4Aul
parse→exec pipeline, the network lockstep loop, and the rendering pipeline.

## Subsystem map

| Subsystem | Key files | Role | Deep dive |
|---|---|---|---|
| App / main loop | `C4Application`, `C4Game`, `StdApp` | Process bootstrap, frame loop, quit handling | [Main loop](architecture.md#the-main-loop) |
| Game world | `C4Section`, `C4Landscape`, `C4Object`, `C4Material`, `C4PXS`, `C4Weather` | Sections, landscape, objects, materials, particles, weather | [Game world](architecture.md#how-legacyclonk-is-organised) |
| C4Aul (scripting) | `C4Aul`, `C4AulExec`, `C4AulParse`, `C4AulBCC`, `C4Script`, `C4Value` | Parse, bytecode-compile, interpret C4Script; engine↔script bridge | [Reader's guide: C4Aul](architecture.md#readers-guide-c4aul) |
| Control / Network | `C4GameControl`, `C4GameControlNetwork`, `C4Network2`, `C4Network2IO`, `C4Control`, `C4Record`, `C4Replay` | Lockstep input queue, network I/O, lobby, league, replay | [Reader's guide: Network lockstep](architecture.md#readers-guide-network-lockstep) |
| Rendering | `C4GraphicsSystem`, `C4Viewport`, `C4Facet`, `C4Surface`, `StdDDraw2`, `StdSurface8` | Per-frame draw composition, viewports, blit primitive, SDL/DirectDraw backends | [Reader's guide: Rendering pipeline](architecture.md#readers-guide-rendering-pipeline) |
| UI / GUI | `C4Gui`, `C4FullScreen`, `C4Console`, `C4Menu`, `C4ObjectMenu`, `C4MessageBoard`, `C4Startup*Dlg` | Dialogs, menus, startup screens, console, message board | [UI / GUI](architecture.md#how-legacyclonk-is-organised) |
| Audio | `C4SoundSystem`, `C4MusicSystem`, `C4AudioSystem*` | SFX playback, music streaming, audio backend selection | [Audio](architecture.md#how-legacyclonk-is-organised) |
| Storage | `C4Group`, `C4GroupSet`, `C4Folder`, `C4File`, `C4Def`, `C4Network2Res` | `.c4g`/`.c4d`/`.c4f` container format, definition loading, resource cache | [Storage](architecture.md#how-legacyclonk-is-organised) |
| Config / glue | `C4Config`, `C4Constants`, `C4ForwardDeclarations`, `C4Log`, `C4ToolsDlg`, `C4InteractiveThread` | Engine config, shared constants, centralised forward declarations, logging, thread glue | [Config / glue](architecture.md#how-legacyclonk-is-organised) |

## Where to go next

- **[Engine architecture](architecture.md)** — the full roadmap deliverable.
- For build, test, and code-style conventions see the repo-root
  `CONTRIBUTING.md` (a future cycle will fold it into this section).
