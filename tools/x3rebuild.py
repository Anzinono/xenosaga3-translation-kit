"""Baut ein neues Disc-Image mit geänderten Archivdateien. Dateien dürfen dabei wachsen.

Das Original wird nur gelesen. Ablauf (siehe docs/formats/iso-neuaufbau.md):
  - Passt eine Ersatzdatei in ihren alten Sektorplatz, wird sie dort geschrieben.
  - Sonst wird sie ans Ende ihrer Archivkette gehängt (hinter X3.02 bzw. X3.13/X3.23);
    alle danach liegenden Sektoren rücken nach hinten.
  - Angepasst werden: Katalog (Sektor/Größe), ISO-9660-Verzeichniseinträge (Lage/Größe),
    Volume-Größe, UDF-Dateieinträge, UDF-Partitionslänge, UDF-Integritätstabelle,
    UDF-Anker am Disc-Ende, jeweils mit neuen Prüfsummen.
Das Spiel liest eine Kette als zusammenhängenden Sektorbereich ab der LBA des Katalogs
(SLUS FUN_00188148): Katalog und Datenteile müssen lückenlos hintereinander liegen.

Aufruf:
  python tools/x3rebuild.py <original.iso> <ordner|-> <ausgabe.iso>
  <ordner> spiegelt die Spielpfade (z. B. <ordner>/mnu/us/DBC.bin); "-" = keine Änderungen
"""
from __future__ import annotations

import os
import struct
import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x3toc import parse_toc  # noqa: E402

S = 2048
CHUNK = 8 << 20


# ---------------------------------------------------------------- ISO 9660
@dataclass
class DirRec:
    pos: int      # Byte-Position des Eintrags im Image
    lba: int
    size: int
    name: str


def read_sector(fh, lba: int, n: int = 1) -> bytes:
    fh.seek(lba * S)
    return fh.read(n * S)


