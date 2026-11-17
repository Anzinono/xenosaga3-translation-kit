"""Pixelbreite von Spieltext im Standard-Font (font0).

Breiten aus extracted/font0/breiten.csv (nicht im Repo, entsteht beim Font-Export, siehe
docs/formats/font.md). Glyphenzuordnung: Ziffern ab Glyphe 128, A–Z ab 138, a–z ab 164,
Satzzeichen in JIS-Zeile-1-Reihenfolge; Abstand 4 px je Zeichen, Leerzeichen 2 px.
Gemessen am Spiel: Cutscene-Box mit Porträt ≈ 384 px, Datenbank-Langtext ≈ 630 px.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

FONT_CSV = Path(__file__).resolve().parent.parent / "extracted" / "font0" / "breiten.csv"
JIS1 = "　、。，．・：；？！゛゜´｀¨＾￣＿ヽヾゝゞ〃仝々〆〇ー―‐／＼～∥｜…‥‘’“”（）〔〕［］｛｝〈〉《》「」『』【】＋－±×÷＝≠＜＞≦≧∞∴♂♀°′″℃￥＄￠￡％＃＆＊＠§☆★○●◎◇"
ASC = {",": "，", ".": "．", ":": "：", ";": "；", "?": "？", "!": "！", "-": "‐", "/": "／", "'": "’", '"': "”",
       "(": "（", ")": "）", "[": "［", "]": "］", "+": "＋", "=": "＝", "<": "＜", ">": "＞", "%": "％", "#": "＃",
       "&": "＆", "*": "＊", "@": "＠", "~": "～", "_": "＿"}
SPACE, GAP, HYPHEN, UNKNOWN = 2, 4, 7, 12
TAG = re.compile(r"<[^>]*>|\$[^;]*;|%button\d|%[sd]")

_widths: list[int] | None = None
_named: dict[str, int] = {}


def available() -> bool:
    return FONT_CSV.exists()


def _load() -> None:
    global _widths
    if _widths is None:
        rows = list(csv.DictReader(FONT_CSV.open(encoding="utf-8")))
        _widths = [int(r["breite"]) for r in rows]
        _named.update({r["zeichen"]: int(r["breite"]) for r in rows if r["zeichen"]})


def char_width(c: str) -> int:
    _load()
    if c in (" ", " "):
        return SPACE
    if "0" <= c <= "9":
        return _widths[128 + ord(c) - 48]
    if "A" <= c <= "Z":
        return _widths[138 + ord(c) - 65]
    if "a" <= c <= "z":
        return _widths[164 + ord(c) - 97]
    if c == "-":
        return HYPHEN
    if c in ASC:
        return _widths[JIS1.index(ASC[c])]
    if c in JIS1:
        return _widths[JIS1.index(c)]
    return _named.get(c, UNKNOWN)


def width(text: str, links_visible: bool = False) -> int:
    """Breite einer Zeile in Pixeln. Steuerzeichen zählen nicht; links_visible=True für die
    Datenbank, deren Verweise <Name> als Text erscheinen."""
    if links_visible:
        text = text.replace("<", "").replace(">", "")
    text = re.sub(r"<k([^>]*)>", lambda m: m.group(1), text)  # Dialog-Verweise <k…> werden angezeigt
    return sum(char_width(c) + GAP for c in TAG.sub("", text))
