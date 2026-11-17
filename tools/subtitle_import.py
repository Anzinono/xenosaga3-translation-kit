"""Untertitel-Import: Gegenstück zu pySkript/subtitle_export.py.

Liest eine CSV im Format des Exporters (datei; nr; zeile; start; ende; text_en; ...; text_de)
und ersetzt in der Originaldatei in Zeile <zeile> den Text nach dem TAB durch text_de.
Zeiten, Befehlszeilen, Leerzeilen und Zeilenenden (CRLF/LF) bleiben unverändert.

datei ist relativ zu extracted/, z. B. "disc1/evt/us/s000100.txt"
-> Quelle extracted/disc1/files/evt/us/s000100.txt, Ziel <out>/disc1/evt/us/s000100.txt

Aufruf: python tools/subtitle_import.py --csv text/de/untertitel.csv --out build/de/untertitel
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL  # noqa: E402
from sbtext import SBError, encode_de  # noqa: E402

SRC_ROOT = Path("extracted")


def source_path(label: str) -> Path:
    disc, rest = label.split("/", 1)
    return SRC_ROOT / disc / "files" / rest


def apply(data: bytes, changes: dict[int, str], label: str, errors: list[str]) -> bytes:
    lines = data.split(b"\n")
    for nr, text in changes.items():
        i = nr - 1
        if i >= len(lines) or b"\t" not in lines[i]:
            errors.append(f"{label} Zeile {nr}: keine Untertitelzeile")
            continue
        time, rest = lines[i].split(b"\t", 1)
        cr = b"\r" if rest.endswith(b"\r") else b""
        try:
            lines[i] = time + b"\t" + encode_de(text, f"{label} Zeile {nr}") + cr
        except SBError as e:
            errors.append(str(e))
    return b"\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    changes: dict[str, dict[int, str]] = defaultdict(dict)
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row.get(COL, "").strip():
                changes[row["datei"]][int(row["zeile"])] = row[COL]
    errors: list[str] = []
    for label, ch in changes.items():
        src = source_path(label)
        new = apply(src.read_bytes(), ch, label, errors)
        dest = Path(args.out) / label
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(new)
    for e in errors:
        print("FEHLER:", e, file=sys.stderr)
    print(f"{len(changes)} Untertiteldateien geschrieben, {len(errors)} Fehler.", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
