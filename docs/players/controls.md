# Controls reference

Clonk exposes 12 logical controls per player, mapped to a physical
key on each of four keyboard sets, to gamepad buttons, or to no
device at all. This page lists the defaults. See the
[first-game guide](first-game.md) for a walkthrough of when to use
each control.

## Per-player control slots

Each player has 12 logical controls (`CON_*`), in this order:

| idx | `CON_*` constant       | human label              |
|----:|------------------------|--------------------------|
|  0  | `CON_CursorLeft`       | Select previous crew     |
|  1  | `CON_CursorToggle`     | Toggle cursor-follow     |
|  2  | `CON_CursorRight`      | Select next crew         |
|  3  | `CON_Throw`            | Throw / drop             |
|  4  | `CON_Up`               | Up / jump                |
|  5  | `CON_Dig`              | Dig                      |
|  6  | `CON_Left`             | Walk left                |
|  7  | `CON_Down`             | Down / crouch            |
|  8  | `CON_Right`            | Walk right               |
|  9  | `CON_Menu`             | Open object menu         |
| 10  | `CON_Special`          | Special 1                |
| 11  | `CON_Special2`         | Special 2                |

Source: `src/C4Constants.h:214-225` (enum),
`src/C4Constants.h:41-43` (`C4MaxKey = 12`).

## Keyboard sets

There are four keyboard sets (`C4MaxKeyboardSet = 4`,
`src/C4Constants.h:42`), intended for up to four local players
sharing one keyboard. Each tab below lists the 12 default bindings
for one set. A player picks their set in the in-game Options dialog.

