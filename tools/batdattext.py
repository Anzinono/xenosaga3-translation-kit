"""Export and re-insert text from bat/us/batdat.bin (battle data: items, ether, techs, equipment …).

Structure (see docs/formats/batdat.md):
  header    u32 number of sections (28), u32 file size, u32 start offset per section (contiguous, 4-byte aligned)
  section   fixed-length records, then a text area (NUL-separated strings).
            Pointers are u16 offsets relative to the section start. The first pointer of the first record
            points to the start of the text area.
Record length and pointer fields per section are listed in LAYOUT. On loading, the tool checks that every
pointer hits a string start and every string is referenced; otherwise it aborts.
Section 0 (character and E.S. names) is not exported.

Commands:
  export  python tools/batdattext.py export <batdat.bin> --out text/en/kampfdaten.csv
  import  python tools/batdattext.py import <batdat.bin> --csv translated.csv --out <target folder>
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

# section: (record length, pointer fields, content)
LAYOUT: dict[int, tuple[int, tuple[int, ...], str]] = {
    4: (32, (0,), "Techs (characters)"),
    5: (32, (0,), "Attacks/techs (enemies, E.S.)"),
    6: (32, (0, 2), "Ether"),
    7: (40, (0, 2), "Techs/Skills"),
    8: (40, (0, 2), "Special attacks"),
    9: (40, (0, 2), "Items"),
    10: (8, (0, 2), "Status changes"),
    11: (8, (0, 2), "Status effects/abilities"),
    12: (20, (0, 2), "Abilities (skills)"),
    13: (20, (0, 2), "Accessories"),
    14: (28, (0, 2), "Weapons"),
    15: (24, (0, 2), "Armour"),
    16: (20, (0, 2), "E.S. frames"),
    17: (20, (0, 2), "E.S. generators"),
    18: (20, (0, 2), "E.S.-CPU"),
    19: (24, (0, 2), "E.S. disks"),
    23: (2, (0,), "Battle commands (name/explanation alternating)"),
    27: (8, (0, 2), "Special items"),
}
FELD = {0: "name", 2: "text"}


@dataclass
class Section:
    data: bytes
    nr: int
    text_start: int = 0
    parts: list[bytes] = field(default_factory=list)      # text area, split at NUL
    starts: list[int] = field(default_factory=list)       # offset of each part
    refs: list[tuple[int, int]] = field(default_factory=list)  # (position of the pointer, part index)
    feld_of: dict[int, str] = field(default_factory=dict)  # part index -> name/text


def split_file(data: bytes) -> list[bytes]:
    n, size = struct.unpack_from("<II", data, 0)
    if size != len(data):
        raise SBError(f"file size in header {size} ≠ {len(data)}")
    offs = list(struct.unpack_from(f"<{n}I", data, 8)) + [len(data)]
    if offs[0] != 8 + 4 * n:
        raise SBError("header has unexpected length")
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
        raise SBError(f"section {nr}: text start {ts:#x} is not a multiple of the record length {rec}")
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
                raise SBError(f"section {nr}, record {r}, field {f}: pointer {o:#x} does not hit a string start")
            i = index[o]
            sec.refs.append((pos, i))
            sec.feld_of.setdefault(i, "liste" if rec == 2 else FELD[f])
    unref = [i for i, s in enumerate(sec.parts) if s and i not in sec.feld_of]
    if unref:
        raise SBError(f"section {nr}: {len(unref)} strings without pointer")
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
        raise SBError(f"section {sec.nr}: {len(out)} bytes, u16 pointers are not enough")
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
    print(f"{rows} strings exported to {out}.", file=sys.stderr)
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
        print("ERROR:", e, file=sys.stderr)
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
    print(f"{p.name}: {len(secs)} sections, {len(LAYOUT)} with text, {n_str} strings, "
          f"round trip {'identical' if same else 'DIFFERENT'}, lengthening {'ok' if ok else 'ERROR'} "
          f"({len(data)} → {len(longer)} bytes)", file=sys.stderr)
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
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
