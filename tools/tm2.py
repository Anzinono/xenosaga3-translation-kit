"""TIM2-Texturen (.tm2) lesen und schreiben.

Aufbau (Standardformat der PS2-SDK-Werkzeuge):
  0x00 "TIM2", u8 Version, u8 Ausrichtung, u16 Bildanzahl, 8 Byte frei
  je Bild ein Kopf (0x30 Byte):
    u32 Gesamtgröße, u32 Palettengröße, u32 Bildgröße, u16 Kopfgröße, u16 Farbanzahl,
    u8 Bildformat, u8 Mipmaps, u8 Palettentyp, u8 Bildtyp, u16 Breite, u16 Höhe, GS-Register (24 Byte)
  danach Bilddaten, danach Palette.
  Bildtyp 1 = RGBA16, 2 = RGB24, 3 = RGBA32, 4 = 4-Bit-Index, 5 = 8-Bit-Index.
  Alpha: meist PS2-Skala (0x80 = voll deckend); manche Bilder nutzen 0..0xFF (z. B. logo_ep1/ep2).
  Ein RGBA32-Bild mit Alpha > 0x80 gilt als 0..0xFF-Skala und wird nicht umgerechnet.

Befehle:
  export  python -I tools/tm2.py export <datei.tm2> --out <ordner>   -> <name>.png (RGBA)
  import  python -I tools/tm2.py import <datei.tm2> <bild.png> --out <neu.tm2>   (nur Bildtyp 3)
  test    python -I tools/tm2.py test <datei.tm2> [...]   (lesen -> schreiben muss byte-identisch sein)
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xtx import write_png  # noqa: E402
from pngrgba import read_png_rgba  # noqa: E402


@dataclass
class Picture:
    head: int          # Offset des Bildkopfs
    img_off: int       # Offset der Bilddaten
    img_size: int
    clut_off: int
    clut_size: int
    colors: int
    clut_type: int
    img_type: int
    w: int
    h: int


def parse(data: bytes) -> list[Picture]:
    if data[:4] != b"TIM2":
        raise ValueError("keine TIM2-Datei")
    count = struct.unpack_from("<H", data, 6)[0]
    pos = 16 if data[5] == 0 else 128
    pics = []
    for _ in range(count):
        total, clut_size, img_size, hsize, colors = struct.unpack_from("<IIIHH", data, pos)
        _fmt, _mip, clut_type, img_type, w, h = struct.unpack_from("<BBBBHH", data, pos + 16)
        img_off = pos + hsize
        pics.append(Picture(pos, img_off, img_size, img_off + img_size, clut_size, colors,
                            clut_type, img_type, w, h))
        pos += total
    return pics


def full_alpha(data: bytes, pic: Picture) -> bool:
    """True, wenn ein RGBA32-Bild Alpha 0..0xFF statt der PS2-Skala 0..0x80 nutzt."""
    return pic.img_type == 3 and max(data[pic.img_off + 3:pic.img_off + pic.img_size:4]) > 0x80


def _color(raw: bytes, i: int, kind: int, full: bool = False) -> tuple[int, int, int, int]:
    if kind == 3:
        r, g, b, a = raw[i * 4:i * 4 + 4]
        return r, g, b, a if full else min(a * 2, 255)
    if kind == 2:
        r, g, b = raw[i * 3:i * 3 + 3]
        return r, g, b, 255
    v = struct.unpack_from("<H", raw, i * 2)[0]
    return ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3, 255 if v & 0x8000 else 0)


def to_rgba(data: bytes, pic: Picture) -> list[bytes]:
    """-> Zeilen mit RGBA-Pixeln (Alpha auf 0..255 skaliert)."""
    img = data[pic.img_off:pic.img_off + pic.img_size]
    w, h = pic.w, pic.h
    if pic.img_type in (1, 2, 3):
        full = full_alpha(data, pic)
        return [b"".join(bytes(_color(img, y * w + x, pic.img_type, full)) for x in range(w)) for y in range(h)]
    clut = data[pic.clut_off:pic.clut_off + pic.clut_size]
    kind = pic.clut_type & 0x3F
    pal = [_color(clut, i, kind) for i in range(pic.colors)]
    if pic.img_type == 5 and not pic.clut_type & 0x80 and pic.colors == 256:   # CSM1 -> logisch
        for g in range(8):
            for j in range(8):
                k, m = g * 32 + 8 + j, g * 32 + 16 + j
                pal[k], pal[m] = pal[m], pal[k]
    rows = []
    for y in range(h):
        if pic.img_type == 5:
            idx = img[y * w:(y + 1) * w]
        else:
            line = img[y * w // 2:(y + 1) * w // 2]
            idx = [v for b in line for v in (b & 15, b >> 4)]
        rows.append(b"".join(bytes(pal[i]) for i in idx))
    return rows


def set_rgba32(data: bytes, pic: Picture, rows: list[bytes]) -> bytes:
    """Ersetzt die Bilddaten eines RGBA32-Bilds (Alpha 0..255 -> Skala des Originals). Kopf und Größe bleiben."""
    if pic.img_type != 3:
        raise ValueError("Schreiben nur für Bildtyp 3 (RGBA32)")
    full = full_alpha(data, pic)
    out = bytearray()
    for r in rows:
        for x in range(pic.w):
            p = r[x * 4:x * 4 + 4]
            out += bytes((p[0], p[1], p[2], p[3] if full else (p[3] + 1) // 2))
    if len(out) != pic.img_size:
        raise ValueError("Bildgröße passt nicht")
    return data[:pic.img_off] + bytes(out) + data[pic.img_off + pic.img_size:]


def cmd_export(args) -> int:
    p = Path(args.file)
    data = p.read_bytes()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for n, pic in enumerate(parse(data)):
        name = p.stem if n == 0 else f"{p.stem}_{n}"
        write_png(out / f"{name}.png", pic.w, pic.h, to_rgba(data, pic), rgba=True)
        print(f"{name}: {pic.w}x{pic.h}, Bildtyp {pic.img_type}", file=sys.stderr)
    return 0


def cmd_import(args) -> int:
    data = Path(args.file).read_bytes()
    pic = parse(data)[0]
    w, h, rows = read_png_rgba(Path(args.png))
    if (w, h) != (pic.w, pic.h):
        raise SystemExit(f"PNG ist {w}x{h}, erwartet {pic.w}x{pic.h}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_bytes(set_rgba32(data, pic, [bytes(r) for r in rows]))
    return 0


def cmd_test(args) -> int:
    bad = 0
    for f in args.files:
        data = Path(f).read_bytes()
        for pic in parse(data):
            ok = True
            if pic.img_type == 3:
                # über die skalierte Darstellung zurück (wie beim echten Import)
                ok = set_rgba32(data, pic, to_rgba(data, pic)) == data
            print(f"{Path(f).name}: {pic.w}x{pic.h} Typ {pic.img_type}: "
                  f"{'identisch' if ok else 'ABWEICHEND'}", file=sys.stderr)
            bad += not ok
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("file"); p.add_argument("--out", required=True)
    p = sub.add_parser("import"); p.add_argument("file"); p.add_argument("png"); p.add_argument("--out", required=True)
    p = sub.add_parser("test"); p.add_argument("files", nargs="+")
    args = ap.parse_args()
    return {"export": cmd_export, "import": cmd_import, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
