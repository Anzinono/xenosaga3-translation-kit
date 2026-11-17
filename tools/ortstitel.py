"""Creates the translated location titles (effect files ef/esd/us/*.esd, ef/map/us/*.esp).

The lettering is stored as 4-bit opacity masks '<name>-a.bmp' in the effect containers (docs/grafik.md).
For each mask in text/<lang>/grafik_orte.json:
  1. Measure the original (area with text).
  2. Scale the English original text with the substitute font so that it matches the original's height and width
     (font size + horizontal condensing).
  3. Set the translated text with the same values, on the same baseline and centre; text that is too wide is
     condensed further (max_breite).
  4. Map the opacity to the nearest palette entry of the mask (palette from the file, never assume it is linear).
A '●' in the text is replaced by the button symbol from the original mask.
File size and all other data stay unchanged.

Usage:  python -I tools/ortstitel.py --out build/<lang>/x3 [--vorschau build/grafik/orte] [--config text/<lang>/grafik_orte.json]
Needs Pillow (user site packages, see docs/grafik.md).
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
except ImportError:                                   # python -I hides user site packages
    sys.path.append(site.getusersitepackages())
    from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extracted" / "disc1" / "files"
CONFIG = TEXT_DIR / "grafik_orte.json"
FONTS = Path("C:/Windows/Fonts")
SS = 4                                                # supersampling when rendering
BUTTON = "●"


def ink_box(idx: list[int], w: int, h: int) -> tuple[int, int, int, int] | None:
    ys = [y for y in range(h) if any(idx[y * w:(y + 1) * w])]
    xs = [x for x in range(w) if any(idx[y * w + x] for y in range(h))]
    return (xs[0], ys[0], xs[-1] + 1, ys[-1] + 1) if ys else None


def button_block(idx: list[int], w: int, h: int) -> tuple[int, int]:
    """Column range of the button symbol: densest block 10..20 px wide."""
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
        raise SystemExit("button symbol not found in the original mask")
    _, a, b = max(cand)
    return a, b


class Setter:
    """Renders text into an opacity area (0..1) with font size, condensing and shadow of a style."""

    def __init__(self, style: dict):
        self.fontfile = str(FONTS / style["schrift"])
        self.shadow = [tuple(s) for s in style.get("schatten", [])]
        self.shadow_a = style.get("schatten_deckkraft", 0) / 254

    def font(self, size: float) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.fontfile, max(1, round(size * SS)))

    def layer(self, text: str, size: float, sx: float, gap_px: int = 0) -> tuple[Image.Image, int, list[tuple[int, int]]]:
        """-> (grayscale image without shadow at target resolution, baseline y, positions of the ● gaps [x0, x1])."""
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
    """Font size and condensing with which the English text matches the original area; plus baseline offset."""
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
    top_from_base = bb[1] - base                       # distance top of text -> baseline (negative)
    return size, sx, box[1] - top_from_base             # baseline in the target image


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
    if width > max_w:                                   # too wide: condense further
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
                raise SystemExit(f"{entry['maske']}: text sticks out of the texture at the top/bottom")
            continue
        for x, v in enumerate(row):
            tx = x + ox
            if 0 <= tx < w and v > 0:
                out[ty * w + tx] = max(out[ty * w + tx], v)
            elif v > 0.25:
                raise SystemExit(f"{entry['maske']}: text sticks out of the texture at the side")
    if btn:                                             # insert the button symbol from the original
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
    """Opacity 0..1 -> index with the nearest palette opacity (palette from the file)."""
    lut = [min(range(len(pal_alpha)), key=lambda i: abs(pal_alpha[i] - v)) for v in range(256)]
    return [lut[min(255, round(a * 255))] for a in alpha]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="target folder (corresponds to the archive root, e.g. build/<lang>/x3)")
    ap.add_argument("--vorschau", help="folder for preview images")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--src", default=str(SRC))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    src, out = Path(args.src), Path(args.out)
    entries = {e["maske"]: e for e in cfg["eintraege"] if e.get(LANG) and e[LANG] != e["en"]}
    setters = {k: Setter(v) for k, v in cfg["stile"].items()}
    files = sorted(src.glob("ef/esd/us/*.esd")) + sorted(src.glob("ef/map/us/*.esp"))
    if not files:
        raise SystemExit(f"No effect files under {src}/ef – extract them with x3extract.py first")
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
                raise SystemExit(f"{f.name}: size changed")
            dst = out / f.relative_to(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(new)
            changed += 1
    missing = sorted(set(entries) - set(previews))
    if missing:
        raise SystemExit(f"Masks from the configuration not found: {missing}")
    print(f"Location titles: {len(previews)} masks, {changed} files written", file=sys.stderr)
    for name, (_, _, _, _, info) in sorted(previews.items()):
        print(f"  {name:24} {entries[name][LANG]!r:42} size {info['groesse']}, condensing {info['stauchung']}, "
              f"width {info['breite']}", file=sys.stderr)
    if args.vorschau:
        write_preview(Path(args.vorschau), previews, entries)
    return 0


def write_preview(folder: Path, previews: dict, entries: dict) -> None:
    """Original and new one below the other, white on dark grey, double size."""
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
    # cut into handy parts
    part, y0 = 1, 0
    while y0 < sheet.height:
        sheet.crop((0, y0, 512, min(sheet.height, y0 + 1400))).save(folder / f"orte_vorschau_{part}.png")
        y0 += 1400
        part += 1


if __name__ == "__main__":
    sys.exit(main())
