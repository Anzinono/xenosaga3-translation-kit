# ISO-Neuaufbau (Dateien dürfen wachsen)

Tools: `tools/x3rebuild.py` (bauen), `tools/verify_rebuild.py` (prüfen).

## Wie das Spiel die Archive liest

`FUN_00188148` (SLUS_213.89) sucht einen Pfad in den drei geladenen Katalogen (`x3.00`, `x3.10`, `x3.20`, Deskriptoren bei `0x89B5E0/0x89B600/0x89B640`). Lesestart ist **Basis der Kette + Sektor aus dem Katalog**. Die Basis ist die LBA des Katalogs, über das Dateisystem gefunden (`\X3.00;1`).
→ Katalog und Datenteile (`X3.00`, `X3.01`, `X3.02` …) müssen **lückenlos hintereinander** auf der Disc liegen. Die Aufteilung in 1-GiB-Dateien ist nur eine Grenze des Dateisystems.

## Physischer Aufbau Disc 1 (Original)

| LBA | Inhalt |
|---|---|
| 16–20 | ISO-9660-PVD, Terminator, UDF-Erkennung (`BEA01`, `NSR02`, `TEA01`) |
| 32–37, 48–53 | UDF-Volume-Deskriptoren (Haupt- und Reservekopie) |
| 64 | UDF Logical Volume Integrity Descriptor |
| 256 | UDF-Anker |
| 257–262 | ISO-Pfadtabellen und Verzeichnisse (Root 261, IOP 262) |
| 263–290 | UDF-Partition beginnt (263), Dateieinträge 267–290 |
| 291–3113 | SYSTEM.CNF, SLUS, OVLs, IOP-Module |
| 3114–807413 | **Kette 1:** X3.00 (55) + X3.01 + X3.02 |
| 807414–1905668 | **Kette 2:** X3.10 (26) + X3.11 + X3.12 + X3.13 |
| 1905669–1915918 | 10 251 leere Füllsektoren |
| 1915919 | UDF-Anker (Ende) |

## Verfahren

1. Ersatzdatei passt in ihren alten Sektorplatz → wird dort geschrieben.
2. Sonst → ans Ende ihrer Kette gehängt (hinter `X3.02` bzw. `X3.13`/`X3.23`). Der letzte Datenteil wird größer, alle späteren Sektoren rücken nach hinten.
3. Angepasst werden:
   - Katalog: Sektor (u24) und Größe.
   - ISO 9660: Lage und Größe in den Verzeichniseinträgen (LE und BE), Volume-Größe im PVD.
   - UDF: Dateieinträge (Allocation Descriptor, Informationslänge, belegte Blöcke), Partitionslänge (Haupt- und Reservekopie), Größentabelle im LVID, Ortsangabe des End-Ankers, jeweils mit neu berechneter Tag-Prüfsumme und CRC-CCITT.

## Prüfungen

- **Neuaufbau ohne Änderungen → byte-identisch zum Original.** Das bestätigt auch die UDF-CRC-Berechnung.
- `verify_rebuild.py`: ISO-9660 und UDF stimmen für jede Datei überein; Volume-Größe, Partition und End-Anker passen. Alle Dateien außerhalb der Archive sind unverändert. **Jede** Archivdatei (13 516 auf Disc 1) entspricht der Ersatzdatei bzw. dem Original.
- Testpatch 2: 20 Dateien verschoben, darunter `DBC.bin` mit +24 %. Es wurden 831 Sektoren eingefügt, die Prüfung ergab 0 Fehler.

## Hinweise

- Disc 2 hat dieselbe Struktur (`X3.20`–`X3.23`). Das gemeinsame Archiv `X3.00`–`X3.02` muss auf beiden Discs gleich gepatcht werden.
- Größe: Disc 2 ist 4,516 GB groß, eine einschichtige DVD fasst 4,700 GB → rund 184 MB Reserve. Textänderungen brauchen nur wenige MB.
- Noch nicht im Spiel getestet: eine Datei, die innerhalb von **Kette 2** (Untertitel) ans Ende verschoben wird. Verfahren und Code sind identisch zu Kette 1.
