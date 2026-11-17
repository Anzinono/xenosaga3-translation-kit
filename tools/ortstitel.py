"""Erzeugt die deutschen Ortseinblendungen (Effekt-Dateien ef/esd/us/*.esd, ef/map/us/*.esp).

Die Schriftzüge liegen als 4-Bit-Deckkraftmasken '<name>-a.bmp' in den Effekt-Containern (docs/grafik.md).
Für jede Maske aus text/de/grafik_orte.json:
  1. Original ausmessen (Bereich mit Schrift).
  2. Englischen Originaltext mit der Ersatzschrift so skalieren, dass er Höhe und Breite des Originals trifft
     (Schriftgröße + horizontale Stauchung).
  3. Deutschen Text mit denselben Werten setzen, auf dieselbe Grundlinie und Mitte; zu breite Texte werden
     zusätzlich gestaucht (max_breite).
  4. Deckkraft auf den nächstliegenden Paletteneintrag der Maske abbilden (Palette aus der Datei, nie linear annehmen).
Ein '●' im Text wird durch das Tastensymbol aus der Originalmaske ersetzt.
Dateigröße und alle anderen Daten bleiben unverändert.

Aufruf:  python -I tools/ortstitel.py --out build/de/x3 [--vorschau build/grafik/orte] [--config text/de/grafik_orte.json]
Braucht Pillow (Benutzer-Pakete, siehe docs/grafik.md).
"""
from __future__ import annotations

import argparse
import json
import site
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import LANG, TEXT_DIR  # noqa: E402
import eftex  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:                                   # python -I blendet die Benutzer-Pakete aus
    sys.path.append(site.getusersitepackages())
    from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extracted" / "disc1" / "files"
CONFIG = TEXT_DIR / "grafik_orte.json"
FONTS = Path("C:/Windows/Fonts")
SS = 4                                                # Überabtastung beim Rendern
BUTTON = "●"


def ink_box(idx: list[int], w: int, h: int) -> tuple[int, int, int, int] | None:
    ys = [y for y in range(h) if any(idx[y * w:(y + 1) * w])]
    xs = [x for x in range(w) if any(idx[y * w + x] for y in range(h))]
    return (xs[0], ys[0], xs[-1] + 1, ys[-1] + 1) if ys else None


def button_block(idx: list[int], w: int, h: int) -> tuple[int, int]:
    """Spaltenbereich des Tastensymbols: dichtester Block 10..20 px breit."""
    cols = [sum(1 for y in range(h) if idx[y * w + x]) for x in range(w)]
    segs, start = [], None
    for x, c in enumerate(cols + [0]):
        if c and start is None:
            start = x
        elif not c and start is not None:
            segs.append((start, x))
            start = None
    cand = [(sum(cols[a:b]) / ((b - a) * max(cols[a:b])), a, b) for a, b in segs if 10 <= b - a <= 20]
    if not cand:
        raise SystemExit("Tastensymbol in der Originalmaske nicht gefunden")
    _, a, b = max(cand)
    return a, b


class Setter:
    """Rendert Text in eine Deckkraftfläche (0..1) mit Schriftgröße, Stauchung und Schatten eines Stils."""

    def __init__(self, style: dict):
        self.fontfile = str(FONTS / style["schrift"])
        self.shadow = [tuple(s) for s in style.get("schatten", [])]
        self.shadow_a = style.get("schatten_deckkraft", 0) / 254

    def font(self, size: float) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.fontfile, max(1, round(size * SS)))

    def layer(self, text: str, size: float, sx: float, gap_px: int = 0) -> tuple[Image.Image, int, list[tuple[int, int]]]:
        """-> (Graustufenbild ohne Schatten in Zielauflösung, Grundlinie y, Positionen der ●-Lücken [x0, x1])."""
        f = self.font(size)
        parts = text.split(BUTTON)
        asc, desc = f.getmetrics()
        space = f.getlength(" ")
        widths = [f.getlength(p) for p in parts]
        gap = gap_px * SS / sx if gap_px else 0
        total = sum(widths) + gap * (len(parts) - 1)
        big = Image.new("L", (int(total) + 8 * SS, asc + desc + 8 * SS))
        d = ImageDraw.Draw(big)
        x, holes = 4 * SS, []
        for i, p in enumerate(parts):
            d.text((x, 4 * SS), p, font=f, fill=255)
            x += widths[i]
            if i < len(parts) - 1:
                holes.append((x, x + gap))
                x += gap
        tw = max(1, round(big.width * sx / SS))
        th = max(1, round(big.height / SS))
        small = big.resize((tw, th), Image.LANCZOS)
        baseline = round((4 * SS + asc) / SS)
        holes = [(round(a * sx / SS), round(b * sx / SS)) for a, b in holes]
        del space
        return small, baseline, holes

    def with_shadow(self, body: Image.Image) -> list[list[float]]:
        w, h = body.size
        b = [[body.getpixel((x, y)) / 255 for x in range(w)] for y in range(h)]
        out = [row[:] for row in b]
        if self.shadow:
            for y in range(h):
                for x in range(w):
                    s = max((b[y - dy][x - dx] if y - dy >= 0 and x - dx >= 0 else 0) for dx, dy in self.shadow)
                    s *= self.shadow_a
                    out[y][x] = b[y][x] + s * (1 - b[y][x])
        return out


