"""Prüft ein mit x3rebuild.py gebautes Image gegen das Original.

1. Strukturen: ISO-9660 und UDF stimmen für jede Datei überein (Lage, Größe); Volume-Größe,
   UDF-Partitionslänge und End-Anker passen zur Imagegröße; Archivketten sind lückenlos.
2. Inhalt: Jede Datei außerhalb der Archive ist identisch. Jede Archivdatei (alle Katalogeinträge)
   entspricht der Ersatzdatei aus <ordner> oder, falls keine existiert, dem Original.

Aufruf: python tools/verify_rebuild.py <original.iso> <neu.iso> <ordner|->
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x3rebuild import S, find_chains, iso_records, read_sector, tag_id  # noqa: E402
from x3toc import parse_toc  # noqa: E402


def udf_files(fh) -> tuple[dict[int, tuple[int, int]], int, int]:
    """-> {LBA: (Länge, FE-Sektor)}, Partitionsbeginn, Partitionslänge"""
    anchor = read_sector(fh, 256)
    _, main_loc = struct.unpack_from("<II", anchor, 16)
    part_start = part_len = None
    for lba in range(main_loc, main_loc + 16):
        d = read_sector(fh, lba)
        if tag_id(d) == 5:
            part_start, part_len = struct.unpack_from("<II", d, 188)
    out = {}
    for lba in range(part_start, part_start + 2048):
        d = read_sector(fh, lba)
        if tag_id(d) != 261:
            continue
        l_ea, l_ad = struct.unpack_from("<II", d, 168)
        if l_ad != 8:
            continue
        info_len = struct.unpack_from("<Q", d, 56)[0]
        _, ppos = struct.unpack_from("<II", d, 176 + l_ea)
        out[ppos + part_start] = (info_len, lba)
    return out, part_start, part_len


def sha(fh, lba: int, size: int) -> str:
    h = hashlib.sha1()
    fh.seek(lba * S)
    left = size
    while left:
        b = fh.read(min(left, 8 << 20))
        h.update(b)
        left -= len(b)
    return h.hexdigest()


def main() -> int:
    orig, new, folder = sys.argv[1:4]
    files = {}
    if folder != "-":
        root = Path(folder)
        files = {"\\" + "\\".join(p.relative_to(root).parts).lower(): p for p in root.rglob("*") if p.is_file()}
    errors = []
    with open(orig, "rb") as fo, open(new, "rb") as fn:
        total = fn.seek(0, 2) // S
        pvd_o, recs_o = iso_records(fo)
        pvd_n, recs_n = iso_records(fn)
        ro = {r.name: r for r in recs_o}
        rn = {r.name: r for r in recs_n}
        if set(ro) != set(rn):
            errors.append("Dateiliste unterschiedlich")
        if struct.unpack_from("<I", pvd_n, 80)[0] != total or struct.unpack_from(">I", pvd_n, 84)[0] != total:
            errors.append("Volume-Größe passt nicht zur Imagegröße")
        udf, part_start, part_len = udf_files(fn)
        _, ps_o, pl_o = udf_files(fo)
        total_o = fo.seek(0, 2) // S
        if total - (part_start + part_len) != total_o - (ps_o + pl_o):
            errors.append(f"UDF-Partition endet bei {part_start + part_len}, Image hat {total} Sektoren (Original: {ps_o + pl_o} von {total_o})")
        end_anchor = read_sector(fn, total - 1)
        if tag_id(end_anchor) != 2 or struct.unpack_from("<I", end_anchor, 12)[0] != total - 1:
            errors.append("UDF-Anker am Ende fehlt oder hat falsche Ortsangabe")
        for name, r in rn.items():
            if name.endswith("IOP"):
                continue
            u = udf.get(r.lba)
            if u is None or u[0] != r.size:
                errors.append(f"UDF/ISO uneinig bei {name}: ISO ({r.lba}, {r.size}) UDF {u}")
        # Dateien außerhalb der Archive
        for name, r in rn.items():
            if name.startswith("X3.") or name == "IOP":
                continue
            if sha(fo, ro[name].lba, ro[name].size) != sha(fn, r.lba, r.size):
                errors.append(f"Inhalt geändert: {name}")
        # Archivinhalte
        chains_o, chains_n = find_chains(fo, recs_o), find_chains(fn, recs_n)
        checked = replaced = 0
        for co, cn in zip(chains_o, chains_n):
            eo = {e.path.lower(): e for e in parse_toc(bytes(co.toc_data))}
            for e in parse_toc(bytes(cn.toc_data)):
                fn.seek((cn.toc.lba + e.sector) * S)
                got = fn.read(e.size)
                src = files.get(e.path.lower())
                if src is not None:
                    want = src.read_bytes()
                    replaced += 1
                else:
                    o = eo[e.path.lower()]
                    fo.seek((co.toc.lba + o.sector) * S)
                    want = fo.read(o.size)
                if got != want:
                    errors.append(f"Inhalt falsch: {e.path}")
                if cn.toc.lba + e.sector + -(-e.size // S) > cn.end_lba:
                    errors.append(f"{e.path} liegt außerhalb der Kette")
                checked += 1
    for e in errors[:30]:
        print("FEHLER:", e)
    print(f"Archivdateien geprüft: {checked} (davon ersetzt: {replaced}), Fehler: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
