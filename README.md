# Summon Night Swordcraft Story 3: Stone of Beginnings — English Translation

[![Translation build](https://github.com/akiyamasho/csm3/actions/workflows/translation-ci.yml/badge.svg?branch=complete-english-translation)](https://github.com/akiyamasho/csm3/actions/workflows/translation-ci.yml)
[![Latest release](https://img.shields.io/github/v/release/akiyamasho/csm3?display_name=tag)](https://github.com/akiyamasho/csm3/releases)

This repository contains the English translation patch for *Summon Night Swordcraft Story 3: Stone of Beginnings* (サモンナイト クラフトソード物語 はじまりの石), built from the [upstream GBA decompilation](https://github.com/jiangzhengwenjz/csm3) and the original game data.

The project is distributed as a patching project, not as a copyrighted game copy. You must provide your own legally obtained Japanese ROM. The expected input ROM is `csm3.gba` with SHA-1:

```
3f5253fcf57e07ce52472bd29a61d16b98a12376
```

No ROM image or save file is included in this repository. Do not upload or commit either one.

## Build and use

See [INSTALL.md](INSTALL.md) for the original decompilation setup. The translation build materials are in [`translation_patch/`](translation_patch/), including the reproducible full-coverage build script and its tracked manifest. Follow [`translation_patch/README.md`](translation_patch/README.md) and the canonical build script for the current platform-specific build flow; do not substitute an arbitrary script list.

The resulting English ROM is for personal use with an emulator or compatible hardware. Keep original ROMs and save files outside Git and protect existing save data when replacing a test build.

## Quality and coverage

The tracked manifest selects exactly one source for every unique ROM script address. All 51 duplicate Day 2 scripts are deliberate overrides. Static checks cover dialogue, menu text, location text (`placetxt`), control markers, and conservative VWF width limits. Emulator testing remains necessary for dynamic names, caller-specific placement, and state-dependent scenes.

## License and legal notice

The decompilation and source components retain their upstream licenses. Translation text and patch-specific tooling are provided under the terms in [`translation_patch/LICENSE`](translation_patch/LICENSE). This project does not grant rights to the original game, characters, art, music, or other copyrighted assets.
