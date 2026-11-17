# Xenosaga Episode III – Translation Kit

Tools to translate **Xenosaga Episode III: Also sprach Zarathustra** (PS2, USA release) into your own language
and to build patched disc images that run in PCSX2.

The tools were developed for a complete German translation (≈ 14 300 texts / 155 000 words, menus, battle data,
database, subtitles and graphics with text) and are tested in PCSX2.

> **No game data is included.** You need your own original discs (USA, 2 DVDs) and must create the disc images yourself.
> The exported game text, your translation and the resulting patches are derived from copyrighted material –
> keep them private and do not upload them to public repositories.

*Deutsche Kurzfassung weiter unten.*

**Note on names:** the tools come from a German project. Code, comments, messages and documentation are in English,
but file names, command-line flags (`--sprache`, `--nur-dateien`, `--ohne-pruefsumme`), CSV column names
(`datei`, `kategorie`, `eintrag`, …) and JSON keys in the templates (`schrift`, `zeilen`, …) keep their German names,
because the tables and configurations depend on them. The template files explain their keys in `_hinweis`.

## What it can do

- Read and rebuild the game archives (`X3.00` … `X3.23`), including growing files (ISO 9660 + UDF are updated).
- Export and re-insert **all** text: dialogue scripts (`.sb`), menus (`.txd`, `.bin`), database, battle data,
  minigame, episode recaps and cutscene subtitles – every format has a byte-identical round-trip test.
- Translation memory (identical English text is translated once), report with control-code and pixel-width checks.
- Replace English text in graphics: title screen, location titles, character cards, database images (configurable via JSON).
- Build both disc images and xdelta patches in one command, with full verification.

## Requirements

- Windows 10/11 (graphics text rendering uses GDI+/Windows fonts via PowerShell)
- Python 3.10+
- [Pillow](https://pypi.org/project/Pillow/) for some graphics tools: `pip install pillow`
- Optional: [xdelta3](https://github.com/jmacd/xdelta-gpl) for patches, PCSX2 for testing,
  Ghidra 12 + ghidra-emotionengine-reloaded for reverse engineering (see `docs/werkzeuge.md`)

## Language support

Text is written in **Windows-1252**, which the game's font already contains (glyphs for à é ñ ö ß œ € „ “ …).
This covers most Western European languages (French, Spanish, Italian, Portuguese, German, Dutch, Scandinavian …)
**without any font changes**. Languages outside Windows-1252 (e.g. Polish, Czech, Russian, Greek) would need
additional font/encoding work – see `docs/formats/font.md`.

## Quick start

1. Put your disc images into `ISO/` with these exact names (checksums in `docs/iso-pruefsummen.md`):
   - `Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 1).iso`
   - `Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 2).iso`
2. Export all English text and create templates for your language (example: French):
   ```bash
   python -I tools/vorbereiten.py --sprache fr
   ```
   This creates `text/en/*.csv` (English originals) and `text/fr/*.csv` + `text/fr/grafik_*.json` (templates).
3. Translate: fill the column `text_fr` in the CSV tables (semicolon-separated, UTF-8 – opens in Excel/LibreOffice)
   and the `"fr"` fields in the `grafik_*.json` files. Empty cells stay English, so you can work step by step.
   Keep control codes like `<f>`, `<w15>`, `\n`, `%s`, `$...;` unchanged.
4. Build:
   ```bash
   python -I tools/build.py --sprache fr            # both discs + patches
   python -I tools/build.py --sprache fr --disc 1   # only disc 1
   python -I tools/build.py --sprache fr --nur-dateien   # quick check, no images
   ```
   Result: `build/Xenosaga3_FR_Disc1.iso` / `Disc2.iso`, patches in `patch/`, report in `build/pruefbericht.md`.
5. Test in PCSX2, fix, rebuild.

## Documentation

| File | Content |
|---|---|
| `docs/build.md` | Build pipeline, workflow, rules for translations |
| `docs/formats/x3-archiv.md` | Archive/catalog format |
| `docs/formats/iso-neuaufbau.md` | Rebuilding the ISO with growing files |
| `docs/formats/font.md` | Font, encoding, allowed characters |
| `docs/formats/sb.md`, `menue.md`, `datenbank.md`, `batdat.md`, `untertitel.md` | Text formats |
| `docs/formats/xtx.md`, `docs/grafik.md` | Textures and graphics with text |
| `docs/iso-layout.md`, `docs/werkzeuge.md` | Disc layout, tools, Ghidra setup |

## Credits

- Tools and research: **Anzinono**
- XTX decoding based on [Xenosaga3PythonExtractor](https://github.com/LinuxJessi/Xenosaga3PythonExtractor) by Jessi Ray Godsibb (MIT) – see `THIRD_PARTY_NOTICES.md`
- Xenosaga Episode III © Bandai Namco Entertainment / Monolith Soft. This is an unofficial fan project, not affiliated with the rights holders.

License: [MIT](LICENSE) (tools and documentation only).

---

## Deutsch (Kurzfassung)

Werkzeuge, um Xenosaga Episode III (PS2, US-Fassung) in die eigene Sprache zu übersetzen und gepatchte
Disc-Images für PCSX2 zu bauen. **Keine Spieldaten enthalten** – du brauchst deine eigenen Original-Discs.

```bash
python -I tools/vorbereiten.py --sprache fr     # Texte exportieren, Vorlagen anlegen
# Spalte text_fr in text/fr/*.csv und Felder "fr" in text/fr/grafik_*.json ausfüllen
python -I tools/build.py --sprache fr           # Images + Patches bauen
```

Exportierte Texte, Übersetzungen und Patches enthalten geschützten Spieltext: nur privat verwenden, nicht öffentlich hochladen.
Ausführliche Doku (englisch) in `docs/`.
