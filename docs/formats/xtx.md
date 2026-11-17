# XTX-Texturen und Titelbildschirm

Tools: `tools/xtx.py` (lesen/schreiben), `tools/titelbild.py` (deutscher Titelbildschirm), `tools/render_text.ps1` (Schrift über Windows-GDI+).
Header und Swizzle nach [Xenosaga3PythonExtractor](https://github.com/LinuxJessi/Xenosaga3PythonExtractor) `xtx_decode.py` (MIT, © 2026 Jessi Ray Godsibb). Das Zurückschreiben (Swizzle in Gegenrichtung) ist eigene Arbeit.

## Format

```
0x00 "XTX\0"   0x04 u32 Dateigröße   0x08 u32 Anzahl (1)   0x0C u32 0x10
0x10 u16 Breite W   0x12 u16 Format   0x14 u32 Höhe H   0x20 u32 Datenoffset (0x30)
0x30 W*H*4 Byte "CT32-Fläche", danach ~32 Restbytes
```

- **Format 0x04:** lineares RGBA.
- **Format 0x08:** Die Fläche enthält ein **8-Bit-Indexbild der Größe 2W × 2H** in PS2-Speicheranordnung (PSMT8, „swizzled“). Umrechnung: `swizzle8_offset()` in `xtx.py`, für alle Pixel eindeutig umkehrbar (geprüft). Die 256-Farben-Palette liegt als 16×16-Kachel in derselben Fläche. Wo, steht nicht in der Datei; das Spiel adressiert sie über einen Zeiger im Grafikspeicher.
- **Roundtrip:** `python -I tools/xtx.py test <datei>` → `titleobj.xtx` und `window0.xtx` byte-identisch.

## Titelbildschirm

| Datei | Inhalt | Änderung |
|---|---|---|
| `mnu/us/title1.png` | Logo, „Also sprach Zarathustra“, Copyright-Zeile (normales PNG 512×448 RGBA) | zusätzliche Credit-Zeile **unter** der unveränderten Copyright-Zeile |
| `mnu/us/titleobj.xtx` | Format 0x08, Fläche 72×128 → Bild 144×256: NEW GAME (y 2–15), CONTINUE (21–33), DATA (39–51), DISC 1 (77–86), DISC 2 (95–104), Auswahlbalken (108–142) | die drei Menüwörter ersetzt |

Die Menüschrift nutzt nur die Indizes **1–15**. Ihre Palette liegt in der CT32-Fläche als **16-Farben-Palette, 8×2 Einträge ab Pixel (8, 112)**: überall Farbe `2A2A2A` (wie die Copyright-Zeile), Alpha als Deckkraftskala in **vertauschter Reihenfolge**:

| Index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Alpha | 00 | 11 | 22 | 08 | 19 | 3B | **80** | 5D | 77 | 44 | 33 | 66 | 55 | 4C | 2A | 6E |

Index 6 ist voll deckend und füllt im Original das Innere der Buchstaben. Daneben liegt eine zweite Palette (`89FEE0`, ab Pixel (24, 112)) für den türkisen Auswahlbalken.
`titelbild.py` liest die Schriftpalette aus und wählt je Pixel den Index mit der nächstliegenden Deckkraft. Die erste Version hatte eine lineare Skala 0–15 angenommen; das ergab im Spiel helle Streifen in den Buchstaben (Index 15 ist nur zu 86 % deckend). Deutscher Text wird mit GDI+ gerendert, auf 0–15 abgebildet und auf Höhe und Mitte des Originalworts gesetzt. Ist ein Wort breiter als der alte Bereich, wird es horizontal gestaucht. Die Palette bleibt unverändert.

Texte: `text/de/grafik_titel.json` (Menüwörter, Schrift, Credit-Zeile). `tools/build.py` ruft `titelbild.py` automatisch auf, wenn die Datei existiert. Die erzeugten Grafiken sind Spieldaten und kommen nicht ins Git, nur Werkzeug und Konfiguration.

| Original | Deutsch | Größe |
|---|---|---|
| NEW GAME | NEUES SPIEL | 86×14 px (Arial Narrow **Bold**) |
| CONTINUE | FORTSETZEN | 84×13 px |
| DATA | DATEN | 45×13 px (leicht gestaucht) |
| – | „Deutsche Übersetzung von: Anzinono“ | 173×11 px, Arial Bold, y = 400 (**über** der Copyright-Zeile y = 415), Farbe wie Copyright |

Erste PCSX2-Prüfung (2026-11-15): Die Menüwörter werden vollständig angezeigt, waren aber zu dünn, und die Credit-Zeile war zu klein → auf Fettschrift umgestellt, Credit vergrößert und über die Copyright-Zeile gesetzt (Wunsch des Nutzers).

**Offen:** Im Spiel prüfen, ob das Spiel die Menüwörter mit genau dem alten Rechteck ausschneidet (dann passt alles) und ob die Credit-Zeile am unteren Bildrand vollständig sichtbar ist.
