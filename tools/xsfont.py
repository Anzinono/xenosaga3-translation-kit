"""Exports the game font (mnu/us/font0.bin, font1.bin) as PNG and the width table as CSV.

Format (see docs/formats/font.md):
  0x00000-0x77FFF  4 planes of 1024 glyphs, 20x24 pixels, 1 byte per pixel;
                   each plane uses 2 bits of the byte (plane n = bits 2n..2n+1), gray level 0-3
  0x78000-0x783FF  width table: 512 x (left, right) for glyphs 0-511 of plane 0
  0x78400-0x78BFF  extra graphic (loaded separately as a texture), not analysed yet

Usage:
  python tools/xsfont.py <font.bin> --out <folder>
Creates: ebene0.png .. ebene3.png (32 glyphs per row, glyph number = row*32 + column)
         breiten.csv (glyph, cp1252 byte, character, left, right, width)
"""
from __future__ import annotations

import argparse
import csv
import os
import struct
import sys
import zlib

GW, GH, PER_PLANE, COLS = 20, 24, 1024, 32
PIXELS = 0x78000
WIDTHS = 0x78000
WIDTH_COUNT = 512


def write_png_gray(path: str, w: int, h: int, rows: list[list[int]]) -> None:
    raw = b"".join(b"\0" + bytes(r) for r in rows)

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def glyph_for_byte(b: int) -> int | None:
    """Glyph number for a single byte >= 0x80 (Windows-1252), per FUN_00184b30/FUN_00184938."""
    return b + 0x80 if b >= 0x80 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("font")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    data = open(args.font, "rb").read()
    if len(data) != 0x78C00:
        print(f"Warning: unexpected size {len(data):#x}", file=sys.stderr)
    os.makedirs(args.out, exist_ok=True)
    rows_g = PER_PLANE // COLS
    for plane in range(4):
        w, h = COLS * (GW + 1), rows_g * (GH + 1)
        img = [[40] * w for _ in range(h)]
        for g in range(PER_PLANE):
            gx, gy, base = (g % COLS) * (GW + 1), (g // COLS) * (GH + 1), g * GW * GH
            for y in range(GH):
                row = img[gy + y]
                for x in range(GW):
                    row[gx + x] = ((data[base + y * GW + x] >> (2 * plane)) & 3) * 85
        write_png_gray(os.path.join(args.out, f"ebene{plane}.png"), w, h, img)
    with open(os.path.join(args.out, "breiten.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["glyphe", "byte_cp1252", "zeichen", "links", "rechts", "breite"])
        byte_of = {glyph_for_byte(b): b for b in range(0x80, 0x100)}
        for g in range(WIDTH_COUNT):
            l, r = data[WIDTHS + 2 * g], data[WIDTHS + 2 * g + 1]
            b = byte_of.get(g)
            ch = bytes([b]).decode("cp1252", "replace") if b is not None else ""
            wr.writerow([g, f"{b:02X}" if b is not None else "", ch, l, r, r - l + 1 if r or l else 0])
    print(f"Exported to {args.out}: ebene0-3.png, breiten.csv", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
