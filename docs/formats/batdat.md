# Kampfdaten `bat/us/batdat.bin`

Enthält die Namen und Beschreibungen von Äthern, Techs, Spezialangriffen, Gegenständen, Statuseffekten, Fähigkeiten, Ausrüstung, E.S.-Teilen, Kampfbefehlen und Sondergegenständen. Die Datei liegt im gemeinsamen Archiv (beide Discs), Größe 125 764 Byte.

Werkzeug: `tools/batdattext.py` (export / import / test), Tabelle `text/en/kampfdaten.csv` → `text/de/kampfdaten.csv`, in `tools/build.py` eingebunden.

## Aufbau

| Offset | Inhalt |
|---|---|
| `0x00` | u32 Anzahl Abschnitte (28) |
| `0x04` | u32 Dateigröße |
| `0x08` | u32 Startoffset je Abschnitt (der erste ist `0x78`). Abschnitte liegen lückenlos hintereinander, Länge immer ein Vielfaches von 4. |

Jeder Abschnitt mit Text: **Datensätze fester Länge**, danach ein **Textbereich** mit NUL-getrennten Strings (cp1252 wie überall, `\n` als zwei Zeichen Backslash + n, Steuerfolgen `$col…;`, `$zoomA,B;`). Zeiger sind **u16-Offsets relativ zum Abschnittsanfang**. Der erste Zeiger des ersten Datensatzes zeigt auf den Textanfang. Mehrere Datensätze dürfen denselben String nutzen (Abschnitt 5: 612 Zeiger auf 357 Strings).

| Abschnitt | Satzlänge | Zeigerfelder | Inhalt |
|---|---|---|---|
| 0 | – | – | Werte der Figuren, Namen (Shion … E.S. Reuben), nicht exportiert |
| 4 | 32 | 0 | Techs der Figuren + Werte-Beschreibungen |
| 5 | 32 | 0 | Angriffe von Gegnern und E.S. |
| 6 | 32 | 0 Name, 2 Text | Äther |
| 7 | 40 | 0, 2 | Techs |
| 8 | 40 | 0, 2 | Spezialangriffe |
| 9 | 40 | 0, 2 | Gegenstände |
| 10 | 8 | 0, 2 | Statusveränderungen |
| 11 | 8 | 0, 2 | Statuseffekte (Anima/Status-Unterstützung) |
| 12 | 20 | 0, 2 | Fähigkeiten (Skills) |
| 13 | 20 | 0, 2 | Accessoires |
| 14 | 28 | 0, 2 | Waffen (Figuren und E.S.) |
| 15 | 24 | 0, 2 | Rüstungen |
| 16–19 | 20/20/20/24 | 0, 2 | E.S.-Rahmen, Generatoren, CPU, Disks |
| 23 | 2 | 0 | Zeigerliste: Kampfbefehle und Kampfmeldungen (Name/Erklärung im Wechsel) |
| 27 | 8 | 0, 2 | Sondergegenstände |
| 1–3, 20–22, 24–26 | – | – | ohne Text (Gegnerwerte, Tabellen) |

Gefunden durch Prüfung aller Satzlängen: Für die genannten Abschnitte zeigt das Feld in **jedem** Datensatz auf einen Stringanfang, und jeder String wird referenziert. Das Tool prüft beides beim Laden und bricht sonst ab.

## Import

Neue Strings werden in Originalreihenfolge in den Textbereich geschrieben, die Zeiger neu gesetzt, der Abschnitt auf 4 Byte aufgefüllt; Kopf und Startoffsets werden neu berechnet. Grenze: ein Abschnitt darf 64 KiB nicht überschreiten (u16-Zeiger), der größte hat 24 KiB.

`python -I tools/batdattext.py test extracted/disc1/files/bat/us/batdat.bin`: Roundtrip byte-identisch, Verlängerung aller Strings um 7 Zeichen wird korrekt zurückgelesen.
Deutsche Fassung 2026-11-15: 126 708 Byte (+944).

## Test in PCSX2

2026-11-15: Gewachsene Datei (+944 Byte) läuft. Kampf startet, Befehlsleiste und Erklärungen deutsch, Item-/Äther-Beschreibungen korrekt.

## Offen

- „COMMAND“, „BOOST“, „PLAYER/ENEMY“, „ACT“ im Kampf sind Grafiken (Texturen), kein Text in `batdat.bin`. Gehören zu Phase 5 (Grafiken mit Text).
