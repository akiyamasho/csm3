# Craftsword 3 Translation Memory

Living reference for the complete English patch. This file is a consistency aid, not a replacement for the Japanese source. When the source, an established English string, and a plausible guess disagree, preserve the source structure, prefer an established English term, and report the conflict. Never silently invent canon.

## Scope and evidence

- Runtime dialogue is in `script/*.txt`; `script/Day2_scripts/*.txt` is a duplicated/alternate Day 2 corpus and must not be edited by a normal pass. System text is in `system_messages/*.txt`; credits are in `credits.txt`.
- Existing translation examples: `script/17bd14c.txt` establishes **Master Rob**, **Master V.E**, **Sister V.E**, **Summon Beast**, and the reveal “Rob was... / A Stray Summon Beast...”; `script/17c741c.txt` establishes **Summon Stone**, **Ms. V.E**, **Murno**, and partner-introduction wording.
- `script/18c754c.txt` establishes the four forest-worker challenge NPC names **Zenichi, Zenzou, Zenji, Zentatsu**, their casual “brother(s)” references, and the recurring “legendary...” ellipsis.
- Place examples: `script/174f19c.txt` uses “Rob's Workshop 2nd Floor”; `script/176ca4c.txt` uses “Benson's workshop - Workshop”; `script/1890d0c.txt` uses “Bajan Forest”; `script/18ba71c.txt` uses “Mishus Ruins”. Preserve the project’s spelling unless a source-backed correction is logged.
- `system_messages/dictionary.txt` is the strongest current speaker/name index. `system_messages/link.txt` confirms **Rob**, **GUNVALD**, **Bogrim**, **GUNVALD EX**, and `[NAME 0]/[NAME 1]` substitution forms.
- Current system terminology is visible in `system_messages/menu.txt`, `magic.txt`, `items.txt`, `weapons.txt`, `special_attacks.txt`, and `effects.txt`. These files contain comments exposing Japanese source and occasional translator uncertainty; comments are evidence, not runtime payload.
- Japanese is still present in runtime payloads (for example `script/18a3eec.txt` and `script/17b23ac.txt`) and placeholder entries such as `system_messages/magic.txt` indexes 52–55 and `items.txt` index 49. Treat every finding as work to report or translate, not as proof that the corresponding English guess is correct.

## Canonical names, aliases, roles, relationships

Use these spellings exactly in runtime text and menus. Names with uncertain status are marked **[UNCERTAIN]** and require a report with file/address/index and proposed alternatives.

| Canonical English | Known aliases/forms | Role and relationship | Evidence / policy |
|---|---|---|---|
| `[NAME 0]`, `[NAME 1]` | Player name substitutions | Player/caller-selected names; do not translate, reorder, or replace | `system_messages/dictionary.txt`, `link.txt`; preserve token exactly |
| Rob | Master Rob | Player’s master; later revealed as a Stray Summon Beast | `17bd14c.txt`; use “Master Rob” only where source says title + name |
| V.E | Ms. V.E; Sister V.E; Master V.E | Female craft mentor/master; called “Sis” by younger characters, insists on “Master” | `dictionary.txt`, `17bd14c.txt`, `17c741c.txt`; do not collapse forms |
| Murno | Lady Murno | Summon Beast/character whose fever and concealment are discussed | `dictionary.txt`, `17d027c.txt`; “Lady” is a contextual title, not always required |
| γ | Gamma only when a spoken/localization expansion is source-supported | Murno’s Summon Beast; newly introduced partner | `17c741c.txt`, `17d027c.txt`; preserve Greek variable/name glyph |
| δ | Delta only when source supports it | Player-facing character marker in dialogue | `17bd14c.txt`; preserve glyph in substitutions |
| Gunvald | GUNVALD; GUNVALD EX | Unlockable/controllable Summon Beast/character | `link.txt`, `bonus.txt`, `magic.txt`; menu form is uppercase `GUNVALD` |
| Bogrim | **[UNCERTAIN]** source reading may be ボルガノ | Unlockable/controllable Summon Beast/character | `link.txt`, `magic.txt`, `bonus.txt`; existing patch uses Bogrim; report any challenge |
| Zenzou, Zenji, Zenichi, Zentatsu | — | Related forest-industry challenge NPCs; brother relationships are explicit | `18c754c.txt`; do not merge their names |
| Bostaph | — | Character tied to Rob reveal sequence | `dictionary.txt`, `17bd14c.txt` |
| Lemmy, Serj, Jade, Tier, Pike, Gillan, Anise, Tram, Velworen, Ritchburn, Rifmonica | — | Named dictionary/NPC cast | `dictionary.txt`; preserve spelling and capitalization |
| Chief | **[UNCERTAIN]** may be a title/name | Authority whom γ is to be introduced to | `17d027c.txt`; do not turn title into a proper name without source support |

