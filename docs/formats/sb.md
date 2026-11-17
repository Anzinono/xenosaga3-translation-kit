# Scripts (.sb) – dialogue

`\cf\us\*.sb` (647 map scripts) and `\bat\us\*.sb` (69 battle scripts), archive X3.00. Tool: `tools/sbtext.py`.

## Structure

```
0x00  "SB  "   u16 1   u16 1
0x08  6 × u32  offsets of sections 1–6
0x20  padding up to 0x40
```

| Section | Starts with | Content |
|---|---|---|
| 1 (from 0x40) | u32 12 | bytecode |
| 2 | u32 8, u32 count | table (jump targets/data) |
| **3** | **u32 8, u32 count** | **string table**: count × u32 offset (relative to the data start right after the table), then null-terminated strings without gaps, section end padded to 4 bytes |
| 4 | u32 8, u32 count | symbols: pairs (name offset, code offset), names like `runtime_M_setDoorAttr`; relative offsets |
| 5 | u32 8, u32 count | probably debug/line information |
| 6 | u32 1 | resources (`BGM`, `us\1010`), usually 20 bytes |

Checked on all 715 files: header, string table and alignment are the same everywhere. The content contains no absolute offsets
into sections 4–6. The bytecode references strings by their **index**.
→ Texts may become longer or shorter. When rebuilding, only the header offsets of sections 4–6 move (`build()` in `sbtext.py`).

**Round trip:** `python -I tools/sbtext.py test extracted/disc1/files/cf/us extracted/disc1/files/bat/us` → 715 identical, 0 errors.
With lengthened strings, the sections after the string table stay byte-identical.

## Content of the string tables (90 580 strings)

| Category | Count | Unique | Translate? |
|---|---|---|---|
| `dialog` – starts with `[Speaker]` or contains `<f>/<w>/<l>` | 8 935 | 7 231 (≈ 76 000 words) | yes |
| `text` – other English text (menus, choices, system messages) | 2 196 | 450 | yes |
| `wort` – single words | 1 061 | 243 | **check**: database keywords (`Durandal`, `Dämmerung`) or internal names (`getitem`, `kowaremono`) |
| `bezeichner` – identifiers like `s082000_02_1mom`, `B01`, `CHRV_EVE0100` | 7 520 | – | no |
| `technisch` – debug labels like `--- main ---`, `*****`, `  px =` | 2 448 | – | no |
| `jp` – Japanese debug text (Shift-JIS/EUC-JP) | 68 420 | – | no, and **never** re-encode as cp1252 |

Only `dialog`, `text` and `wort` are exported. Many strings repeat (e.g. "Board the E.S.?<f>" in all 647 map scripts) – the
translation memory in `build.py` handles that.

## Tags in the text

| Tag | Meaning |
|---|---|
| `[Name]` at the start | speaker, shown in the name field |
| `<f>` | end of text box / wait for button |
| `<wNN>` | pause of NN frames |
| `<lN>` | line/layout control (e.g. `<l2>` – keep the number of lines) |
| `<kText>` | keyword link to the database (e.g. `<kMöbius Hotel>`) – use the same term as the database title |
| `<col…>`, `$col…;` | colour |
| `\n` | line break (two characters) |

Dialogue boxes with a portrait fit about 384 px per line (measured with the game font, `tools/pixelbreite.py`).

## Export / import

```bash
python -I tools/sbtext.py export extracted/disc1/files/cf/us extracted/disc1/files/bat/us --out text/en/skripte.csv
python -I tools/sbtext.py import extracted/disc1/files/cf/us extracted/disc1/files/bat/us --csv text/fr/skripte.csv --out build/sb
```

The import checks every translated text: it must be representable in Windows-1252 (plus the game symbols) and must not contain
the forbidden bytes `A1–A4/A6/AD` (`docs/formats/font.md`).

## Open questions

- Meaning of sections 2 and 5 and the opcode that prints dialogue – this would allow classifying `wort` strings reliably.
