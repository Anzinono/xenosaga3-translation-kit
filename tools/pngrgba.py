"""PNG reader without extra packages: 8-bit grayscale, RGB, RGBA, palette, grayscale+alpha -> RGBA rows."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

_CH = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def read_png_rgba(path: Path) -> tuple[int, int, list[bytearray]]:
    d = Path(path).read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat, plte, trns = 8, b"", b"", b""
    w = h = ctype = 0
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ, body = d[pos + 4:pos + 8], d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or inter or ctype not in _CH:
                raise ValueError(f"{path}: only 8-bit PNG without interlace is supported")
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    bpp = _CH[ctype]
    raw, stride = zlib.decompress(idat), w * bpp + 1
    rows, prev = [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * stride], bytearray(raw[y * stride + 1:(y + 1) * stride])
        for i in range(len(line)):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    if ctype == 6:
        return w, h, rows
    out = []
    for line in rows:
        o = bytearray()
        for x in range(w):
            if ctype == 0:
                v = line[x]; o += bytes((v, v, v, 255))
            elif ctype == 4:
                v = line[2 * x]; o += bytes((v, v, v, line[2 * x + 1]))
            elif ctype == 2:
                o += line[3 * x:3 * x + 3] + b"\xff"
            else:
                i = line[x]
                o += plte[3 * i:3 * i + 3] + bytes((trns[i] if i < len(trns) else 255,))
        out.append(o)
    return w, h, out
