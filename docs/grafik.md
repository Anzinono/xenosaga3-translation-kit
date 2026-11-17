# Spielgrafiken mit Text (Phase 5, Punkt 4)

**Status (2026-11-16): abgeschlossen.** Titelbildschirm, Ortseinblendungen, Figurenkarten und Datenbankbilder sind übersetzt und in PCSX2 bestätigt; Kampfanzeige, Game Over und A.G.W.S. bleiben auf Wunsch englisch.

Stand 2026-11-16. Gesichtet wurden alle Bildformate von Disc 1 (Disc 2 enthält dieselben Grafiken).

## Werkzeuge

| Tool | Zweck |
|---|---|
| `tools/grafik_inventar.py` | exportiert alle Kandidaten nach `build/grafik/inventar/` (PNG/JPG), schreibt `index.html` (Übersicht), `kontakt.html` (Kontaktbogen) und `inventar.csv` |
| `tools/eftex.py` | Texturen in Effekt-Containern `.esd`/`.esp` lesen/schreiben (`list`, `export`, `test`) |
| `tools/tm2.py` | TIM2-Texturen `.tm2` lesen/schreiben (`export`, `import` für RGBA32, `test`) |
| `tools/pngrgba.py` | PNG lesen ohne Zusatzpakete (Graustufen, RGB, RGBA, Palette) |
| `tools/xtx.py` | XTX 0x08 (siehe `docs/formats/xtx.md`) |

Vorher entpacken (einmalig):

```bash
python -I tools/x3extract.py "ISO/Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 1).iso" --out extracted/disc1/files --filter "\mnu\*" --filter "\jpg\*" --filter "\mg1\us\*" --filter "\mov\us\w09.png" --filter "\ef\esd\us\*" --filter "\ef\esp\us\*" --filter "\ef\map\us\*" --filter "\bat\bat_face\*"
```

```bash
python -I tools/grafik_inventar.py
```

Roundtrips (unverändert lesen → schreiben): `eftex.py test` 67/67 Effekt-Dateien identisch, `tm2.py test` 4/4 identisch, `xtx.py test` für `ctrl`, `itemcap`, `Picture`, `window0–2`, `titleobj` identisch.

## Formate

### Effekt-Container `.esd` / `.esp` (`ef/esd/us`, `ef/map/us`, `ef/esp/us`)

Datensätze an 0x40er-Grenzen, jeweils 0x40-Byte-Kopf, danach Daten:

```
+0x00 u32 Gesamtgröße (Kopf + Daten)   +0x04 u32 unklar (Adresse/Kennung)
+0x08 u16 Typ: 4 = Bild, 3 = Palette   +0x0A u16 Platz
+0x0C u16 Breite  +0x0E u16 Höhe       +0x10 u32 Bits je Pixel (4/8)
+0x14 Name, z. B. "moji.bmp", "5thelsalem-a.bmp", "moji.clt"
```

- Bilder: 4 Bit (unteres Nibble = linkes Pixel) oder 8 Bit, linear (kein Swizzle).
- Paletten: RGBA32, Alpha 0x80 = deckend; Anzahl = 2^Bits (16 oder 256). Zuordnung über den Namensstamm (`x.bmp` ↔ `x.clt`), die Paletten stehen hinter den Bildern.
- **Texte stecken in Deckkraftmasken:** Jede Einblendung besteht aus einem Farbbild (`moji.bmp`, Palette RGB, voll deckend) und einer Maske `<ortsname>-a.bmp` (Palette: schwarz mit Alphaskala 0…0xFE). Der Schriftzug ist nur in der Maske sichtbar.
- 25 Gebietstitel (256×32, verzierte Schrift mit Schatten) in `ce0xx_9xx.esd` und den zugehörigen `ef*.esp`; 14 Kartenbeschriftungen (256×64, schlichte Schrift) in `ef1210/ef1218` (Orbitalaufzug) und `ef2310–ef2328` (Stadt). Dieselbe Maske steckt oft in mehreren Dateien (bis 5×).
- Hinweis „Press ● button to enter this area.“ = `under-a.bmp` (256×64), 44 identische Kopien.
- Japanische Reste: `ce006_999` (ゾハル・ダンジョン), `ce008_999` (ミルチア).

### TIM2 `.tm2` (`mnu/pse`)

Standard-TIM2 (siehe Kopf von `tools/tm2.py`). Alle vier Dateien sind RGBA32 (Bildtyp 3). Achtung: `logo_ep1/ep2` nutzen Alpha 0…0xFF, `logo_pp`/`haikei` die PS2-Skala 0…0x80 – `tm2.py` erkennt das je Bild.

