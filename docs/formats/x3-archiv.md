# X3-Archive (Kataloge X3.00 / X3.10 / X3.20)

Selbst hergeleitet aus Hexdumps, geprüft gegen die Lybac-Listen in
[Xenosaga3PythonExtractor/lba](https://github.com/LinuxJessi/Xenosaga3PythonExtractor/tree/main/lba)
(alle Stichproben byte-genau identisch, inkl. Index-Spalte). Implementierung: `tools/x3toc.py`.

## Ketten

| Katalog | Datenteile | Disc | Inhalt |
|---|---|---|---|
| `X3.00` (55 Sektoren) | `X3.01` + `X3.02` | beide (identisch) | Menüs, Skripte, Modelle, Effekte, Sound, Gesichter |
| `X3.10` (26 Sektoren) | `X3.11` + `X3.12` + `X3.13` | 1 | Zwischensequenzen, Filme, Sprachausgabe |
| `X3.20` (13 Sektoren) | `X3.21` + `X3.22` + `X3.23` | 2 | Zwischensequenzen, Filme, Sprachausgabe |

Die Datenteile bilden je einen zusammenhängenden Adressraum (X3.x1, dann X3.x2, …).
Der Katalog zählt seine eigenen Sektoren mit:
`Offset in der Kette = (Sektor − Katalogsektoren) × 2048`.

## Katalogformat

```
Byte 0      Katalogsektoren (u8)
ab Byte 1   Einträge bis zum ersten 00-Byte, danach Füllung
            ("MONOLITHSOFT Xenosaga Episode.2" wiederholt)
```

**Verzeichnis** – erstes Byte hat Bit 7 gesetzt:

```
[0x80 | reclen] [up] [ctrl] [Namensdaten]       reclen = Gesamtlänge des Eintrags
```
- `up`: so viele Ebenen zuerst nach oben gehen.
- Der Name wird gegen den vorherigen Namen **auf derselben Ebene** komprimiert (siehe ctrl).

**Datei:**

```
[reclen] [ctrl] [Namensdaten] [Sektor u24 LE] [Größe u32 LE]
```

**Namenskompression (ctrl):**
- `ctrl == 0`: Namensdaten = vollständiger Name (mit 00 am Ende).
- sonst: `start = len(alter Name) − (ctrl >> 4) − 1`.
  - Enden die Namensdaten auf `00`: `neu = alt[:start] + daten`, der Rest wird abgeschnitten.
  - sonst: Die Daten überschreiben `alt` ab `start`, die Zeichen danach bleiben stehen.
- Das untere Nibble von ctrl entspricht der Datenlänge (redundant, wird nicht benötigt).

Beispiel: `s000100.xep` → Eintrag `03 61 "3"` → start = 11 − 6 − 1 = 4 → `s000300.xep`.

Die „INDEX“-Spalte der Lybac-Listen ist die Byte-Position des Sektorfelds im Katalog.
Das ist nützlich für den späteren Repacker: Dort werden Sektor und Größe beim Neuschreiben angepasst.

## Prüfung (`tools/x3stats.py`)

| Katalog | Dateien | belegt / Kette | außerhalb | Überlappungen | doppelte Pfade |
|---|---|---|---|---|---|
| X3.00 | 9 867 | 1 559 / 1 571 MiB | 0 | 0 | 0 |
| X3.10 | 3 649 | 2 141 / 2 145 MiB | 0 | 0 | 0 |
| X3.20 | 1 709 | 2 708 / 2 710 MiB | 0 | 0 | 0 |

## Für den Repacker relevant (offen)

- Ausrichtung: Dateien beginnen auf Sektorgrenzen (2048 Byte), teils mit größeren Lücken. Ist mehr Platz nötig, kann eine Datei verschoben oder ans Kettenende gehängt werden. Dann müssen nur Sektor und Größe im Katalog angepasst werden; der Katalog selbst ändert seine Länge nicht.
- Ob das Spiel die Katalogsektorzahl (Byte 0) oder feste Größen im ELF erwartet, ist noch zu prüfen. Relevant wird das nur, wenn der Katalog wächst.
