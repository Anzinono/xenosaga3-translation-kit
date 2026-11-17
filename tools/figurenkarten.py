"""Figurenkarten auf Deutsch: 'height :' / 'weight :' -> 'Größe:' / 'Gewicht:' (Namen und Werte bleiben).

Dateien: mnu/intm/01-09.jpg und das JPG in mnu/diskchg.bin (Disc-Wechsel; dort folgen ADX-Sprachdaten,
das neue JPG muss in den alten Platz passen und wird mit Nullen aufgefüllt).
Ablauf je Bild:
  1. Beschriftungen per Bildvergleich mit den Vorlagen aus intm/01.jpg finden (auch zwei Figuren je Karte).
  2. Englisches Wort samt Doppelpunkt löschen: die Schriftpixel (Maske aus der Vorlage) werden von außen nach
     innen aus ihren Nachbarn aufgefüllt; Hintergrund und dunkler Schein bleiben erhalten.
  3. Deutsches Wort setzen: Schrift so skaliert, dass das englische Wort Höhe/Breite des Originals trifft,
     gleiche Grundlinie und linke Kante, Farbe aus dem Original; bei Platzmangel vor den Zahlen gestaucht.
  4. Als JPG mit den Quantisierungstabellen und der Unterabtastung des Originals speichern (quality='keep').

Aufruf:  python -I tools/figurenkarten.py --out build/de/x3 [--vorschau build/grafik/figurenkarten]
"""
from __future__ import annotations

import argparse
import io
import json
import site
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import LANG, TEXT_DIR  # noqa: E402

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat
except ImportError:                                   # python -I blendet die Benutzer-Pakete aus
    sys.path.append(site.getusersitepackages())
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extracted" / "disc1" / "files"
CONFIG = TEXT_DIR / "grafik_figurenkarten.json"
FONTS = Path("C:/Windows/Fonts")
SS = 8
# Vorlagen in intm/01.jpg (gemessen): Wort + Doppelpunkt, Zeile ohne Nachbarzeilen
TEMPLATE_FILE = "mnu/intm/01.jpg"
BOXES = {"height": (55, 397, 96, 407), "weight": (55, 407, 96, 417)}
INK = {"height": (56, 398, 89, 406), "weight": (56, 408, 89, 416)}   # Tintenbereich des Worts (ohne Doppelpunkt)
SEARCH_Y = (300, 440)
MATCH_MAX = 33.0        # mittlere Abweichung der Schriftpixel: echte Treffer 0–30 (03: 29,7), Fehltreffer ab 39,9
PAD = 3
OUTLINE = (22, 24, 40)  # dunkler Schriftrand (gemessen auf intm/03.jpg)


# ---------------------------------------------------------------- JPG in diskchg.bin
def bin_jpg_slot(data: bytes) -> tuple[int, int]:
    """(Start, Ende des Platzes) des ersten JPGs: Start = SOI, Ende = nächste 0x40er-Grenze nach EOI."""
    s = data.index(b"\xff\xd8\xff")
    e = data.index(b"\xff\xd9", s)
    # EOI des Hauptbilds: das letzte FFD9 vor dem nächsten Datenblock (EXIF-Vorschaubilder liegen davor)
    nxt = struct.unpack_from("<I", data, 4)[0]
    e = data.rfind(b"\xff\xd9", s, nxt + 0x40) + 2
    return s, (e + 0x3F) & ~0x3F


# ---------------------------------------------------------------- Suche
def text_mask(tpl: Image.Image) -> Image.Image:
    """Schriftpixel der Vorlage (hell auf schwarz), 1 px erweitert."""
    return tpl.point(lambda v: 255 if v > 60 else 0).filter(ImageFilter.MaxFilter(3))


def find_labels(gray: Image.Image, templates: dict[str, Image.Image]) -> list[tuple[str, int, int]]:
    """Sucht 'height' (nur Schriftpixel + Rand werden verglichen, der Hintergrund ist je Karte verschieden).
    'weight' steht immer genau 10 px darunter (in allen Karten so)."""
    tpl = templates["height"]
    tw, th = tpl.size
    mask = text_mask(tpl)
    cands = []
    for y in range(SEARCH_Y[0], SEARCH_Y[1] - th):
        for x in range(0, gray.width - tw):
            d = ImageStat.Stat(ImageChops.difference(gray.crop((x, y, x + tw, y + th)), tpl), mask).mean[0]
            if d < MATCH_MAX:
                cands.append((d, x, y))
    cands.sort()
    hits: list[tuple[str, int, int]] = []
    for d, x, y in cands:                                 # nicht-maximale Unterdrückung
        if all(abs(x - hx) > 20 or abs(y - hy) > 14 for _, hx, hy in hits):
            hits.append(("height", x, y))
    dy = BOXES["weight"][1] - BOXES["height"][1]
    return hits + [("weight", x, y + dy) for _, x, y in hits]


