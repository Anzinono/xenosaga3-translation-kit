# ISO-Layout (US, SLUS-213.89 / SLUS-214.17)

## Wurzelverzeichnis

| Datei | Disc 1 | Disc 2 | Bemerkung |
|---|---|---|---|
| `SYSTEM.CNF` | ✓ | ✓ | Bootet `SLUS_213.89` bzw. `SLUS_214.17`, NTSC, VER 1.00 |
| `SLUS_213.89` / `SLUS_214.17` | 4 513 232 B | 4 513 232 B | Hauptprogramm, **byte-identisch** auf beiden Discs |
| `OV01.OVL`, `OV02.OVL`, `OV04.OVL` | ✓ | ✓ | Code-Overlays, identisch |
| `X3.00` + `X3.01`, `X3.02` | ✓ | ✓ | gemeinsames Archiv, identisch |
| `X3.10` + `X3.11`–`X3.13` | ✓ | – | Disc-1-Archiv |
| `X3.20` + `X3.21`–`X3.23` | – | ✓ | Disc-2-Archiv |
| `IOP\*.IRX`, `IOPRP300.IMG` | ✓ | ✓ | IOP-Module (CRI ADX, Sound, Memory Card, Pad) |

Archivformat: [formats/x3-archiv.md](formats/x3-archiv.md).

## Inhalt der Archive (Auszug, nach Größe)

**X3.00 (beide Discs), 9 867 Dateien:** `snd\adx` (Musik/Stimmen, 441 MiB), `mdl\map` (Karten), `mdl\chr` (Figuren), `pac\bat` (Kampf), `ef\*` (Effekte), `kao` (Gesichter, `.xtx`), `jpg` (Datenbankbilder), `mnu\*` (Menüs), `cf\us` (Skripte), `bat\us` (Kampfdialoge), `mg1` (Minispiel).

**X3.10 (Disc 1), 3 649 Dateien / X3.20 (Disc 2), 1 709 Dateien:** `mov` (`.sfd`-Filme, 1,6 bzw. 2,4 GiB), `evt` (Echtzeit-Zwischensequenzen `.xep`/`.xev`), `snd\adx` (Sprachausgabe), `evt\us` und `mov\us` (Untertitel).

## Übersetzungsrelevante Dateien (Disc 1 geprüft)

| Pfad | Anzahl | Format (erster Eindruck) |
|---|---|---|
| `\cf\us\*.sb` | 647 | Kompiliertes Skript, Header `SB  `, 6 Abschnitte. Dialoge als ASCII im Datenabschnitt, Tags: `[Shion]` Sprecher, `<f>` Textbox-Ende, `\n` Zeilenumbruch, `<…>` Tasten/Namen |
| `\bat\us\*.sb` | 69 | wie oben, Kampfdialoge (`MIK_B01.sb` …) |
| `\evt\us\*.txt`, `\mov\us\*.txt` | 36 + 111 (Disc 1) | **Klartext-Untertitel** mit Zeitstempeln und Steuerbefehlen (`$col…`, `$ruby…`) |
| `\mnu\us\menutext.txd` | 1 | Zeigertabelle (907 Einträge) + ASCII-Strings, `printf`-Platzhalter (`%s`, `%d`) |
| `\mnu\us\DBC.bin`, `DBC2.bin` | 2 | Datenbank (Einträge mit langen Texten, `<Name>`-Verweise) |
| `\mnu\us\njDataText.bin`, `njBtlText.bin`, `njDBcommon.bin`, `MVtext.bin`, `SegmentFileData.bin` | 5 | Menü-/Kampf-/Bonustexte |
| `\mnu\us\synopsis.txd`, `devchk.txd`, `discchg.txd` | 3 | Zusammenfassungen, Systemmeldungen |
| `\mnu\us\font0.bin`, `font1.bin` | 2 | je 494 592 B, Rohbitmap ohne Header → Phase 2 |
| `\mnu\pse\*.mes` | 6 | Texte der Episoden-Rückblicke |
| `\mnu\us\*.xtx`, `title1.png`, `syno.png` | – | Grafiken mit Text (Titel, Fenster) |

Texte sind ASCII. Für Umlaute braucht es eigene Zeichen im Font und eine angepasste Zeichentabelle (Phase 2/5).
