"""Read and write textures in effect containers (.esd, .esp under ef/).

The containers hold records with a 0x40-byte header, each on a 0x40 boundary:
  +0x00 u32 total size (header + data)   +0x04 u32 (address/ID, unknown)
  +0x08 u16 type (4 = image, 3 = palette) +0x0A u16 slot
  +0x0C u16 width  +0x0E u16 height      +0x10 u32 bits per pixel (image: 4/8; palette: 4)
  +0x14 name (e.g. "moji.bmp", "elevator-a.bmp", "moji.clt"), followed by data.
Palettes are RGBA32 (alpha 0x80 = opaque); number of entries = 2^(bits field): 4 -> 16, 8 -> 256 colours.
Image -> palette: the next still unused palette with the same name stem after the image.
4-bit images: low nibble = left pixel.

Commands:
  list    python -I tools/eftex.py list <file> [...]
  export  python -I tools/eftex.py export <file> --out <folder>
  test    python -I tools/eftex.py test <file> [...]   (index read -> write must be byte-identical)
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xtx import write_png  # noqa: E402


@dataclass
class Rec:
    off: int
    typ: int
    slot: int
    w: int
    h: int
    bpp: int
    name: str
    pal: "Rec | None" = None

    @property
    def data_off(self) -> int:
        return self.off + 0x40



def scan(data: bytes) -> list[Rec]:
    recs = []
    for off in range(0, len(data) - 0x40, 0x40):
        total, _, typ, slot, w, h, bpp = struct.unpack_from("<IIHHHHI", data, off)
        if typ not in (3, 4) or not (0 < w <= 1024 and 0 < h <= 1024):
            continue
        raw = data[off + 0x14:off + 0x40].split(b"\0")[0]
        try:
            name = raw.decode("ascii")
        except UnicodeDecodeError:
            continue
        if typ == 4 and (bpp not in (4, 8, 32) or not name.endswith(".bmp")):
            continue
        if typ == 3 and (bpp not in (4, 8) or not name.endswith(".clt")):
            continue
        size = w * h * bpp // 8 if typ == 4 else (1 << bpp) * 4
        if total != size + 0x40 or off + total > len(data):
            continue
        recs.append(Rec(off, typ, slot, w, h, bpp, name))
    used: set[int] = set()
    for r in recs:
        if r.typ != 4:
            continue
        stem = r.name[:-4]
        for c in recs:
            if c.typ == 3 and c.off > r.off and c.off not in used and c.name[:-4] == stem:
                r.pal = c
                used.add(c.off)
                break
    return recs


def textures(data: bytes) -> list[Rec]:
    return [r for r in scan(data) if r.typ == 4]


def palette(data: bytes, r: Rec) -> list[tuple[int, int, int, int]]:
    n = 1 << r.bpp if r.bpp <= 8 else 0
    if r.pal is None:
        return [(v * 255 // max(n - 1, 1),) * 3 + (255,) for v in range(n)]
    raw = data[r.pal.data_off:r.pal.data_off + (1 << r.pal.bpp) * 4]
    pal = [(raw[i], raw[i + 1], raw[i + 2], min(raw[i + 3] * 2, 255)) for i in range(0, len(raw), 4)]
    if len(pal) == 256:                           # CSM1 memory order -> logical order
        for g in range(8):
            for j in range(8):
                k, m = g * 32 + 8 + j, g * 32 + 16 + j
                pal[k], pal[m] = pal[m], pal[k]
    return pal


def indices(data: bytes, r: Rec) -> list[int]:
    raw = data[r.data_off:r.data_off + r.w * r.h * r.bpp // 8]
    if r.bpp == 8:
        return list(raw)
    return [v for b in raw for v in (b & 15, b >> 4)]


def set_indices(data: bytes, r: Rec, idx: list[int]) -> bytes:
    if len(idx) != r.w * r.h:
        raise ValueError("wrong pixel count")
    if r.bpp == 8:
        raw = bytes(idx)
    else:
        raw = bytes((idx[i] & 15) | ((idx[i + 1] & 15) << 4) for i in range(0, len(idx), 2))
    return data[:r.data_off] + raw + data[r.data_off + len(raw):]


def to_rgba(data: bytes, r: Rec) -> list[bytes]:
    if r.bpp == 32:
        raw = data[r.data_off:r.data_off + r.w * r.h * 4]
        return [bytes(v if i % 4 != 3 else min(v * 2, 255) for i, v in enumerate(raw[y * r.w * 4:(y + 1) * r.w * 4]))
                for y in range(r.h)]
    pal = palette(data, r)
    idx = indices(data, r)
    return [b"".join(bytes(pal[i]) for i in idx[y * r.w:(y + 1) * r.w]) for y in range(r.h)]


def cmd_list(args) -> int:
    for f in args.files:
        data = Path(f).read_bytes()
        for r in textures(data):
            print(f"{Path(f).name}\t{r.off:#07x}\t{r.name}\t{r.w}x{r.h}\t{r.bpp} bpp\tPalette: {r.pal.name if r.pal else '-'}")
    return 0


def cmd_export(args) -> int:
    p = Path(args.file)
    data = p.read_bytes()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for n, r in enumerate(textures(data)):
        write_png(out / f"{p.stem}_{n:02d}_{r.name[:-4]}.png", r.w, r.h, to_rgba(data, r), rgba=True)
    return 0


def cmd_test(args) -> int:
    bad = 0
    for f in args.files:
        data = Path(f).read_bytes()
        out = data
        for r in textures(data):
            if r.bpp in (4, 8):
                out = set_indices(out, r, indices(data, r))
        ok = out == data
        print(f"{Path(f).name}: {len(textures(data))} images, round trip {'identical' if ok else 'DIFFERENT'}", file=sys.stderr)
        bad += not ok
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("files", nargs="+")
    p = sub.add_parser("export"); p.add_argument("file"); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("files", nargs="+")
    args = ap.parse_args()
    return {"list": cmd_list, "export": cmd_export, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
