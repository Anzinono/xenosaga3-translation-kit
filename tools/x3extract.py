"""Extracts files from the X3 archives directly from the disc image (ISO).

Reads the ISO 9660 root directory, finds the catalog (X3.00/X3.10/X3.20) and the
data parts (X3.01, X3.02, ...) and copies the requested files out.
The ISO is only read, never changed.

Usage:
  python tools/x3extract.py <image.iso> --out extracted/disc1/files [--filter "\\cf\\us\\*"] [--list]

--filter is a file-name pattern (fnmatch, case-insensitive), can be given several times.
Without --filter everything is extracted (several GB!).
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x3toc import parse_toc  # noqa: E402

SECTOR = 2048


def iso_root_files(fh) -> dict[str, tuple[int, int]]:
    """File name -> (byte offset in the ISO, size) for the root directory."""
    fh.seek(16 * SECTOR)
    pvd = fh.read(SECTOR)
    if pvd[1:6] != b"CD001":
        raise SystemExit("Not an ISO 9660 image")
    root = pvd[156:190]
    (lba,) = struct.unpack_from("<I", root, 2)
    (size,) = struct.unpack_from("<I", root, 10)
    fh.seek(lba * SECTOR)
    data = fh.read(size)
    files: dict[str, tuple[int, int]] = {}
    pos = 0
    while pos < len(data):
        rl = data[pos]
        if rl == 0:  # rest of the sector is empty
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        (flba,) = struct.unpack_from("<I", data, pos + 2)
        (fsize,) = struct.unpack_from("<I", data, pos + 10)
        nlen = data[pos + 32]
        name = data[pos + 33 : pos + 33 + nlen].decode("ascii", "replace").split(";")[0]
        files[name.upper()] = (flba * SECTOR, fsize)
        pos += rl
    return files


class Chain:
    """Several ISO files (X3.x1, X3.x2, ...) as one contiguous address space."""

    def __init__(self, fh, parts: list[tuple[int, int]]):
        self.fh = fh
        self.parts = parts

    def read(self, offset: int, length: int) -> bytes:
        out = bytearray()
        base = 0
        for iso_off, size in self.parts:
            if length and offset < base + size:
                start = max(offset - base, 0)
                n = min(size - start, length)
                self.fh.seek(iso_off + start)
                out += self.fh.read(n)
                offset += n
                length -= n
            base += size
        if length:
            raise ValueError("Read beyond the end of the chain")
        return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("iso")
    ap.add_argument("--out", required=True)
    ap.add_argument("--filter", action="append", default=[])
    ap.add_argument("--list", action="store_true", help="only list, write nothing")
    args = ap.parse_args()
    pats = [p.lower() for p in args.filter]
    total = count = 0
    with open(args.iso, "rb") as fh:
        root = iso_root_files(fh)
        for toc_name in ("X3.00", "X3.10", "X3.20"):
            if toc_name not in root:
                continue
            toc_off, toc_size = root[toc_name]
            fh.seek(toc_off)
            entries = parse_toc(fh.read(toc_size))
            stem = toc_name[:-1]
            parts = [root[n] for n in sorted(root) if n.startswith(stem) and n != toc_name]
            chain = Chain(fh, parts)
            for e in entries:
                if pats and not any(fnmatch.fnmatch(e.path.lower(), p) for p in pats):
                    continue
                count += 1
                total += e.size
                if args.list:
                    print(f"{e.size:>10}  {toc_name}  {e.path}")
                    continue
                dest = os.path.join(args.out, *e.path.strip("\\").split("\\"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as out:
                    out.write(chain.read(e.offset, e.size))
    print(f"{count} files, {total / 2**20:.1f} MiB{' (list only)' if args.list else ''}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
