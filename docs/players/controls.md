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

=== "Kbd1 (WASD-ish)"

    | idx | slot           | key          | source                  |
    |----:|----------------|--------------|-------------------------|
    |  0  | CursorLeft     | <kbd>Q</kbd> | `C4Config.cpp:345`      |
    |  1  | CursorToggle   | <kbd>W</kbd> | `C4Config.cpp:346`      |
    |  2  | CursorRight    | <kbd>E</kbd> | `C4Config.cpp:347`      |
    |  3  | Throw          | <kbd>A</kbd> | `C4Config.cpp:348`      |
    |  4  | Up             | <kbd>S</kbd> | `C4Config.cpp:349`      |
    |  5  | Dig            | <kbd>D</kbd> | `C4Config.cpp:350`      |
    |  6  | Left           | <kbd>Y</kbd>/<kbd>Z</kbd> | `C4Config.cpp:351` |
    |  7  | Down           | <kbd>X</kbd> | `C4Config.cpp:352`      |
    |  8  | Right          | <kbd>C</kbd> | `C4Config.cpp:353`      |
    |  9  | Menu           | <kbd>R</kbd>/<kbd>&lt;</kbd> | `C4Config.cpp:354` |
    | 10  | Special        | <kbd>V</kbd> | `C4Config.cpp:355`      |
    | 11  | Special2       | <kbd>F</kbd> | `C4Config.cpp:356`      |

    !!! note "German-locale swap"
        On a German-locale system, slot 6 defaults to <kbd>Y</kbd>
        instead of <kbd>Z</kbd>, and slot 9 defaults to the `<` key
        instead of <kbd>R</kbd>. See the `fGer` branch at
        `C4Config.cpp:343` and the per-key conditionals at
        `C4Config.cpp:351` and `C4Config.cpp:354`.

=== "Kbd2 (numpad)"

    | idx | slot           | key             | source                  |
    |----:|----------------|-----------------|-------------------------|
    |  0  | CursorLeft     | <kbd>KP_7</kbd> | `C4Config.cpp:358`      |
    |  1  | CursorToggle   | <kbd>KP_8</kbd> | `C4Config.cpp:359`      |
    |  2  | CursorRight    | <kbd>KP_9</kbd> | `C4Config.cpp:360`      |
    |  3  | Throw          | <kbd>KP_4</kbd> | `C4Config.cpp:361`      |
    |  4  | Up             | <kbd>KP_5</kbd> | `C4Config.cpp:362`      |
    |  5  | Dig            | <kbd>KP_6</kbd> | `C4Config.cpp:363`      |
    |  6  | Left           | <kbd>KP_1</kbd> | `C4Config.cpp:364`      |
    |  7  | Down           | <kbd>KP_2</kbd> | `C4Config.cpp:365`      |
    |  8  | Right          | <kbd>KP_3</kbd> | `C4Config.cpp:366`      |
    |  9  | Menu           | <kbd>KP_0</kbd> | `C4Config.cpp:367`      |
    | 10  | Special        | <kbd>KP_Del</kbd> | `C4Config.cpp:368`    |
    | 11  | Special2       | <kbd>KP_+</kbd> | `C4Config.cpp:369`      |

=== "Kbd3 (right-hand)"

    | idx | slot           | key            | source                  |
    |----:|----------------|----------------|-------------------------|
    |  0  | CursorLeft     | <kbd>I</kbd>   | `C4Config.cpp:371`      |
    |  1  | CursorToggle   | <kbd>O</kbd>   | `C4Config.cpp:372`      |
    |  2  | CursorRight    | <kbd>P</kbd>   | `C4Config.cpp:373`      |
    |  3  | Throw          | <kbd>K</kbd>   | `C4Config.cpp:374`      |
    |  4  | Up             | <kbd>L</kbd>   | `C4Config.cpp:375`      |
    |  5  | Dig            | <kbd>;</kbd>   | `C4Config.cpp:376`      |
    |  6  | Left           | <kbd>,</kbd>   | `C4Config.cpp:377`      |
    |  7  | Down           | <kbd>.</kbd>   | `C4Config.cpp:378`      |
    |  8  | Right          | <kbd>/</kbd>   | `C4Config.cpp:379`      |
    |  9  | Menu           | <kbd>M</kbd>   | `C4Config.cpp:380`      |
    | 10  | Special        | <kbd>ä</kbd>   | `C4Config.cpp:381`      |
    | 11  | Special2       | <kbd>ü</kbd>   | `C4Config.cpp:382`      |

    !!! note "German-locale swap"
        On a German-locale system, slot 5 defaults to <kbd>ö</kbd>
        instead of <kbd>;</kbd>, and slot 8 defaults to <kbd>-</kbd>
        instead of <kbd>/</kbd>. See the `fGer` branches at
        `C4Config.cpp:376` and `C4Config.cpp:379`.

=== "Kbd4 (cluster)"

    | idx | slot           | key               | source                  |
    |----:|----------------|-------------------|-------------------------|
    |  0  | CursorLeft     | <kbd>Ins</kbd>    | `C4Config.cpp:384`      |
    |  1  | CursorToggle   | <kbd>Home</kbd>   | `C4Config.cpp:385`      |
    |  2  | CursorRight    | <kbd>PgUp</kbd>   | `C4Config.cpp:386`      |
    |  3  | Throw          | <kbd>Del</kbd>    | `C4Config.cpp:387`      |
    |  4  | Up             | <kbd>↑</kbd>      | `C4Config.cpp:388`      |
    |  5  | Dig            | <kbd>PgDn</kbd>   | `C4Config.cpp:389`      |
    |  6  | Left           | <kbd>←</kbd>      | `C4Config.cpp:390`      |
    |  7  | Down           | <kbd>↓</kbd>      | `C4Config.cpp:391`      |
    |  8  | Right          | <kbd>→</kbd>      | `C4Config.cpp:392`      |
    |  9  | Menu           | <kbd>End</kbd>    | `C4Config.cpp:393`      |
    | 10  | Special        | <kbd>Return</kbd> | `C4Config.cpp:394`      |
    | 11  | Special2       | <kbd>Backspace</kbd> | `C4Config.cpp:395`   |

## Gamepad

Gamepads expose the same 12 `CON_*` slots, mapped via
`Config.Gamepads[i].Button[j]` (`src/C4Game.cpp:3110-3124`). Axes
are translated into synthetic keys at
`src/C4GamePadCon.cpp:230-236`. The default gamepad mapping is
configurable in the in-game Options dialog; this page does not list
a default per-button table because the engine ships no gamepad
default in `C4Config.cpp` (the `Button[]` array defaults to `-1`,
meaning "unbound", per the `if (cfg.Button[iCtrl] == -1) continue;`
guard at `src/C4Game.cpp:3117`).

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
Controls). This page documents only the defaults. See
`src/C4StartupOptionsDlg.cpp:255` ("every key from 0 to C4MaxKey-1
MUST BE present here, or the engine will crash") for the engine-side
constraint that all 12 keys must be bound.
