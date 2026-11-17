"""Texte aus bat/us/batdat.bin (Kampfdaten: Gegenstände, Äther, Techs, Ausrüstung …) exportieren und einsetzen.

Aufbau (siehe docs/formats/batdat.md):
  Kopf      u32 Anzahl Abschnitte (28), u32 Dateigröße, u32 Startoffset je Abschnitt (lückenlos, 4-Byte-Grenzen)
  Abschnitt Datensätze fester Länge, danach ein Textbereich (NUL-getrennte Strings).
            Zeiger sind u16-Offsets relativ zum Abschnittsanfang. Der erste Zeiger des ersten Satzes
            zeigt auf den Anfang des Textbereichs.
Die Satzlänge und die Zeigerfelder je Abschnitt stehen in LAYOUT. Beim Laden wird geprüft, dass jeder
Zeiger auf einen Stringanfang zeigt und jeder String referenziert ist; sonst bricht das Tool ab.
Abschnitt 0 (Figuren- und E.S.-Namen, bleiben englisch) wird nicht exportiert.

Befehle:
  export  python tools/batdattext.py export <batdat.bin> --out text/en/kampfdaten.csv
  import  python tools/batdattext.py import <batdat.bin> --csv übersetzt.csv --out <zielordner>
  test    python tools/batdattext.py test <batdat.bin>
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL  # noqa: E402
from sbtext import SBError, decode_game, encode_de  # noqa: E402

# Abschnitt: (Satzlänge, Zeigerfelder, Inhalt)
LAYOUT: dict[int, tuple[int, tuple[int, ...], str]] = {
    4: (32, (0,), "Techs (Charaktere)"),
    5: (32, (0,), "Angriffe/Techs (Gegner, E.S.)"),
    6: (32, (0, 2), "Äther"),
    7: (40, (0, 2), "Techs/Skills"),
    8: (40, (0, 2), "Spezialangriffe"),
    9: (40, (0, 2), "Gegenstände"),
    10: (8, (0, 2), "Statusveränderungen"),
    11: (8, (0, 2), "Statuseffekte/Fähigkeiten"),
    12: (20, (0, 2), "Fähigkeiten (Skills)"),
    13: (20, (0, 2), "Accessoires"),
    14: (28, (0, 2), "Waffen"),
    15: (24, (0, 2), "Rüstungen"),
    16: (20, (0, 2), "E.S.-Rahmen"),
    17: (20, (0, 2), "E.S.-Generatoren"),
    18: (20, (0, 2), "E.S.-CPU"),
    19: (24, (0, 2), "E.S.-Disks"),
    23: (2, (0,), "Kampfbefehle (Name/Erklärung im Wechsel)"),
    27: (8, (0, 2), "Sondergegenstände"),
}
FELD = {0: "name", 2: "text"}


@dataclass
class Section:
    data: bytes
    nr: int
    text_start: int = 0
    parts: list[bytes] = field(default_factory=list)      # Textbereich, an NUL getrennt
    starts: list[int] = field(default_factory=list)       # Offset jedes Teils
    refs: list[tuple[int, int]] = field(default_factory=list)  # (Position des Zeigers, Teilindex)
    feld_of: dict[int, str] = field(default_factory=dict)  # Teilindex -> name/text


def split_file(data: bytes) -> list[bytes]:
    n, size = struct.unpack_from("<II", data, 0)
    if size != len(data):
        raise SBError(f"Dateigröße im Kopf {size} ≠ {len(data)}")
    offs = list(struct.unpack_from(f"<{n}I", data, 8)) + [len(data)]
    if offs[0] != 8 + 4 * n:
        raise SBError("Kopf hat unerwartete Länge")
    return [data[offs[i]:offs[i + 1]] for i in range(n)]


def join_file(secs: list[bytes]) -> bytes:
    n = len(secs)
    pos = 8 + 4 * n
    offs = []
    for s in secs:
        offs.append(pos)
        pos += len(s)
    return struct.pack(f"<II{n}I", n, pos, *offs) + b"".join(secs)


def analyse(nr: int, data: bytes) -> Section:
    sec = Section(data, nr)
    if nr not in LAYOUT:
        return sec
    rec, fields, _ = LAYOUT[nr]
    ts = struct.unpack_from("<H", data, 0)[0]
    if ts % rec:
        raise SBError(f"Abschnitt {nr}: Textanfang {ts:#x} kein Vielfaches der Satzlänge {rec}")
    sec.text_start = ts
    p = ts
    for part in data[ts:].split(b"\0"):
        sec.parts.append(part); sec.starts.append(p); p += len(part) + 1
    index = {o: i for i, o in enumerate(sec.starts)}
    for r in range(ts // rec):
        for f in fields:
            pos = r * rec + f
            o = struct.unpack_from("<H", data, pos)[0]
            if o not in index:
                raise SBError(f"Abschnitt {nr}, Satz {r}, Feld {f}: Zeiger {o:#x} trifft keinen Stringanfang")
            i = index[o]
            sec.refs.append((pos, i))
            sec.feld_of.setdefault(i, "liste" if rec == 2 else FELD[f])
    unref = [i for i, s in enumerate(sec.parts) if s and i not in sec.feld_of]
    if unref:
        raise SBError(f"Abschnitt {nr}: {len(unref)} Strings ohne Zeiger")
    return sec


def rebuild(sec: Section, parts: list[bytes]) -> bytes:
    if sec.nr not in LAYOUT or parts == sec.parts:
        return sec.data
    used = max(sec.feld_of) if sec.feld_of else 0
    keep = parts[:used + 1]
    starts, p = [], sec.text_start
    for s in keep:
        starts.append(p); p += len(s) + 1
    region = b"\0".join(keep) + b"\0"
    out = bytearray(sec.data[:sec.text_start] + region)
    out += b"\0" * (-len(out) % 4)
    if len(out) > 0x10000:
        raise SBError(f"Abschnitt {sec.nr}: {len(out)} Byte, u16-Zeiger reichen nicht")
    for pos, i in sec.refs:
        struct.pack_into("<H", out, pos, starts[i])
    return bytes(out)


def load(path: Path) -> list[Section]:
    return [analyse(i, s) for i, s in enumerate(split_file(path.read_bytes()))]


def cmd_export(args) -> int:
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    p = Path(args.file)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["datei", "idx", "kategorie", "inhalt", "text_en", COL])
        for sec in load(p):
            for i, s in enumerate(sec.parts):
                if s and i in sec.feld_of:
                    w.writerow([p.name, f"{sec.nr}.{i}", f"{sec.nr}:{sec.feld_of[i]}", LAYOUT[sec.nr][2], decode_game(s), ""])
                    rows += 1
    print(f"{rows} Strings nach {out} exportiert.", file=sys.stderr)
    return 0


def cmd_import(args) -> int:
    changes: dict[str, str] = {}
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row.get(COL, "").strip():
                changes[row["idx"]] = row[COL]
    p = Path(args.file)
    errors, secs = [], []
    for sec in load(p):
        parts = list(sec.parts)
        for i in range(len(parts)):
            text = changes.get(f"{sec.nr}.{i}")
            if text is not None:
                try:
                    parts[i] = encode_de(text, f"{p.name} {sec.nr}.{i}")
                except SBError as e:
                    errors.append(str(e))
        secs.append(rebuild(sec, parts))
    dest = Path(args.out) / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(join_file(secs))
    for e in errors:
        print("FEHLER:", e, file=sys.stderr)
    return 1 if errors else 0


def cmd_test(args) -> int:
    p = Path(args.file)
    data = p.read_bytes()
    secs = load(p)
    same = join_file([rebuild(s, s.parts) for s in secs]) == data
    longer = join_file([rebuild(s, [x + b" (Test)" if x else x for x in s.parts]) for s in secs])
    new = [analyse(i, s) for i, s in enumerate(split_file(longer))]
    ok = all(
        [x for x in n.parts if x][:len([y for y in o.parts if y])] == [y + b" (Test)" for y in o.parts if y]
        and all(n.parts[ni] == (o.parts[oi] + b" (Test)" if o.parts[oi] else b"")
                for (_, oi), (_, ni) in zip(o.refs, n.refs))
        for o, n in zip(secs, new) if o.nr in LAYOUT
    )
    n_str = sum(1 for s in secs for i, x in enumerate(s.parts) if x and i in s.feld_of)
    print(f"{p.name}: {len(secs)} Abschnitte, {len(LAYOUT)} mit Text, {n_str} Strings, "
          f"Roundtrip {'identisch' if same else 'ABWEICHEND'}, Verlängerung {'ok' if ok else 'FEHLER'} "
          f"({len(data)} → {len(longer)} Byte)", file=sys.stderr)
    return 0 if same and ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("file"); p.add_argument("--out", required=True)
    p = sub.add_parser("import"); p.add_argument("file"); p.add_argument("--csv", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("file")
    args = ap.parse_args()
    try:
        return {"export": cmd_export, "import": cmd_import, "test": cmd_test}[args.cmd](args)
    except SBError as e:
        print("FEHLER:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
