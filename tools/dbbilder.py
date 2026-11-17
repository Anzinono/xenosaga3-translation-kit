"""Translate database images (jpg/us/dtimg_*.jpg) that contain English text.

For each text line in text/<lang>/grafik_datenbank.json:
  1. Detect text pixels in the given box by contrast to the local background (median 9x9).
  2. Fill these pixels (grown by 1 px) from their neighbours (like tools/figurenkarten.py).
  3. Fit the English text with the substitute font to the height/width of the original, set the translation with the same
     values (left/right/centred like the original), colour taken from the original; 'sperren' = letter spacing
     instead of condensing (for letter-spaced titles like "R E A L I A N").
  4. Save the JPG with the original's tables (quality="keep"). Identical copies dtimg_1xxx get the same image.

Usage:  python -I tools/dbbilder.py --out build/<lang>/x3 [--vorschau build/grafik/datenbank]
"""
from __future__ import annotations

import argparse
import io
import json
import site
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import LANG, TEXT_DIR  # noqa: E402
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:                                   # python -I hides user site packages
    sys.path.append(site.getusersitepackages())
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
from figurenkarten import erase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extracted" / "disc1" / "files"
CONFIG = TEXT_DIR / "grafik_datenbank.json"
FONTS = Path("C:/Windows/Fonts")
SS = 8
CONTRAST = 32


