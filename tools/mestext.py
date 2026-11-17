"""Texte aus dem Minispiel (mg1/us/Message.Dat) und den Episoden-Rückblicken (mnu/pse/us/*.mes).

Message.Dat (siehe docs/formats/menue.md):
  0x0000  933 x u32 Offset (relativ zu 0x2800)
  danach  bis 0x2800 andere Daten (bleiben unverändert)
  0x2800  nullterminierte Strings bis Dateiende
.mes (nur EP1.mes und EP2.mes sind englisch; AC/PP/opening/test enthalten nur Japanisch):
  Textdatei (CRLF), Abschnitte "#MESSAGE n", danach Textzeilen, Leerzeilen als Abstand.
  Exportiert wird pro Abschnitt der Text ohne die abschließenden Leerzeilen (Zeilen mit
  echtem Zeilenumbruch in der CSV-Zelle). Beim Import bleiben Leerzeilen und Kopf erhalten.

Befehle:
  export  python tools/mestext.py export <Message.Dat|*.mes> [...] --out text/en/minispiel_mes.csv
  import  python tools/mestext.py import <Dateien> [...] --csv übersetzt.csv --out <zielordner>
  test    python tools/mestext.py test <Dateien> [...]
"""
from __future__ import annotations

import argparse
import csv
import re
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL  # noqa: E402
from sbtext import JAPANESE_RE, SBError, decode_game, encode_de  # noqa: E402

MSG_BASE = 0x2800
MSG_COUNT = 933


# ---------------------------------------------------------------- Message.Dat
def msg_parse(data: bytes) -> tuple[list[int], dict[int, bytes]]:
    table = list(struct.unpack_from(f"<{MSG_COUNT}I", data, 0))
    if struct.unpack_from("<I", data, 4 * MSG_COUNT)[0] != 0:
        raise SBError("Message.Dat: Tabelle hat nicht 933 Einträge")
    strings = {o: data[MSG_BASE + o:data.index(b"\0", MSG_BASE + o)] for o in sorted(set(table))}
    starts = {0} | {i + 1 - MSG_BASE for i in range(MSG_BASE, len(data) - 1) if data[i] == 0}
    unref = [s for s in starts if s not in strings and data[MSG_BASE + s] != 0]
    if unref:
        raise SBError(f"Message.Dat: {len(unref)} Strings ohne Verweis")
    return table, strings


def msg_build(data: bytes, table: list[int], strings: dict[int, bytes]) -> bytes:
    new_off, blob = {}, bytearray()
    for o in sorted(strings):
        new_off[o] = len(blob)
        blob += strings[o] + b"\0"
    head = bytearray(data[:MSG_BASE])
    struct.pack_into(f"<{MSG_COUNT}I", head, 0, *[new_off[o] for o in table])
    return bytes(head + blob)


# ---------------------------------------------------------------- .mes
MSG_RE = re.compile(rb"^#MESSAGE (\d+)\r?$")


def mes_parse(data: bytes) -> list[tuple[bytes, list[bytes], list[bytes]]]:
    """-> Abschnitte (Kopfzeile, Textzeilen, Leerzeilen danach roh); Abschnitt 0 = Vorspann."""
    lines = data.split(b"\n")
    sections: list[tuple[bytes, list[bytes]]] = [(b"", [])]
    for line in lines:
        if MSG_RE.match(line):
            sections.append((line, []))
        else:
            sections[-1][1].append(line)
    out = []
    for head, body in sections:
        n = len(body)
        while n and body[n - 1].strip(b"\r") == b"":
            n -= 1
        out.append((head, body[:n], body[n:]))
    return out


def mes_build(sections: list[tuple[bytes, list[bytes], list[bytes]]]) -> bytes:
    lines: list[bytes] = []
    for i, (head, body, blanks) in enumerate(sections):
        if i:
            lines.append(head)
        lines += body + blanks
    return b"\n".join(lines)


def eol_of(data: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in data else b"\n"


def is_english(data: bytes) -> bool:
    return not re.search(rb"[\xa1-\xfe][\xa1-\xfe]", data)


# ---------------------------------------------------------------- Befehle
def entries(path: Path) -> list[tuple[str, str]]:
    """-> [(schluessel, text_en)]"""
    data = path.read_bytes()
    if path.name.lower() == "message.dat":
        _, strings = msg_parse(data)
        # japanische Reste (Hiragana/Kanji) werden im US-Spiel nicht angezeigt -> nicht exportieren
        return [(str(o), decode_game(s)) for o, s in strings.items() if s and not JAPANESE_RE.search(s)]
    if not is_english(data):
        return []
    out = []
    for i, (head, body, _) in enumerate(mes_parse(data)):
        if i and body:
            out.append((head.decode().strip(), "\n".join(decode_game(l.rstrip(b"\r")) for l in body)))
    return out


def cmd_export(args) -> int:
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["datei", "schluessel", "text_en", COL])
        for f in args.files:
            p = Path(f)
            rows = entries(p)
            if not rows and p.suffix.lower() == ".mes":
                print(f"{p.name}: nur Japanisch, übersprungen", file=sys.stderr)
            for key, text in rows:
                w.writerow([p.name, key, text, ""]); n += 1
    print(f"{n} Texte nach {out} exportiert.", file=sys.stderr)
    return 0


def translate(path: Path, changes: dict[str, str], errors: list[str]) -> bytes:
    data = path.read_bytes()
    if path.name.lower() == "message.dat":
        table, strings = msg_parse(data)
        for o in strings:
            if str(o) in changes:
                try:
                    strings[o] = encode_de(changes[str(o)], f"{path.name} {o}")
                except SBError as e:
                    errors.append(str(e))
        return msg_build(data, table, strings)
    eol = eol_of(data)
    sections = mes_parse(data)
    for i, (head, body, blanks) in enumerate(sections):
        key = head.decode().strip()
        if i and key in changes:
            try:
                new_lines = [encode_de(l, f"{path.name} {key}") + (b"\r" if eol == b"\r\n" else b"") for l in changes[key].split("\n")]
                sections[i] = (head, new_lines, blanks)
            except SBError as e:
                errors.append(str(e))
    return mes_build(sections)


def cmd_import(args) -> int:
    changes: dict[str, dict[str, str]] = {}
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if row.get(COL, "").strip():
                changes.setdefault(row["datei"], {})[row["schluessel"]] = row[COL].replace("\r\n", "\n")
    errors: list[str] = []
    for f in args.files:
        p = Path(f)
        if p.name not in changes:
            continue
        new = translate(p, changes[p.name], errors)
        dest = Path(args.out) / p.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(new)
    for e in errors:
        print("FEHLER:", e, file=sys.stderr)
    return 1 if errors else 0


def cmd_test(args) -> int:
    bad = 0
    for f in args.files:
        p = Path(f)
        data = p.read_bytes()
        rows = entries(p)
        same = translate(p, {}, []) == data
        longer = {k: t + " (Test)" for k, t in rows}
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / p.name                       # gleicher Name: Format wird am Namen erkannt
            tmp.write_bytes(translate(p, longer, []))
            again = dict(entries(tmp))
        # Message.Dat: Schlüssel sind Offsets und ändern sich -> Texte vergleichen
        ok = sorted(again.values()) == sorted(longer.values()) if p.name.lower() == "message.dat" else again == longer
        print(f"{p.name}: {len(rows)} Texte, Roundtrip {'identisch' if same else 'ABWEICHEND'}, Verlängerung {'ok' if ok else 'FEHLER'}", file=sys.stderr)
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
