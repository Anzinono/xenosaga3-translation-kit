"""Texte aus den kleinen Menü-.bin-Dateien exportieren und wieder einsetzen.

Betrifft mnu/us/njBtlText.bin, njDBcommon.bin, njDataText.bin, MVtext.bin, SegmentFileData.bin
(Container wie DBC.bin, siehe docs/formats/menue.md). Jeder Block ist eine von zwei Bauarten:

  Tabelle    u32-Offsets (relativ zum Block) bis zum ersten String, danach die Strings
  Datensätze Kennung "XXX\\0" (SEG, MVD, TOP, CHA, EVE …), feste Satzlänge, 0x90-Füllung,
             danach die Strings. Die Zeigerfelder werden statistisch bestimmt: ein Feld gilt als
             Zeiger, wenn es in JEDEM Datensatz auf einen Stringanfang zeigt.
Sicherheitsprüfung: Jeder String muss referenziert sein, sonst bricht das Tool ab.

Befehle:
  export  python tools/bintext.py export <datei.bin> [...] --out text/en/menue_bin.csv
  import  python tools/bintext.py import <datei.bin> [...] --csv übersetzt.csv --out <zielordner>
  test    python tools/bintext.py test <datei.bin> [...]
"""
from __future__ import annotations

import argparse
import collections
import csv
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL  # noqa: E402
from dbctext import join_container, split_container  # noqa: E402
from sbtext import ENCODING, SBError, decode_game, encode_de  # noqa: E402


NULLS = (0, 0xFFFFFFFF)


@dataclass
class Block:
    data: bytes
    kind: str                       # "tabelle" oder "datensaetze"
    text_start: int
    pointer_pos: list[int]          # Byte-Positionen aller Zeigerfelder im Block
    strings: dict[int, bytes]       # Offset -> String


def string_starts(b: bytes, text_start: int) -> set[int]:
    return {text_start} | {i + 1 for i in range(text_start, len(b) - 1) if b[i] == 0}


