# Datenbank (`\mnu\us\DBC.bin`, `DBC2.bin`)

Tool: `tools/dbctext.py`. Roundtrip für beide Dateien identisch, verlängerte Texte werden korrekt gelesen.

## Container

```
u32 Anzahl Blöcke
Anzahl × (u32 Offset, u32 Größe)
Füllung 0x90 bis zur 16-Byte-Grenze
Blöcke, jeweils auf 16 Byte ausgerichtet (Füllung 0x90), nach dem letzten Block keine Füllung
```

`DBC.bin`: 10 Blöcke, einer pro Kategorie (0 Characters … 9). `DBC2.bin`: 27 Blöcke mit **denselben Texten**, nach Anfangsbuchstaben gruppiert. Das ist der **alphabetische Index**, die Gruppenüberschriften sind Einzelbuchstaben (`P`, `G`, `O`). Die Blöcke 25/26 sind byte-identisch mit DBC-Block 8/9.

## Block (`DBF`)

```
n Datensätze à 0xD0 Byte (50 × u32 + 8 Byte 0x90), der letzte nur 0xC8 Byte
nullterminierte Strings (Windows-1252), lückenlos
```

| Feld (u32) | Inhalt |
|---|---|
| 0 | `"DBF\0"` |
| 1 | Eintragsnummer |
| 2 | Kategorie |
| **3** | → Kategoriename („Characters“) |
| 4, 6 | Nummern |
| **5** | → Titel („Ernest Luis“) |
| 7, 8, 16, 17 | meist `FFFFFFFF` |
| **9** | → Kurzbeschreibung (Liste) |
| **10** | → Langtext (bis 6 852 Zeichen / 149 Zeilen, scrollbar) |
| **11–14** | → Zusatztexte, meist `"-1"` |
| 15 | `0x200` (Flags?) |
| 18–49 | Zahlen, vermutlich Verknüpfungen/Bilder, sonst `FFFFFFFF` |

Statistisch geprüft an allen 906 Datensätzen beider Dateien: **Genau** die Felder 3, 5, 9–14 sind String-Offsets (relativ zum Blockanfang), kein anderes Feld zeigt in den Textbereich, und jeder String wird referenziert.

## Texte

`python -I tools/dbctext.py export extracted/disc1/files/mnu/us/DBC.bin --out text/en/datenbank.csv`
→ **1 454 eindeutige Texte, ≈ 63 800 Wörter** (453 Titel, 453 Langtexte, 414 Kurzbeschreibungen, Rest Zusatztexte/Kategorien).

Import (wendet die Übersetzung über den englischen Text auf **beide** Dateien an):
`python -I tools/dbctext.py import …/DBC.bin …/DBC2.bin --csv text/de/datenbank.csv --out build/mnu`

Tags: `<colRRGGBB>` Farbe, `<Name>` Verweis auf einen anderen Eintrag (z. B. `<Vector>`, `<Zohar>`), `\n` Zeilenumbruch.

## Offen / Risiken

- **Verweise `<Name>`:** Vermutlich muss der Text exakt einem (übersetzten) Titel entsprechen → Glossar, im Spiel prüfen.
- **Alphabetischer Index (DBC2):** Mit deutschen Titeln stimmt die Sortierung nach Anfangsbuchstaben nicht mehr. Für eine saubere Lösung müssten die Datensätze neu auf die Buchstabenblöcke verteilt werden. Erst klären, ob das Spiel die Gruppierung aus der Datei nimmt.
- **Puffergröße:** Im Spiel getestet (Testpatch 2): `DBC.bin` +24 % (511 → 634 KB) wird geladen, die Langtexte werden bis zum Ende angezeigt. Wo die Obergrenze liegt, ist nicht bekannt. Deutsche Texte werden voraussichtlich 15–30 % länger, das liegt im getesteten Bereich.
- **Gesperrte Kategorien** zeigen ihren Namen aus `njDBcommon.bin`, nicht aus `DBC.bin` → beide gleich übersetzen.