=== "Kbd1 (two-hand WASD+mouse)"

    Kbd1's defaults are the **Two-Hand WASD+Mouse** preset — the
    fresh-install default. See the [Presets](#presets) section for the
    layout rationale and the other presets.

    | idx | slot           | key             | source                    |
    |----:|----------------|-----------------|---------------------------|
    |  0  | CursorLeft     | <kbd>Q</kbd>    | `C4ControlPresets.cpp:79` |
    |  1  | CursorToggle   | <kbd>Space</kbd> | `C4ControlPresets.cpp:80` |
    |  2  | CursorRight    | <kbd>E</kbd>    | `C4ControlPresets.cpp:81` |
    |  3  | Throw          | <kbd>J</kbd>    | `C4ControlPresets.cpp:82` |
    |  4  | Up             | <kbd>W</kbd>    | `C4ControlPresets.cpp:83` |
    |  5  | Dig            | <kbd>I</kbd>    | `C4ControlPresets.cpp:84` |
    |  6  | Left           | <kbd>A</kbd>    | `C4ControlPresets.cpp:85` |
    |  7  | Down           | <kbd>S</kbd>    | `C4ControlPresets.cpp:86` |
    |  8  | Right          | <kbd>D</kbd>    | `C4ControlPresets.cpp:87` |
    |  9  | Menu           | <kbd>K</kbd>    | `C4ControlPresets.cpp:88` |
    | 10  | Special        | <kbd>O</kbd>    | `C4ControlPresets.cpp:89` |
    | 11  | Special2       | <kbd>L</kbd>    | `C4ControlPresets.cpp:90` |

    !!! note "Single-sourced from the preset registry"
        These defaults are read from the registry, not written out:
        `C4ConfigControls::CompileFunc` pulls the Two-Hand WASD+Mouse
        table via `GetPreset(C4PR_TwoHandMouse, fGer)`
        (`src/C4Config.cpp:349`). The table is locale-neutral — no QWERTZ
        variants. The pre-flip Classic One-Hand defaults now live only in
        the registry as a preset (see [Presets](#presets)).

=== "Kbd2 (numpad)"

    | idx | slot           | key             | source                  |
    |----:|----------------|-----------------|-------------------------|
    |  0  | CursorLeft     | <kbd>KP_7</kbd> | `C4Config.cpp:363`      |
    |  1  | CursorToggle   | <kbd>KP_8</kbd> | `C4Config.cpp:364`      |
    |  2  | CursorRight    | <kbd>KP_9</kbd> | `C4Config.cpp:365`      |
    |  3  | Throw          | <kbd>KP_4</kbd> | `C4Config.cpp:366`      |
    |  4  | Up             | <kbd>KP_5</kbd> | `C4Config.cpp:367`      |
    |  5  | Dig            | <kbd>KP_6</kbd> | `C4Config.cpp:368`      |
    |  6  | Left           | <kbd>KP_1</kbd> | `C4Config.cpp:369`      |
    |  7  | Down           | <kbd>KP_2</kbd> | `C4Config.cpp:370`      |
    |  8  | Right          | <kbd>KP_3</kbd> | `C4Config.cpp:371`      |
    |  9  | Menu           | <kbd>KP_0</kbd> | `C4Config.cpp:372`      |
    | 10  | Special        | <kbd>KP_Del</kbd> | `C4Config.cpp:373`    |
    | 11  | Special2       | <kbd>KP_+</kbd> | `C4Config.cpp:374`      |

=== "Kbd3 (right-hand)"

    | idx | slot           | key            | source                  |
    |----:|----------------|----------------|-------------------------|
    |  0  | CursorLeft     | <kbd>I</kbd>   | `C4Config.cpp:376`      |
    |  1  | CursorToggle   | <kbd>O</kbd>   | `C4Config.cpp:377`      |
    |  2  | CursorRight    | <kbd>P</kbd>   | `C4Config.cpp:378`      |
    |  3  | Throw          | <kbd>K</kbd>   | `C4Config.cpp:379`      |
    |  4  | Up             | <kbd>L</kbd>   | `C4Config.cpp:380`      |
    |  5  | Dig            | <kbd>;</kbd>   | `C4Config.cpp:381`      |
    |  6  | Left           | <kbd>,</kbd>   | `C4Config.cpp:382`      |
    |  7  | Down           | <kbd>.</kbd>   | `C4Config.cpp:383`      |
    |  8  | Right          | <kbd>/</kbd>   | `C4Config.cpp:384`      |
    |  9  | Menu           | <kbd>M</kbd>   | `C4Config.cpp:385`      |
    | 10  | Special        | <kbd>ä</kbd>   | `C4Config.cpp:386`      |
    | 11  | Special2       | <kbd>ü</kbd>   | `C4Config.cpp:387`      |

    !!! note "German-locale swap"
        On a German-locale system, slot 5 defaults to <kbd>ö</kbd>
        instead of <kbd>;</kbd>, and slot 8 defaults to <kbd>-</kbd>
        instead of <kbd>/</kbd>. See the `fGer` branches at
        `C4Config.cpp:381` and `C4Config.cpp:384`.

=== "Kbd4 (cluster)"

    | idx | slot           | key               | source                  |
    |----:|----------------|-------------------|-------------------------|
    |  0  | CursorLeft     | <kbd>Ins</kbd>    | `C4Config.cpp:389`      |
    |  1  | CursorToggle   | <kbd>Home</kbd>   | `C4Config.cpp:390`      |
    |  2  | CursorRight    | <kbd>PgUp</kbd>   | `C4Config.cpp:391`      |
    |  3  | Throw          | <kbd>Del</kbd>    | `C4Config.cpp:392`      |
    |  4  | Up             | <kbd>↑</kbd>      | `C4Config.cpp:393`      |
    |  5  | Dig            | <kbd>PgDn</kbd>   | `C4Config.cpp:394`      |
    |  6  | Left           | <kbd>←</kbd>      | `C4Config.cpp:395`      |
    |  7  | Down           | <kbd>↓</kbd>      | `C4Config.cpp:396`      |
    |  8  | Right          | <kbd>→</kbd>      | `C4Config.cpp:397`      |
    |  9  | Menu           | <kbd>End</kbd>    | `C4Config.cpp:398`      |
    | 10  | Special        | <kbd>Return</kbd> | `C4Config.cpp:399`      |
    | 11  | Special2       | <kbd>Backspace</kbd> | `C4Config.cpp:400`   |

## Presets

The engine ships six stock control presets, each a complete 12-slot key
table plus a mouse recommendation, applicable in one click:

| preset                | applies to | mouse   | locale-aware             |
|-----------------------|------------|---------|--------------------------|
| Classic One-Hand      | Kbd1       | keep    | QWERTZ (slots 6, 9)      |
| Numpad                | Kbd2       | keep    | no                       |
| Right-Hand            | Kbd3       | keep    | QWERTZ (slots 5, 8)      |
| Nav Cluster           | Kbd4       | keep    | no                       |
| Two-Hand WASD+IJKL    | Kbd1       | keep    | no                       |
| Two-Hand WASD+Mouse   | Kbd1       | force on | no                       |

**Fresh installs start on Two-Hand WASD+Mouse.** The Kbd1 defaults are
that preset (single-sourced from the registry — see the Kbd1 tab above).
WASD movement on the left hand, an IJKL+O action cluster on the right:

| idx | slot           | key             |
|----:|----------------|-----------------|
|  0  | CursorLeft     | <kbd>Q</kbd>    |
|  1  | CursorToggle   | <kbd>Space</kbd> |
|  2  | CursorRight    | <kbd>E</kbd>    |
|  3  | Throw          | <kbd>J</kbd>    |
|  4  | Up             | <kbd>W</kbd>    |
|  5  | Dig            | <kbd>I</kbd>    |
|  6  | Left           | <kbd>A</kbd>    |
|  7  | Down           | <kbd>S</kbd>    |
|  8  | Right          | <kbd>D</kbd>    |
|  9  | Menu           | <kbd>K</kbd>    |
| 10  | Special        | <kbd>O</kbd>    |
| 11  | Special2       | <kbd>L</kbd>    |

Left hand: <kbd>Q</kbd>/<kbd>E</kbd> crew cycling, <kbd>Space</kbd>
cursor toggle, <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd>
movement. Right hand: <kbd>I</kbd> dig, <kbd>J</kbd> throw,
<kbd>K</kbd> menu, <kbd>O</kbd>/<kbd>L</kbd> specials. The table is
locale-neutral by construction — no QWERTZ variants. Two-Hand WASD+IJKL
shares this exact table and differs only in leaving the mouse setting
alone instead of forcing it on. The two-hand tables live at
`src/C4ControlPresets.cpp:77-91`; the six-preset list begins at
`src/C4ControlPresets.cpp:193`.

Classic One-Hand — the pre-flip Kbd1 defaults — is kept as a preset for
veterans:

| idx | slot           | key                    | source                    |
|----:|----------------|------------------------|---------------------------|
|  0  | CursorLeft     | <kbd>Q</kbd>           | `C4ControlPresets.cpp:99` |
|  1  | CursorToggle   | <kbd>W</kbd>           | `C4ControlPresets.cpp:100` |
|  2  | CursorRight    | <kbd>E</kbd>           | `C4ControlPresets.cpp:101` |
|  3  | Throw          | <kbd>A</kbd>           | `C4ControlPresets.cpp:102` |
|  4  | Up             | <kbd>S</kbd>           | `C4ControlPresets.cpp:103` |
|  5  | Dig            | <kbd>D</kbd>           | `C4ControlPresets.cpp:104` |
|  6  | Left           | <kbd>Z</kbd>/<kbd>Y</kbd> | `C4ControlPresets.cpp:105` |
|  7  | Down           | <kbd>X</kbd>           | `C4ControlPresets.cpp:106` |
|  8  | Right          | <kbd>C</kbd>           | `C4ControlPresets.cpp:107` |
|  9  | Menu           | <kbd>R</kbd>/<kbd>&lt;</kbd> | `C4ControlPresets.cpp:108` |
| 10  | Special        | <kbd>V</kbd>           | `C4ControlPresets.cpp:109` |
| 11  | Special2       | <kbd>F</kbd>           | `C4ControlPresets.cpp:110` |

The German (`fGer`) branch puts <kbd>Y</kbd> on slot 6 and `<` on
slot 9 (`src/C4ControlPresets.cpp:121`, `:124`) — the same swap the
pre-flip Kbd1 defaults had. Numpad, Right-Hand, and Nav Cluster repeat
the Kbd2-4 tables in the keyboard-set tabs above.

**Where the pickers are.** A **Preset** dropdown exists in two places:
the player-properties dialog (forced on the very first start,
`src/C4StartupMainDlg.cpp:292-294`) and **Options → Keyboard** above the
key grid (`src/C4StartupOptionsDlg.cpp:349-359`). The player dialog
applies the chosen preset to the player's keyboard set and persists it
on OK (`src/C4StartupPlrSelDlg.cpp:1420`); the Options dropdown applies
it immediately to the currently selected set and the dialog's
save-on-close persists it.

**One table per set, shared.** Applying a preset rewrites the chosen
set's single global table — the same table every player using that set
reads. Two hot-seat players sharing a set therefore share the applied
preset (per-player preset profiles are a later feature). Remapping
individual keys afterwards works exactly as before, see Remapping.

**Fresh vs existing installs.** The flip changes the Kbd1 *defaults*.
Existing installs keep every explicitly saved binding, slot by slot;
slots that were never customized load the new two-hand defaults. In
particular, an existing install that never customized Kbd1 starts on the
two-hand layout after the update — an intended, user-visible "upgrade to
modern defaults". Classic One-Hand is one click away in either picker.

**The reset button.** The Options dialog's reset
(`Config.Controls.ResetKeys()`, `src/C4Config.cpp:778`) restores all four
sets' default tables — which now means Kbd1 resets to Two-Hand
WASD+Mouse. Resetting a classic-edited Kbd1 therefore flips it to
two-hand; the button still resets all four sets (unchanged behavior, new
values).

## Gamepad

Gamepads expose the same 12 `CON_*` slots, mapped via
`Config.Gamepads[i].Button[j]` (`src/C4Game.cpp:3296-3311`). Axes
are translated into synthetic keys at
`src/C4GamePadCon.cpp:230-236`. The default gamepad mapping is
configurable in the in-game Options dialog; this page does not list
a default per-button table because the engine ships no gamepad
default in `C4Config.cpp` (the `Button[]` array defaults to `-1`,
meaning "unbound", per the `if (cfg.Button[iCtrl] == -1) continue;`
guard at `src/C4Game.cpp:3303`).

## Engine hotkeys

These are not player controls but round-level hotkeys registered in
`src/C4Game.cpp:3069-3086`:

| key                  | action                  | source                  |
|----------------------|-------------------------|-------------------------|
| <kbd>Esc</kbd>       | Show abort dialog       | `C4Game.cpp:3074`       |
| <kbd>Pause</kbd>     | Pause toggle (fullscreen) | `C4Game.cpp:3075`     |
| <kbd>Tab</kbd>       | Scoreboard toggle       | `C4Game.cpp:3073`       |
| <kbd>F9</kbd>        | Screenshot              | `C4Game.cpp:3019`       |
| <kbd>Ctrl</kbd>+<kbd>F9</kbd> | Screenshot (all) | `C4Game.cpp:3020`       |
| <kbd>←</kbd>/<kbd>→</kbd>/<kbd>↑</kbd>/<kbd>↓</kbd> | Free-view scroll | `C4Game.cpp:3069-3072` |

## Crew selection

Crew selection uses three of the 12 `CON_*` slots:

- `CON_CursorLeft` (slot 0) — select previous crew
- `CON_CursorRight` (slot 2) — select next crew
- `CON_CursorToggle` (slot 1) — toggle cursor-follow mode

There is no separate subsystem: cycling the crew is just three of
the 12 per-player controls, mapped the same way as the others.
Source: `src/C4Constants.h:214-216`, with the `COM_Cursor*` command
variants at `src/C4Constants.h:266-270`.

## Command variants

Each `CON_*` can fire as single, double, or released. A single tap
fires `COM_*_S`; a double-tap fires `COM_*_D`; releasing the key
fires `COM_*_R`. Source: `src/C4Constants.h:246-308`,
`src/C4ObjectCom.cpp:791-901`.

## Remapping

Remapping a binding is done in the in-game Options dialog (Player →
Controls). The fastest route to a personal layout is to pick one of the
six stock [presets](#presets) first, then customize individual keys —
either via the bindings tab or the per-set editor (each set's 12 key
buttons) in the same dialog. This page documents only the defaults. See
`src/C4StartupOptionsDlg.cpp:256` ("every key from 0 to C4MaxKey-1
MUST BE present here, or the engine will crash") for the engine-side
constraint that all 12 keys must be bound.