def iso_records(fh) -> tuple[bytes, list[DirRec]]:
    pvd = read_sector(fh, 16)
    if pvd[1:6] != b"CD001":
        raise SystemExit("Kein ISO-9660-Image")
    recs: list[DirRec] = []

    def walk(lba: int, length: int, prefix: str) -> None:
        data = read_sector(fh, lba, -(-length // S))[:length]
        p = 0
        while p < len(data):
            rl = data[p]
            if rl == 0:
                p = (p // S + 1) * S
                continue
            flba, fsize = struct.unpack_from("<I", data, p + 2)[0], struct.unpack_from("<I", data, p + 10)[0]
            flags, nl = data[p + 25], data[p + 32]
            raw = data[p + 33:p + 33 + nl]
            if raw not in (b"\0", b"\1"):
                name = prefix + raw.decode("ascii").split(";")[0].upper()
                recs.append(DirRec(lba * S + p, flba, fsize, name))
                if flags & 2:
                    walk(flba, fsize, name + "/")
            p += rl

    root = pvd[156:190]
    walk(struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], "")
    return pvd, recs


# ---------------------------------------------------------------- UDF
def crc_ccitt(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def fix_tag(d: bytearray, location: int | None = None) -> None:
    if location is not None:
        struct.pack_into("<I", d, 12, location)
    crc_len = struct.unpack_from("<H", d, 10)[0]
    struct.pack_into("<H", d, 8, crc_ccitt(bytes(d[16:16 + crc_len])))
    d[4] = (sum(d[0:4]) + sum(d[5:16])) & 0xFF


def tag_id(d: bytes) -> int:
    return struct.unpack_from("<H", d, 0)[0]


# ---------------------------------------------------------------- Ketten
@dataclass
class Chain:
    toc: DirRec
    parts: list[DirRec]
    toc_data: bytearray = field(default_factory=bytearray)
    end_lba: int = 0                       # erste LBA hinter dem letzten Datenteil
    appended: bytearray = field(default_factory=bytearray)
    inplace: list[tuple[int, bytes]] = field(default_factory=list)   # (alte LBA, Daten inkl. Füllung)


def find_chains(fh, recs: list[DirRec]) -> list[Chain]:
    by_name = {r.name: r for r in recs}
    chains = []
    for toc_name in ("X3.00", "X3.10", "X3.20"):
        if toc_name not in by_name:
            continue
        toc = by_name[toc_name]
        parts = sorted((r for r in recs if r.name.startswith(toc_name[:-1]) and r.name != toc_name), key=lambda r: r.name)
        lba = toc.lba + -(-toc.size // S)
        for p in parts:
            if p.lba != lba:
                raise SystemExit(f"{p.name} liegt nicht direkt hinter dem Vorgänger (LBA {p.lba}, erwartet {lba})")
            lba += -(-p.size // S)
        c = Chain(toc, parts, bytearray(read_sector(fh, toc.lba, -(-toc.size // S))[:toc.size]), lba)
        chains.append(c)
    return chains


def plan(fh, chains: list[Chain], files: dict[str, bytes]) -> list[str]:
    log = []
    for c in chains:
        chain_end_sector = c.end_lba - c.toc.lba
        for e in parse_toc(bytes(c.toc_data)):
            data = files.pop(e.path.lower(), None)
            if data is None:
                continue
            slot = -(-e.size // S) * S
            if len(data) <= slot:
                c.inplace.append((c.toc.lba + e.sector, data + b"\0" * (slot - len(data))))
                new_sector = e.sector
                log.append(f"{e.path}: an alter Stelle ({len(data)} B)")
            else:
                new_sector = chain_end_sector + len(c.appended) // S
                c.appended += data + b"\0" * (-len(data) % S)
                log.append(f"{e.path}: ans Kettenende verschoben ({e.size} -> {len(data)} B)")
            if new_sector >= 1 << 24:
                raise SystemExit("Sektornummer passt nicht in 24 Bit")
            c.toc_data[e.index:e.index + 3] = new_sector.to_bytes(3, "little")
            struct.pack_into("<I", c.toc_data, e.index + 3, len(data))
    return log


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    src, folder, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    if os.path.abspath(src) == os.path.abspath(dst):
        raise SystemExit("Ausgabe darf nicht das Original sein")
    files: dict[str, bytes] = {}
    if folder != "-":
        root = Path(folder)
        files = {"\\" + "\\".join(p.relative_to(root).parts).lower(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    with open(src, "rb") as fi:
        total = fi.seek(0, 2) // S
        pvd, recs = iso_records(fi)
        chains = find_chains(fi, recs)
        log = plan(fi, chains, files)
        if files:
            raise SystemExit("Nicht in den Katalogen gefunden: " + ", ".join(sorted(files)))

        inserts = sorted((c.end_lba, bytes(c.appended)) for c in chains if c.appended)
        points = [p for p, _ in inserts]
        cum = []
        acc = 0
        for _, blob in inserts:
            acc += len(blob) // S
            cum.append(acc)

        def shift(lba: int) -> int:
            i = bisect_right(points, lba) - 1     # Einfügung bei p verschiebt Sektoren >= p
            return cum[i] if i >= 0 else 0

        added = acc
        # 1) Image mit Einfügungen kopieren
        with open(dst, "wb") as fo:
            pos = 0
            for p, blob in inserts + [(total, b"")]:
                fi.seek(pos * S)
                remaining = (p - pos) * S
                while remaining:
                    chunk = fi.read(min(CHUNK, remaining))
                    fo.write(chunk)
                    remaining -= len(chunk)
                fo.write(blob)
                pos = p

        # 2) Metadaten und Daten im neuen Image anpassen
        with open(dst, "r+b") as fo:
            for c in chains:
                # Kataloge späterer Ketten (X3.10/X3.20) rücken mit, wenn davor eingefügt wurde
                fo.seek((c.toc.lba + shift(c.toc.lba)) * S)
                fo.write(c.toc_data)
                for old_lba, data in c.inplace:
                    fo.seek((old_lba + shift(old_lba)) * S)
                    fo.write(data)
            last_parts = {c.parts[-1].name: len(c.appended) for c in chains}
            # ISO 9660
            for r in recs:
                new_lba = r.lba + shift(r.lba)
                new_size = r.size + last_parts.get(r.name, 0)
                rec_pos = r.pos + shift(r.pos // S) * S
                fo.seek(rec_pos + 2)
                fo.write(struct.pack("<I", new_lba) + struct.pack(">I", new_lba) + struct.pack("<I", new_size) + struct.pack(">I", new_size))
            vol = struct.unpack_from("<I", pvd, 80)[0] + added
            fo.seek(16 * S + 80)
            fo.write(struct.pack("<I", vol) + struct.pack(">I", vol))
            # UDF
            fo.seek(256 * S)
            anchor = bytearray(fo.read(S))
            if tag_id(anchor) == 2:
                part_start = None
                main_len, main_loc, res_len, res_loc = struct.unpack_from("<IIII", anchor, 16)
                for vds in (main_loc, res_loc):
                    for lba in range(vds, vds + -(-main_len // S)):
                        fo.seek(lba * S)
                        d = bytearray(fo.read(S))
                        if tag_id(d) == 5:                      # Partition Descriptor
                            part_start = struct.unpack_from("<I", d, 188)[0]
                            struct.pack_into("<I", d, 192, struct.unpack_from("<I", d, 192)[0] + added)
                            fix_tag(d); fo.seek(lba * S); fo.write(d)
                        if tag_id(d) == 6:                      # Logical Volume Descriptor -> LVID
                            lvid_len, lvid_loc = struct.unpack_from("<II", d, 432)
                            fo.seek(lvid_loc * S)
                            lv = bytearray(fo.read(S))
                            if tag_id(lv) == 9:
                                n = struct.unpack_from("<I", lv, 72)[0]
                                for k in range(n):
                                    o = 80 + 4 * n + 4 * k
                                    struct.pack_into("<I", lv, o, struct.unpack_from("<I", lv, o)[0] + added)
                                fix_tag(lv); fo.seek(lvid_loc * S); fo.write(lv)
                # Dateieinträge: in den Sektoren der ISO-Verzeichnisse folgende Partition durchsuchen
                udf_fixed = 0
                old_lbas = {r.lba: r for r in recs}
                for lba in range(part_start, part_start + 2048):
                    fo.seek(lba * S)
                    d = bytearray(fo.read(S))
                    if tag_id(d) != 261:
                        continue
                    l_ea, l_ad = struct.unpack_from("<II", d, 168)
                    if struct.unpack_from("<H", d, 34)[0] & 7 != 0 or l_ad != 8:
                        continue
                    ad = 176 + l_ea
                    raw_len, ppos = struct.unpack_from("<II", d, ad)
                    old = ppos + part_start
                    r = old_lbas.get(old)
                    if r is None or r.name.endswith("/") or old < part_start:
                        continue
                    grow = last_parts.get(r.name, 0)
                    new_pos = old + shift(old) - part_start
                    if grow:
                        struct.pack_into("<Q", d, 56, struct.unpack_from("<Q", d, 56)[0] + grow)
                        struct.pack_into("<Q", d, 64, struct.unpack_from("<Q", d, 64)[0] + grow // S)
                        raw_len += grow
                    struct.pack_into("<II", d, ad, raw_len, new_pos)
                    if new_pos != ppos or grow:
                        fix_tag(d)
                        fo.seek(lba * S); fo.write(d)
                        udf_fixed += 1
                # Anker am Disc-Ende ist mitgewandert: Ortsangabe anpassen
                new_total = total + added
                for lba in (new_total - 1, new_total - 257):
                    fo.seek(lba * S)
                    d = bytearray(fo.read(S))
                    if tag_id(d) == 2 and struct.unpack_from("<I", d, 12)[0] in (lba - added,):
                        fix_tag(d, lba); fo.seek(lba * S); fo.write(d)
                log.append(f"UDF: {udf_fixed} Dateieinträge angepasst")

    for line in log:
        print(line, file=sys.stderr)
    print(f"Fertig: {added} Sektoren ({added * S / 2**20:.1f} MiB) eingefügt -> {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