def bbox(a: list[list[float]], thr: float = 0.04) -> tuple[int, int, int, int] | None:
    ys = [y for y, row in enumerate(a) if any(v > thr for v in row)]
    if not ys:
        return None
    xs = [x for x in range(len(a[0])) if any(a[y][x] > thr for y in ys)]
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def fit(setter: Setter, en: str, box: tuple[int, int, int, int], gap_px: int) -> tuple[float, float, int]:
    """Schriftgröße und Stauchung, mit denen der englische Text den Originalbereich trifft; dazu Grundlinien-Versatz."""
    target_h = box[3] - box[1]
    target_w = box[2] - box[0]
    lo, hi = 4.0, 64.0
    for _ in range(18):
        mid = (lo + hi) / 2
        img, _, _ = setter.layer(en, mid, 1.0, gap_px)
        bb = bbox(setter.with_shadow(img))
        if bb and bb[3] - bb[1] > target_h:
            hi = mid
        else:
            lo = mid
    size = lo
    img, base, _ = setter.layer(en, size, 1.0, gap_px)
    bb = bbox(setter.with_shadow(img))
    sx = target_w / (bb[2] - bb[0])
    img, base, _ = setter.layer(en, size, sx, gap_px)
    bb = bbox(setter.with_shadow(img))
    top_from_base = bb[1] - base                       # Abstand Oberkante Schrift -> Grundlinie (negativ)
    return size, sx, box[1] - top_from_base             # Grundlinie im Zielbild


def make_mask(entry: dict, setter: Setter, idx: list[int], w: int, h: int, max_w: int) -> tuple[list[float], dict]:
    box = ink_box(idx, w, h)
    btn = None
    gap_px = 0
    if BUTTON in entry["en"]:
        btn = button_block(idx, w, h)
        gap_px = btn[1] - btn[0] + 6
    size, sx, base_y = fit(setter, entry["en"], box, gap_px)
    img, base, holes = setter.layer(entry[LANG], size, sx, gap_px)
    a = setter.with_shadow(img)
    bb = bbox(a)
    width = bb[2] - bb[0]
    if width > max_w:                                   # zu breit: zusätzlich stauchen
        sx2 = sx * max_w / width
        img, base, holes = setter.layer(entry[LANG], size, sx2, gap_px)
        a = setter.with_shadow(img)
        bb = bbox(a)
        width = bb[2] - bb[0]
    else:
        sx2 = sx
    cx = (box[0] + box[2]) / 2
    ox = round(cx - width / 2) - bb[0]
    oy = base_y - base
    out = [0.0] * (w * h)
    for y, row in enumerate(a):
        ty = y + oy
        if not 0 <= ty < h:
            if any(v > 0.25 for v in row):
                raise SystemExit(f"{entry['maske']}: Text ragt oben/unten aus der Textur")
            continue
        for x, v in enumerate(row):
            tx = x + ox
            if 0 <= tx < w and v > 0:
                out[ty * w + tx] = max(out[ty * w + tx], v)
            elif v > 0.25:
                raise SystemExit(f"{entry['maske']}: Text ragt seitlich aus der Textur")
    if btn:                                             # Tastensymbol aus dem Original einsetzen
        bw = btn[1] - btn[0]
        for hx0, hx1 in holes:
            x0 = ox + round((hx0 + hx1) / 2 - bw / 2)
            for y in range(h):
                for i in range(bw):
                    v = idx[y * w + btn[0] + i] / 15
                    if v and 0 <= x0 + i < w:
                        out[y * w + x0 + i] = v
    info = {"groesse": round(size, 1), "stauchung": round(sx2, 3), "breite": width,
            "orig": box, "neu": (ox + bb[0], oy + bb[1], ox + bb[2], oy + bb[3])}
    return out, info


