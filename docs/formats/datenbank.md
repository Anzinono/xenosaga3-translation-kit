# Database (`\mnu\us\DBC.bin`, `DBC2.bin`)

Tool: `tools/dbctext.py`. Round trip identical for both files; lengthened texts are read back correctly.

## Container

```
u32 number of blocks
count × (u32 offset, u32 size)
padding 0x90 up to a 16-byte boundary
blocks, each aligned to 16 bytes (padding 0x90), no padding after the last block
```

`DBC.bin`: 10 blocks, one per category (0 Characters … 9). `DBC2.bin`: 27 blocks with **the same texts**, grouped by first letter –
this is the **alphabetical index**; the group headings are single letters (`P`, `G`, `O`). Blocks 25/26 are byte-identical to DBC
blocks 8/9.

## Block (`DBF`)

```
n records of 0xD0 bytes (50 × u32 + 8 bytes 0x90), the last one only 0xC8 bytes
null-terminated strings (Windows-1252), without gaps
```

| Field (u32) | Content |
|---|---|
| 0 | `"DBF\0"` |
| 1 | entry number |
| 2 | category |
| **3** | → category name ("Characters") |
| 4, 6 | numbers |
| **5** | → title ("Ernest Luis") |
| 7, 8, 16, 17 | mostly `FFFFFFFF` |
| **9** | → short description (list) |
| **10** | → long text (up to 6 852 characters / 149 lines, scrollable) |
| **11–14** | → extra texts, mostly `"-1"` |
| 15 | `0x200` (flags?) |
| 18–49 | numbers, probably links/images, otherwise `FFFFFFFF` |

Checked statistically on all 906 records of both files: **exactly** fields 3, 5, 9–14 are string offsets (relative to the block start),
no other field points into the text area, and every string is referenced.

## Texts

`python -I tools/dbctext.py export extracted/disc1/files/mnu/us/DBC.bin --out text/en/datenbank.csv`
→ **1 454 unique texts, ≈ 63 800 words** (453 titles, 453 long texts, 414 short descriptions, the rest extra texts/categories).

Import (applies the translation via the English text to **both** files):
`python -I tools/dbctext.py import …/DBC.bin …/DBC2.bin --csv text/fr/datenbank.csv --out build/mnu`

Tags: `<colRRGGBB>` colour, `<Name>` link to another entry (e.g. `<Vector>`, `<Zohar>`), `\n` line break.
Long texts are wrapped at 630 px (game font); `build.py` checks this in pixels and counts visible link text.

## Notes and risks

- **Links `<Name>`:** keep the linked text identical to the (translated) title of the target entry → glossary.
- **Alphabetical index (DBC2):** with translated titles, the grouping by first letter no longer matches. A clean solution would
  redistribute records to the letter blocks; not done yet.
- **Buffer size:** tested in PCSX2: `DBC.bin` +24 % (511 → 634 KB) loads, long texts are shown to the end. The upper limit is unknown;
  translations are typically 15–30 % longer than English, which is within the tested range.
- **Locked categories** show their name from `njDBcommon.bin`, not from `DBC.bin` → translate both identically.