### Eingebettete JPGs

- `mnu/credit.bin`: Kopf mit Offsets, 4 JPGs (Hersteller-Logos).
- `mnu/diskchg.bin`: 1 JPG (Shion, Disc-Wechsel) + ADX-Sprachaufnahmen (`(c)CRI`).

### Sonstiges

- `mnu/segcap.xtx`: Breite 246 passt nicht zum Swizzle, Inhalt unklar (vermutlich Segment-Bilder ohne Text).
- `mnu/umn.txy`, `mnu/skillbg.bin`, `mnu/umn.bin`: 3D-Modelle (`Xc`/`pxy`/`txy`) mit Linientexturen, ohne Text.

## Ergebnis der Sichtung

| Gruppe | Dateien | Englischer Text | Empfehlung |
|---|---|---|---|
| Titelbildschirm | `mnu/us/titleobj.xtx`, `title1.png` | NEW GAME … | erledigt |
| Ortseinblendungen | `ef/esd/us/*.esd`, `ef/map/us/*.esp` | 25 Gebietstitel, 14 Kartenbeschriftungen, „Press ● button …“ | ja |
| Figurenkarten | `mnu/intm/01–09.jpg`, `mnu/diskchg.bin` | „height“, „weight“ | optional (JPG → Pillow) |
| Game Over | `mnu/us/gameov1.jpg` | GAME OVER | optional (JPG → Pillow) |
| Kampfanzeige | `mnu/us/window0–2.xtx` | ATTACKER, RESERVE, ENEMY INFO, COMMAND, STOCK, BOOST, ANIMA, ACT | optional, eher nein (G3) |
| Datenbankbilder | `jpg/us/dtimg_0150, 0151, 0176, 0237, 0244, 0245, 0250` | Titelkarten, Bildschirmtext | optional |
| Tutorial-Screenshots | `jpg/us/dtimg_0431–0453` | Kampfoberfläche | nein |
| Minispiel | `mg1/us/Picture.xtx` | SURREALISTIC PUZZLE ACTION | nein (Logo, Regel Block 6) |
| Logos, Szenen, Porträts, Speicherbilder | `syno.png`, `w09.png`, `wall.jpg`, `logo_*.tm2`, `credit.bin`, `mnu/syno`, `mnu/pse/EP1/EP2`, `mcimg_*`, `bat_face`, `kao` | – / Marke | bleibt |

`dtimg_1xxx` ist größtenteils eine Kopie der `0xxx`-Reihe (275 identisch); deren Tutorial-Bilder sind japanisch.

**Entscheidung des Nutzers (2026-11-16):** übersetzt werden **A** Ortseinblendungen, **B** Figurenkarten (height/weight), **D** Kampfanzeige, **E** Datenbank-Titelkarten.
**Nicht** übersetzt: GAME OVER und andere typische Gaming-Begriffe, A.G.W.S. (inkl. „Assault Maneuver Weapon System“, `dtimg_0244/0245`) und Begriffe ohne offizielle deutsche Fassung, Tutorial-Screenshots, Minispiel-Logo.
JPG-Bearbeitung mit Pillow (Nutzer hat der Installation zugestimmt, Pillow 13.0.0 von PyPI).

**Pillow und `python -I`:** Pillow liegt in den Benutzer-Paketen (`%APPDATA%\Python\Python314\site-packages`), die der isolierte Modus ausblendet. Die Grafik-Werkzeuge hängen diesen einen Ordner gezielt an (`site.getusersitepackages()`), sonst bleibt die Isolation unverändert.

## Block A: Ortseinblendungen (`tools/ortstitel.py`, `text/de/grafik_orte.json`)

- 31 Masken (17 Gebietstitel Stil A, 13 Kartenbeschriftungen Stil B, 1 Hinweiszeile) in 49 Dateien. Eigennamen (Elsa, Durandal, Labyrinthos, Michtam, Rennes-le-Château, Miltia) bleiben, die zwei japanischen Reste ebenso.
- Namen wie in Dialogen/Datenbank (Übersetzungsspeicher), z. B. „Klinik für akute Neurosen“, „Stadtgebiet A“, „Vector, S-Linien-Abteilung“. Hinweis: „Mit ● dieses Gebiet betreten.“ (Muster wie „Mit %button7 zum Anführer machen.“).
- Schrift: Stil A **Courier New Bold** mit Schatten (+1/+1 und +2/+2, Deckkraft 64/254 wie im Original), Stil B **MS Gothic** (trifft das Original fast exakt: gemessene Stauchung 0,98).
- Verfahren: Englischer Originaltext wird mit der Ersatzschrift auf Höhe und Breite der Originalmaske eingepasst (Größe + Stauchung); der deutsche Text übernimmt diese Werte, Grundlinie und Mitte. Zu lange Texte werden bis 250 px Breite zusätzlich gestaucht (z. B. „Abgelegene Forschungseinrichtung“). Das Tastensymbol ● wird aus der Originalmaske kopiert.
- Deckkraft → Index über die Palette der jeweiligen Maske (nächstliegender Wert), nicht linear.
- Dateigrößen bleiben gleich. Vorschau: `python -I tools/ortstitel.py --out <tmp> --vorschau build/grafik/orte`.

