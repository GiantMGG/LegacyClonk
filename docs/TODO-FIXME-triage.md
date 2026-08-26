# TODO/FIXME triage worksheet

Frozen snapshot of every `TODO|FIXME|HACK|XXX|BUG` marker in `src/`.
Columns: `#`, `blame-date`, `file:line`, `marker-text`, `category`, `disposition`, `status`.

| # | blame-date | file:line | marker-text | category | disposition | status |
|---|---|---|---|---|---|---|
| 1 | 02702628f | src/C4Surface.cpp:471 | `// Take shortcut. FIXME: Check Endian` |   |   | open (grandfathered) |
| 2 | 1af35f997 | src/C4NetIO.cpp:381 | `// TODO: Maybe use addresses from local client to avoid the extra system calls.` |   |   | open (grandfathered) |
| 3 | 26394748a | src/C4AulExec.cpp:1231 | `// Ignore. TODO: Fix this.` | unimplemented-stub | convert-to-issue | resolved |
| 4 | 26394748a | src/C4Game.cpp:1025 | `// FIXME: C4Application::Execute should do this, but what about the stats?` | stale-comment | remove | resolved |
| 5 | 26394748a | src/C4GamePadCon.cpp:380 | `// FIXME: This assumes that the axis really rests around (0, 0) if it is not ...` | input-assumption | convert-to-issue | resolved |
| 6 | 26394748a | src/C4Menu.cpp:658 | `// FIXME: Blah. This stuff should be calculated correctly by pTitle.` | stale-comment | remove | resolved |
| 7 | 26394748a | src/C4Network2Res.cpp:1196 | `} /* TODO: Test failure */` | missing-test | convert-to-issue | resolved |
| 8 | 26394748a | src/C4Object.cpp:2845 | `pComp->Value(mkNamingAdapt(Color,                                   "Color", ...` | stale-comment | remove | resolved |
| 9 | 26394748a | src/C4Object.cpp:3779 | `// FIXME: replace constants` | magic-constants | convert-to-issue | resolved |
| 10 | 26394748a | src/C4ScriptHost.h:90 | `// FIXME: Move to C4AulScriptEngine` | architecture | convert-to-issue | resolved |
| 11 | 26394748a | src/C4ValueMap.cpp:183 | `// FIXME: This optimization is ugly.` | code-quality | convert-to-issue | resolved |
| 12 | 4e1f32a9a | src/C4StartupWelcomeDlg.cpp:35 | `// Hardcoded English strings for now; follow-up TODO wires these through` |   |   | open (grandfathered) |
| 13 | 505b86996 | src/StdGLCtx.cpp:312 | `// update size FIXME: Don't call this every frame` |   |   | open (grandfathered) |
| 14 | 505b86996 | src/StdGLCtx.cpp:473 | `// update size FIXME: Don't call this every frame` |   |   | open (grandfathered) |
| 15 | 6a4aa8abb | src/C4Particles.cpp:419 | `// FIXME` |   |   | open (grandfathered) |
| 16 | 6a4aa8abb | src/C4Player.cpp:196 | `// FIXME` |   |   | open (grandfathered) |
| 17 | 6a4aa8abb | src/C4Player.cpp:743 | `while (Game.Players.PositionTaken(iPosition)) // FIXME` |   |   | open (grandfathered) |
| 18 | 6a4aa8abb | src/C4Section.cpp:1244 | `// FIXME: Use C4FindObject here for optimization` |   |   | open (grandfathered) |
| 19 | 6e7ef2fb2 | src/C4IDList.cpp:191 | `// FIXME: Should call GetValue here` |   |   | open (grandfathered) |
| 20 | 93827ffba | src/C4NetIO.cpp:1616 | `// TODO: do multicast on all interfaces?` |   |   | open (grandfathered) |
| 21 | 93827ffba | src/C4NetIO.cpp:2149 | `const auto rnd = static_cast<std::uint32_t>(std::rand()); // FIXME: better re...` |   |   | open (grandfathered) |
| 22 | 93827ffba | src/C4Network2.cpp:1007 | `// TODO: is this all thread-safe?` |   |   | open (grandfathered) |
| 23 | 955d816a4 | src/C4Object.cpp:3695 | `case COM_Dig:    ObjectComLetGo(this, (Action.Dir == DIR_Left) ? +1 : -1); [[...` |   |   | open (grandfathered) |
| 24 | ^66b40452 | src/C4Console.cpp:885 | `// C4Network2 will have to handle that cases somehow (TODO: test)` |   |   | open (grandfathered) |
| 25 | ^66b40452 | src/C4Console.cpp:917 | `// C4Network2 will have to handle that cases somehow (TODO: test)` |   |   | open (grandfathered) |
| 26 | ^66b40452 | src/C4Console.cpp:1022 | `// TODO: Set dialog modal?` |   |   | open (grandfathered) |
| 27 | ^66b40452 | src/C4Console.cpp:1433 | `// TODO: Implement AddMenuItem...` |   |   | open (grandfathered) |
| 28 | ^66b40452 | src/C4Control.cpp:670 | `// TODO: in replays, client list is not yet synchronized` |   |   | open (grandfathered) |
| 29 | ^66b40452 | src/C4DevmodeDlg.h:26 | `// TODO: Threadsafety?` |   |   | open (grandfathered) |
| 30 | ^66b40452 | src/C4Game.cpp:1802 | `// HACK: Reinsert player sections, if any.` |   |   | open (grandfathered) |
| 31 | ^66b40452 | src/C4GameObjects.cpp:440 | `// FIXME: Inform C4ObjectList that this is a reorder, not a remove+insert` |   |   | open (grandfathered) |
| 32 | ^66b40452 | src/C4GameObjects.cpp:508 | `// FIXME: Inform C4ObjectList about this reorder` |   |   | open (grandfathered) |
| 33 | ^66b40452 | src/C4GameSave.cpp:618 | `// TODO: remove it? (-> PeterW ;))` |   |   | open (grandfathered) |
| 34 | ^66b40452 | src/C4GraphicsResource.cpp:411 | `// FIXME: Use LogFatal here` |   |   | open (grandfathered) |
| 35 | ^66b40452 | src/C4GuiDialogs.cpp:307 | `// FIXME: Close the dialog of this window` |   |   | open (grandfathered) |
| 36 | ^66b40452 | src/C4MainMenu.cpp:901 | `// TODO!` |   |   | open (grandfathered) |
| 37 | ^66b40452 | src/C4Network2IO.cpp:407 | `// TODO: ugly algorithm. do better` |   |   | open (grandfathered) |
| 38 | ^66b40452 | src/C4Network2IO.cpp:991 | `// FIXME: Note this happens if the peer has exclusive connection mode on.` |   |   | open (grandfathered) |
| 39 | ^66b40452 | src/C4Network2Reference.cpp:170 | `// TODO` |   |   | open (grandfathered) |
| 40 | ^66b40452 | src/C4ObjectListDlg.cpp:674 | `// FIXME: Invalidate cache when objects change color, and redraw.` |   |   | open (grandfathered) |
| 41 | ^66b40452 | src/C4PlayerInfo.cpp:265 | `// add failed? invalid ressource??! -- TODO: may be too large to load` |   |   | open (grandfathered) |
| 42 | ^66b40452 | src/C4PlayerInfoListBox.cpp:353 | `// if evaluation and team lists, move score label into second line - TODO: so...` |   |   | open (grandfathered) |
| 43 | ^66b40452 | src/C4PlayerInfoListBox.cpp:761 | `btnAddPlayer = new C4GUI::CallbackButton<ClientListItem, C4GUI::IconButton>(C...` |   |   | open (grandfathered) |
| 44 | ^66b40452 | src/C4PlayerInfoListBox.cpp:1166 | `btnAddPlayer = new C4GUI::CallbackButton<ScriptPlayersListItem, C4GUI::IconBu...` |   |   | open (grandfathered) |
| 45 | ^66b40452 | src/C4Sky.cpp:189 | `// FIXME?` |   |   | open (grandfathered) |
| 46 | ^66b40452 | src/C4StartupPlrSelDlg.cpp:204 | `// FIXME: Unicode` |   |   | open (grandfathered) |
| 47 | ^66b40452 | src/C4StartupPlrSelDlg.cpp:1104 | `// FIXME: Use Player, not Clonkranks` |   |   | open (grandfathered) |
| 48 | ^66b40452 | src/C4StartupScenSelDlg.cpp:1275 | `// FIXME: make unicode-ready` |   |   | open (grandfathered) |
| 49 | ^66b40452 | src/C4ToolsDlg.cpp:694 | `// TODO: Can we optimize this?` |   |   | open (grandfathered) |
| 50 | ^66b40452 | src/C4Update.cpp:799 | `// TODO: write DeleteEntries.txt` |   |   | open (grandfathered) |
| 51 | ^66b40452 | src/C4Viewport.cpp:446 | `// TODO: Redraw only event->area` |   |   | open (grandfathered) |
| 52 | ^66b40452 | src/C4WinMain.cpp:267 | `// FIXME: This should only be done in developer mode.` |   |   | open (grandfathered) |
| 53 | ^66b40452 | src/StdBuf.cpp:265 | `// FIXME: could check for UTF-16 surrogates from a broken utf-16->utf-8 conve...` |   |   | open (grandfathered) |
| 54 | ^66b40452 | src/StdFile.cpp:651 | `// FIXME: What if the directory would have to be copied?` |   |   | open (grandfathered) |
| 55 | ^66b40452 | src/StdFont.cpp:351 | `// FIXME: use bbox or dynamically determined line heights here` |   |   | open (grandfathered) |
| 56 | ^66b40452 | src/StdSDLWindow.cpp:51 | `// FIXME: Read from application bundle on the Mac.` |   |   | open (grandfathered) |
| 57 | a6dc0ab01 | src/StdAppUnix.cpp:387 | `// FIXME: do not add a new timeout instead of deleting the old one in the nex...` |   |   | open (grandfathered) |
| 58 | a6dc0ab01 | src/StdAppUnix.cpp:660 | `fputs("FIXME: XmbLookupString returned XLookupKeySym", stderr);` |   |   | open (grandfathered) |
| 59 | a6dc0ab01 | src/StdAppUnix.cpp:664 | `fputs("FIXME: XmbLookupString returned XBufferOverflow\n", stderr);` |   |   | open (grandfathered) |
| 60 | a6dc0ab01 | src/StdAppUnix.cpp:690 | `// involved. TODO: We probably need to correct button state` |   |   | open (grandfathered) |
| 61 | a76a6bd29 | src/C4ToolsDlg.cpp:606 | `// TODO: Set size request for image to read size from image's size request?` |   |   | open (grandfathered) |
| 62 | b1a619949 | src/C4GameLobby.h:20 | `// TODO: Tab: NickCompletion - and can't do this here, because tab is used to...` | feature-gap | convert-to-issue | resolved |
| 63 | bde7e1936 | src/C4Player.cpp:874 | `if (!(pThing = section.CreateObject(id, pBuyObj, iForPlr))) return nullptr; /...` |   |   | open (grandfathered) |
| 64 | bfd00f598 | src/C4GamePadCon.cpp:291 | `// TODO: Handle` |   |   | open (grandfathered) |
| 65 | e148a772a | src/C4ValueList.cpp:106 | `// FIXME: this should be one of C4ValueInt or (u)intptr_t (or C4ID), but whic...` |   |   | open (grandfathered) |
| 66 | e9fd84107 | src/C4HudBars.cpp:460 | `// TODO: Check Type and const?` |   |   | open (grandfathered) |
| 67 | f37a1b11f | src/C4Script.cpp:1453 | `return {}; // FIXME` |   |   | open (grandfathered) |
