"""Read and write XTX textures (format 0x08: swizzled 8-bit image with 256-colour palette).

Format (see docs/formats/xtx.md). Header and swizzle logic after
LinuxJessi/Xenosaga3PythonExtractor, xtx_decode.py (MIT, Copyright (c) 2026 Jessi Ray Godsibb):
  0x00 "XTX\\0", 0x04 u32 file size, 0x08 u32 count (1), 0x0C u32 0x10,
  0x10 u16 width W, 0x12 u16 format (0x04 linear RGBA, 0x08 swizzled 8 bpp), 0x14 u32 height H,
  0x20 u32 data offset (0x30). Data: W*H*4 bytes "CT32 area"; then remaining bytes.
  Format 0x08: the area holds a PSMT8 image of size (2W) x (2H) (PS2 memory layout)
  and somewhere a 256-colour palette as a 16x16 tile (CT32, CSM1 order).

Commands:
  export  python tools/xtx.py export <file.xtx> --out <folder> [--palette X,Y]
          -> <name>_index.png (indices as grayscale), <name>.png (colour, if a palette was found)
  import  python tools/xtx.py import <file.xtx> <index.png> --out <new.xtx>
          -> writes back an 8-bit index image (PNG, grayscale = index); the palette stays unchanged
  test    python tools/xtx.py test <file.xtx> [...]   (export -> import must be byte-identical)
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path


# ---------------------------------------------------------------- PNG (no extra packages)
def write_png(path: Path, w: int, h: int, rows: list[bytes], rgba: bool = False) -> None:
    raw = b"".join(b"\0" + r for r in rows)

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    ctype = 6 if rgba else 0
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def read_png_gray(path: Path) -> tuple[int, int, bytes]:
    """Reads an 8-bit PNG (grayscale, type 0, no interlace) -> (w, h, pixels)."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype != 0 or inter:
                raise ValueError("index PNG must be 8-bit grayscale without interlace")
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    out, prev, stride = bytearray(), bytearray(w), w + 1
    for y in range(h):
        f, line = raw[y * stride], bytearray(raw[y * stride + 1:(y + 1) * stride])
        for x in range(w):
            a = line[x - 1] if x else 0
            b = prev[x]
            c = prev[x - 1] if x else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line
        prev = line
    return w, h, bytes(out)


# ---------------------------------------------------------------- XTX
def parse(data: bytes) -> tuple[int, int, int, int]:
    if data[:4] != b"XTX\0":
        raise ValueError("not an XTX file")
    w = struct.unpack_from("<H", data, 16)[0]
    fmt = struct.unpack_from("<H", data, 18)[0]
    h = struct.unpack_from("<I", data, 20)[0]
    off = struct.unpack_from("<I", data, 32)[0]
    if off + w * h * 4 > len(data):
        raise ValueError("XTX abgeschnitten")
    return w, fmt, h, off


def swizzle8_offset(canvas_w: int, x: int, y: int) -> int:
    """Byte offset of PSMT8 pixel (x, y) in the CT32 area (PS2 'unswizzle8')."""
    tw = canvas_w * 2
    block_row = (y & ~0xF) * tw
    swap_selector = (((y + 2) >> 2) & 1) * 4
    col_row = ((((y & ~3) >> 1) + (y & 1)) & 7) * tw * 2
    byte_y = (y >> 1) & 1
    return block_row + (x & ~0xF) * 2 + col_row + ((x + swap_selector) & 7) * 4 + byte_y + ((x >> 2) & 2)


def unswizzle8(canvas: bytes, canvas_w: int, out_w: int, out_h: int) -> bytes:
    idx = bytearray(out_w * out_h)
    for y in range(out_h):
        for x in range(out_w):
            idx[y * out_w + x] = canvas[swizzle8_offset(canvas_w, x, y)]
    return bytes(idx)


def swizzle8(canvas: bytearray, canvas_w: int, idx: bytes, out_w: int, out_h: int) -> None:
    for y in range(out_h):
        for x in range(out_w):
            canvas[swizzle8_offset(canvas_w, x, y)] = idx[y * out_w + x]


