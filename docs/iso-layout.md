# ISO layout (USA, SLUS-213.89 / SLUS-214.17)

## Root directory

| File | Disc 1 | Disc 2 | Note |
|---|---|---|---|
| `SYSTEM.CNF` | ✓ | ✓ | boots `SLUS_213.89` / `SLUS_214.17`, NTSC, VER 1.00 |
| `SLUS_213.89` / `SLUS_214.17` | 4 513 232 B | 4 513 232 B | main executable, **byte-identical** on both discs |
| `OV01.OVL`, `OV02.OVL`, `OV04.OVL` | ✓ | ✓ | code overlays, identical |
| `X3.00` + `X3.01`, `X3.02` | ✓ | ✓ | shared archive, identical |
| `X3.10` + `X3.11`–`X3.13` | ✓ | – | disc 1 archive |
| `X3.20` + `X3.21`–`X3.23` | – | ✓ | disc 2 archive |
| `IOP\*.IRX`, `IOPRP300.IMG` | ✓ | ✓ | IOP modules (CRI ADX, sound, memory card, pad) |

Archive format: [formats/x3-archiv.md](formats/x3-archiv.md).

## Archive contents (excerpt, by size)

**X3.00 (both discs), 9 867 files:** `snd\adx` (music/voices, 441 MiB), `mdl\map` (maps), `mdl\chr` (characters), `pac\bat` (battle),
`ef\*` (effects), `kao` (faces, `.xtx`), `jpg` (database images), `mnu\*` (menus), `cf\us` (scripts), `bat\us` (battle dialogue), `mg1` (minigame).

**X3.10 (disc 1), 3 649 files / X3.20 (disc 2), 1 709 files:** `mov` (`.sfd` movies, 1.6 / 2.4 GiB), `evt` (real-time cutscenes
`.xep`/`.xev`), `snd\adx` (voice), `evt\us` and `mov\us` (subtitles).

## Files relevant for translation

| Path | Count | Format |
|---|---|---|
| `\cf\us\*.sb` | 647 | compiled script, header `SB  `, 6 sections; dialogue as text in the string table, tags `[Speaker]`, `<f>`, `\n` … ([sb.md](formats/sb.md)) |
| `\bat\us\*.sb` | 69 | same, battle dialogue |
| `\bat\us\batdat.bin` | 1 | battle data: items, ether, equipment … ([batdat.md](formats/batdat.md)) |
| `\evt\us\*.txt`, `\mov\us\*.txt` | 36 + 111 (disc 1) | **plain-text subtitles** with timestamps ([untertitel.md](formats/untertitel.md)) |
| `\mnu\us\menutext.txd` and other `.txd` | 4 | pointer table + strings, `printf` placeholders (`%s`, `%d`) ([menue.md](formats/menue.md)) |
| `\mnu\us\DBC.bin`, `DBC2.bin` | 2 | database ([datenbank.md](formats/datenbank.md)) |
| `\mnu\us\njDataText.bin`, `njBtlText.bin`, `njDBcommon.bin`, `MVtext.bin`, `SegmentFileData.bin` | 5 | menu/battle/bonus text |
| `\mg1\us\Message.Dat`, `\mnu\pse\us\EP1.mes`, `EP2.mes` | 3 | minigame and episode recaps |
| `\mnu\us\font0.bin`, `font1.bin` | 2 | game font ([font.md](formats/font.md)) |
| `\mnu\us\*.xtx`, `title1.png`, `ef\esd\*`, `jpg\us\*`, `mnu\intm\*` | – | graphics with text ([grafik.md](grafik.md)) |

Text is single-byte Windows-1252; the font already contains the Latin-1 glyphs (é, ñ, ö, ß …), so Western European
languages need no font changes.
