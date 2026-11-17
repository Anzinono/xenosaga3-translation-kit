# Font and character encoding

**Result: Western European characters work without changing the font.** Text is encoded in Windows-1252. The US release already
does this itself: "Möbius Hotel", "Dämmerung", "Floßhilde" (`cf\us\1220.sb`, `1230.sb`, `1300.sb`).

## Files

`\mnu\us\font0.bin` and `font1.bin`, 494 592 bytes each (0x78C00). The two files differ but share the same width table.
Export: `python -I tools/xsfont.py <font.bin> --out <folder>` → `ebene0-3.png` (planes), `breiten.csv` (widths).

| Range | Content |
|---|---|
| `0x00000–0x77FFF` | 1 024 glyphs × 20 × 24 pixels, 1 byte per pixel. Each byte holds **4 planes of 2 bits** (plane n = bits 2n…2n+1, gray level 0–3), so 4 096 glyphs in total. |
| `0x78000–0x783FF` | width table: 512 × (left, right) in pixels for glyphs 0–511 of plane 0. Width = right − left + 1 (`FUN_00185770`). |
| `0x78400–0x78BFF` | 2 KiB of extra data, 4-bit values expanded via a table and uploaded as a separate texture (`FUN_00181fa0`), probably button icons. |

Plane 0: symbols and punctuation in JIS order, digits, A–Z, a–z, from glyph 256 **Windows-1252 0x80–0xFF**, then Greek, Cyrillic,
box drawing, ①–⑳, Roman numerals. From glyph 576 a second, partly placeholder-filled copy follows.
Planes 1–3: Japanese kanji (leftovers from the Japanese release).

## Encoding in the text renderer (`FUN_00184b30`, SLUS_213.89)

Analysed with Ghidra (requires the gp value `0x5571F0`, see `docs/werkzeuge.md`).

| Byte(s) | Meaning |
|---|---|
| `0x00` | end |
| `0x01–0x1F` | control codes with parameters (position, colour `0x0C`, numbers `0x11`, substring `0x16`, callback `0x17` …) – keep unchanged |
| `0x24` `$` | special handling (`FUN_00184090`), probably variables/commands |
| `0x20–0x7F` | ASCII |
| `0x80–0xFF` + next byte | only if `FUN_00181e48(b1, b2)` = 1: 2-byte EUC character. This applies only to certain pairs whose first byte is `A1`, `A2`, `A3`, `A4`, `A6` or `AD` (e.g. `A6 B2` Greek, `AD B5` circled number). |
| `0x80–0xFF` otherwise | **single byte → glyph `byte + 0x80`** = Windows-1252 character |

### Implementation in the tools

`tools/sbtext.py` contains `game_pair_ok()` (a re-implementation of `FUN_00181e48`), `decode_game()` and `encode_de()`, used by all text tools:
- **Export:** valid 2-byte pairs appear as the real character (EUC-JP), e.g. `○ □ △ × ↑ → Σ`. Everything else is shown as Windows-1252.
- **Import:** Windows-1252. Characters outside it are only allowed if the game renders them as a 2-byte pair. The single bytes
  `A1–A4`, `A6` and `AD` are rejected.
- A string counts as Japanese (not exported) only if it contains hiragana/katakana (EUC `A4`/`A5`), kanji (from `B0`) or Shift-JIS.
  Symbols from rows `A1–A3`, `A6` and `AD` do not count.

### Rules for translations

- Encoding: **Windows-1252** (cp1252), e.g. `à â ç é è ê ë î ï ô œ ù û ü ÿ ñ ¿ ä ö ß å æ ø „ “ ‚ ‘ « » – — … €`.
- **Do not use** the bytes `A1–A4`, `A6`, `AD` (cp1252: `¡ ¢ £ ¤ ¦` and the soft hyphen). If they are followed by a suitable byte,
  the game reads both as one Japanese character. The import rejects them. (`¡` is a problem for Spanish – use `!` or rephrase.)
- The widths of all Windows-1252 glyphs are set. Line length must still be checked in pixels, not characters
  (`tools/pixelbreite.py`, `build.py` does this for dialogue and database).

### Other languages

Languages that need characters outside Windows-1252 (e.g. Polish, Czech, Turkish, Greek, Russian) are not supported yet.
Plane 0 already contains Greek and Cyrillic glyphs, but the renderer only reaches them through specific 2-byte EUC pairs
(`A6xx` Greek, `A7xx` would be Cyrillic but is not in the whitelist of `FUN_00181e48`). Supporting them would need either
executable patches or replacing unused Windows-1252 glyphs in the font with the required letters (and a matching encoding table
in `sbtext.py`).

## Open questions

- Meaning of `font0` vs. `font1` (parameter of `FUN_00185cb0`) and of the extra range `0x78400`.
