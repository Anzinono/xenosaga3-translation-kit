# Skripte (.sb) – Dialoge

`\cf\us\*.sb` (647 Kartenskripte) und `\bat\us\*.sb` (69 Kampfskripte), Archiv X3.00. Tool: `tools/sbtext.py`.

## Aufbau

```
0x00  "SB  "   u16 1   u16 1
0x08  6 × u32  Offsets der Abschnitte 1–6
0x20  Füllung bis 0x40
```

| Abschnitt | Beginnt mit | Inhalt |
|---|---|---|
| 1 (ab 0x40) | u32 12 | Bytecode |
| 2 | u32 8, u32 Anzahl | Tabelle (Sprungziele/Daten) |
| **3** | **u32 8, u32 Anzahl** | **Stringtabelle**: Anzahl × u32 Offset (relativ zum Datenbeginn direkt nach der Tabelle), dann nullterminierte Strings lückenlos, Abschnittsende auf 4 Byte aufgefüllt |
| 4 | u32 8, u32 Anzahl | Symbole: Paare (Namens-Offset, Code-Offset), Namen wie `runtime_M_setDoorAttr`; Offsets relativ |
| 5 | u32 8, u32 Anzahl | vermutlich Debug-/Zeileninformationen |
| 6 | u32 1 | Ressourcen (`BGM`, `us\1010`), meist 20 Byte |

Geprüft an allen 715 Dateien: Header, Stringtabelle und Ausrichtung sind überall gleich. Im Inhalt stehen keine absoluten Offsets auf die Abschnitte 4–6. Der Bytecode verweist auf Strings über deren **Nummer**.
→ Texte dürfen beliebig länger oder kürzer werden. Beim Neubau werden nur die Header-Offsets der Abschnitte 4–6 verschoben (`build()` in `sbtext.py`). Das koreanische Projekt macht das ebenso.

**Roundtrip:** `python -I tools/sbtext.py test extracted/disc1/files/cf/us extracted/disc1/files/bat/us` → 715 identisch, 0 Fehler. Bei verlängerten Strings bleiben die Abschnitte dahinter byte-gleich.

## Inhalt der Stringtabellen (90 580 Strings)

| Kategorie | Anzahl | eindeutig | Übersetzen? |
|---|---|---|---|
| `dialog` – beginnt mit `[Sprecher]` oder enthält `<f>/<w>/<l>` | 8 935 | 7 231 (≈ 76 000 Wörter) | ja |
| `text` – sonstiger englischer Text (Menüs, Auswahl, Systemmeldungen) | 2 196 | 450 | ja |
| `wort` – Einzelwörter | 1 061 | 243 | **prüfen**: Datenbank-Stichwörter (`Durandal`, `Dämmerung`) oder interne Namen (`getitem`, `kowaremono`) |
| `bezeichner` – `s082000_02_1mom`, `B01`, `CHRV_EVE0100` | 7 520 | – | nein |
| `technisch` – `--- main ---`, `*****`, `  px =` | 2 448 | – | nein |
| `jp` – japanische Debug-Texte (Shift-JIS/EUC-JP) | 68 420 | – | nein, **nicht** als cp1252 umkodieren |

Viele Strings wiederholen sich (z. B. „Board the E.S.?<f>“ in allen 647 Kartenskripten). Ein Übersetzungsspeicher nach `text_en` spart viel Arbeit.

## Tags im Text

| Tag | Bedeutung (vorläufig) |
|---|---|
| `[Name]` am Anfang | Sprecher, wird als Namensfeld angezeigt |
| `<f>` | Textbox-Ende / auf Tastendruck warten |
| `<wNN>` | Pause von NN Frames |
| `<lN>` | Zeilen-/Layoutsteuerung (z. B. `<l2>`) |
| `<kText>` | Stichwort-Verknüpfung zur Datenbank (z. B. `<kMöbius Hotel>`). Vermutlich muss der Text identisch zum Datenbank-Stichwort sein → Glossar. |
| `<col…>`, `$col…;` | Farbe |
| `\n` | Zeilenumbruch (zwei Zeichen) |

## Export / Import

```bash
python -I tools/sbtext.py export extracted/disc1/files/cf/us extracted/disc1/files/bat/us --out text/en/skripte.csv
python -I tools/sbtext.py import extracted/disc1/files/cf/us extracted/disc1/files/bat/us --csv text/de/skripte.csv --out build/sb
```

Der Import prüft jeden deutschen Text: Er muss in Windows-1252 darstellbar sein und darf keine verbotenen Bytes `A1–A4/A6/AD` enthalten (`docs/formats/font.md`).

## Offen

- Bedeutung der Abschnitte 2 und 5 sowie der Opcode, der Dialogtexte ausgibt. Damit ließe sich „wort“ sicher zuordnen.
- Maximale Breite einer Textbox in Pixeln (für die Längenprüfung).
- Ob die Tags `<k…>` mit Datenbank-Stichwörtern verglichen werden.
- **Test im Spiel** mit verlängertem deutschem Text.
