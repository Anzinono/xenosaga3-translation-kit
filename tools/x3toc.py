"""Parser für die Xenosaga-III-Kataloge X3.00 / X3.10 / X3.20.

Format (selbst hergeleitet, siehe docs/formats/x3-archiv.md):

  Byte 0            Größe des Katalogs in Sektoren (2048 Byte). Der Katalog
                    belegt die ersten Sektoren des Adressraums seiner Kette.
  danach Einträge:
    Verzeichnis     [0x80 | reclen] [up] [?] [Name] 00
                    up = Anzahl Ebenen, die vorher nach oben gegangen wird
    Datei           [reclen] [ctrl] [Namensdaten] [Sektor u24] [Größe u32]
                    Neuer Name = alter Name, ab Position len(alt) - (ctrl>>4) - 1
                    mit den Namensdaten überschrieben. Endet die Namensdaten auf 00,
                    wird danach abgeschnitten (Name wird kürzer/länger).
                    ctrl == 0 bedeutet: komplett neuer Name.

Aufruf:
  python tools/x3toc.py <Katalogdatei> [--csv ausgabe.csv]
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
from dataclasses import dataclass

SECTOR = 2048


@dataclass
class Entry:
    path: str          # Pfad im Spiel, z. B. \evt\s000100.xep
    sector: int        # Sektor laut Katalog (inkl. Katalogsektoren)
    offset: int        # Byte-Offset in der Datenkette (X3.x1 + X3.x2 + ...)
    size: int          # Größe in Bytes
    index: int         # Byte-Position des Sektorfelds im Katalog (= Lybac "INDEX")


class TocError(Exception):
    pass


def _apply(prev: str, ctrl: int, namedata: bytes, pos: int) -> str:
    """Neuen Namen aus dem vorherigen Namen und den komprimierten Namensdaten bilden."""
    if ctrl == 0:
        prev, start = "", 0
    else:
        start = len(prev) - (ctrl >> 4) - 1
        if start < 0:
            raise TocError(f"Ungültige Namensposition bei 0x{pos:X} (ctrl 0x{ctrl:02X}, alt '{prev}')")
    if namedata.endswith(b"\0"):
        return prev[:start] + namedata[:-1].decode("ascii")
    part = namedata.decode("ascii")
    return prev[:start] + part + prev[start + len(part):]


def parse_toc(data: bytes) -> list[Entry]:
    table_sectors = data[0]
    pos = 1
    dirs: list[str] = []
    name = ""
    entries: list[Entry] = []
    while pos < len(data):
        b = data[pos]
        if b == 0:
            break  # Ende der Einträge (danach folgt Füllung)
        if b & 0x80:
            reclen = b & 0x7F
            up, ctrl = data[pos + 1], data[pos + 2]
            if up > len(dirs):
                raise TocError(f"Zu viele Ebenen nach oben ({up}) bei 0x{pos:X}")
            # Vorheriger Name auf derselben Ebene (Geschwister), Basis für die Kompression
            sibling = dirs[-up] if up else ""
            if up:
                del dirs[-up:]
            dirs.append(_apply(sibling, ctrl, data[pos + 3 : pos + reclen], pos))
            name = ""
            pos += reclen
            continue
        reclen = b
        name = _apply(name, data[pos + 1], data[pos + 2 : pos + reclen], pos)
        field = pos + reclen
        sector = data[field] | data[field + 1] << 8 | data[field + 2] << 16
        (size,) = struct.unpack_from("<I", data, field + 3)
        path = "\\" + "\\".join(dirs + [name])
        entries.append(Entry(path, sector, (sector - table_sectors) * SECTOR, size, field))
        pos = field + 7
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("toc")
    ap.add_argument("--csv", help="Einträge als CSV schreiben")
    args = ap.parse_args()
    with open(args.toc, "rb") as fh:
        entries = parse_toc(fh.read())
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["pfad", "offset", "groesse", "sektor", "index"])
            for e in entries:
                w.writerow([e.path, e.offset, e.size, e.sector, e.index])
    else:
        for e in entries:
            print(f"{e.offset:08X}|{e.size:08X}|{e.index:08X}|{e.path}")
    print(f"{len(entries)} Einträge", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
