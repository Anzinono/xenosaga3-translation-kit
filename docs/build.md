# Build pipeline: from translation tables to a playable image

One command turns your translation tables into both disc images and the xdelta patches:

```bash
python -I tools/build.py --sprache <code>      # e.g. fr, es, it, pt-br (default: de)
```

| Option | Effect |
|---|---|
| `--sprache <code>` | target language (also via environment variable `XS3_LANG`) |
| `--disc 1` | only disc 1 (can be given twice) |
| `--nur-dateien` | only tables → game files + report (a few seconds, no images) |
| `--ohne-pruefsumme` | skip the SHA1 check of the original images (saves about a minute) |
| `--de <folder>` | use a different folder with tables (e.g. for experiments); patches then go to `build/patch_probe/` |

Duration for both discs incl. verification and patches: about 3–4 minutes.

## Translation workflow

1. Export the English text and create templates (once):
   ```bash
   python -I tools/vorbereiten.py --sprache fr
   ```

   | Table | Content | Key columns |
   |---|---|---|
   | `skripte.csv` | dialogue, choice menus, messages | datei, idx, kategorie |
   | `menue_txd.csv` | menus, items, system messages, summaries | datei, idx, kategorie |
   | `datenbank.csv` | database (applied to DBC.bin **and** DBC2.bin) | eintrag, feld |
   | `menue_bin.csv` | battle/database headings, bonus menu, movie selection | datei, block, idx |
   | `minispiel_rueckblick.csv` | minigame, Episode I/II recaps | datei, schluessel |
   | `untertitel.csv` | subtitles of both discs | datei, zeile |
   | `kampfdaten.csv` | ether, techs, items, equipment, status effects, battle commands (`bat/us/batdat.bin`) | datei, idx |

2. Fill the column **`text_<code>`** in `text/<code>/*.csv`. Empty cells stay English. Do not change the other columns.
3. A text only needs to be translated **once**: the **translation memory** fills every row with the identical `text_en`
   in the same table. Example: "Board the E.S.?" appears in 647 scripts.
4. Graphics: fill the `"<code>"` fields in `text/<code>/grafik_*.json` (see `docs/grafik.md`). Empty fields keep the original graphic.
5. Run `python -I tools/build.py --sprache <code>`.
6. Read `build/pruefbericht.md`: progress, errors, warnings.
7. Test `build/Xenosaga3_<CODE>_Disc1.iso` in PCSX2.

Optional: `python -I tools/glossar_kandidaten.py` collects names and terms into `text/<code>/glossar.csv`.

**Git / publishing:** `text/en/` and `text/<code>/` contain game text (the English original and your translation), and so do the
patches in `patch/`. Both are copyrighted or derived from copyrighted material – **do not upload them publicly**.
The `.gitignore` of this repository excludes them.

## Rules for the translation column

- **Copy control codes exactly:** `<f>`, `<wNN>`, `<lN>`, `<col…>`, `$…;`, `%s`, `%d`, `\n` (line break, backslash + n).
  The report warns if they differ.
- `[Speaker]` at the start may be translated. Keep names consistent with your glossary.
- `<kKeyword>` links to the database. Translate the term exactly like the database title.
- Allowed: all Windows-1252 characters (à é ñ ö ß œ „ “ – … €) and the game symbols ○ □ △ × ↑ → Σ.
  Not allowed: `¡ ¢ £ ¤ ¦` and the soft hyphen – the tools report them as errors (reason: `docs/formats/font.md`).
- Line length: the report warns if a line is longer than the longest English line of the same kind (dialogue is measured in
  pixels using the game font) or if a text has more lines than the original.

## What the pipeline does internally

1. **Prerequisites:** original images in `ISO/` with known SHA1. Missing text files are extracted with `x3extract.py`.
2. **Translation memory** → `build/<code>/csv/`.
3. **Import** with the format tools `sbtext`, `txdtext`, `dbctext`, `bintext`, `mestext`, `batdattext`, `subtitle_import`
   and the graphics tools → `build/<code>/x3/` (shared archive) and `build/<code>/untertitel/discN/`.
4. **Report** → `build/pruefbericht.md`.
5. **Images:** `x3rebuild.py` per disc (shared files + that disc's subtitles), then `verify_rebuild.py`: every archive file is
   checked against its expected content.
6. **Patches:** `xdelta3 -e -9` → `patch/Xenosaga3_<CODE>_DiscN.xdelta`. Cross-check: the patch is applied to the original and
   the result must have the same SHA1 as the built image. xdelta3 is looked up in `PATH` and in `C:\tools\xdelta3\`.

## Applying a patch (for players)

```bash
xdelta3 -d -s "Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 1).iso" Xenosaga3_FR_Disc1.xdelta Xenosaga3_FR_Disc1.iso
```

This requires an original image with the SHA1 listed in `docs/iso-pruefsummen.md`.
