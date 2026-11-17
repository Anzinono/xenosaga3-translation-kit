# Game graphics with text

Covers all image formats on disc 1 (disc 2 contains the same graphics). Translated and tested in PCSX2 (German):
title screen, location titles, character cards, database images. Battle HUD, GAME OVER and A.G.W.S. were left in English.

## Tools

| Tool | Purpose |
|---|---|
| `tools/grafik_inventar.py` | exports all candidates to `build/grafik/inventar/` (PNG/JPG) with `index.html` (overview), `kontakt.html` (contact sheet) and `inventar.csv` |
| `tools/grafik_vergleich.py` | before/after page of all translated graphics → `build/grafik/inventar/vergleich.html` |
| `tools/eftex.py` | textures in effect containers `.esd`/`.esp` (`list`, `export`, `test`) |
| `tools/tm2.py` | TIM2 textures `.tm2` (`export`, `import` for RGBA32, `test`) |
| `tools/pngrgba.py` | PNG reader without extra packages (gray, RGB, RGBA, palette) |
| `tools/xtx.py` | XTX format 0x08 (see `docs/formats/xtx.md`) |
| `tools/titelbild.py`, `ortstitel.py`, `figurenkarten.py`, `dbbilder.py` | generators for the translated graphics (configured in `text/<code>/grafik_*.json`) |

Extract first (once; `tools/vorbereiten.py` already does this for the files the build needs):

```bash
python -I tools/x3extract.py "ISO/Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 1).iso" --out extracted/disc1/files --filter "\mnu\*" --filter "\jpg\*" --filter "\mg1\us\*" --filter "\ef\esd\us\*" --filter "\ef\esp\us\*" --filter "\ef\map\us\*" --filter "\bat\bat_face\*"
python -I tools/grafik_inventar.py
```

Round trips (read → write unchanged): `eftex.py test` 67/67 effect files identical, `tm2.py test` 4/4, `xtx.py test` for
`ctrl`, `itemcap`, `Picture`, `window0–2`, `titleobj` identical.

**Pillow and `python -I`:** if Pillow is installed in the user site-packages, isolated mode hides it. The graphics tools add
exactly that one folder (`site.getusersitepackages()`); otherwise isolation stays in place.

## Formats

### Effect containers `.esd` / `.esp` (`ef/esd/us`, `ef/map/us`, `ef/esp/us`)

Records on 0x40 boundaries, each with a 0x40-byte header followed by data:

```
+0x00 u32 total size (header + data)   +0x04 u32 unknown (address/ID)
+0x08 u16 type: 4 = image, 3 = palette +0x0A u16 slot
+0x0C u16 width  +0x0E u16 height      +0x10 u32 bits per pixel (4/8)
+0x14 name, e.g. "moji.bmp", "5thelsalem-a.bmp", "moji.clt"
```

- Images: 4 bit (low nibble = left pixel) or 8 bit, linear (no swizzle).
- Palettes: RGBA32, alpha 0x80 = opaque; 2^bits entries. Matched by name stem (`x.bmp` ↔ `x.clt`); palettes follow the images.
- **Text lives in opacity masks:** each title consists of a colour image (`moji.bmp`, opaque) and a mask `<name>-a.bmp`
  (palette: black with an alpha ramp 0…0xFE). The lettering is only visible in the mask.
- 25 area titles (256×32, ornate font with shadow) in `ce0xx_9xx.esd` and the related `ef*.esp`; 14 map labels (256×64, plain font)
  in `ef1210/ef1218` and `ef2310–ef2328`. The same mask often appears in several files (up to 5×).
- Hint "Press ● button to enter this area." = `under-a.bmp` (256×64), 44 identical copies.
- Japanese leftovers: `ce006_999`, `ce008_999`.

### TIM2 `.tm2` (`mnu/pse`)

Standard TIM2 (see the header of `tools/tm2.py`). All four files are RGBA32 (image type 3). `logo_ep1/ep2` use alpha 0…0xFF,
`logo_pp`/`haikei` the PS2 scale 0…0x80 – `tm2.py` detects this per image.

### Embedded JPGs

- `mnu/credit.bin`: header with offsets, 4 JPGs (company logos).
- `mnu/diskchg.bin`: 1 JPG (disc change) + ADX voice data (`(c)CRI`).

### Other

- `mnu/segcap.xtx`: width 246 does not match the swizzle; probably segment images without text.
- `mnu/umn.txy`, `mnu/skillbg.bin`, `mnu/umn.bin`: 3D models (`Xc`/`pxy`/`txy`) with line textures, no text.

## Survey

