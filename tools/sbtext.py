"""Texte aus Xenosaga-III-Skripten (.sb) exportieren und wieder einsetzen.

Format (siehe docs/formats/sb.md):
  0x00  "SB  "  u16 1, u16 1
  0x08  6 x u32 Abschnitts-Offsets (Code, Daten, Strings, Symbole, Debug, Ressourcen)
  Abschnitt 3 (Strings): u32 8, u32 Anzahl, Anzahl x u32 Offset (relativ zum Datenbeginn),
                         danach nullterminierte Strings, Abschnittsende auf 4 Byte aufgefüllt.
  Der Bytecode verweist über die String-Nummer, nicht über Offsets. Längere Texte
  verschieben nur die Abschnitte 4-6; deren Header-Offsets werden angepasst.

Befehle:
  export    python tools/sbtext.py export <ordner mit .sb> [...] --out text/en/skripte.csv
  import    python tools/sbtext.py import <ordner mit .sb> [...] --csv übersetzt.csv --out <zielordner>
  test      python tools/sbtext.py test <ordner mit .sb> [...]   (Roundtrip: unverändert neu bauen = identisch)

CSV (Trennzeichen ;, UTF-8 mit BOM): datei; idx; kategorie; text_en; text_de
  Exportiert werden die Kategorien "dialog", "text" und "wort" (Einzelwörter: vor dem
  Übersetzen prüfen, ob Datenbank-Stichwort oder interner Name). Japanische Debug-Strings,
  Bezeichner und technische Beschriftungen bleiben unberührt (mit --all trotzdem exportieren).
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
STRTAB = 2  # Index des Stringabschnitts in der Offsetliste
# Bytes, die das Spiel zusammen mit dem Folgebyte als japanisches Zeichen liest (docs/formats/font.md)
FORBIDDEN = {0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xAD}

# Japanisch: Hiragana/Katakana (EUC A4/A5), Kanji (EUC ab B0) oder Shift-JIS.
# Symbole aus den EUC-Zeilen A1–A3/A6/AD (○ △ × α …) zählen NICHT als Japanisch.
JAPANESE_RE = re.compile(rb"[\xa4\xa5\xb0-\xfe][\xa1-\xfe]|[\x81-\x9f][\x40-\xfc]")
IDENT_RE = re.compile(r"[A-Za-z0-9_./-]+")
DIALOG_RE = re.compile(r"^\[[^\]]+\]|<[fwl]")
# Debug-Beschriftungen: "--- main ---", "*****", "*MAPJYUMP****", "  px ="
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
        raise SBError("kein SB-Skript")
    offsets = list(struct.unpack_from("<6I", data, 8))
    s, end = offsets[STRTAB], offsets[STRTAB + 1]
    hdr, count = struct.unpack_from("<II", data, s)
    if hdr != 8:
        raise SBError(f"unerwarteter Stringtabellen-Header {hdr}")
    table = struct.unpack_from(f"<{count}I", data, s + 8)
    base = s + 8 + 4 * count
    strings = []
    for o in table:
        start = base + o
        stop = data.index(b"\0", start)
        if stop >= end:
            raise SBError("String reicht über das Abschnittsende")
        strings.append(data[start:stop])
    return SB(data, offsets, strings)


def build(sb: SB, strings: list[bytes]) -> bytes:
    if len(strings) != len(sb.strings):
        raise SBError("Anzahl der Strings darf sich nicht ändern")
    s = sb.offsets[STRTAB]
    table, blob = [], bytearray()
    for b in strings:
        if b"\0" in b:
            raise SBError("String enthält ein Nullbyte")
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
    """dialog/text = übersetzen; jp/bezeichner/technisch = nicht anfassen."""
    if JAPANESE_RE.search(raw):
        return "jp"
    t = decode_game(raw)
    if t == "" or (IDENT_RE.fullmatch(t) and (re.search(r"[_\d./]", t) or t.isupper())):
        return "bezeichner"       # z. B. s082000_02_1mom, B01, CHRV_EVE0100, KOS-MOS
    if DIALOG_RE.search(t):
        return "dialog"
    if TECH_RE.fullmatch(t) or not re.search(r"[A-Za-z]", t):
        return "technisch"
    if " " not in t and "\\n" not in t:
        return "wort"             # Einzelwort: DB-Stichwort ODER interner Name -> vor Übersetzung prüfen
    return "text"


def sb_files(folders: list[str]) -> list[tuple[str, Path]]:
    out = []
    for folder in folders:
        root = Path(folder)
        for p in sorted(root.rglob("*.sb")):
            out.append((f"{root.parent.name}/{root.name}/{p.relative_to(root).as_posix()}", p))
    return out


def game_pair_ok(b1: int, b2: int) -> bool:
    """Nachbau von FUN_00181e48 (SLUS_213.89): liest das Spiel b1 b2 als ein 2-Byte-Zeichen?"""
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
    """Bytes so dekodieren, wie das Spiel sie darstellt: gültige 2-Byte-Paare (○ △ × α …) als
    echtes Zeichen (EUC-JP), alles andere als Windows-1252."""
    out, i = [], 0
    while i < len(raw):
        b = raw[i]
        if b >= 0x80 and i + 1 < len(raw) and game_pair_ok(b, raw[i + 1]):
            ch = raw[i:i + 2].decode("euc_jp", "replace")
            if "�" in ch:  # z. B. AD B5 = Ⅰ (NEC-Sonderzeichen), nur in euc_jis_2004
                ch = raw[i:i + 2].decode("euc_jis_2004", "replace")
            out.append(ch)
            i += 2
        else:
            out.append(bytes([b]).decode(ENCODING, "replace"))
            i += 1
    return "".join(out)


def encode_de(text: str, where: str) -> bytes:
    """Text -> Spielbytes. Windows-1252; zusätzlich Zeichen, die das Spiel als 2-Byte-Paar
    darstellt (○ △ □ × ↑ …, siehe decode_game). Verbotene Einzelbytes werden abgelehnt."""
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
            raise SBError(f"{where}: Zeichen '{ch}' kann das Spiel nicht darstellen") from None
        if b[0] in FORBIDDEN:
            raise SBError(f"{where}: verbotenes Zeichen '{ch}' (Byte {b[0]:02X}, siehe docs/formats/font.md)")
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
    print(f"{rows} von {total} Strings nach {out} exportiert.", file=sys.stderr)
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
        print("FEHLER:", e, file=sys.stderr)
    print(f"{written} Dateien nach {out_root} geschrieben, {len(errors)} Fehler.", file=sys.stderr)
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
            print("Roundtrip abweichend:", label, file=sys.stderr)
        # zusätzlich: verlängerter String muss wieder lesbar sein
        longer = list(sb.strings)
        longer[-1] = longer[-1] + b" (Test)"
        re_sb = parse(build(sb, longer))
        if re_sb.strings != longer or re_sb.data[re_sb.offsets[3]:] != data[sb.offsets[3]:]:
            bad += 1
            print("Verlängerung fehlerhaft:", label, file=sys.stderr)
    print(f"Roundtrip: {ok} identisch, {bad} Fehler", file=sys.stderr)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("folders", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--all", action="store_true", help="auch jp/bezeichner/technisch exportieren")
    p = sub.add_parser("import"); p.add_argument("folders", nargs="+"); p.add_argument("--csv", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("folders", nargs="+")
    args = ap.parse_args()
    return {"export": cmd_export, "import": cmd_import, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
