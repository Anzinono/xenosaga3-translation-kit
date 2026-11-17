"""Export and re-insert text from Xenosaga III scripts (.sb).

Format (see docs/formats/sb.md):
  0x00  "SB  "  u16 1, u16 1
  0x08  6 x u32 section offsets (code, data, strings, symbols, debug, resources)
  section 3 (strings): u32 8, u32 count, count x u32 offset (relative to the data start),
                       then null-terminated strings, section end padded to 4 bytes.
  The bytecode refers to strings by number, not by offset. Longer text only
  moves sections 4-6; their header offsets are updated.

Commands:
  export    python tools/sbtext.py export <folder with .sb> [...] --out text/en/skripte.csv
  import    python tools/sbtext.py import <folder with .sb> [...] --csv translated.csv --out <target folder>
  test      python tools/sbtext.py test <folder with .sb> [...]   (round trip: rebuilding unchanged = identical)

CSV (separator ;, UTF-8 with BOM): datei; idx; kategorie; text_en; text_<lang>
  The categories "dialog", "text" and "wort" (single words: before translating, check whether it is
  a database keyword or an internal name) are exported. Japanese debug strings,
  identifiers ("bezeichner") and technical labels ("technisch") stay untouched (export them anyway with --all).
"""
from __future__ import annotations

import argparse
import csv
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL  # noqa: E402

ENCODING = "cp1252"
STRTAB = 2  # index of the string section in the offset list
# bytes the game reads together with the following byte as a Japanese character (docs/formats/font.md)
FORBIDDEN = {0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xAD}

# Japanese: hiragana/katakana (EUC A4/A5), kanji (EUC from B0) or Shift-JIS.
# symbols from the EUC rows A1–A3/A6/AD (○ △ × α …) do NOT count as Japanese.
JAPANESE_RE = re.compile(rb"[\xa4\xa5\xb0-\xfe][\xa1-\xfe]|[\x81-\x9f][\x40-\xfc]")
IDENT_RE = re.compile(r"[A-Za-z0-9_./-]+")
DIALOG_RE = re.compile(r"^\[[^\]]+\]|<[fwl]")
# debug labels: "--- main ---", "*****", "*MAPJYUMP****", "  px ="
TECH_RE = re.compile(r"[-*=#~]{2,}.*|\*+\w*\*+|\s+\w{1,4} =")


@dataclass
class SB:
    data: bytes
    offsets: list[int]
    strings: list[bytes]


class SBError(Exception):
    pass


def parse(data: bytes) -> SB:
    if data[:4] != b"SB  ":
        raise SBError("not an SB script")
    offsets = list(struct.unpack_from("<6I", data, 8))
    s, end = offsets[STRTAB], offsets[STRTAB + 1]
    hdr, count = struct.unpack_from("<II", data, s)
    if hdr != 8:
        raise SBError(f"unexpected string table header {hdr}")
    table = struct.unpack_from(f"<{count}I", data, s + 8)
    base = s + 8 + 4 * count
    strings = []
    for o in table:
        start = base + o
        stop = data.index(b"\0", start)
        if stop >= end:
            raise SBError("string runs past the end of the section")
        strings.append(data[start:stop])
    return SB(data, offsets, strings)


def build(sb: SB, strings: list[bytes]) -> bytes:
    if len(strings) != len(sb.strings):
        raise SBError("the number of strings must not change")
    s = sb.offsets[STRTAB]
    table, blob = [], bytearray()
    for b in strings:
        if b"\0" in b:
            raise SBError("string contains a null byte")
        table.append(len(blob))
        blob += b + b"\0"
    section = struct.pack("<II", 8, len(strings)) + struct.pack(f"<{len(table)}I", *table) + blob
    section += b"\0" * (-(s + len(section)) % 4)
    old_end = sb.offsets[STRTAB + 1]
    delta = s + len(section) - old_end
    out = bytearray(sb.data[:s] + section + sb.data[old_end:])
    new_offsets = sb.offsets[: STRTAB + 1] + [o + delta for o in sb.offsets[STRTAB + 1 :]]
    struct.pack_into("<6I", out, 8, *new_offsets)
    return bytes(out)


def category(raw: bytes) -> str:
    """dialog/text = translate; jp/bezeichner (identifier)/technisch (technical) = do not touch."""
    if JAPANESE_RE.search(raw):
        return "jp"
    t = decode_game(raw)
    if t == "" or (IDENT_RE.fullmatch(t) and (re.search(r"[_\d./]", t) or t.isupper())):
        return "bezeichner"       # e.g. s082000_02_1mom, B01, CHRV_EVE0100, KOS-MOS
    if DIALOG_RE.search(t):
        return "dialog"
    if TECH_RE.fullmatch(t) or not re.search(r"[A-Za-z]", t):
        return "technisch"
    if " " not in t and "\\n" not in t:
        return "wort"             # single word: DB keyword OR internal name -> check before translating
    return "text"


def sb_files(folders: list[str]) -> list[tuple[str, Path]]:
    out = []
    for folder in folders:
        root = Path(folder)
        for p in sorted(root.rglob("*.sb")):
            out.append((f"{root.parent.name}/{root.name}/{p.relative_to(root).as_posix()}", p))
    return out