def text_mask(gray: Image.Image, box: list[int], bright: bool, contrast: int = CONTRAST) -> Image.Image:
    """Mask (size of the box) of the pixels that clearly stand out from the local background."""
    x0, y0, x1, y1 = box
    pad = 6
    big = gray.crop((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    bg = big.filter(ImageFilter.MedianFilter(9))
    out = Image.new("L", (x1 - x0, y1 - y0))
    for y in range(y1 - y0):
        for x in range(x1 - x0):
            v, b = big.getpixel((x + pad, y + pad)), bg.getpixel((x + pad, y + pad))
            if (v - b if bright else b - v) > contrast:
                out.putpixel((x, y), 255)
    return out


def render(text: str, fontfile: str, size: float, sx: float, gap: float | None = None) -> tuple[Image.Image, int]:
    """Grayscale opacity at target resolution + baseline. gap: fixed letter spacing in target pixels (sperren)."""
    f = ImageFont.truetype(str(FONTS / fontfile), max(1, round(size * SS)))
    asc, desc = f.getmetrics()
    if gap is None:
        w = int(f.getlength(text)) + 4 * SS
        big = Image.new("L", (w, asc + desc + 4 * SS))
        ImageDraw.Draw(big).text((2 * SS, 2 * SS), text, font=f, fill=255)
    else:
        adv = [f.getbbox(c)[2] - f.getbbox(c)[0] for c in text]
        w = int(sum(adv) + gap * SS / sx * (len(text) - 1)) + 4 * SS
        big = Image.new("L", (w, asc + desc + 4 * SS))
        d = ImageDraw.Draw(big)
        x = 2 * SS
        for c, a in zip(text, adv):
            d.text((x - f.getbbox(c)[0], 2 * SS), c, font=f, fill=255)
            x += a + gap * SS / sx
    small = big.resize((max(1, round(big.width * sx / SS)), round(big.height / SS)), Image.LANCZOS)
    return small, round((2 * SS + asc) / SS)


def ink(img: Image.Image) -> tuple[int, int, int, int]:
    return img.point(lambda v: 255 if v > 60 else 0).getbbox()


def fit(en: str, fontfile: str, wf: float, target: tuple[int, int, int, int], sperren: bool,
        size: float | None = None, sx: float | None = None):
    """Size/condensing (or letter spacing) with which the English text matches the target box.
    size/sx from the configuration ('groesse', 'stauchung') are used instead of measured."""
    th, tw = target[3] - target[1], target[2] - target[0]
    probe = en.replace(" ", "") if sperren else en
    if size is not None:
        if sperren:
            bb = ink(render(probe, fontfile, size, wf, gap=0)[0])
            return size, wf, (tw - (bb[2] - bb[0])) / max(1, len(probe) - 1)
        if sx is not None:
            return size, sx, None
        bb = ink(render(en, fontfile, size, wf)[0])
        return size, wf * tw / (bb[2] - bb[0]), None
    lo, hi = 3.0, 60.0
    for _ in range(16):
        mid = (lo + hi) / 2
        bb = ink(render(probe, fontfile, mid, wf)[0])
        if bb and bb[3] - bb[1] > th:
            hi = mid
        else:
            lo = mid
    if sperren:
        img, _ = render(probe, fontfile, lo, wf, gap=0)
        bb = ink(img)
        n = len(probe)
        gap = (tw - (bb[2] - bb[0])) / max(1, n - 1)        # spacing in the original
        return lo, wf, gap
    bb = ink(render(en, fontfile, lo, wf)[0])
    return lo, wf * tw / (bb[2] - bb[0]), None


def erase_columns(im: Image.Image, box: list[int]) -> None:
    """Erase a rectangle: per column, blend vertically between the row above and below
    (for text on a busy but vertically structured background)."""
    x0, y0, x1, y1 = box
    px = im.load()
    for x in range(x0, x1):
        a, b = px[x, y0 - 1], px[x, y1]
        for y in range(y0, y1):
            t = (y - y0 + 1) / (y1 - y0 + 1)
            px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def measure(im: Image.Image, z: dict) -> dict:
    """Text mask, target box and colour of the original line (on the unchanged image)."""
    gray = im.convert("L")
    box = z["box"]
    m = text_mask(gray, box, z["hell"], z.get("kontrast", CONTRAST))
    rows = [sum(1 for x in range(m.width) if m.getpixel((x, y))) for y in range(m.height)]
    if not max(rows):
        raise SystemExit(f"{z['en']!r}: no text in box {box}")
    # contiguous block of rows around the densest row (noise/neighbouring lines stay out)
    pk = rows.index(max(rows))
    y0 = pk
    while y0 > 0 and rows[y0 - 1] >= 2:
        y0 -= 1
    y1 = pk
    while y1 < len(rows) - 1 and rows[y1 + 1] >= 2:
        y1 += 1
    cols = [x for x in range(m.width) if any(m.getpixel((x, y)) for y in range(y0, y1 + 1))]
    sdx, sdy = z.get("schatten", (0, 0))
    target = (box[0] + cols[0], box[1] + y0, box[0] + cols[-1] + 1 - sdx, box[1] + y1 + 1 - sdy)
    pts = [(x, y) for y in range(y0, y1 + 1) for x in range(m.width) if m.getpixel((x, y))]
    cl = sorted((im.getpixel((box[0] + x, box[1] + y)) for x, y in pts), key=sum, reverse=z["hell"])
    top = cl[:max(1, len(cl) // 2)]
    color = tuple(round(sum(c[i] for c in top) / len(top)) for i in range(3))
    return {"mask": m, "target": target, "color": color}


def draw_line(im: Image.Image, z: dict, meas: dict) -> str:
    target, color, box = meas["target"], meas["color"], z["box"]
    font = z["schrift"]
    wf = z.get("breite_faktor", 1.0)
    sperren = z.get("sperren", False)
    size, sx, gap = fit(z["en"], font, wf, target, sperren, z.get("groesse"), z.get("stauchung"))
    text = z[LANG]
    img, base = render(text, font, size, sx, gap)
    bb = ink(img)
    maxw = box[2] - box[0]
    if sperren and bb[2] - bb[0] > maxw:                     # reduce the spacing until it fits
        gap = max(0.0, gap - (bb[2] - bb[0] - maxw) / max(1, len(text) - 1))
        img, base = render(text, font, size, sx, gap)
        bb = ink(img)
    elif not sperren and bb[2] - bb[0] > maxw:
        sx *= maxw / (bb[2] - bb[0])
        img, base = render(text, font, size, sx, gap)
        bb = ink(img)
    # baseline as for the English text
    probe = z["en"].replace(" ", "") if sperren else z["en"]
    en_img, en_base = render(probe, font, size, wf if sperren else sx, gap)
    base_y = target[1] - (ink(en_img)[1] - en_base)
    al = z.get("ausrichtung", "links")
    w = bb[2] - bb[0]
    x = target[0] if al == "links" else target[2] - w if al == "rechts" else round((target[0] + target[2] - w) / 2)
    ox, oy = x - bb[0], base_y - base
    if z.get("schatten"):
        dx, dy = z["schatten"]
        sh = img.filter(ImageFilter.GaussianBlur(0.8)).point(lambda v: round(v * 0.45))
        im.paste(Image.new("RGB", img.size, (0, 0, 0)), (ox + dx, oy + dy), sh)
    im.paste(Image.new("RGB", img.size, color), (ox, oy), img)
    return f"{z[LANG]!r} size {size:.1f}" + (f", spacing {gap:.1f}" if gap is not None else "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--vorschau")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--src", default=str(SRC))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    src, out = Path(args.src), Path(args.out)
    pv = []
    for b in cfg["bilder"]:
        if not all(str(z.get(LANG, "")).strip() for z in b["zeilen"]):
            continue                                               # untranslated: original stays
        f = src / b["datei"]
        data = f.read_bytes()
        im = Image.open(io.BytesIO(data))
        im.load()
        orig = im.copy()
        meas = [measure(orig, z) for z in b["zeilen"]]           # measure everything first …
        if "loeschbox" in b:                                        # … then erase: whole block column by column …
            erase_columns(im, b["loeschbox"])
        else:                                                       # … or only the text pixels …
            for z, mz in zip(b["zeilen"], meas):
                erase(im, (z["box"][0], z["box"][1]), mz["mask"].filter(ImageFilter.MaxFilter(z.get("loeschrand", 5 if z.get("schatten") else 3))))
        notes = [draw_line(im, z, mz) for z, mz in zip(b["zeilen"], meas)]   # … then draw anew
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality="keep")
        targets = [b["datei"]]
        twin = f.with_name(f.name.replace("dtimg_0", "dtimg_1"))
        if twin != f and twin.exists() and twin.read_bytes() == data:
            targets.append(twin.relative_to(src).as_posix())
        for t in targets:
            dst = out / t
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(buf.getvalue())
        print(f"{' + '.join(targets)}: {'; '.join(notes)}", file=sys.stderr)
        pv.append((orig, im))
    if args.vorschau:
        p = Path(args.vorschau)
        p.mkdir(parents=True, exist_ok=True)
        w, h = pv[0][0].size
        sheet = Image.new("RGB", (w * 4 + 6, (h * 2 + 6) * len(pv)), (90, 30, 30))
        for i, (a, b) in enumerate(pv):
            sheet.paste(a.resize((w * 2, h * 2), Image.LANCZOS), (0, i * (h * 2 + 6)))
            sheet.paste(b.resize((w * 2, h * 2), Image.LANCZOS), (w * 2 + 6, i * (h * 2 + 6)))
        sheet.save(p / "datenbank_vorschau.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
