# Font und Zeichenkodierung

**Ergebnis: Umlaute und ß funktionieren ohne Font-Änderung.** Texte werden in Windows-1252 kodiert. Die US-Version macht das schon selbst: „Möbius Hotel“, „Dämmerung“, „Floßhilde“ (`cf\us\1220.sb`, `1230.sb`, `1300.sb`).

## Dateien

`\mnu\us\font0.bin` und `font1.bin`, je 494 592 Byte (0x78C00). Die beiden Dateien unterscheiden sich, haben aber dieselbe Breitentabelle.
Export: `python -I tools/xsfont.py <font.bin> --out <ordner>` → `ebene0-3.png`, `breiten.csv`.

| Bereich | Inhalt |
|---|---|
| `0x00000–0x77FFF` | 1 024 Glyphen × 20 × 24 Pixel, 1 Byte pro Pixel. Jedes Byte enthält **4 Ebenen à 2 Bit** (Ebene n = Bits 2n…2n+1, Graustufe 0–3). Insgesamt also 4 096 Glyphen. |
| `0x78000–0x783FF` | Breitentabelle: 512 × (links, rechts) in Pixeln für die Glyphen 0–511 von Ebene 0. Breite = rechts − links + 1 (`FUN_00185770`). |
| `0x78400–0x78BFF` | 2 KiB Zusatzdaten, 4-Bit-Werte, werden über eine Tabelle expandiert und als eigene Textur hochgeladen (`FUN_00181fa0`). Vermutlich Tasten-Icons. Noch offen. |

Ebene 0: Symbole und Satzzeichen in JIS-Reihenfolge, Ziffern, A–Z, a–z, ab Glyphe 256 **Windows-1252 0x80–0xFF**, danach Griechisch, Kyrillisch, Rahmenlinien, ①–⑳, römische Zahlen. Ab Glyphe 576 folgt eine zweite, teils mit Platzhaltern gefüllte Kopie.
Ebenen 1–3: japanische Kanji (Überbleibsel der JP-Fassung).

## Zeichenkodierung im Text-Renderer (`FUN_00184b30`, SLUS_213.89)

Analysiert mit Ghidra. **Wichtig:** Das Projekt braucht den gp-Wert `0x5571F0` (`re/scripts/SetGp.java`, siehe `docs/werkzeuge.md`).

| Byte(s) | Bedeutung |
|---|---|
| `0x00` | Ende |
| `0x01–0x1F` | Steuercodes mit Parametern (Position, Farbe `0x0C`, Zahlen `0x11`, Unterstring `0x16`, Callback `0x17` …). Bei der Reinsertion unverändert lassen. |
| `0x24` `$` | Sonderbehandlung (`FUN_00184090`), vermutlich Variablen/Befehle |
| `0x20–0x7F` | ASCII |
| `0x80–0xFF` + nächstes Byte | Nur wenn `FUN_00181e48(b1, b2)` = 1: 2-Byte-EUC-Zeichen. Das gilt nur für bestimmte Paare mit erstem Byte `A1`, `A2`, `A3`, `A4`, `A6`, `AD` (z. B. `A6 B2` griechisch, `AD B5` eingekreiste Zahl). |
| `0x80–0xFF` sonst | **Einzelbyte → Glyphe `Byte + 0x80`** = Windows-1252-Zeichen |

### Umsetzung in den Tools

`tools/sbtext.py` enthält `game_pair_ok()` (Nachbau von `FUN_00181e48`), `decode_game()` und `encode_de()`, die von allen Text-Tools genutzt werden:
- **Export:** Gültige 2-Byte-Paare erscheinen als echtes Zeichen (EUC-JP), z. B. `○ □ △ × ↑ → Σ`. Alles andere wird als Windows-1252 ausgegeben.
- **Import:** Windows-1252. Zeichen außerhalb davon sind nur erlaubt, wenn das Spiel sie als 2-Byte-Paar darstellt. Die Einzelbytes `A1–A4`, `A6` und `AD` werden abgelehnt.
- Als „japanisch“ (nicht exportiert) gilt ein String nur bei Hiragana/Katakana (EUC `A4`/`A5`), Kanji (ab `B0`) oder Shift-JIS. Symbole aus den Zeilen `A1–A3`, `A6` und `AD` zählen nicht dazu. Dadurch wurden in den Skripten 125 echte Dialoge mit Tastensymbolen wiedergefunden (z. B. „Press <○>!“, „Erde Kaiser Σ“).

### Regeln für die deutsche Übersetzung

- Kodierung: **Windows-1252** (cp1252). Erlaubt sind u. a. `ä ö ü Ä Ö Ü ß „ “ ‚ ‘ – — … é`.
- **Nicht verwenden:** die Bytes `A1–A4`, `A6` und `AD` (cp1252: `¡ ¢ £ ¤ ¦` und weiches Trennzeichen). Folgt ihnen ein passendes Byte, liest das Spiel beide als ein japanisches Zeichen. Das Prüfskript für die Übersetzung muss sie ablehnen.
- Die Breiten aller Windows-1252-Glyphen sind gesetzt (ä 9 px, Ö 14 px, ß 9 px …). Die Zeilenlänge muss trotzdem in Pixeln geprüft werden, nicht in Zeichen: `extracted/font0/breiten.csv`.

## Offen

- Andere Textwege (Untertitel `evt\us`, `mov\us`, Kampftexte) eventuell mit eigener Ausgaberoutine; per Test in PCSX2 bestätigen.
- Bedeutung von `font0` vs. `font1` (Parameter von `FUN_00185cb0`) und des Zusatzbereichs `0x78400`.
