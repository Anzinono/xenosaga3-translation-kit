"""
Xenosaga III - subtitle exporter

Reads the subtitle files (evt/us and mov/us, both discs) and exports
them as CSV: one row per subtitle. Format description:
docs/formats/untertitel.md

Usage (in the project root):
    python pySkript/subtitle_export.py
    python pySkript/subtitle_export.py --dir extracted/disc1/files/evt/us --out text/en/untertitel.csv

Columns:
    datei        path relative to the "files" folder (e.g. disc1/evt/us/s000100.txt)
    nr           running number of the subtitle in the file
    zeile        line number of the start line (1-based) -> needed for writing back
    start        start time as in the file (e.g. 00:22:18, 1054, +00:00:15)
    ende         end time or duration from the following line (e.g. +00:01:20, 1140), empty if none
    text_en      original text; "\\n" (backslash + n) = line break in the game
    zeilen       number of text lines in the game
    max_zeichen  longest text line in characters (for the length check)
    text_<lang>  empty, for the translation
"""

import argparse
import csv
import os
from pathlib import Path

# target language as in tools/sprache.py (environment variable XS3_LANG, default de)
COL = f"text_{os.environ.get('XS3_LANG', 'de').strip().lower()}"

ENCODING = "cp1252"          # see docs/formats/font.md
SKIP_WORDS = {"end", "mono"}  # control lines without text
LINE_BREAK = "\\n"            # two characters: backslash + n

DEFAULT_DIRS = [
    "extracted/disc1/files/evt/us",
    "extracted/disc1/files/mov/us",
    "extracted/disc2/files/evt/us",
    "extracted/disc2/files/mov/us",
]


def split_line(line: str) -> tuple[str, str | None]:
    """Split a line into (time, text). text is None if the line has no TAB."""
    if "\t" in line:
        time, text = line.split("\t", 1)
        return time.strip(), text
    return line.strip(), None


def parse_file(path: Path) -> list[dict]:
    """All subtitles of a file. Command lines ($...) and end lines are not exported."""
    lines = path.read_bytes().decode(ENCODING).splitlines()
    subs: list[dict] = []
    current: dict | None = None
    for nr, line in enumerate(lines, start=1):
        time, text = split_line(line)
        if not time and text is None:
            continue                                # blank line
        if text is None:
            if time.lower() in SKIP_WORDS:
                current = None
            elif current is not None and not current["ende"]:
                current["ende"] = time               # end time/duration of the current subtitle
            continue
        if text.startswith("$"):
            current = None                           # display commands stay unchanged
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
    """Short, unique path from the disc folder, e.g. disc1/evt/us/s000100.txt."""
    parts = path.parts
    if "files" in parts:
        i = parts.index("files")
        return "/".join(parts[i - 1:i] + parts[i + 1:])
    return path.as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export subtitles to CSV")
    parser.add_argument("--dir", action="append", help="source folder (can be given several times)")
    parser.add_argument("--out", default="text/en/untertitel.csv")
    args = parser.parse_args()

    dirs = [Path(d) for d in (args.dir or DEFAULT_DIRS)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(p for d in dirs if d.is_dir() for p in d.rglob("*.txt") if p.is_file())
    missing = [str(d) for d in dirs if not d.is_dir()]
    if missing:
        print("Folder not found (skipped):", ", ".join(missing))
    if not files:
        print("No subtitle files found.")
        return

    rows = 0
    without_subs = []
    with out.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig = Excel-friendly
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

    print(f"{rows} subtitles from {len(files)} files exported to {out}.")
    if without_subs:
        print(f"{len(without_subs)} files without subtitles:", ", ".join(without_subs[:10]))


if __name__ == "__main__":
    main()
