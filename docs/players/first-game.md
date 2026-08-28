# Your first game in 5 minutes

Clonk is a tactical action game of digging, building, and commanding small
crews. This guide gets you playing your first settlement round in five
minutes on the shipped **Colony Bay** scenario.

[Launch Colony Bay](#1-start-colony-bay){ .md-button .md-button--primary }

!!! note "Don't have Colony Bay installed?"
    Colony Bay ships in the default content pack. See the
    [installation manual](https://clonkspot.org/lc-en#installation-1) if the
    scenario browser in step 1 doesn't list it.

---

## 1. Start Colony Bay

**Goal:** load the scenario with 3 shipwrecked clonks.

From the main menu, choose **Single player → Worlds → Colony Bay → Start**.
The opening cutscene washes three clonks ashore next to a ruined hut and a
lighthouse stump on the headland.

<!-- TODO: capture -->
!!! note "Screenshot pending"
    A screenshot of the scenario browser with Colony Bay selected, plus a
    short GIF of the clonks washing ashore, will appear here once the GUI
    build is unblocked. See the asset-pipeline appendix at the bottom of
    this page.

!!! tip "Pro tip"
    The first clonk carries salvaged `WOOD`×10 and `METL`×5 — enough to
    queue the first sawmill kit immediately.

---

## 2. Clear the ruins and salvage

**Goal:** clear the headland rubble around the ruined `HUT2`.

Select a clonk, walk to the rubble around the ruined hut, and press
<kbd>D</kbd> to dig or <kbd>G</kbd> to grab. Loose `WOOD` and `ROCK` scatter
as you clear; grab them so the buy menu can spend them.

<!-- TODO: capture -->
!!! note "Screenshot pending"
    A screenshot of the headland rubble plus a 2–3 s GIF of a clonk clearing
    it will appear here.

!!! warning "Watch out"
    Loose `ROCK` falls through terrain edges — don't dig straight down
    under a rock pile or you'll lose the material into the sea.

---

## 3. Restore the wood–stone–tools chain

**Goal:** build a sawmill + foundry, then produce construction kits.

Open the buy menu with <kbd>B</kbd>. Queue `SAWM` (sawmill) first — it
converts `WOOD` into the processed lumber the foundry needs. Once the
sawmill is up, queue `FNDR` (foundry) and `WRKS` (workshop). The foundry
turns `ROCK` into `METL`; the workshop combines `WOOD` + `METL` into `CNKT`
(construction kits). `CNKT` is the universal building material — every
subsequent structure costs kits.

<!-- TODO: capture -->
!!! note "Screenshot pending"
    A screenshot of the buy menu with `SAWM`/`FNDR`/`WRKS` queued, plus a
    GIF of the sawmill assembling, will appear here.

!!! tip "Pro tip"
    Settlement value climbs as you place structures. You don't need to
    *finish* every building for the value to tick up — a half-built sawmill
    already counts.

---

## 4. Reach settlement value 300

**Goal:** trigger the lighthouse recipe unlock.

Keep building. The `FxWealthCheckTimer` effect fires every 30 frames and
checks the total settlement value; at **≥ 300** it grants the `LGHT`
(lighthouse) recipe to every player, human or AI, and pops the
`$MsgLighthouseUnlocked$` toast in the top-left.

<!-- TODO: capture -->
!!! note "Screenshot pending"
    A screenshot of the settlement-value readout at ≥ 300, plus a GIF of
    the `$MsgLighthouseUnlocked$` toast, will appear here.

!!! note "Note"
    The recipe is granted to *all* players — AI crew can also build the
    lighthouse if they get there first. In single-player Colony Bay you are
    the only player, so this is moot.

---

## 5. Build the lighthouse on the stump

**Goal:** complete the `LGHT` construction from 10% → 100%.

Select a clonk that holds the `LGHT` recipe (any clonk — the recipe was
granted globally in step 4). Walk to the pre-placed stump on the headland
and supply it with `WOOD`, `METL`, and `CNKT`. The stump counts as 10%
completion, so you only need to top the structure up to 100%.

<!-- TODO: capture -->
!!! note "Screenshot pending"
    A screenshot of the lighthouse under construction on the stump, plus a
    GIF of the structure climbing from 10% → 100%, will appear here.

!!! tip "Pro tip"
    The pre-placed stump counts as 10% completion — don't demolish it. If
    you accidentally clear it, the lighthouse recipe is still unlocked from
    step 4 and you can re-queue `LGHT` on any suitable foundation.

---

## 6. Light the beacon at night

**Goal:** trigger the trade-ship ending sequence.

Wait for nightfall (the sky darkens — use the `TIME` object to fast-wait if
you want). Enter the completed lighthouse and activate it. The
`Lighthouse.c4d` `Activate` callback requires `GetCon() >= 100` *and*
`!IsDay()`, so a half-built lighthouse or a daytime activation will refuse.
Once lit, the `EndingSequence` schedules the `TradeShip` (`TSHp`) to spawn
from the left edge after 350 frames; the ship sails to the dock and grants
**CHEM** (chemistry) knowledge to all players on arrival.

<!-- TODO: capture -->
!!! note "Screenshot pending"
    A screenshot of the beacon lit at night, plus a GIF of the trade ship
    arriving and the CHEM knowledge toast, will appear here.

!!! tip "Pro tip"
    The `IsDay()` check in `Lighthouse.c4d/Script.c` refuses activation
    during daylight — don't waste materials re-queuing if it didn't light.
    Use the `TIME` object to fast-wait to nightfall.

---

## Where next

- Want the full course? Play the 10-scenario voiced
  [Tutorial chain](https://legacyclonk.github.io/LegacyClonk/tutorials/first-object/).
- Want to make your own scenario? Read the
  [Modder Quickstart](https://legacyclonk.github.io/LegacyClonk/tutorials/first-object/).
- Got stuck? Press <kbd>Esc</kbd> → **Exit round**; Colony Bay is replayable.

---

<details>
<summary>How these screenshots and GIFs were captured (asset pipeline)</summary>

1. Launch Colony Bay; at each milestone tap <kbd>F9</kbd> → PNG in
   `<exe>/Screenshots/ScreenshotNNN.png` (engine:
   `C4GraphicsSystem::SaveScreenshot`, `src/C4Game.cpp`).
2. For each GIF: capture a 2–3 s OBS clip; encode with gifski:

   ```bash
   ffmpeg -i clip.mp4 -f yuv4mpegpipe - | gifski --width=480 -o stepN.gif -
   ```

3. Drop the PNGs and GIFs into `docs/players/img/` and commit. Replace the
   matching `!!! note "Screenshot pending"` admonition with the real image
   markdown:

   ```markdown
   ![Step N scenario browser](img/stepN.png){ loading=lazy }
   ![Step N clearing rubble](img/stepN.gif){ loading=lazy }
   ```

This recipe lets any contributor regenerate all twelve assets from a single
~5-minute playthrough after a Colony Bay tweak. Width is capped at 480 px and
each GIF stays ≤ 500 KB so the page loads fast on mobile data.

</details>