# ---------------------------------------------------------------- Setzen
class Setter:
    def __init__(self, fontfile: str, wf: float, variante: str | None = None):
        self.fontfile = str(FONTS / fontfile)
        self.wf = wf
        self.variante = variante

    def render(self, text: str, size: float, sx: float) -> tuple[Image.Image, int]:
        f = ImageFont.truetype(self.fontfile, max(1, round(size * SS)))
        if self.variante:
            f.set_variation_by_name(self.variante)
        asc, desc = f.getmetrics()
        w = int(f.getlength(text)) + 4 * SS
        big = Image.new("L", (w, asc + desc + 4 * SS))
        ImageDraw.Draw(big).text((2 * SS, 2 * SS), text, font=f, fill=255)
        small = big.resize((max(1, round(w * sx / SS)), round(big.height / SS)), Image.LANCZOS)
        return small, round((2 * SS + asc) / SS)

    def fit(self, en: str, ink: tuple[int, int, int, int]) -> tuple[float, float, int]:
        th, tw = ink[3] - ink[1], ink[2] - ink[0]
        lo, hi = 3.0, 40.0
        for _ in range(16):
            mid = (lo + hi) / 2
            img, _ = self.render(en, mid, self.wf)
            bb = img.point(lambda v: 255 if v > 40 else 0).getbbox()
            if bb and bb[3] - bb[1] > th:
                hi = mid
            else:
                lo = mid
        img, base = self.render(en, lo, self.wf)
        bb = img.point(lambda v: 255 if v > 40 else 0).getbbox()
        sx = self.wf * tw / (bb[2] - bb[0])
        img, base = self.render(en, lo, sx)
        bb = img.point(lambda v: 255 if v > 40 else 0).getbbox()
        return lo, sx, ink[1] - (bb[1] - base)          # Grundlinie im Zielbild (für Wort an y=ink[1])


def erase(im: Image.Image, box: tuple[int, int, int, int], mask: Image.Image) -> None:
    """Schriftpixel (mask) aus den Nachbarpixeln auffüllen, von außen nach innen. Hintergrund und
    dunkler Schein um die Schrift bleiben so erhalten."""
    x0, y0 = box[0], box[1]
    px = im.load()
    todo = {(x0 + x, y0 + y) for y in range(mask.height) for x in range(mask.width) if mask.getpixel((x, y))}
    while todo:
        done = {}
        for (x, y) in todo:
            nb = [px[x + i, y + j] for i in (-1, 0, 1) for j in (-1, 0, 1)
                  if (i or j) and (x + i, y + j) not in todo and 0 <= x + i < im.width and 0 <= y + j < im.height]
            if nb:
                done[(x, y)] = tuple(round(sum(c[k] for c in nb) / len(nb)) for k in range(3))
        if not done:
            break
        for xy, c in done.items():
            px[xy] = c
        todo -= set(done)


