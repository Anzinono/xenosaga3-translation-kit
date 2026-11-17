# XTX textures and title screen

Tools: `tools/xtx.py` (read/write), `tools/titelbild.py` (title screen), `tools/render_text.ps1` (text rendering via Windows GDI+).
Header and swizzle based on [Xenosaga3PythonExtractor](https://github.com/LinuxJessi/Xenosaga3PythonExtractor) `xtx_decode.py`
(MIT, © 2026 Jessi Ray Godsibb). Writing back (swizzling in the reverse direction) is original work.

## Format

```
0x00 "XTX\0"   0x04 u32 file size   0x08 u32 count (1)   0x0C u32 0x10
0x10 u16 width W   0x12 u16 format   0x14 u32 height H   0x20 u32 data offset (0x30)
0x30 W*H*4 bytes "CT32 canvas", followed by ~32 trailing bytes
```

- **Format 0x04:** linear RGBA.
- **Format 0x08:** the canvas holds an **8-bit index image of 2W × 2H** in PS2 memory layout (PSMT8, "swizzled"). Mapping:
  `swizzle8_offset()` in `xtx.py`, verified to be a bijection for all pixels. The palette lies in the same canvas; its location is
  not stored in the file (the game addresses it via a GS memory pointer).
- **Round trip:** `python -I tools/xtx.py test <file>` → `titleobj.xtx` and `window0.xtx` byte-identical.

## Title screen

| File | Content | Change |
|---|---|---|
| `mnu/us/title1.png` | logo, "Also sprach Zarathustra", copyright line (plain PNG 512×448 RGBA) | optional credit line **above** the unchanged copyright line |
| `mnu/us/titleobj.xtx` | format 0x08, canvas 72×128 → image 144×256: NEW GAME (y 2–15), CONTINUE (21–33), DATA (39–51), DISC 1 (77–86), DISC 2 (95–104), selection bar (108–142) | the three menu words |

The menu font uses only indices **1–15**. Its palette lies in the CT32 canvas as a **16-colour palette, 8×2 entries from pixel
(8, 112)**: colour `2A2A2A` everywhere (like the copyright line), alpha as an opacity ramp in a **shuffled order**:

| Index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Alpha | 00 | 11 | 22 | 08 | 19 | 3B | **80** | 5D | 77 | 44 | 33 | 66 | 55 | 4C | 2A | 6E |

Index 6 is fully opaque and fills the inside of the original letters. A second palette (`89FEE0`, from pixel (24, 112)) is used by the
turquoise selection bar. `titelbild.py` reads the font palette and picks, per pixel, the index with the nearest opacity – assuming a
linear 0–15 ramp produces bright stripes inside the letters (index 15 is only 86 % opaque).
The translated words are rendered with GDI+ (default Arial Narrow Bold), mapped to the palette and placed at the height and centre of
the original word. Words wider than the old area are squeezed horizontally.

Configuration: `text/<code>/grafik_titel.json` (template in `vorlagen/`):

| Key | Meaning |
|---|---|
| `menue` | the three menu words (`"NEW GAME": "…"`), upper case like the original; empty = keep |
| `schrift`, `schrift_fett` | font and bold flag for the menu words |
| `credit`, `credit_schrift`, `credit_fett`, `credit_hoehe`, `credit_position` | optional credit line (text, font, bold, height in px, `ueber` = above / `unter` = below the copyright line); empty = no line |

The copyright line of the rights holders is never changed. Tested in PCSX2: menu words are shown completely (the game cuts them with
the original rectangles), the credit line above the copyright line is fully visible.
