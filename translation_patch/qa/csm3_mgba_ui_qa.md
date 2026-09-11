# mGBA UI QA — swordcraft3-test.gba

Date: 2026-09-12 (JST)
ROM: `translation_patch/swordcraft3-test.gba` (32 MiB, timestamp 2026-09-12 01:45)
Emulator: `/Applications/mGBA.app/Contents/MacOS/mGBA` 0.10.5 (26b7884)

## Files and routes tested

The following user saves were copied, without modification, to `/tmp/csm3_mgba_qa/` before launching:

- `swordcraft3-test.sav` (8 KiB; used automatically by mGBA beside the test ROM)
- `day2sav.sav` (8 KiB)
- `swordcraft3.sav` (8 KiB)
- `a.ss0` (PNG, 240×160; this is an image, not an mGBA savestate)

The test ROM booted to the translated title screen. The mGBA Load Game screen then showed two SRAM records. DATA 1 retained Japanese save metadata; DATA 2 rendered English metadata including `Ritchburn`, `Rob's Workshop`, and `Workshop`. The selected DATA 2 record was attempted as the representative route. Native mGBA screenshots were obtained for the title and load-menu screens:

- [mgba_native_boot.png](mgba_native_boot.png)
- [mgba_native_load_menu.png](mgba_native_load_menu.png)

The visible desktop capture [mgba_front.png](mgba_front.png) also records the mGBA window and confirms the game was running, but it is not used as pixel-accurate evidence because another emulator window overlapped it.

## Observations

- Boot succeeds; the title menu is fully English (`New Game`, `Load Game`, `Link`, `Extras`) with no apparent glyph corruption or clipping.
- The mGBA save-list renderer is legible at native 240×160. DATA 2’s English fields fit visibly across their rows; the location is split as `Rob's Workshop` / `Workshop` and remains inside the panel.
- DATA 1’s Japanese metadata is expected legacy save content, not a ROM translation failure.
- No gameplay dialogue screen could be reached reliably from DATA 2 during this run. Keyboard events reached the running emulator sufficiently to change the visible map/dialogue state in the desktop capture, but the mGBA window was behind an already-running VisualBoyAdvance-M window and could not be brought to the foreground through the available macOS accessibility session. Native F12 captures stopped at the title/load-menu pair.
- Consequently, dynamic `[NAME n]` substitutions, long player-entered names, choice prompts, in-game menus, and map/location labels were not directly verified in mGBA. The repository’s static report records 1,280 dynamic-token review findings (160 conservative worst-case overflows), so this remains an explicit coverage limitation rather than a pass.

## CLI/automation findings and limitations

- `mGBA --help` exposes `--savestate FILE` (`-t`) but no headless screenshot or scripted input option.
- `a.ss0` is a PNG screenshot and is not a loadable mGBA state. The `.sav` files are SRAM saves; mGBA used the matching `swordcraft3-test.sav` automatically.
- F12 produced native 240×160 PNGs in the ROM directory. Full-screen `screencapture` worked, but the desktop contains unrelated windows and is unsuitable for exact game-frame QA.
- No source files, ROMs, original saves, Git state, or `current.txt` were modified. Only this report and copied QA screenshots were added under `translation_patch/qa/`.

This is representative smoke QA, not exhaustive branch coverage. The cleanly demonstrated screens are boot/title and SRAM load selection; gameplay/dynamic-name verification requires a foreground mGBA session or a compatible mGBA savestate with controllable input.

## Retry (2026-09-12 01:52 JST)

I launched/targeted a separate mGBA process and confirmed two independent `mGBA` processes through macOS Accessibility. Directly setting the selected mGBA process `frontmost` and sending Down/Z/Start events did advance one mGBA instance into its saved gameplay state, but the visible desktop continued to place VisualBoyAdvance-M over the other display region. Because the instruction was not to close, modify, or control VisualBoyAdvance-M, I did not manipulate that app. mGBA’s F12 action produced no additional native PNG after the title/load pair, and no clean window-ID capture was available from the restricted session. The retry therefore adds no reliable new gameplay screenshot; dynamic-name, choice, pause-menu, and longest-string checks remain unverified rather than being reported as passes.