def to_indices(alpha: list[float], pal_alpha: list[int]) -> list[int]:
    """Deckkraft 0..1 -> Index mit nächstliegender Palettendeckkraft (Palette aus der Datei)."""
    lut = [min(range(len(pal_alpha)), key=lambda i: abs(pal_alpha[i] - v)) for v in range(256)]
    return [lut[min(255, round(a * 255))] for a in alpha]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="Zielordner (entspricht der Archivwurzel, z. B. build/de/x3)")
    ap.add_argument("--vorschau", help="Ordner für Vorschaubilder")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--src", default=str(SRC))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    src, out = Path(args.src), Path(args.out)
    entries = {e["maske"]: e for e in cfg["eintraege"] if e.get(LANG) and e[LANG] != e["en"]}
    setters = {k: Setter(v) for k, v in cfg["stile"].items()}
    files = sorted(src.glob("ef/esd/us/*.esd")) + sorted(src.glob("ef/map/us/*.esp"))
    if not files:
        raise SystemExit(f"Keine Effekt-Dateien unter {src}/ef – vorher mit x3extract.py entpacken")
    cache: dict[tuple[str, bytes], list[float]] = {}
    previews: dict[str, tuple[list[int], list[float], int, int, dict]] = {}
    changed = 0
    for f in files:
        data = f.read_bytes()
        new = data
        for r in eftex.textures(data):
            e = entries.get(r.name)
            if not e or r.bpp != 4:
                continue
            idx = eftex.indices(data, r)
            key = (r.name, bytes(idx))
            if key not in cache:
                alpha, info = make_mask(e, setters[e["stil"]], idx, r.w, r.h, cfg.get("max_breite", 250))
                cache[key] = alpha
                previews.setdefault(r.name, (idx, alpha, r.w, r.h, info))
            pal = [p[3] for p in eftex.palette(data, r)]
            new = eftex.set_indices(new, r, to_indices(cache[key], pal))
        if new != data:
            if len(new) != len(data):
                raise SystemExit(f"{f.name}: Größe verändert")
            dst = out / f.relative_to(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(new)
            changed += 1
    missing = sorted(set(entries) - set(previews))
    if missing:
        raise SystemExit(f"Masken aus der Konfiguration nicht gefunden: {missing}")
    print(f"Ortseinblendungen: {len(previews)} Masken, {changed} Dateien geschrieben", file=sys.stderr)
    for name, (_, _, _, _, info) in sorted(previews.items()):
        print(f"  {name:24} {entries[name]['de']!r:42} Größe {info['groesse']}, Stauchung {info['stauchung']}, "
              f"Breite {info['breite']}", file=sys.stderr)
    if args.vorschau:
        write_preview(Path(args.vorschau), previews, entries)
    return 0


def write_preview(folder: Path, previews: dict, entries: dict) -> None:
    """Original und neu untereinander, weiß auf dunkelgrau, doppelte Größe."""
    folder.mkdir(parents=True, exist_ok=True)
    tiles = []
    for name in [e for e in entries if e in previews]:
        idx, alpha, w, h, _ = previews[name]
        for vals in ([v / 15 for v in idx], alpha):
            im = Image.new("RGB", (w, h), (40, 44, 52))
            px = im.load()
            for i, v in enumerate(vals):
                if v:
                    c = round(40 + (255 - 40) * v)
                    px[i % w, i // w] = (c, c, c)
            tiles.append(im)
        tiles.append(Image.new("RGB", (256, 6), (90, 30, 30)))
    hgt = sum(t.height for t in tiles)
    sheet = Image.new("RGB", (256, hgt))
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y))
        y += t.height
    sheet = sheet.resize((512, hgt * 2), Image.NEAREST)
    # in handliche Teile schneiden
    part, y0 = 1, 0
    while y0 < sheet.height:
        sheet.crop((0, y0, 512, min(sheet.height, y0 + 1400))).save(folder / f"orte_vorschau_{part}.png")
        y0 += 1400
        part += 1


if __name__ == "__main__":
    sys.exit(main())
