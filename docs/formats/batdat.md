# Battle data `bat/us/batdat.bin`

Contains names and descriptions of ether, techs, special attacks, items, status changes, skills, equipment, E.S. parts, battle
commands and special items. The file lives in the shared archive (both discs), size 125 764 bytes.

Tool: `tools/batdattext.py` (export / import / test), table `text/en/kampfdaten.csv` → `text/<code>/kampfdaten.csv`, used by `tools/build.py`.

## Structure

| Offset | Content |
|---|---|
| `0x00` | u32 number of sections (28) |
| `0x04` | u32 file size |
| `0x08` | u32 start offset per section (the first is `0x78`). Sections follow each other without gaps; each length is a multiple of 4. |

Every section with text: **fixed-length records** followed by a **text area** with NUL-separated strings (cp1252 as everywhere, `\n`
as backslash + n, control sequences `$col…;`, `$zoomA,B;`). Pointers are **u16 offsets relative to the section start**. The first
pointer of the first record points to the start of the text. Several records may share a string (section 5: 612 pointers to 357 strings).

| Section | Record length | Pointer fields | Content |
|---|---|---|---|
| 0 | – | – | character stats and names (Shion … E.S. Reuben), not exported |
| 4 | 32 | 0 | character techs + stat descriptions |
| 5 | 32 | 0 | enemy and E.S. attacks |
| 6 | 32 | 0 name, 2 text | ether |
| 7 | 40 | 0, 2 | techs |
| 8 | 40 | 0, 2 | special attacks |
| 9 | 40 | 0, 2 | items |
| 10 | 8 | 0, 2 | status changes |
| 11 | 8 | 0, 2 | status effects (anima/status support) |
| 12 | 20 | 0, 2 | skills |
| 13 | 20 | 0, 2 | accessories |
| 14 | 28 | 0, 2 | weapons (characters and E.S.) |
| 15 | 24 | 0, 2 | armour |
| 16–19 | 20/20/20/24 | 0, 2 | E.S. frames, generators, CPU, disks |
| 23 | 2 | 0 | pointer list: battle commands and battle messages (name/explanation alternating) |
| 27 | 8 | 0, 2 | special items |
| 1–3, 20–22, 24–26 | – | – | no text (enemy stats, tables) |

Found by testing all record lengths: for the sections listed, the field points to a string start in **every** record and every string
is referenced. The tool checks both when loading and aborts otherwise.

## Import

New strings are written to the text area in original order, pointers are updated, the section is padded to 4 bytes; header and start
offsets are recomputed. Limit: a section must not exceed 64 KiB (u16 pointers); the largest has 24 KiB.

`python -I tools/batdattext.py test extracted/disc1/files/bat/us/batdat.bin`: round trip byte-identical; lengthening every string by
7 characters reads back correctly. A grown file (+944 bytes, German) runs in PCSX2: battles start, command bar, explanations and
item/ether descriptions are shown correctly.

"COMMAND", "BOOST", "PLAYER/ENEMY", "ACT" in battle are graphics (textures), not text in `batdat.bin` – see `docs/grafik.md`.