def game_pair_ok(b1: int, b2: int) -> bool:
    """Re-implementation of FUN_00181e48 (SLUS_213.89): does the game read b1 b2 as one 2-byte character?"""
    if b2 == 0:
        return False
    if b1 in (0xA4, 0xA6):
        return True
    if b1 == 0xA1 and b2 in (0xBD, 0xDA, 0xDB, 0xDF, 0xEE, 0xF9, 0xFA, 0xFB, 0xFC):
        return True
    if b1 == 0xA2 and (0xA2 <= b2 <= 0xA6 or b2 in (0xAA, 0xAB, 0xAC, 0xAD, 0xF6)):
        return True
    if b1 == 0xA3 and 0xB0 <= b2 <= 0xB9:
        return True
    return b1 == 0xAD and 0xB5 <= b2 <= 0xB7


def decode_game(raw: bytes) -> str:
    """Decode bytes the way the game displays them: valid 2-byte pairs (○ △ × α …) as
    the real character (EUC-JP), everything else as Windows-1252."""
    out, i = [], 0
    while i < len(raw):
        b = raw[i]
        if b >= 0x80 and i + 1 < len(raw) and game_pair_ok(b, raw[i + 1]):
            ch = raw[i:i + 2].decode("euc_jp", "replace")
            if "�" in ch:  # e.g. AD B5 = Ⅰ (NEC special character), only in euc_jis_2004
                ch = raw[i:i + 2].decode("euc_jis_2004", "replace")
            out.append(ch)
            i += 2
        else:
            out.append(bytes([b]).decode(ENCODING, "replace"))
            i += 1
    return "".join(out)


def encode_de(text: str, where: str) -> bytes:
    """Text -> game bytes. Windows-1252, plus characters the game displays as a 2-byte pair
    (○ △ □ × ↑ …, see decode_game). Forbidden single bytes are rejected."""
    out = bytearray()
    for ch in text:
        try:
            b = ch.encode(ENCODING)
        except UnicodeEncodeError:
            pair = b""
            for codec in ("euc_jp", "euc_jis_2004"):
                try:
                    pair = ch.encode(codec)
                    break
                except UnicodeEncodeError:
                    pass
            if len(pair) == 2 and game_pair_ok(pair[0], pair[1]):
                out += pair
                continue
            raise SBError(f"{where}: the game cannot display the character '{ch}'") from None
        if b[0] in FORBIDDEN:
            raise SBError(f"{where}: forbidden character '{ch}' (byte {b[0]:02X}, see docs/formats/font.md)")
        out += b
    return bytes(out)


def cmd_export(args) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = total = 0
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["datei", "idx", "kategorie", "text_en", COL])
        for label, path in sb_files(args.folders):
            sb = parse(path.read_bytes())
            for i, raw in enumerate(sb.strings):
                total += 1
                cat = category(raw)
                if cat in ("dialog", "text", "wort") or args.all:
                    w.writerow([label, i, cat, decode_game(raw) if cat != "jp" else raw.hex(), ""])
                    rows += 1
    print(f"{rows} of {total} strings exported to {out}.", file=sys.stderr)
    return 0


def cmd_import(args) -> int:
    changes: dict[str, dict[int, str]] = {}
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row.get(COL, "").strip():
                changes.setdefault(row["datei"], {})[int(row["idx"])] = row[COL]
    out_root = Path(args.out)
    written = 0
    errors = []
    for label, path in sb_files(args.folders):
        if label not in changes:
            continue
        sb = parse(path.read_bytes())
        strings = list(sb.strings)
        for idx, text in changes[label].items():
            try:
                strings[idx] = encode_de(text, f"{label} #{idx}")
            except (SBError, IndexError) as e:
                errors.append(str(e))
        dest = out_root / label
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(build(sb, strings))
        written += 1
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    print(f"{written} files written to {out_root}, {len(errors)} errors.", file=sys.stderr)
    return 1 if errors else 0


def cmd_test(args) -> int:
    ok = bad = 0
    for label, path in sb_files(args.folders):
        data = path.read_bytes()
        sb = parse(data)
        if build(sb, sb.strings) == data:
            ok += 1
        else:
            bad += 1
            print("round trip differs:", label, file=sys.stderr)
        # additionally: a lengthened string must be readable again
        longer = list(sb.strings)
        longer[-1] = longer[-1] + b" (Test)"
        re_sb = parse(build(sb, longer))
        if re_sb.strings != longer or re_sb.data[re_sb.offsets[3]:] != data[sb.offsets[3]:]:
            bad += 1
            print("lengthening failed:", label, file=sys.stderr)
    print(f"Round trip: {ok} identical, {bad} errors", file=sys.stderr)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("folders", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--all", action="store_true", help="also export jp/bezeichner/technisch")
    p = sub.add_parser("import"); p.add_argument("folders", nargs="+"); p.add_argument("--csv", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("folders", nargs="+")
    args = ap.parse_args()
    return {"export": cmd_export, "import": cmd_import, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