def clut_at(canvas: bytes, canvas_w: int, px: int, py: int) -> list[tuple[int, int, int, int]]:
    pal = []
    for ey in range(16):
        row = ((py + ey) * canvas_w + px) * 4
        for ex in range(16):
            p = canvas[row + ex * 4:row + ex * 4 + 4]
            pal.append((p[0], p[1], p[2], min(p[3] * 2, 255)))
    for g in range(8):                        # CSM1-Speicherreihenfolge -> logische Reihenfolge
        for j in range(8):
            k, m = g * 32 + 8 + j, g * 32 + 16 + j
            pal[k], pal[m] = pal[m], pal[k]
    return pal


def find_cluts(canvas: bytes, canvas_w: int, canvas_h: int) -> list[tuple[int, int]]:
    """Candidates for palette tiles: 16x16 CT32, alpha <= 0x80, at least 64 colours."""
    found = []
    for py in range(0, canvas_h - 15, 8):
        for px in range(0, canvas_w - 15, 8):
            cols, ok = set(), True
            for ey in range(16):
                row = ((py + ey) * canvas_w + px) * 4
                for ex in range(16):
                    p = canvas[row + ex * 4:row + ex * 4 + 4]
                    if p[3] > 0x80:
                        ok = False
                        break
                    cols.add(bytes(p))
                if not ok:
                    break
            if ok and len(cols) >= 64:
                found.append((px, py))
    return found


def cmd_export(args) -> int:
    p = Path(args.file)
    data = p.read_bytes()
    w, fmt, h, off = parse(data)
    if fmt != 0x08:
        raise SystemExit(f"Format {fmt:#x} is not supported yet (only 0x08)")
    canvas = data[off:off + w * h * 4]
    ow, oh = w * 2, h * 2
    idx = unswizzle8(canvas, w, ow, oh)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_png(out / f"{p.stem}_index.png", ow, oh, [idx[y * ow:(y + 1) * ow] for y in range(oh)])
    cands = [tuple(map(int, args.palette.split(",")))] if args.palette else find_cluts(canvas, w, h)
    print(f"{p.name}: {w}x{h} area, image {ow}x{oh}, palette candidates (x,y in area pixels): {cands[:10]}", file=sys.stderr)
    if cands:
        pal = clut_at(canvas, w, *cands[0])
        rows = [b"".join(bytes(pal[i]) for i in idx[y * ow:(y + 1) * ow]) for y in range(oh)]
        write_png(out / f"{p.stem}.png", ow, oh, rows, rgba=True)
        used = sorted(set(idx))
        print(f"Palette {cands[0]}: benutzte Indizes {len(used)}: "
              + ", ".join(f"{i}={pal[i]}" for i in used[:24]), file=sys.stderr)
    return 0


def build(data: bytes, idx: bytes) -> bytes:
    w, fmt, h, off = parse(data)
    if len(idx) != w * 2 * h * 2:
        raise ValueError(f"index image has the wrong size (expected {w * 2}x{h * 2})")
    canvas = bytearray(data[off:off + w * h * 4])
    swizzle8(canvas, w, idx, w * 2, h * 2)
    return data[:off] + bytes(canvas) + data[off + w * h * 4:]


def cmd_import(args) -> int:
    data = Path(args.file).read_bytes()
    pw, ph, idx = read_png_gray(Path(args.png))
    w, _, h, _ = parse(data)
    if (pw, ph) != (w * 2, h * 2):
        raise SystemExit(f"PNG is {pw}x{ph}, expected {w * 2}x{h * 2}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_bytes(build(data, idx))
    return 0


def cmd_test(args) -> int:
    bad = 0
    for f in args.files:
        data = Path(f).read_bytes()
        w, fmt, h, off = parse(data)
        if fmt != 0x08:
            print(f"{Path(f).name}: format {fmt:#x} skipped", file=sys.stderr)
            continue
        idx = unswizzle8(data[off:off + w * h * 4], w, w * 2, h * 2)
        same = build(data, idx) == data
        # the mapping must be a bijection (every byte of the area exactly once)
        offs = {swizzle8_offset(w, x, y) for y in range(h * 2) for x in range(w * 2)}
        biject = len(offs) == w * h * 4 and max(offs) == w * h * 4 - 1
        print(f"{Path(f).name}: round trip {'identical' if same else 'DIFFERENT'}, swizzle bijective: {biject}", file=sys.stderr)
        bad += (not same) + (not biject)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("file"); p.add_argument("--out", required=True); p.add_argument("--palette")
    p = sub.add_parser("import"); p.add_argument("file"); p.add_argument("png"); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("files", nargs="+")
    args = ap.parse_args()
    return {"export": cmd_export, "import": cmd_import, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
