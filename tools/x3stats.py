"""Checks the X3 catalogs against their data chains and counts contents by folder/extension.

Usage:
  python tools/x3stats.py <folder with X3.* files> [<folder disc 2> ...]

Expects per folder the catalog file(s) X3.00 / X3.10 / X3.20 and the
matching data parts (X3.01, X3.02, ...). Without the data parts only the
catalogs are evaluated; the chain size can then be given with --size CATALOG=BYTES.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x3toc import parse_toc  # noqa: E402


def chain_size(folder: str, toc_name: str) -> int | None:
    stem = toc_name[:-1]  # "X3.0" from "X3.00"
    parts = sorted(p for p in glob.glob(os.path.join(folder, stem + "*")) if not p.endswith(toc_name))
    return sum(os.path.getsize(p) for p in parts) if parts else None


def ext_of(path: str) -> str:
    base = path.rsplit("\\", 1)[-1]
    return base.rsplit(".", 1)[-1].lower() if "." in base else "(none)"


def group_of(path: str) -> str:
    parts = path.strip("\\").split("\\")
    return "\\".join(parts[:2]) if len(parts) > 2 else parts[0]


def report(toc_path: str, size: int | None) -> None:
    with open(toc_path, "rb") as fh:
        entries = parse_toc(fh.read())
    used = sum(e.size for e in entries)
    srt = sorted(entries, key=lambda e: e.offset)
    overlaps = sum(1 for a, b in zip(srt, srt[1:]) if a.offset + a.size > b.offset)
    dupes = len(entries) - len({e.path.lower() for e in entries})
    print(f"== {toc_path}: {len(entries)} files, {used / 2**20:.0f} MiB used")
    if size is not None:
        outside = sum(1 for e in entries if e.offset + e.size > size)
        print(f"   chain {size / 2**20:.0f} MiB, outside: {outside}, overlaps: {overlaps}, duplicate paths: {dupes}")
    else:
        print(f"   (chain size unknown) overlaps: {overlaps}, duplicate paths: {dupes}")
    for title, key in (("Extensions", ext_of), ("Folders", group_of)):
        agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for e in entries:
            a = agg[key(e.path)]
            a[0] += 1
            a[1] += e.size
        rows = sorted(agg.items(), key=lambda kv: -kv[1][1])
        print(f"   {title}:")
        for name, (n, s) in rows:
            print(f"     {name:<22} {n:>6} files {s / 2**20:>9.1f} MiB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--size", action="append", default=[], help="CATALOG=BYTES (chain size if the data parts are missing)")
    args = ap.parse_args()
    sizes = dict(s.split("=", 1) for s in args.size)
    for folder in args.folders:
        for toc in ("X3.00", "X3.10", "X3.20"):
            p = os.path.join(folder, toc)
            if os.path.exists(p):
                size = int(sizes[toc]) if toc in sizes else chain_size(folder, toc)
                report(p, size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