## Block B: Figurenkarten (`tools/figurenkarten.py`, `text/de/grafik_figurenkarten.json`)

- `mnu/intm/01–09.jpg` und das JPG in `mnu/diskchg.bin` (gleiches Bild wie `intm/08.jpg`): „height :“/„weight :“ → „Größe:“/„Gewicht:“. Namen und Werte bleiben.
- Suche über die Vorlage aus `intm/01.jpg` (nur Schriftpixel werden verglichen; Karte 09 hat zwei Figuren). „weight“ liegt immer 10 px unter „height“.
- Alte Schrift samt dunklem Rand (Maske 2 px erweitert) wird von außen nach innen aus den Nachbarn aufgefüllt; erst alle Wörter löschen, dann neu setzen. Erste Fassung ließ auf `intm/03.jpg` (KOS-MOS vor hellem Haar) Reste des alten Rands stehen (Nutzer-Rückmeldung 2026-11-16). Neue Schrift: **Bahnschrift SemiBold**, 1,25-fach breit, Kanten nachgeschärft, Rand 1 px kräftig + 1 px schwach ohne Weichzeichnen (erste Korrektur mit weichgezeichnetem Rand wirkte laut Nutzer unscharf) (Original ist eine breite Eurostile-artige Schrift), eingepasst auf das englische Wort, dunkler Rand wie im Original.
- JPG wird mit den Quantisierungstabellen und der 4:4:4-Unterabtastung des Originals gespeichert (`quality="keep"`), ohne EXIF/Photoshop-Metadaten; die Dateien werden dadurch ≈ 15 % kleiner. In `diskchg.bin` muss das JPG in den alten Platz passen (bis 0x181C0, danach ADX-Sprachdaten); der Rest wird mit Nullen gefüllt.

## Block E: Datenbankbilder (`tools/dbbilder.py`, `text/de/grafik_datenbank.json`)

| Bild | Original | Deutsch | Schrift |
|---|---|---|---|
| `dtimg_0150` (+1150) | Transgenic Type | Transgener Typ | Times New Roman, Schatten |
| `dtimg_0176` (+1176) | R E A L I A N | R E A L I A N E R | Times New Roman, gesperrt, 18 px |
| `dtimg_0237` (+1237) | TYPE 27 / COMBAT REALIAN | TYP 27 / KAMPF-REALIANER | Bahnschrift, 1,35-fach breit |
| `dtimg_0151` (+1151) | Connection system NATARAJA now loading… / User name / Password | Verbindungssystem NATARAJA wird geladen… / Benutzername / Passwort (Passwort „Ye shall be as gods“ bleibt als Zitat) | Times New Roman fett, 12 px |

- Schriftpixel werden per Kontrast zum örtlichen Hintergrund (Median 9×9) erkannt und aus den Nachbarn aufgefüllt. Bei 0151 (Text auf hellem Bildschirm) wird stattdessen der ganze Textblock spaltenweise überblendet (`loeschbox`), weil die Kontrasterkennung Reste ließ.
- Erst alle Zeilen messen, dann löschen, dann setzen (sonst misst Zeile 2 den neuen Text von Zeile 1 mit).
- Identische Kopien in der 1xxx-Reihe werden mitgeschrieben (Bildnummer kommt aus den Datenbankdaten, Zuordnung unklar).

## Block D: Kampfanzeige – bleibt englisch

Entscheidung des Nutzers (2026-11-16): Grafiken mit schattierter Pixelschrift bleiben englisch, weil nachgebaute Buchstaben dort fremd aussehen würden. Betrifft `window0–2.xtx` (ATTACKER, RESERVE, ENEMY INFO, BOOST, COMMAND, STOCK, ANIMA, ACT).
Notiz für später: Palettensuche per Glätte-Maß ergab (232, 96) als besten Kandidaten; die Buchstaben G, H, L, R, V und „-“ fehlen in diesem Stil.
