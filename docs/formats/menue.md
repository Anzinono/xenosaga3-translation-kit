# Menütexte und Datenbank (`\mnu\us\`)

## .txd – Texttabellen (Tool: `tools/txdtext.py`)

| Datei | Variante | Strings | Inhalt |
|---|---|---|---|
| `menutext.txd` | A | 907 | Menüs, Items, Meldungen (`Acquired %s x %d!`) |
| `synopsis.txd` | B | 166 | Zusammenfassungen der Vorgeschichte, mit `$`-Befehlen für Layout |
| `devchk.txd` | B | 20 | Memory Card, Progressive Scan, Controller |
| `discchg.txd` | B | 13 | Discwechsel |

- **Variante A:** `u32 Anzahl`, `Anzahl × u32` absolute Offsets, dann die Strings.
- **Variante B:** `Anzahl × u32` absolute Offsets, wobei der erste Offset der Tabellenlänge entspricht. Danach die Strings.

Mehrfach verwendete Offsets bleiben beim Neubau zusammengefasst. Der Roundtrip ist für alle 4 Dateien identisch, verlängerte Texte werden korrekt gelesen.
Steuerzeichen im Text: `\31\3` (Präfix), `\n`, `\button0`, `\m` (Platzhalter), `$ax…;$ay…;$col…;` (Layout). Diese bleiben unverändert.
Export: `text/en/menue_txd.csv` (1 106 Strings, Kategorien `text`/`befehl`/`leer`).

## .bin-Container (DBC.bin, DBC2.bin, njDataText.bin, MVtext.bin, SegmentFileData.bin, njBtlText.bin, njDBcommon.bin)

```
u32 Anzahl Blöcke
Anzahl × (u32 Offset, u32 Größe)
Füllung 0x90 bis zur 16-Byte-Grenze
Blöcke (jeweils auf 16 Byte ausgerichtet, Füllung 0x90)
```

| Datei | Blöcke | Text (grob) |
|---|---|---|
| `DBC.bin` | 10 | ≈ 56 000 Wörter (Datenbank) |
| `DBC2.bin` | 27 | ≈ 56 000 Wörter (zweite Fassung der Datenbank; das koreanische Projekt baut beide gemeinsam) |
| `njDataText.bin` | 13 | ≈ 1 250 Wörter (Bonusmenü, Datensätze `TOP`) |
| `MVtext.bin` | 4 | ≈ 450 Wörter (Filmauswahl) |
| `SegmentFileData.bin` | 2 | ≈ 400 Wörter (Segment-Adressen, Datensätze `SEG`) |
| `njBtlText.bin`, `njDBcommon.bin` | 1 | Überschriften |

In den Blöcken stehen Datensätze mit Kennung (`DBF\0`, `SEG\0`, `TOP\0`), String-Offsets relativ zum Block und Zahlen.
- `DBC.bin`/`DBC2.bin`: siehe [datenbank.md](datenbank.md) (eigenes Tool `dbctext.py`).
- Übrige Dateien: generisches Tool **`tools/bintext.py`**. Jeder Block ist eine von zwei Bauarten:
  - **Tabelle:** u32-Offsets (relativ zum Block), der erste Offset entspricht der Tabellenlänge, danach die Strings. Betrifft `njBtlText`, `njDBcommon`, den letzten Block von `SegmentFileData`/`MVtext`/`njDataText`.
  - **Datensätze:** Kennung (`SEG` 48 B, `MVD` 48 B, `TOP` 32 B, `CHA` 16 B, `EVE` 32 B), `0x90`-Füllung, der letzte Satz ohne Füllung, danach die Strings. Ein Feld gilt als Zeiger, wenn es in **jedem** Satz auf einen Stringanfang oder auf `0`/`FFFFFFFF` (kein String, z. B. `EVE` ohne Kapitelüberschrift) zeigt. Zeigt ein Feld nur teilweise auf Strings, bricht das Tool ab.
  - Jeder String muss referenziert sein, sonst Abbruch.
- Roundtrip identisch für `njBtlText` (51 Strings), `njDBcommon` (48), `SegmentFileData` (88), `MVtext` (280), `njDataText` (443). Zur Kontrolle werden auch `DBC`/`DBC2` korrekt erkannt.
- `njDBcommon.bin` enthält u. a. die Datenbank-Kategorienamen für **gesperrte** Kategorien → gleich übersetzen wie in `DBC.bin`.

## Minispiel und Episoden-Rückblicke (Tool: `tools/mestext.py`)

**`\mg1\us\Message.Dat`** (Minispiel):
```
0x0000  933 × u32 Offset (relativ zu 0x2800)
0x0E94  bis 0x2800 andere Daten (Grafik/Attribute?) – bleiben unverändert
0x2800  nullterminierte Strings bis Dateiende
```
Roundtrip identisch. 931 Texte exportiert, 2 japanische Reste ausgelassen. Viele Texte enthalten Tastensymbole (`<○>`, `<□>`, `△`, `×`, `↑`).

**`\mnu\pse\us\*.mes`**: Textdateien (CRLF) mit Abschnitten `#MESSAGE n`.
- **Englisch:** nur `EP1.mes` (29 Abschnitte) und `EP2.mes` (40), vermutlich die Zusammenfassungen von Episode I/II im Bonusmenü.
- **Nur Japanisch:** `AC.mes`, `PP.mes`, `opening.mes`, `test.mes`. Wahrscheinlich in der US-Fassung ungenutzt; „Pied Piper“ steht englisch in `njDataText.bin`/`synopsis.txd`. Im Spiel prüfen.
- Exportiert wird pro Abschnitt der Text mit echten Zeilenumbrüchen in der CSV-Zelle. Leerzeilen und Kopf bleiben erhalten. Roundtrip identisch.
