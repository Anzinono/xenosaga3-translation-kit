"""Comparison page of all translated graphics: original (extracted/disc1/files) next to the translation (build/<lang>/x3).

Usage:  python -I tools/grafik_vergleich.py   ->  build/grafik/inventar/vergleich.html (+ images in vergleich/)
Build first (python -I tools/build.py --nur-dateien is enough). Game data – do not commit.
"""
from __future__ import annotations

import html
import io
import json
import shutil
import site
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import LANG, TEXT_DIR  # noqa: E402
try:
    from PIL import Image
except ImportError:
    sys.path.append(site.getusersitepackages())
    from PIL import Image
import eftex  # noqa: E402
import xtx  # noqa: E402
from figurenkarten import bin_jpg_slot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extracted" / "disc1" / "files"
DE = ROOT / "build" / LANG / "x3"
OUT = ROOT / "build" / "grafik" / "inventar"
IMG = OUT / "vergleich"


def save(im: Image.Image, name: str, scale: int = 1) -> str:
    if scale > 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(IMG / name)
    return f"vergleich/{name}"


def titleobj_img(path: Path) -> Image.Image:
    d = path.read_bytes()
    w, _, h, off = xtx.parse(d)
    cv = d[off:off + w * h * 4]
    idx = xtx.unswizzle8(cv, w, 2 * w, 2 * h)
    alphas = [cv[((112 + i // 8) * w + 8 + i % 8) * 4 + 3] for i in range(16)]   # font palette (8, 112)
    im = Image.new("RGB", (144, 56), (235, 235, 235))
    px = im.load()
    for y in range(56):
        for x in range(144):
            v = idx[y * 2 * w + x]
            if 0 < v < 16:
                a = min(255, alphas[v] * 2) / 255
                c = round(235 + (0x2A - 235) * a)
                px[x, y] = (c, c, c)
    return im


def mask_img(data: bytes, r) -> Image.Image:
    idx = eftex.indices(data, r)
    pal = eftex.palette(data, r)
    im = Image.new("RGB", (r.w, r.h), (38, 42, 52))
    px = im.load()
    for i, v in enumerate(idx):
        a = pal[v][3] / 255
        if a:
            c = round(38 + (240 - 38) * a)
            px[i % r.w, i // r.w] = (c, c, c)
    return im


def jpg_of(path: Path) -> Image.Image:
    data = path.read_bytes()
    if path.suffix == ".bin":
        s, e = bin_jpg_slot(data)
        data = data[s:e]
    return Image.open(io.BytesIO(data)).convert("RGB")


def main() -> int:
    if IMG.exists():
        shutil.rmtree(IMG)
    IMG.mkdir(parents=True)
    sections = []

    # title screen
    rows = [("mnu/us/title1.png", save(Image.open(SRC / "mnu/us/title1.png").convert("RGBA"), "title1_en.png"),
             save(Image.open(DE / "mnu/us/title1.png").convert("RGBA"), "title1_de.png"), "credit line added")]
    rows.append(("mnu/us/titleobj.xtx", save(titleobj_img(SRC / "mnu/us/titleobj.xtx"), "titleobj_en.png", 3),
                 save(titleobj_img(DE / "mnu/us/titleobj.xtx"), "titleobj_de.png", 3), "menu items"))
    sections.append(("Title screen", rows, "breit"))

    # location titles: each changed mask once
    cfg = json.loads((TEXT_DIR / "grafik_orte.json").read_text(encoding="utf-8"))
    want = {e["maske"]: e for e in cfg["eintraege"] if e.get(LANG)}
    rows, seen = [], set()
    for f in sorted((DE / "ef").rglob("*.es[dp]")):
        rel = f.relative_to(DE)
        a, b = (SRC / rel).read_bytes(), f.read_bytes()
        for ra, rb in zip(eftex.textures(a), eftex.textures(b)):
            if ra.name in want and ra.name not in seen and eftex.indices(a, ra) != eftex.indices(b, rb):
                seen.add(ra.name)
                n = ra.name[:-4]
                rows.append((f"{rel.as_posix()} · {ra.name}", save(mask_img(a, ra), f"ort_{n}_en.png", 2),
                             save(mask_img(b, rb), f"ort_{n}_de.png", 2), want[ra.name][LANG]))
    sections.append((f"Location titles ({len(rows)})", rows, "breit"))

    # character cards
    k = json.loads((TEXT_DIR / "grafik_figurenkarten.json").read_text(encoding="utf-8"))
    rows = []
    for rel in k["dateien"]:
        n = Path(rel).stem
        rows.append((rel, save(jpg_of(SRC / rel), f"karte_{n}_en.png"), save(jpg_of(DE / rel), f"karte_{n}_de.png"),
                     "height / weight"))
    sections.append((f"Character cards ({len(rows)})", rows, "breit"))

    # database images
    d = json.loads((TEXT_DIR / "grafik_datenbank.json").read_text(encoding="utf-8"))
    rows = []
    for b in d["bilder"]:
        rel = b["datei"]
        n = Path(rel).stem
        rows.append((rel + " (+ copy 1xxx)", save(jpg_of(SRC / rel), f"db_{n}_en.png", 2), save(jpg_of(DE / rel), f"db_{n}_de.png", 2),
                     " / ".join(z[LANG] for z in b["zeilen"])))
    sections.append((f"Database images ({len(rows)})", rows, "breit"))

    body = []
    nav = []
    for i, (title, rows, _) in enumerate(sections):
        nav.append(f'<a href="#s{i}">{html.escape(title)}</a>')
        cards = "".join(
            f'<div class="row"><div class="cap"><b>{html.escape(de)}</b><br><span>{html.escape(name)}</span></div>'
            f'<figure><img src="{a}"><figcaption>Original</figcaption></figure>'
            f'<figure><img src="{b}"><figcaption>Deutsch</figcaption></figure></div>'
            for name, a, b, de in rows)
        body.append(f'<h2 id="s{i}">{html.escape(title)}</h2>{cards}')
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Grafik-Vergleich</title>
<style>
body{{background:#1b1d22;color:#e8e8e8;font:15px/1.4 system-ui,sans-serif;margin:0;padding:16px}}
h1{{font-size:22px}} h2{{font-size:18px;margin-top:30px;border-bottom:1px solid #444;padding-bottom:4px}}
nav a{{color:#6cc3ff;margin-right:14px}}
.row{{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start;background:#262a31;border-radius:6px;padding:8px;margin:8px 0}}
.cap{{width:220px;font-size:13px}} .cap span{{color:#9aa0a8;word-break:break-all}}
figure{{margin:0}} img{{display:block;max-width:100%;image-rendering:pixelated;
background:repeating-conic-gradient(#333 0 25%,#3c3c3c 0 50%) 0 0/16px 16px}}
figcaption{{font-size:12px;color:#9aa0a8}}
</style></head><body><h1>Translated graphics – original and translation</h1><nav>{''.join(nav)}</nav>{''.join(body)}</body></html>"""
    (OUT / "vergleich.html").write_text(page, encoding="utf-8")
    print(f"{sum(len(s[1]) for s in sections)} Vergleiche -> {OUT / 'vergleich.html'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
