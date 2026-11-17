"""
Xenosaga III - Untertitel-Exporter

Liest die Untertiteldateien (evt/us und mov/us, beide Discs) und exportiert
sie als CSV: eine Zeile pro Untertitel. Formatbeschreibung:
docs/formats/untertitel.md

Aufruf (im Projekt-Root):
    python pySkript/subtitle_export.py
    python pySkript/subtitle_export.py --dir extracted/disc1/files/evt/us --out text/en/untertitel.csv

Spalten:
    datei      Pfad relativ zum Ordner "files" (z. B. disc1/evt/us/s000100.txt)
    nr         laufende Nummer des Untertitels in der Datei
    zeile      Zeilennummer der Startzeile (1-basiert) -> wird zum Zurückschreiben gebraucht
    start      Startzeit, wie in der Datei (z. B. 00:22:18, 1054, +00:00:15)
    ende       Endzeit oder Dauer aus der Folgezeile (z. B. +00:01:20, 1140), leer falls keine
    text_en    Originaltext; "\\n" (Backslash + n) = Zeilenumbruch im Spiel
    zeilen     Anzahl Textzeilen im Spiel
    max_zeichen  längste Textzeile in Zeichen (für die Längenprüfung)
    text_de    leer, für die Übersetzung
"""

import argparse
import csv
import os
from pathlib import Path

# Zielsprache wie in tools/sprache.py (Umgebungsvariable XS3_LANG, Standard de)
COL = f"text_{os.environ.get('XS3_LANG', 'de').strip().lower()}"

ENCODING = "cp1252"          # siehe docs/formats/font.md
SKIP_WORDS = {"end", "mono"}  # Steuerzeilen ohne Text
LINE_BREAK = "\\n"            # zwei Zeichen: Backslash + n

DEFAULT_DIRS = [
    "extracted/disc1/files/evt/us",
    "extracted/disc1/files/mov/us",
    "extracted/disc2/files/evt/us",
    "extracted/disc2/files/mov/us",
]


def split_line(line: str) -> tuple[str, str | None]:
    """Zeile in (Zeit, Text) teilen. Text ist None, wenn die Zeile keinen TAB hat."""
    if "\t" in line:
        time, text = line.split("\t", 1)
        return time.strip(), text
    return line.strip(), None


def parse_file(path: Path) -> list[dict]:
    """Alle Untertitel einer Datei. Befehlszeilen ($...) und Endzeilen werden nicht exportiert."""
    lines = path.read_bytes().decode(ENCODING).splitlines()
    subs: list[dict] = []
    current: dict | None = None
    for nr, line in enumerate(lines, start=1):
        time, text = split_line(line)
        if not time and text is None:
            continue                                # Leerzeile
        if text is None:
            if time.lower() in SKIP_WORDS:
                current = None
            elif current is not None and not current["ende"]:
                current["ende"] = time               # Endzeit/Dauer des laufenden Untertitels
            continue
        if text.startswith("$"):
            current = None                           # Darstellungsbefehle bleiben unverändert
            continue
        parts = text.split(LINE_BREAK)
        current = {
            "nr": len(subs) + 1,
            "zeile": nr,
            "start": time,
            "ende": "",
            "text_en": text,
            "zeilen": len(parts),
            "max_zeichen": max(len(p) for p in parts),
            COL: "",
        }
        subs.append(current)
    return subs


def file_label(path: Path) -> str:
    """Kurzer, eindeutiger Pfad ab dem Disc-Ordner, z. B. disc1/evt/us/s000100.txt."""
    parts = path.parts
    if "files" in parts:
        i = parts.index("files")
        return "/".join(parts[i - 1:i] + parts[i + 1:])
    return path.as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(description="Untertitel nach CSV exportieren")
    parser.add_argument("--dir", action="append", help="Quellordner (mehrfach möglich)")
    parser.add_argument("--out", default="text/en/untertitel.csv")
    args = parser.parse_args()

    dirs = [Path(d) for d in (args.dir or DEFAULT_DIRS)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(p for d in dirs if d.is_dir() for p in d.rglob("*.txt") if p.is_file())
    missing = [str(d) for d in dirs if not d.is_dir()]
    if missing:
        print("Ordner nicht gefunden (übersprungen):", ", ".join(missing))
    if not files:
        print("Keine Untertiteldateien gefunden.")
        return

    rows = 0
    without_subs = []
    with out.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig = Excel-freundlich
        writer = csv.DictWriter(
            f,
            fieldnames=["datei", "nr", "zeile", "start", "ende", "text_en", "zeilen", "max_zeichen", COL],
            delimiter=";",
        )
        writer.writeheader()
        for path in files:
            subs = parse_file(path)
            if not subs:
                without_subs.append(file_label(path))
            for sub in subs:
                sub["datei"] = file_label(path)
                writer.writerow(sub)
            rows += len(subs)

    print(f"{rows} Untertitel aus {len(files)} Dateien nach {out} exportiert.")
    if without_subs:
        print(f"{len(without_subs)} Dateien ohne Untertitel:", ", ".join(without_subs[:10]))


if __name__ == "__main__":
    main()
