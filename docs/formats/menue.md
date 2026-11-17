# Menu text, small text containers, minigame and recaps (`\mnu\us\`, `\mg1\us\`, `\mnu\pse\us\`)

## .txd – text tables (tool: `tools/txdtext.py`)

| File | Variant | Strings | Content |
|---|---|---|---|
| `menutext.txd` | A | 907 | menus, items, messages (`Acquired %s x %d!`) |
| `synopsis.txd` | B | 166 | story summaries, with `$` commands for layout |
| `devchk.txd` | B | 20 | memory card, progressive scan, controller |
| `discchg.txd` | B | 13 | disc change |

- **Variant A:** `u32 count`, `count × u32` absolute offsets, then the strings.
- **Variant B:** `count × u32` absolute offsets where the first offset equals the table length, then the strings.

Shared offsets stay shared when rebuilding. The round trip is identical for all 4 files; lengthened texts are read back correctly.
Some entries separate lines with **CR+LF** – the tools keep these line endings; when editing a table make sure your editor does not
drop the CR inside a cell (a missing CR shifted the cutscene pause display).
Control codes in the text: `\31\3` (prefix), `\n`, `\button0`, `\m` (placeholder), `$ax…;$ay…;$col…;` (layout) – keep unchanged.
Export: `text/en/menue_txd.csv` (1 106 strings, categories `text`/`befehl` (command)/`leer` (empty)).

## .bin containers (DBC.bin, DBC2.bin, njDataText.bin, MVtext.bin, SegmentFileData.bin, njBtlText.bin, njDBcommon.bin)

```
u32 number of blocks
count × (u32 offset, u32 size)
padding 0x90 up to a 16-byte boundary
blocks (each aligned to 16 bytes, padding 0x90)
```

| File | Blocks | Text (approx.) |
|---|---|---|
| `DBC.bin` | 10 | ≈ 56 000 words (database) |
| `DBC2.bin` | 27 | the same texts as alphabetical index |
| `njDataText.bin` | 13 | ≈ 1 250 words (bonus menu, records `TOP`) |
| `MVtext.bin` | 4 | ≈ 450 words (movie selection) |
| `SegmentFileData.bin` | 2 | ≈ 400 words (segment addresses, records `SEG`) |
| `njBtlText.bin`, `njDBcommon.bin` | 1 | headings |

Blocks contain records with a tag (`DBF\0`, `SEG\0`, `TOP\0`), string offsets relative to the block and numbers.
- `DBC.bin`/`DBC2.bin`: see [datenbank.md](datenbank.md) (own tool `dbctext.py`).
- Other files: generic tool **`tools/bintext.py`**. Each block is one of two kinds:
  - **Table:** u32 offsets (relative to the block), the first offset equals the table length, then the strings. Used by `njBtlText`,
    `njDBcommon` and the last block of `SegmentFileData`/`MVtext`/`njDataText`.
  - **Records:** tag (`SEG` 48 B, `MVD` 48 B, `TOP` 32 B, `CHA` 16 B, `EVE` 32 B), `0x90` padding, the last record without padding,
    then the strings. A field counts as a pointer if in **every** record it points to a string start or is `0`/`FFFFFFFF` (no string,
    e.g. `EVE` without chapter heading). If a field points to strings only sometimes, the tool aborts.
  - Every string must be referenced, otherwise the tool aborts.
- Round trip identical for `njBtlText` (51 strings), `njDBcommon` (48), `SegmentFileData` (88), `MVtext` (280), `njDataText` (443).
  As a cross-check, `DBC`/`DBC2` are recognised correctly too.
- `njDBcommon.bin` contains the database category names for **locked** categories → translate them like in `DBC.bin`.

## Minigame and episode recaps (tool: `tools/mestext.py`)

**`\mg1\us\Message.Dat`** (minigame):
```
0x0000  933 × u32 offset (relative to 0x2800)
0x0E94  up to 0x2800 other data (graphics/attributes?) – unchanged
0x2800  null-terminated strings up to the end of the file
```
Round trip identical. 931 texts exported, 2 Japanese leftovers skipped. Many texts contain button symbols (`<○>`, `<□>`, `△`, `×`, `↑`).
Upper-case texts drawn with the minigame's bitmap font (e.g. "PRESS START BUTTON!") only support the glyphs of that font – keep them
in English unless you check the font.

**`\mnu\pse\us\*.mes`**: text files (CRLF) with sections `#MESSAGE n`.
- **English:** only `EP1.mes` (29 sections) and `EP2.mes` (40) – the Episode I/II summaries in the bonus menu.
- **Japanese only:** `AC.mes`, `PP.mes`, `opening.mes`, `test.mes` – apparently unused in the US release.
- Each section is exported as one cell with real line breaks. Blank lines and headers are preserved. Round trip identical.
