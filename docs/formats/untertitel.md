# Subtitles (`\evt\us\*.txt`, `\mov\us\**\*.txt`)

275 files on both discs (disc 1: 36 evt + 111 mov, disc 2: 18 evt + 110 mov; `mov\us` has a subfolder `bat`).
Plain text, **Windows-1252**, mixed CRLF/LF line endings.

## Structure

```
00:00:00<TAB>$ay375;$xx0,24;$rubyy-4;$col707070;     ← settings (first line, 273 files)
00:22:18<TAB>This thing is pretty big!                ← start + text
+00:01:20                                             ← end as duration (relative)
00:30:20<TAB>Unable to determine mass due to\nabnormal gravitational fields.
+00:03:25
1054<TAB>Still, these values seem to be rather unusual.
1140                                                  ← end as absolute value
end                                                   ← end of file
```

| Line type | Count | Meaning |
|---|---|---|
| `time<TAB>text` / `+time<TAB>text` | 3 053 | subtitle starts (`+` = relative to the previous time) |
| `time` alone | ≈ 1 900 | end of the previous subtitle (absolute) |
| `+time` alone | ≈ 400 | end as duration from the start |
| `time<TAB>$command…;` | 273 | display: `$ay` y position, `$xx` x position/spacing, `$rubyy` ruby offset, `$col` colour (RRGGBB) |
| `end` | 274 | end of file |
| `mono` | 1 | special case in `mov\us\s020000.txt` |

751 subtitles have no end line of their own – the next start follows directly (e.g. "Right!" → `+00:00:15<TAB>Roger!`).

Time formats: `MM:SS:FF` (most), `+MM:SS:FF`, `MMM:SS:FF` (once), `+00:0:25` (once, typo in the original) and plain numbers (frames?).
`s020000.txt` contains position lines `x,y,…,text` – translate the text part only and do not add line breaks.

In the text: `\n` = line break (**two characters**, backslash + n). No other tags. At most 2 lines per subtitle in the original.

## Export / import

```bash
python -I pySkript/subtitle_export.py --out text/en/untertitel.csv     # language column via XS3_LANG
python -I tools/subtitle_import.py --csv text/fr/untertitel.csv --out build/fr/untertitel
```

Columns: `datei; nr; zeile; start; ende; text_en; zeilen; max_zeichen; text_<code>` (file, number, line, start, end, English text,
lines, max. characters, translation). Only the text is translated; times and command lines stay unchanged. The import rebuilds each
file line by line and only replaces the text after the TAB, keeping each line's ending (CRLF/LF).
