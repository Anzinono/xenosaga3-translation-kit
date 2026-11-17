"""Parser for the Xenosaga III catalogs X3.00 / X3.10 / X3.20.

Format (derived from hex dumps, see docs/formats/x3-archiv.md):

  byte 0            size of the catalog in sectors (2048 bytes). The catalog
                    occupies the first sectors of its chain's address space.
  then entries:
    Verzeichnis     [0x80 | reclen] [up] [?] [Name] 00
                    up = number of levels to go up first
    file            [reclen] [ctrl] [name data] [sector u24] [size u32]
                    new name = previous name, from position len(prev) - (ctrl>>4) - 1
                    overwritten with the name data. If the name data ends with 00,
                    the rest is cut off (the name gets shorter/longer).
                    ctrl == 0 bedeutet: komplett neuer Name.

Usage:
  python tools/x3toc.py <catalog file> [--csv output.csv]
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
    path: str          # path in the game, e.g. \evt\s000100.xep
    sector: int        # Sektor laut Katalog (inkl. Katalogsektoren)
    offset: int        # byte offset in the data chain (X3.x1 + X3.x2 + ...)
    size: int          # size in bytes
    index: int         # byte position of the sector field in the catalog (= Lybac "INDEX")


class TocError(Exception):
    pass


def _apply(prev: str, ctrl: int, namedata: bytes, pos: int) -> str:
    """Build the new name from the previous name and the compressed name data."""
    if ctrl == 0:
        prev, start = "", 0
    else:
        start = len(prev) - (ctrl >> 4) - 1
        if start < 0:
            raise TocError(f"Invalid name position at 0x{pos:X} (ctrl 0x{ctrl:02X}, previous '{prev}')")
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
            break  # end of entries (padding follows)
        if b & 0x80:
            reclen = b & 0x7F
            up, ctrl = data[pos + 1], data[pos + 2]
            if up > len(dirs):
                raise TocError(f"Too many levels up ({up}) at 0x{pos:X}")
            # previous name on the same level (sibling), base for the compression
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
    ap.add_argument("--csv", help="write entries as CSV")
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
    print(f"{len(entries)} entries", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
