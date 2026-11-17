"""Export and re-insert database text (mnu/us/DBC.bin, DBC2.bin).

Format (see docs/formats/datenbank.md):
  container: u32 number of blocks, count x (u32 offset, u32 size), padding 0x90 to 16 bytes,
             blocks aligned to 16 bytes (padding 0x90), last block without padding.
  block:     n records of 0xD0 bytes ("DBF\\0" ...), the last one only 0xC8 bytes,
             followed by null-terminated strings (Windows-1252).
  record:    u32 fields; fields 3, 5, 9, 10, 11-14 are string offsets relative to the block start
             (3 category, 5 title, 9 short description, 10 long text, 11-14 mostly "-1").

DBC2.bin contains the same texts grouped differently. The translation is therefore matched via the
English text and applied to both files.

Commands:
  export  python tools/dbctext.py export <DBC.bin> --out text/en/datenbank.csv
  import  python tools/dbctext.py import <DBC.bin> <DBC2.bin> --csv translated.csv --out <target folder>
  test    python tools/dbctext.py test <DBC.bin> <DBC2.bin>
"""
from __future__ import annotations

import argparse
import collections
import csv
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL  # noqa: E402
from sbtext import ENCODING, SBError, decode_game, encode_de  # noqa: E402

REC, RECLEN = 0xD0, 0xC8
PTR_FIELDS = (3, 5, 9, 10, 11, 12, 13, 14)
FIELD_NAMES = {3: "kategorie", 5: "titel", 9: "kurz", 10: "lang", 11: "extra1", 12: "extra2", 13: "extra3", 14: "extra4"}
PAD = b"\x90"


def split_container(data: bytes) -> list[bytes]:
    n = struct.unpack_from("<I", data, 0)[0]
    return [data[o:o + s] for o, s in (struct.unpack_from("<II", data, 4 + 8 * i) for i in range(n))]


def join_container(blocks: list[bytes]) -> bytes:
    head = struct.pack("<I", len(blocks))
    pos = -(-(4 + 8 * len(blocks)) // 16) * 16
    table, body = [], bytearray()
    for i, b in enumerate(blocks):
        table.append((pos + len(body), len(b)))
        body += b
        if i < len(blocks) - 1:
            body += PAD * (-(pos + len(body)) % 16)
    head += b"".join(struct.pack("<II", o, s) for o, s in table)
    head += PAD * (pos - len(head))
    return head + bytes(body)


def parse_block(b: bytes) -> tuple[int, list[list[int]], dict[int, bytes]]:
    n = 0
    while b[n * REC:n * REC + 4] == b"DBF\0":
        n += 1
    if n == 0:
        raise SBError("Block without DBF records")
    recs = [list(struct.unpack_from("<50I", b, r * REC)) for r in range(n)]
    strings: dict[int, bytes] = {}
    for w in recs:
        for f in PTR_FIELDS:
            o = w[f]
            if o not in strings:
                strings[o] = b[o:b.index(b"\0", o)]
    return n, recs, strings


def build_block(b: bytes, n: int, recs: list[list[int]], strings: dict[int, bytes]) -> bytes:
    text_start = (n - 1) * REC + RECLEN
    new_off: dict[int, int] = {}
    blob = bytearray()
    for o in sorted(strings):                     # keep the original order
        new_off[o] = text_start + len(blob)
        blob += strings[o] + b"\0"
    out = bytearray(b[:text_start])
    for r, w in enumerate(recs):
        w = list(w)
        for f in PTR_FIELDS:
            w[f] = new_off[w[f]]
        struct.pack_into("<50I", out, r * REC, *w)
    return bytes(out + blob)


def translate_file(data: bytes, mapping: dict[bytes, bytes]) -> bytes:
    blocks = []
    for b in split_container(data):
        n, recs, strings = parse_block(b)
        strings = {o: mapping.get(s, s) for o, s in strings.items()}
        blocks.append(build_block(b, n, recs, strings))
    return join_container(blocks)


def cmd_export(args) -> int:
    data = Path(args.dbc).read_bytes()
    rows: "collections.OrderedDict[bytes, dict]" = collections.OrderedDict()
    for bi, b in enumerate(split_container(data)):
        n, recs, strings = parse_block(b)
        for w in recs:
            for f in PTR_FIELDS:
                raw = strings[w[f]]
                if raw in (b"", b"-1"):
                    continue
                if raw not in rows:
                    rows[raw] = {"eintrag": w[1], "feld": FIELD_NAMES[f], "vorkommen": 0}
                rows[raw]["vorkommen"] += 1
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        wr = csv.writer(fh, delimiter=";")
        wr.writerow(["eintrag", "feld", "vorkommen", "text_en", COL])
        for raw, r in rows.items():
            wr.writerow([r["eintrag"], r["feld"], r["vorkommen"], decode_game(raw), ""])
    words = sum(len(decode_game(k).replace("\\n", " ").split()) for k in rows)
    print(f"{len(rows)} unique texts ({words} words) -> {out}", file=sys.stderr)
    return 0


def cmd_import(args) -> int:
    mapping: dict[bytes, bytes] = {}
    errors = []
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row.get(COL, "").strip():
                try:
                    # key decoded like the export (2-byte symbols such as β), hence encode_de instead of cp1252
                    key = encode_de(row["text_en"], f"entry {row['eintrag']} {row['feld']} (en)")
                    mapping[key] = encode_de(row[COL], f"entry {row['eintrag']} {row['feld']}")
                except SBError as e:
                    errors.append(str(e))
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    if errors:
        return 1
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    for f in args.files:
        p = Path(f)
        (out / p.name).write_bytes(translate_file(p.read_bytes(), mapping))
    print(f"{len(mapping)} translations applied to {len(args.files)} files -> {out}", file=sys.stderr)
    return 0


def cmd_test(args) -> int:
    bad = 0
    for f in args.files:
        data = Path(f).read_bytes()
        same = translate_file(data, {}) == data
        # lengthening test: lengthen every title, afterwards all texts must match
        titles = {}
        for b in split_container(data):
            _, recs, strings = parse_block(b)
            for w in recs:
                titles[strings[w[5]]] = strings[w[5]] + b" (Test)"
        new = translate_file(data, titles)
        ok = True
        for b_old, b_new in zip(split_container(data), split_container(new)):
            _, r_old, s_old = parse_block(b_old)
            _, r_new, s_new = parse_block(b_new)
            for w_old, w_new in zip(r_old, r_new):
                if [x for i, x in enumerate(w_old) if i not in PTR_FIELDS] != [x for i, x in enumerate(w_new) if i not in PTR_FIELDS]:
                    ok = False
                for fld in PTR_FIELDS:
                    expect = titles.get(s_old[w_old[fld]], s_old[w_old[fld]])
                    if s_new[w_new[fld]] != expect:
                        ok = False
        print(f"{Path(f).name}: round trip {'identical' if same else 'DIFFERENT'}, lengthening {'ok' if ok else 'ERROR'}", file=sys.stderr)
        bad += (not same) + (not ok)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("dbc"); p.add_argument("--out", required=True)
    p = sub.add_parser("import"); p.add_argument("files", nargs="+"); p.add_argument("--csv", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("files", nargs="+")
    args = ap.parse_args()
    return {"export": cmd_export, "import": cmd_import, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
