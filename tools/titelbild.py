"""Erzeugt den deutschen Titelbildschirm aus den Originalgrafiken.

  mnu/us/titleobj.xtx  Menüpunkte NEW GAME / CONTINUE / DATA -> Texte aus text/de/grafik_titel.json
                       (8-Bit-Textur, Schrift nutzt die Deckkraftstufen 1–15, siehe docs/formats/xtx.md)
  mnu/us/title1.png    zusätzliche Credit-Zeile unter der Copyright-Zeile (diese bleibt unverändert)

Schrift wird mit Windows/GDI+ gerendert (tools/render_text.ps1), keine Zusatzpakete nötig.

Aufruf:  python -I tools/titelbild.py --out build/de/x3/mnu/us [--vorschau build/grafik]
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import LANG, TEXT_DIR  # noqa: E402
from xtx import build as xtx_build, parse as xtx_parse, unswizzle8, write_png  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extracted" / "disc1" / "files" / "mnu" / "us"
CONFIG = TEXT_DIR / "grafik_titel.json"

# Position der Menüwörter im 144x256-Indexbild von titleobj.xtx (gemessen, siehe docs/formats/xtx.md)
WORD_BOXES = {"NEW GAME": (2, 15), "CONTINUE": (21, 33), "DATA": (39, 51)}
WORD_X_MIN = 20          # links davon liegen andere Grafikteile (nicht anfassen)
# 16-Farben-Palette der Menüschrift (grau 2A2A2A) in der CT32-Fläche: 8x2 Einträge ab Pixel (8, 112).
# Die Einträge sind eine Deckkraftskala in VERTAUSCHTER Reihenfolge (Index 6 = voll deckend).
FONT_CLUT = (8, 112)


def font_alpha_table(data: bytes) -> list[int]:
    """Alpha (0..0x80) der 16 Schrift-Indizes aus der Palette in der Textur."""
    w, _, _, off = xtx_parse(data)
    px, py = FONT_CLUT
    alphas = []
    for i in range(16):
        x, y = px + i % 8, py + i // 8
        p = data[off + (y * w + x) * 4: off + (y * w + x) * 4 + 4]
        alphas.append(p[3])
    if alphas[0] != 0 or max(alphas) != 0x80 or len(set(alphas)) != 16:
        raise SystemExit(f"Schriftpalette nicht wie erwartet: {alphas}")
    return alphas


def coverage_to_index(alphas: list[int]) -> list[int]:
    """Nachschlagetabelle Helligkeit 0..255 -> Palettenindex mit der nächstliegenden Deckkraft."""
    return [min(range(16), key=lambda i: abs(alphas[i] - v * 0x80 / 255)) for v in range(256)]


# ---------------------------------------------------------------- Hilfen
def render(text: str, font: str, size: float, bold: bool = False) -> tuple[int, int, list[list[int]]]:
    """-> (w, h, Helligkeit 0..255 je Pixel), auf den sichtbaren Text zugeschnitten."""
    with tempfile.TemporaryDirectory() as td:
        bmp = Path(td) / "m.bmp"
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(ROOT / "tools" / "render_text.ps1"), "-Text", text, "-Font", font,
                            "-Size", str(size), "-Out", str(bmp)] + (["-Bold"] if bold else []),
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"Rendern fehlgeschlagen: {r.stderr.strip()}")
        d = bmp.read_bytes()
    off, w, h = struct.unpack_from("<I", d, 10)[0], *struct.unpack_from("<ii", d, 18)
    stride = (w * 3 + 3) & ~3
    rows = []
    for y in range(abs(h)):
        sy = abs(h) - 1 - y if h > 0 else y               # BMP steht auf dem Kopf
        line = d[off + sy * stride: off + sy * stride + w * 3]
        rows.append([max(line[x * 3:x * 3 + 3]) for x in range(w)])
    ys = [y for y, r in enumerate(rows) if any(r)]
    xs = [x for x in range(w) if any(rows[y][x] for y in ys)]
    rows = [r[xs[0]:xs[-1] + 1] for r in rows[ys[0]:ys[-1] + 1]]
    return len(rows[0]), len(rows), rows


def squeeze(rows: list[list[int]], new_w: int) -> list[list[int]]:
    """Horizontal stauchen (Flächenmittelung)."""
    w = len(rows[0])
    if new_w >= w:
        return rows
    out = []
    for r in rows:
        line = []
        for nx in range(new_w):
            a, b = nx * w / new_w, (nx + 1) * w / new_w
            acc, x = 0.0, int(a)
            while x < b:
                acc += r[min(x, w - 1)] * (min(b, x + 1) - max(a, x))
                x += 1
            line.append(int(acc / (b - a) + 0.5))
        out.append(line)
    return out


def render_height(text: str, font: str, target_h: int, bold: bool = False) -> tuple[int, int, list[list[int]]]:
    """Schriftgröße so wählen, dass die sichtbare Höhe target_h entspricht."""
    size = target_h * 1.35
    for _ in range(12):
        w, h, rows = render(text, font, size, bold)
        if h == target_h:
            break
        size *= target_h / h
    return w, h, rows


# ---------------------------------------------------------------- titleobj.xtx
def make_titleobj(cfg: dict, out: Path, preview: Path | None) -> None:
    data = (SRC / "titleobj.xtx").read_bytes()
    w, _, h, off = xtx_parse(data)
    W, H = w * 2, h * 2
    idx = bytearray(unswizzle8(data[off:off + w * h * 4], w, W, H))
    lut = coverage_to_index(font_alpha_table(data))
    for en, de in cfg["menue"].items():
        if not de.strip():
            continue                                               # unübersetzt: Original bleibt
        y0, y1 = WORD_BOXES[en]
        xs = [x for x in range(WORD_X_MIN, W) for y in range(y0, y1 + 1) if idx[y * W + x]]
        x0, x1 = min(xs), max(xs)
        max_w = x1 - x0 + 1
        for y in range(y0, y1 + 1):                    # altes Wort löschen
            for x in range(x0, x1 + 1):
                idx[y * W + x] = 0
        tw, th, rows = render_height(de, cfg["schrift"], y1 - y0 + 1, cfg.get("schrift_fett", False))
        if tw > max_w:
            rows, tw = squeeze(rows, max_w), max_w
        left = (x0 + x1 + 1) // 2 - tw // 2
        for dy, r in enumerate(rows):
            for dx, v in enumerate(r):
                q = lut[v]
                if q:
                    idx[(y0 + dy) * W + left + dx] = q
        print(f"  {en!r} -> {de!r}: {tw}x{th} px (Platz {max_w}x{y1 - y0 + 1})", file=sys.stderr)
    out.mkdir(parents=True, exist_ok=True)
    (out / "titleobj.xtx").write_bytes(xtx_build(data, bytes(idx)))
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        write_png(preview / "titleobj_de_index.png", W, H, [bytes(min(255, v * 17) for v in idx[y * W:(y + 1) * W]) for y in range(H)])


# ---------------------------------------------------------------- title1.png
def read_png_rgba(path: Path) -> tuple[int, int, list[bytearray]]:
    d = path.read_bytes()
    pos, idat = 8, b""
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ, body = d[pos + 4:pos + 8], d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype != 6 or inter:
                raise SystemExit("title1.png: erwartet 8-Bit-RGBA ohne Interlace")
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    raw, bpp, stride = zlib.decompress(idat), 4, w * 4 + 1
    rows, prev = [], bytearray(w * 4)
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
    return w, h, rows


def write_png_like_original(path: Path, w: int, h: int, rows: list[bytearray]) -> None:
    """RGBA-PNG wie das Original: IHDR, IDAT in 8192-Byte-Stücken, IEND."""
    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    z = zlib.compress(b"".join(b"\0" + bytes(r) for r in rows), 9)
    parts = [z[i:i + 8192] for i in range(0, len(z), 8192)]
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + b"".join(chunk(b"IDAT", p) for p in parts) + chunk(b"IEND", b""))


def make_title1(cfg: dict, out: Path, preview: Path | None) -> None:
    w, h, rows = read_png_rgba(SRC / "title1.png")
    # Copyright-Zeile = unterste Zeilengruppe mit deckenden Pixeln
    opaque = [y for y in range(h) if any(rows[y][x * 4 + 3] > 0x40 for x in range(w))]
    bottom = opaque[-1]
    top = bottom
    while top - 1 in opaque:
        top -= 1
    px = [rows[y][x * 4:x * 4 + 4] for y in range(top, bottom + 1) for x in range(w) if rows[y][x * 4 + 3] > 0xC0]
    color = [sum(p[i] for p in px) // len(px) for i in range(3)]
    line_h = bottom - top + 1
    target = cfg.get("credit_hoehe") or max(8, round(line_h * 0.8))
    tw, th, mask = render_height(cfg["credit"], cfg["credit_schrift"], target, cfg.get("credit_fett", False))
    if cfg.get("credit_position", "unter") == "ueber":
        y0 = top - 4 - th                     # über der Copyright-Zeile, unter dem Titelmenü
        if any(rows[y][x * 4 + 3] for y in range(y0, top) for x in range(w)):
            raise SystemExit("Fläche über der Copyright-Zeile ist nicht frei")
    else:
        y0 = bottom + 4
        if y0 + th > h - 2:
            raise SystemExit("Kein Platz unter der Copyright-Zeile")
    x0 = (w - tw) // 2
    for dy, r in enumerate(mask):
        for dx, v in enumerate(r):
            if v:
                p = rows[y0 + dy]
                i = (x0 + dx) * 4
                a_new = v
                a_old = p[i + 3]
                a = a_new + a_old * (255 - a_new) // 255
                for c in range(3):
                    p[i + c] = (color[c] * a_new + p[i + c] * a_old * (255 - a_new) // 255) // max(a, 1)
                p[i + 3] = a
    out.mkdir(parents=True, exist_ok=True)
    write_png_like_original(out / "title1.png", w, h, rows)
    print(f"  Credit „{cfg['credit']}“: {tw}x{th} px bei y={y0} (Copyright-Zeile y={top}-{bottom}, Farbe {color})", file=sys.stderr)
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        # Vorschau auf hellem Hintergrund (wie im Spiel)
        bg = [bytearray(b"".join(bytes((v,)) * 0 + bytes((
            (r[x * 4] * r[x * 4 + 3] + 235 * (255 - r[x * 4 + 3])) // 255,
            (r[x * 4 + 1] * r[x * 4 + 3] + 235 * (255 - r[x * 4 + 3])) // 255,
            (r[x * 4 + 2] * r[x * 4 + 3] + 238 * (255 - r[x * 4 + 3])) // 255, 255)) for x in range(w) for v in [0]))
            for r in rows]
        write_png_like_original(preview / "title1_de_vorschau.png", w, h, bg)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="Zielordner (entspricht mnu/us)")
    ap.add_argument("--vorschau", help="Ordner für Vorschaubilder")
    ap.add_argument("--config", default=str(CONFIG))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    prev = Path(args.vorschau) if args.vorschau else None
    if any(v.strip() for v in cfg["menue"].values()):
        print("titleobj.xtx:", file=sys.stderr)
        make_titleobj(cfg, Path(args.out), prev)
    if cfg.get("credit", "").strip():
        print("title1.png:", file=sys.stderr)
        make_title1(cfg, Path(args.out), prev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