| Group | Files | English text | Tool |
|---|---|---|---|
| Title screen | `mnu/us/titleobj.xtx`, `title1.png` | NEW GAME, CONTINUE, DATA (+ optional credit line) | `titelbild.py` |
| Location titles | `ef/esd/us/*.esd`, `ef/map/us/*.esp` | 25 area titles, 14 map labels, "Press ● button …" | `ortstitel.py` |
| Character cards | `mnu/intm/01–09.jpg`, `mnu/diskchg.bin` | "height", "weight" | `figurenkarten.py` |
| Database images | `jpg/us/dtimg_0150, 0151, 0176, 0237` (+ `1xxx` copies) | title cards, screen text | `dbbilder.py` |
| Game Over | `mnu/us/gameov1.jpg` | GAME OVER | not covered |
| Battle HUD | `mnu/us/window0–2.xtx` | ATTACKER, RESERVE, ENEMY INFO, COMMAND, STOCK, BOOST, ANIMA, ACT | not covered (shaded pixel font; letters G, H, L, R, V, "-" missing) |
| Tutorial screenshots | `jpg/us/dtimg_0431–0453` | battle UI | not covered |
| Minigame | `mg1/us/Picture.xtx` | SURREALISTIC PUZZLE ACTION | not covered (logo) |
| Logos, scenes, portraits | `syno.png`, `wall.jpg`, `logo_*.tm2`, `credit.bin`, `mnu/syno`, `kao` … | – / trademarks | keep |

`dtimg_1xxx` is mostly a copy of the `0xxx` series (275 identical); its tutorial images are Japanese.

## Title screen (`tools/titelbild.py`, `grafik_titel.json`)

See `docs/formats/xtx.md`. Menu words are re-rendered with a Windows font, mapped to the font palette (which has a
**shuffled** opacity order – always read it from the texture) and fitted to the original word's height and centre.
`credit` adds an optional line above the unchanged copyright line in `title1.png`.

## Location titles (`tools/ortstitel.py`, `grafik_orte.json`)

- 31 masks (17 area titles style A, 13 map labels style B, 1 hint line) in 49 files. Leave untranslated proper nouns empty.
- Fonts: style A **Courier New Bold** with shadow (+1/+1 and +2/+2, opacity 64/254 as in the original), style B **MS Gothic**
  (matches the original almost exactly: measured squeeze 0.98).
- Method: the English original is fitted with the replacement font to the height and width of the original mask (size + squeeze);
  the translation takes over these values, baseline and centre. Texts that are too long are squeezed further up to 250 px.
  The button symbol ● is copied from the original mask.
- Opacity → index via the palette of each mask (nearest value), not linearly. File sizes stay the same.
- Preview: `python -I tools/ortstitel.py --out <tmp> --vorschau build/grafik/orte`.

## Character cards (`tools/figurenkarten.py`, `grafik_figurenkarten.json`)

- `mnu/intm/01–09.jpg` and the JPG in `mnu/diskchg.bin`: the words "height :"/"weight :" are replaced; names and values stay.
- Located via a template from `intm/01.jpg` (only font pixels are compared; card 09 shows two characters). "weight" is always 10 px below "height".
- The old lettering incl. its dark outline (mask widened by 2 px) is filled from the outside in from neighbouring pixels; all words
  are erased first, then the new ones are drawn. Font: **Bahnschrift SemiBold**, 1.25× wide, sharpened edges, outline 1 px strong + 1 px soft.
- The JPG is saved with the original quantisation tables and 4:4:4 subsampling (`quality="keep"`), without EXIF/Photoshop metadata.
  In `diskchg.bin` the JPG must fit its old slot (up to 0x181C0, followed by ADX voice data); the rest is zero-filled.

## Database images (`tools/dbbilder.py`, `grafik_datenbank.json`)

| Image | Original | Font |
|---|---|---|
| `dtimg_0150` (+1150) | Transgenic Type | Times New Roman, shadow |
| `dtimg_0176` (+1176) | R E A L I A N | Times New Roman, letter-spaced, 18 px |
| `dtimg_0237` (+1237) | TYPE 27 / COMBAT REALIAN | Bahnschrift, 1.35× wide |
| `dtimg_0151` (+1151) | Connection system NATARAJA now loading… / User name / Password | Times New Roman bold, 12 px |

- Font pixels are detected by contrast against the local background (median 9×9) and filled from neighbours. For 0151 (text on a
  bright screen) the whole text block is blended column-wise instead (`loeschbox`), because contrast detection left traces.
- All lines are measured first, then erased, then drawn (otherwise line 2 would measure the new text of line 1).
- Identical copies in the `1xxx` series are written too.