def analyse(b: bytes) -> Block:
    tag = b[:4]
    if len(tag) == 4 and tag[3] == 0 and tag[:3].isalpha() and tag[:3].isupper():
        pos = [m.start() for m in re.finditer(re.escape(tag), b) if m.start() % 4 == 0]
        stride = collections.Counter(q - p for p, q in zip(pos, pos[1:])).most_common(1)[0][0] if len(pos) > 1 else None
        n = 1
        while stride and b[n * stride:n * stride + 4] == tag:
            n += 1
        if n > 1:
            pad = min(len(b[r * stride:(r + 1) * stride]) - len(b[r * stride:(r + 1) * stride].rstrip(b"\x90")) for r in range(n - 1))
            rec_len = stride - pad
        else:
            raise SBError("Datensatzblock mit nur einem Satz wird noch nicht unterstützt")
        text_start = (n - 1) * stride + rec_len
        starts = string_starts(b, text_start)
        pointer_pos = []
        for f in range(rec_len // 4):
            vals = [struct.unpack_from("<I", b, r * stride + 4 * f)[0] for r in range(n)]
            hits = [v in starts for v in vals]
            # 0 / FFFFFFFF = Null-Zeiger (z. B. EVE-Sätze ohne Kapitelüberschrift)
            if any(hits) and all(h or v in NULLS for h, v in zip(hits, vals)):
                pointer_pos += [r * stride + 4 * f for r, v in enumerate(vals) if v not in NULLS]
            elif any(hits) and f > 0:
                raise SBError(f"Feld {f} zeigt nur teilweise auf Strings (Kennung {tag!r}) – manuell prüfen")
        kind = "datensaetze"
    else:
        first = struct.unpack_from("<I", b, 0)[0]
        if first % 4 or first == 0 or first >= len(b):
            raise SBError("unbekannte Blockart")
        text_start = first
        count = first // 4
        vals = struct.unpack_from(f"<{count}I", b, 0)
        if min(vals) != first:
            raise SBError("Offset-Tabelle: erster Eintrag ist nicht der kleinste")
        starts = string_starts(b, text_start)
        if not all(v in starts for v in vals):
            raise SBError("Offset-Tabelle zeigt nicht nur auf Stringanfänge")
        pointer_pos = [4 * i for i in range(count)]
        kind = "tabelle"
    referenced = {struct.unpack_from("<I", b, p)[0] for p in pointer_pos}
    unref = [s for s in string_starts(b, text_start) if s < len(b) and s not in referenced and b[s] != 0]
    if unref:
        raise SBError(f"{len(unref)} Strings ohne Verweis, z. B. {b[unref[0]:unref[0] + 30]!r}")
    strings = {o: b[o:b.index(b"\0", o)] for o in sorted(referenced)}
    return Block(b, kind, text_start, pointer_pos, strings)


def rebuild(blk: Block, strings: dict[int, bytes]) -> bytes:
    new_off, blob = {}, bytearray()
    for o in sorted(strings):
        new_off[o] = blk.text_start + len(blob)
        blob += strings[o] + b"\0"
    # Bytes nach dem letzten String (falls vorhanden) übernehmen
    last = max(strings)
    tail = blk.data[blk.data.index(b"\0", last) + 1:]
    out = bytearray(blk.data[:blk.text_start])
    for p in blk.pointer_pos:
        struct.pack_into("<I", out, p, new_off[struct.unpack_from("<I", out, p)[0]])
    return bytes(out + blob + tail)


def load(path: Path) -> list[Block]:
    return [analyse(b) for b in split_container(path.read_bytes())]


def cmd_export(args) -> int:
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["datei", "block", "idx", "text_en", COL])
        for f in args.files:
            p = Path(f)
            for bi, blk in enumerate(load(p)):
                for i, s in enumerate(blk.strings.values()):
                    if s:
                        w.writerow([p.name, bi, i, decode_game(s), ""]); rows += 1
    print(f"{rows} Strings nach {out} exportiert.", file=sys.stderr)
    return 0


def cmd_import(args) -> int:
    changes: dict[tuple[str, int, int], str] = {}
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row.get(COL, "").strip():
                changes[(row["datei"], int(row["block"]), int(row["idx"]))] = row[COL]
    errors = []
    for f in args.files:
        p = Path(f)
        blocks = []
        for bi, blk in enumerate(load(p)):
            strings = dict(blk.strings)
            for i, o in enumerate(list(strings)):
                text = changes.get((p.name, bi, i))
                if text is not None:
                    try:
                        strings[o] = encode_de(text, f"{p.name} Block {bi} #{i}")
                    except SBError as e:
                        errors.append(str(e))
            blocks.append(rebuild(blk, strings))
        dest = Path(args.out) / p.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(join_container(blocks))
    for e in errors:
        print("FEHLER:", e, file=sys.stderr)
    return 1 if errors else 0


def cmd_test(args) -> int:
    bad = 0
    for f in args.files:
        p = Path(f)
        data = p.read_bytes()
        blocks = load(p)
        same = join_container([rebuild(b, b.strings) for b in blocks]) == data
        longer = join_container([rebuild(b, {o: s + b" (Test)" for o, s in b.strings.items()}) for b in blocks])
        ok = all(
            list(nb.strings.values()) == [s + b" (Test)" for s in ob.strings.values()]
            for ob, nb in zip(blocks, [analyse(x) for x in split_container(longer)])
        )
        kinds = collections.Counter(b.kind for b in blocks)
        print(f"{p.name}: {len(blocks)} Blöcke {dict(kinds)}, {sum(len(b.strings) for b in blocks)} Strings, "
              f"Roundtrip {'identisch' if same else 'ABWEICHEND'}, Verlängerung {'ok' if ok else 'FEHLER'}", file=sys.stderr)
        bad += (not same) + (not ok)
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
