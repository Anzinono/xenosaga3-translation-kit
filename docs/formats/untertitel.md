# Untertitel (`\evt\us\*.txt`, `\mov\us\**\*.txt`)

Gilt für 275 Dateien auf beiden Discs (Disc 1: 36 evt + 111 mov, Disc 2: 18 evt + 110 mov; `mov\us` hat einen Unterordner `bat`).
Reiner Text, **Windows-1252** (einziges Sonderzeichen im Original: `ä` in „Dämmerung“, `disc2 \mov\us\s100120.txt`), Zeilenenden gemischt CRLF/LF.

## Aufbau

```
00:00:00<TAB>$ay375;$xx0,24;$rubyy-4;$col707070;     ← Einstellungen (1. Zeile, 273 Dateien)
00:22:18<TAB>This thing is pretty big!                ← Start + Text
+00:01:20                                             ← Ende als Dauer (relativ)
00:30:20<TAB>Unable to determine mass due to\nabnormal gravitational fields.
+00:03:25
1054<TAB>Still, these values seem to be rather unusual.
1140                                                  ← Ende als absoluter Wert
end                                                   ← Dateiende
```

| Zeilenart | Anzahl | Bedeutung |
|---|---|---|
| `Zeit<TAB>Text` / `+Zeit<TAB>Text` | 3 053 | Untertitel beginnt (`+` = relativ zum vorherigen Zeitpunkt) |
| `Zeit` allein | ca. 1 900 | Ende des vorherigen Untertitels (absolut) |
| `+Zeit` allein | ca. 400 | Ende als Dauer ab Start |

751 Untertitel haben keine eigene Endzeile: Auf sie folgt direkt der nächste Start (z. B. „Right!“ → `+00:00:15<TAB>Roger!`). Sie bleiben vermutlich bis dahin sichtbar.
| `Zeit<TAB>$befehl…;` | 273 | Darstellung: `$ay` Y-Position, `$xx` X-Position/Abstand, `$rubyy` Ruby-Versatz, `$col` Farbe (RRGGBB) |
| `end` | 274 | Dateiende |
| `mono` | 1 | Sonderfall in `mov\us\s020000.txt` |

Zeitformate: `MM:SS:FF` (meist), `+MM:SS:FF`, `MMM:SS:FF` (1×), `+00:0:25` (1×, Tippfehler im Original) und reine Zahlen (Frames?). Die Einheit von `FF` und der Zahlen ist noch offen.

Im Text: `\n` = Zeilenumbruch (**zwei Zeichen**, Backslash + n). Andere Tags kommen nicht vor. Längste Einzelzeile im Original: ca. 45 Zeichen.

## Export

`python -I pySkript/subtitle_export.py` → `text/en/untertitel.csv` (3 053 Untertitel aus 275 Dateien; `s060600.txt` enthält keine).
Spalten: `datei; nr; zeile; start; ende; text_en; zeilen; max_zeichen; text_de`. Im Original höchstens 2 Zeilen pro Untertitel und höchstens 69 Zeichen pro Zeile.

## Für die Reinsertion

- Pro Untertitel eine CSV-Zeile: Datei, laufende Nr., Startzeile, Start, Ende, Text. Nur der Text wird übersetzt; Zeiten und Befehlszeilen bleiben unverändert.
- Beim Zurückschreiben die Datei Zeile für Zeile neu aufbauen und nur den Textteil nach dem TAB ersetzen. Zeilenenden pro Zeile beibehalten (CRLF/LF), dann bleibt der Diff minimal.