Relationship and knowledge rules: Rob is “Master” to the player; V.E is both a master and “Sis/Sister” in the family-like address conflict; γ is Murno’s Summon Beast and the player’s new partner in the cover story; Murno’s true identity and the Rob/Stray revelation must not be foreshadowed before the Japanese payload reveals them.

## Voice bible

The source and existing corpus take priority over these defaults. Voice is a constraint on English choices, not permission to add jokes, facts, or emotion.

- **Player / `[NAME 0]`**: direct, readable, youthful-neutral first person. Use contractions in casual scenes. Avoid modern internet slang, faux-medieval diction, or omniscient knowledge.
- **V.E**: confident mentor; brisk imperatives and teasing correction. Uses contractions in casual speech. Can snap (“Stop right there!” in `17d027c.txt`) but should not become cruel or profane. She explicitly demands “Master,” not “sis,” in `17bd14c.txt`; retain this running gag.
- **Rob**: warm, capable master figure. Plain declarative phrasing; affectionate without melodrama. Keep his “Master Rob” address consistent until any source-driven change.
- **Murno**: restrained, formal, vulnerable when ill. Preserve “Lady Murno” when the established text uses it. Do not make her sound childish or sarcastic.
- **γ / machine-like Summon Beast speech**: clipped, analytical, formal. Existing examples capitalize sentence starts in lines such as “We Must Perform Maintenance,” “I Am Not...,” “I Apologize” (`17d027c.txt`, `17c741c.txt`). Keep deliberate stiffness and avoid contractions unless the Japanese clearly relaxes it.
- **Young/energetic partner voices**: short bursts, exclamations, playful contractions (“I won, sis!” / “Yay!” in `17bd14c.txt`). Do not flatten every character into this register.
- **Zenichi/Zenzou/Zenji/Zentatsu**: older, casual forest-worker challenge voices; light “Hoho~”, “Hm?”, and trailing ellipses are established in `18c754c.txt`. Preserve warmth and repetition without adding dialect spelling.
- **Generic NPCs / announcements**: concise, functional. Announcements may be formal (“There've been more strays lately” in `17d027c.txt`), but never insert explanatory lore absent from source.

Pronouns follow the established English line and source context. Prefer “you/your” for player-facing text, “they” only where gender is genuinely unknown, and character-specific pronouns already established above. Contractions are allowed for casual humans, discouraged for γ, and never required merely to fit a line. Emotional range may include embarrassment, worry, anger, awe, and comic timing, but do not intensify a neutral source.

Prohibited out-of-character tendencies: contemporary memes, profanity not present in source, faux Shakespearean language, therapeutic/clinical jargon in ordinary dialogue, explanatory narration, premature reveal language, random honorifics, and swapping names or relationships to make a line smoother.

## Terminology

| Japanese/source concept | Canonical English | Notes |
|---|---|---|
| Summon Beast | Summon Beast | Capitalize both words in narrative and menus when referring to the species/system |
| Sapureth | Sapureth | Canonical English name for the spirit world (サプレス); do not use the placeholder `Sap[NAME 8]s` |
| Summon Stone | Summon Stone | `17c741c.txt`; retain title case |
| Craftknight | Craftknight | One word, capital C; `17bd14c.txt` uses “fully fledged Craftknight” |
| Stray Summon Beast | Stray Summon Beast | Reveal-sensitive; do not paraphrase as “rogue monster” |
| Master | Master | Title/address, title case when used as direct form; lowercase only when ordinary noun grammar requires it |
| Partner | partner | Capitalize in named UI labels only; “new partner” in dialogue is lowercase (`17d027c.txt`) |
| Lyndbaum | Lyndbaum | World name; `17c064c.txt` uses “What on Lyndbaum?” |
| Rob’s Workshop | Rob's Workshop | ASCII apostrophe; preserve floor/area suffixes (`174f19c.txt`) |
| GUNVALD / GUNVALD EX | GUNVALD / GUNVALD EX | Uppercase menu forms (`link.txt`) |
| Bogrim | Bogrim | Existing English form is provisional because source comment reads ボルガノ; report conflicts |
| Gumag | Gumag; Gumag Flame Ruins | Canonical spelling for the グマグ place/name forms in the current patch; this is a consistency decision, while the underlying Japanese reading remains transliteration-sensitive |
| HP, DUR, AGL, DEF, ATK, TEC | HP, DUR, AGL, DEF, ATK, TEC | Preserve all-caps stat abbreviations; descriptions in `magic.txt`/`effects.txt` use them |
| elemental terms | lightning, fire, water, wind, light, dark | Lowercase in descriptions unless title/name; fix existing “lighting” typo only with review evidence |

Weapons/items/magic names are proper labels: use title case (`system_messages/weapons.txt`, `items.txt`, `magic.txt`, `special_attacks.txt`). Preserve established stylization (“GUNVALD Laser”, “Self-destruct”, “Partner Tag”). **[UNCERTAIN]** Existing labels “Lighting Shot”, “lighting attack”, and “HP Convertion” in `special_attacks.txt`/`effects.txt` look like probable English typos; workers must report them with indexes rather than silently broad-editing names.

## Honorifics and cultural terms

Do not add `-san`, `-chan`, `-kun`, `sama`, or Japanese kinship honorifics unless the English corpus already demonstrates a deliberate equivalent. Translate relationship terms by role and scene: “Master,” “Sister/Sis,” “brother,” “Lady,” and “Chief” are established choices. Keep food, festivals, lottery, and craft culture concrete; do not domesticize named items. Use “craft,” “forge,” “workshop,” “ore,” “crystal,” and “Summon” consistently. If a cultural term has no safe established equivalent, retain a concise romanization and flag **[UNCERTAIN]**.

## UI and copy style

- Title Case for menu labels and named equipment/magic/items (`menu.txt`: “Craft Rank”, “Bestiary”; `magic.txt`: “Healing Spell”). Sentence case for descriptions and notices.
- Use ASCII digits and punctuation in new English, but preserve existing intentional glyphs, spacing, and substitution tokens. Do not widen text or “fix” a label beyond its allocated byte count.
- Existing abbreviations such as “Rem. Mod”, “Dis. Mod”, “DUR”, “AOE”, “HP”, “TEC” are UI constraints. Do not expand them unless the field has room and the project lead approves.
- Keep action verbs parallel: “Buy”, “Sell”, “Make”; “Equip”, “Remove”; “Create”, “Upgrade”, “Repair” (`menu.txt`).

## Timeline and knowledge-state cautions

Translate only what the current payload lets its speaker know. Track reveal order locally when a file contains flags/branches. In particular:

1. Do not call Rob a Stray Summon Beast before the line in `17bd14c.txt` where it is revealed.
2. Do not present γ’s identity as Murno’s Summon Beast before the relevant confession/knowledge state in `17c741c.txt`/`17d027c.txt`.
3. “Legendary...” and interrupted names are intentional suspense; preserve ellipses and line breaks.
4. Branches and repeated variants may have different knowledge states even when the English appears similar. Read surrounding labels and conditions before harmonizing.
5. Day 2 duplicates can contain later or alternate content. Do not edit them in the ordinary runtime pass, and do not use them to leak later terminology into earlier files.

## Payload formatting and control codes

Only quoted text payloads are translatable. Preserve exactly, byte-for-byte in placement and spelling where applicable:

- opcodes/commands (`dialogtxt`, `dialogbig`, `placetxt`, `popuptxt`, `menutxt`, `menutxtp`, `tabletxt`, `gotomap`, `mapev`, etc.);
- labels (`@start`, `@Label_*`, `@Cond_*`, `@Menu_*`, `@Event_*`), addresses, comments, variables, expressions, numeric arguments, commas, and indentation unless the file’s formatter requires otherwise;
- substitution/control tokens such as `[NAME 0]`, `[NAME 1]`, and any bracketed token; never translate or reorder them;
- quote delimiters, escaped quotes (`\"`), explicit full-width/ideographic spaces where present, and every `dialogtxt` line/page break;
- `dialogbig` coordinates and flags, `table` widths, allocation lengths, and other size-sensitive arguments.

Line wrapping is presentation data. Preserve existing line boundaries unless the insertion tool’s documented limits require a change; if changing a boundary is unavoidable, report old/new line counts and reason. Keep comments and Japanese source annotations intact unless specifically instructed to translate comments.

## Ambiguity resolution and reporting

1. Search this memory and the whole non-Day2 corpus for the term and surrounding speaker/context.
2. Prefer an exact established English form over a new synonym; preserve capitalization and singular/plural behavior.
3. Compare the Japanese payload and branch/knowledge state. Do not infer from a transliteration alone.
4. Check field width/byte allocation and control-code behavior.
5. If still uncertain, choose the least committal faithful rendering only when needed to keep the build moving, mark it `[UNCERTAIN]` in the report (not in runtime text), and provide file, address/index, Japanese, current English, proposed English, and rationale.

Known review queue from the current corpus: `system_messages/menu.txt` has duplicated “Attack” labels for source `交代` and a comment questioning `攻撃`; `items.txt` indexes 72 and 120–121 contain malformed/“ASK” annotations; `magic.txt` has placeholder `仮` entries and “lighting”/“lighting” wording; `special_attacks.txt` has “Lighting” and “Convertion” spellings; `script/18a3eec.txt` and `script/17b23ac.txt` still contain Japanese runtime lines. These are reportable uncertainties, not permission to rewrite unrelated entries.

### Accepted provisional/debug labels

- `system_messages/magic.txt` indexes 52–55 render source `仮` as **Temporary**. This is a faithful compact provisional label; the Japanese does not identify a final spell name.
- `system_messages/menu.txt` address `0x08bca078` retains **????????**, and `dictionary.txt` index 266 retains **???**. Their Japanese source is question marks, so these are intentional unknown/mystery labels rather than untranslated Japanese.
- `system_messages/link.txt` address `0x08bcd870` retains **Partner Dummy**. The source explicitly says パートナーダミー; this is a literal debug/test label, not a canonical partner name.
- `system_messages/items.txt` indexes 120–121 had trailing `ASK` review annotations outside the quoted payload. They were removed from the runtime source line; the established item names remain unchanged.

## Translator and QA checklist

- Read this memory before editing and record any new canon in the change report.
- Work on quoted playable payloads only; never edit `script/Day2_scripts` during the standard pass.
- Scan all runtime text for Japanese remaining after the pass, including system tables and `credits.txt`; distinguish comments/source annotations from payload.
- Verify every opcode, label, address, variable, token, quote, line break, page break, and allocation width is preserved.
- Search for inconsistent names, title case, terminology, pronouns, contractions, and reveal timing.
- Report changed files, translated payload count, Japanese-payload count before/after, unresolved ambiguities, and any structural/control-code concern.