def text_color(im: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    crop = im.crop(box)
    px = [crop.getpixel((x, y)) for y in range(crop.height) for x in range(crop.width)]
    px = [p for p in px if sum(p) > 450]
    px.sort(key=sum)
    top = px[3 * len(px) // 4:] or [(210, 210, 215)]
    return tuple(round(sum(p[i] for p in top) / len(top)) for i in range(3))


def value_start(gray: Image.Image, x: int, y0: int, y1: int) -> int:
    for xx in range(x, gray.width):
        if max(gray.getpixel((xx, yy)) for yy in range(y0, y1)) > 90:
            return xx
    return gray.width


def process(im: Image.Image, cfg: dict, setter: Setter, templates: dict, fits: dict) -> list[str]:
    # Löschmaske: Schrift + ihr dunkler Rand (auf intm/03.jpg ≈ 2 px), dafür 3 px Rand um die Box
    masks = {}
    for w, t in templates.items():
        m = Image.new("L", (t.width + 2 * PAD, t.height + 2 * PAD))
        m.paste(text_mask(t), (PAD, PAD))
        masks[w] = m.filter(ImageFilter.MaxFilter(5))
    gray = im.convert("L")
    hits = find_labels(gray, templates)
    notes = []
    jobs = []
    for word, x, y in sorted(hits, key=lambda h: (h[1], h[2])):      # erst alle alten Wörter löschen …
        bx0, by0, bx1, by1 = BOXES[word]
        box = (x, y, x + bx1 - bx0, y + by1 - by0)
        jobs.append((word, x, y, text_color(im, box), value_start(gray, box[2], box[1], box[3]) - 3))
        erase(im, (box[0] - PAD, box[1] - PAD), masks[word])
    for word, x, y, color, limit in jobs:                                # … dann die neuen setzen
        dx, dy = x - BOXES[word][0], y - BOXES[word][1]
        size, sx, base = fits[word]
        de = cfg["woerter"][word]
        img, b = setter.render(de, size, sx)
        bb = img.getbbox()
        if INK[word][0] + dx + (bb[2] - bb[0]) > limit:
            sx2 = sx * (limit - INK[word][0] - dx) / (bb[2] - bb[0])
            img, b = setter.render(de, size, sx2)
            bb = img.getbbox()
        ox = INK[word][0] + dx - bb[0]
        oy = base + dy - b
        # dunkler Rand wie im Original (auf hellem Hintergrund sichtbar, auf schwarzem unsichtbar)
        # Schrift schärfen (Kanten steiler, wie die pixelgenaue Originalschrift)
        img = img.point(lambda v: max(0, min(255, round((v - 25) * 1.3))))
        # dunkler Rand: 1 px kräftig, 2. px schwächer, ohne Weichzeichnen
        halo = ImageChops.lighter(img.filter(ImageFilter.MaxFilter(3)),
                                  img.filter(ImageFilter.MaxFilter(5)).point(lambda v: round(v * 0.55)))
        im.paste(Image.new("RGB", img.size, OUTLINE), (ox, oy), halo)
        im.paste(Image.new("RGB", img.size, color), (ox, oy), img)
        notes.append(f"{word}@({x},{y})")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="Zielordner (Archivwurzel, z. B. build/de/x3)")
    ap.add_argument("--vorschau", help="Ordner für Vorschaubilder")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--src", default=str(SRC))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not all(str(v).strip() for v in cfg["woerter"].values()):
        print("Figurenkarten: Wörter nicht (vollständig) übersetzt – Originale bleiben", file=sys.stderr)
        return 0
    src, out = Path(args.src), Path(args.out)
    tim = Image.open(src / TEMPLATE_FILE).convert("L")
    templates = {w: tim.crop(b) for w, b in BOXES.items()}
    setter = Setter(cfg["schrift"], cfg.get("breite_faktor", 1.0), cfg.get("variante"))
    fits = {w: setter.fit(w, INK[w]) for w in BOXES}
    for rel in cfg["dateien"]:
        f = src / rel
        data = f.read_bytes()
        if f.suffix.lower() == ".bin":
            s, e = bin_jpg_slot(data)
            jpg = data[s:e]
        else:
            jpg = data
        im = Image.open(io.BytesIO(jpg))
        im.load()
        orig = im.copy()
        notes = process(im, cfg, setter, templates, fits)
        if len(notes) < 2:
            raise SystemExit(f"{rel}: Beschriftung nicht gefunden ({notes})")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality="keep")
        new = buf.getvalue()
        if f.suffix.lower() == ".bin":
            if len(new) > e - s:
                raise SystemExit(f"{rel}: neues JPG ({len(new)} Byte) passt nicht in den Platz ({e - s} Byte)")
            new = data[:s] + new + bytes(e - s - len(new)) + data[e:]
            assert len(new) == len(data)
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(new)
        print(f"{rel}: {', '.join(notes)}, {len(jpg)} -> {len(buf.getvalue())} Byte", file=sys.stderr)
        if args.vorschau:
            pv = Path(args.vorschau)
            pv.mkdir(parents=True, exist_ok=True)
            y0 = 370
            a = orig.crop((0, y0, 512, 425)).resize((1024, 110), Image.NEAREST)
            b = im.crop((0, y0, 512, 425)).resize((1024, 110), Image.NEAREST)
            sheet = Image.new("RGB", (1024, 224), (90, 30, 30))
            sheet.paste(a, (0, 0))
            sheet.paste(b, (0, 114))
            sheet.save(pv / (rel.replace("/", "_") + ".png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
