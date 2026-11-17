# Build-Pipeline: von der Übersetzung zum spielbaren Image

Ein Befehl macht aus den deutschen Übersetzungstabellen beide Disc-Images und die xdelta-Patches:

```bash
python -I tools/build.py
```

| Option | Wirkung |
|---|---|
| `--disc 1` | nur Disc 1 (mehrfach angebbar) |
| `--nur-dateien` | nur Tabellen → Spieldateien + Prüfbericht (wenige Sekunden, ohne Images) |
| `--ohne-pruefsumme` | SHA1 der Original-Images nicht prüfen (spart ca. 1 Minute) |
| `--de <ordner>` | anderer Ordner mit Tabellen (z. B. Probeläufe) |

Dauer für beide Discs inkl. Prüfungen und Patches: ca. 3–4 Minuten.

## Arbeitsablauf Übersetzung

1. Englische Texte exportieren (ist schon geschehen, liegt in `text/en/`):

   | Tabelle | Inhalt | Schlüsselspalten |
   |---|---|---|
   | `skripte.csv` | Dialoge, Auswahlmenüs, Meldungen | datei, idx, kategorie |
   | `menue_txd.csv` | Menüs, Items, Systemmeldungen, Zusammenfassungen | datei, idx, kategorie |
   | `datenbank.csv` | Datenbank (wirkt auf DBC.bin **und** DBC2.bin) | eintrag, feld |
   | `menue_bin.csv` | Kampf-/Datenbank-Überschriften, Bonusmenü, Filmauswahl | datei, block, idx |
   | `minispiel_rueckblick.csv` | Minispiel, Episode-I/II-Zusammenfassungen | datei, schluessel |
   | `untertitel.csv` | Untertitel beider Discs | datei, zeile |
   | `kampfdaten.csv` | Äther, Techs, Gegenstände, Ausrüstung, Statuseffekte, Kampfbefehle (`bat/us/batdat.bin`) | datei, idx |

2. Tabelle nach `text/de/` kopieren und die Spalte **`text_de`** ausfüllen. Leere Zellen bleiben englisch. Die anderen Spalten nicht ändern.
3. Ein Text muss **nur einmal** übersetzt werden: Der **Übersetzungsspeicher** füllt alle Zeilen mit identischem `text_en` in derselben Tabelle automatisch. Beispiel: „Board the E.S.?“ steht in 647 Skripten.
4. `python -I tools/build.py` ausführen.
5. `build/pruefbericht.md` lesen: Fortschritt, Fehler, Warnungen.
6. `build/Xenosaga3_DE_Disc1.iso` in PCSX2 testen.

**Git / Veröffentlichung:** Die Tabellen in `text/en/` und `text/<sprache>/` enthalten den Spieltext (englisches Original bzw. deine Übersetzung), die Patches in `patch/` ebenfalls. Beides ist urheberrechtlich geschützt bzw. davon abgeleitet – **nicht öffentlich hochladen**. Die `.gitignore` dieses Repos schließt beides aus.

## Regeln für `text_de`

- **Steuerzeichen exakt übernehmen:** `<f>`, `<wNN>`, `<lN>`, `<col…>`, `$…;`, `%s`, `%d`, `\n` (Zeilenumbruch, Backslash + n). Der Prüfbericht warnt, wenn sie abweichen.
- `[Sprecher]` am Anfang darf übersetzt werden, z. B. `[Professor]` → `[Professor]`. Für Namen gilt das Glossar.
- `<kStichwort>` verweist auf die Datenbank. Den Begriff genauso übersetzen wie den Datenbanktitel.
- Erlaubt sind alle Windows-1252-Zeichen (ä ö ü ß „ “ – …) und die Spielsymbole ○ □ △ × ↑ → Σ.
  Nicht erlaubt sind `¡ ¢ £ ¤ ¦` und das weiche Trennzeichen. Das Tool meldet sie als Fehler (Grund: `docs/formats/font.md`).
- Zeilenlänge: Der Prüfbericht warnt, wenn eine Zeile länger ist als die längste englische Zeile derselben Art oder wenn ein Text mehr Zeilen hat als das Original.

## Was die Pipeline intern macht

1. **Voraussetzungen:** Original-Images in `ISO/` mit bekannter SHA1. Fehlende Textdateien werden mit `x3extract.py` entpackt.
2. **Übersetzungsspeicher** → `build/de/csv/`.
3. **Import** mit den Format-Tools: `sbtext`, `txdtext`, `dbctext`, `bintext`, `mestext`, `subtitle_import` → `build/de/x3/` (gemeinsames Archiv) und `build/de/untertitel/discN/`.
4. **Prüfbericht** → `build/pruefbericht.md`.
5. **Images:** `x3rebuild.py` je Disc (gemeinsame Dateien + Untertitel der Disc), danach `verify_rebuild.py`. Jede Archivdatei wird gegen ihren Sollinhalt geprüft.
6. **Patches:** `xdelta3 -e -9` → `patch/Xenosaga3_DE_DiscN.xdelta`. Gegenprobe: Patch auf das Original anwenden, das Ergebnis muss SHA1-gleich zum gebauten Image sein.
   Probeläufe (`--de` ≠ `text/de`) schreiben nach `build/patch_probe/`.
   xdelta3 3.1.0 liegt in `C:\tools\xdelta3\xdelta3.exe` (offizielles Release `jmacd/xdelta-gpl`).

## Patch anwenden (für Spieler)

```bash
xdelta3 -d -s "Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 1).iso" Xenosaga3_DE_Disc1.xdelta Xenosaga3_DE_Disc1.iso
```

Voraussetzung ist ein Original-Image mit der SHA1 aus `docs/iso-pruefsummen.md`.

## Probelauf (2026-11-14)

Tabellen in `build/probe_de/` mit 43 echten Übersetzungen (Menü, Datenbank-Kategorien, E.S.-Abfrage, Speicherpunkt, erste Untertitel).
- Der Übersetzungsspeicher füllte daraus 1 961 weitere Zeilen.
- 658 Spieldateien wurden gebaut, beide Images geprüft (0 Fehler).
- Patches: 81/82 KiB, Gegenprobe ok.
- 1 Warnung: „Organisationen“ (14 Zeichen) ist länger als jeder englische Kategoriename (max. 13).
