"""Export and re-insert text from .txd tables (mnu/us/*.txd).

Two variants (see docs/formats/menue.md):
  A  menutext.txd:   u32 count, count x u32 absolute offset, strings
  B  devchk/discchg/synopsis.txd: count x u32 absolute offset (first offset = table length), strings
Strings are null-terminated, Windows-1252. Shared offsets (strings used several times) stay shared.

Commands:
  export  python tools/txdtext.py export <file.txd> [...] --out text/en/menue_txd.csv
  import  python tools/txdtext.py import <file.txd> [...] --csv translated.csv --out <target folder>
  test    python tools/txdtext.py test <file.txd> [...]
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL  # noqa: E402
from sbtext import ENCODING, SBError, decode_game, encode_de  # noqa: E402


def parse(data: bytes) -> tuple[str, list[int], bytes]:
    """-> (variant, offsets, data)"""
    first = struct.unpack_from("<I", data, 0)[0]
    if first % 4 == 0 and 4 <= first < len(data):
        n = first // 4
        offs = list(struct.unpack_from(f"<{n}I", data, 0))
        if offs[0] == first and all(o < len(data) for o in offs):
            return "B", offs, data
    n = first
    offs = list(struct.unpack_from(f"<{n}I", data, 4))
    if offs and offs[0] == 4 + 4 * n:
        return "A", offs, data
    raise SBError("unbekanntes .txd-Format")


def strings_of(data: bytes, offs: list[int]) -> list[bytes]:
    return [data[o:data.index(b"\0", o)] for o in offs]


def build(variant: str, offs: list[int], data: bytes, strings: list[bytes]) -> bytes:
    n = len(offs)
    head = 4 + 4 * n if variant == "A" else 4 * n
    # An offset may occur several times: the string is then written only once
    order: dict[int, int] = {}
    blob = bytearray()
    new_offs = []
    for o, s in zip(offs, strings):
        key = (o, s)
        if key not in order:
            order[key] = head + len(blob)
            blob += s + b"\0"
        new_offs.append(order[key])
    table = (struct.pack("<I", n) if variant == "A" else b"") + struct.pack(f"<{n}I", *new_offs)
    out = table + bytes(blob)
    # keep the original trailing padding (bytes after the last string)
    last_end = max(data.index(b"\0", o) + 1 for o in offs)
    return out + data[last_end:]


def cmd_export(args) -> int:
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["datei", "idx", "kategorie", "text_en", COL])
        for f in args.files:
            p = Path(f)
            variant, offs, data = parse(p.read_bytes())
            for i, s in enumerate(strings_of(data, offs)):
                t = decode_game(s)
                cat = "befehl" if t.startswith("$") and " " not in t else ("leer" if not t.strip() or t == "\\31\\3" else "text")
                w.writerow([p.name, i, cat, t, ""]); rows += 1
    print(f"{rows} strings exported to {out}.", file=sys.stderr)
    return 0


def cmd_import(args) -> int:
    changes: dict[str, dict[int, str]] = {}
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row.get(COL, "").strip():
                changes.setdefault(row["datei"], {})[int(row["idx"])] = row[COL]
    errors = []
    for f in args.files:
        p = Path(f)
        if p.name not in changes:
            continue
        variant, offs, data = parse(p.read_bytes())
        strings = strings_of(data, offs)
        for idx, text in changes[p.name].items():
            # line endings as in the original string: menutext.txd uses CR+LF, the CSV (and Git with
            # autocrlf) loses the CR. Without CR the game shifts e.g. the pause display.
            text = text.replace("\r\n", "\n")
            if idx < len(strings) and b"\r\n" in strings[idx]:
                text = text.replace("\n", "\r\n")
            try:
                strings[idx] = encode_de(text, f"{p.name} #{idx}")
            except (SBError, IndexError) as e:
                errors.append(str(e))
        dest = Path(args.out) / p.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(build(variant, offs, data, strings))
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    return 1 if errors else 0


def cmd_test(args) -> int:
    bad = 0
    for f in args.files:
        data = Path(f).read_bytes()
        variant, offs, _ = parse(data)
        strings = strings_of(data, offs)
        same = build(variant, offs, data, strings) == data
        longer = list(strings); longer[-1] += b" (Test)"
        v2, o2, d2 = parse(build(variant, offs, data, longer))
        ok_long = strings_of(d2, o2) == longer
        print(f"{Path(f).name}: variant {variant}, {len(offs)} strings, round trip {'identical' if same else 'DIFFERENT'}, lengthening {'ok' if ok_long else 'ERROR'}", file=sys.stderr)
        bad += (not same) + (not ok_long)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("files", nargs="+"); p.add_argument("--out", required=True)
    p = sub.add_parser("import"); p.add_argument("files", nargs="+"); p.add_argument("--csv", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("files", nargs="+")
    args = ap.parse_args()
    return {"export": cmd_export, "import": cmd_import, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
