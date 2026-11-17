"""Bestandsaufnahme aller Spielgrafiken: exportiert sie als PNG/JPG und baut eine Übersichtsseite.

Quelle: extracted/disc1/files (vorher mit x3extract.py entpacken, siehe docs/grafik.md)
Ziel:   build/grafik/inventar/ (index.html + Bilder + inventar.csv); Spieldaten, nicht ins Git.

Unterstützt: .png/.jpg/.bmp (Kopie), .xtx (Format 0x08), .tm2, Effekt-Container .esd/.esp
(eingebettete Texturen), .bin mit eingebetteten JPGs (credit.bin, diskchg.bin).

Aufruf:  python -I tools/grafik_inventar.py [--src extracted/disc1/files] [--out build/grafik/inventar]
"""
from __future__ import annotations

import argparse
import csv
import html
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eftex  # noqa: E402
import tm2  # noqa: E402
from xtx import clut_at, find_cluts, parse as xtx_parse, unswizzle8, write_png  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Gruppen in der Übersicht: (Titel, Muster relativ zur Quelle, Beschreibung)
GROUPS = [
    ("Menü (sprachabhängig)", ["mnu/us/*.png", "mnu/us/*.xtx", "mnu/us/*.jpg"], "Titel, Fenster, Synopsis, Game Over"),
    ("Menü (allgemein)", ["mnu/*.png", "mnu/*.xtx", "mnu/*.bin"], "Steuerung, Item-/Segment-Bilder, Abspann, Disc-Wechsel"),
    ("Rückblick-Logos", ["mnu/pse/us/*.tm2", "mnu/pse/*.tm2", "mnu/pse/*.jpg"], "Episode I/II, Hintergrund"),
    ("Rückblick Episode I", ["mnu/pse/EP1/*.jpg"], ""),
    ("Rückblick Episode II", ["mnu/pse/EP2/*.jpg"], ""),
    ("Synopsis", ["mnu/syno/*.jpg"], ""),
    ("Zwischenbilder", ["mnu/intm/*.jpg", "mnu/umn/*.jpg"], ""),
    ("Minispiel", ["mg1/us/*.xtx"], "HaKox"),
    ("Film", ["mov/us/*.png"], ""),
    ("Ortseinblendungen (Effekte)", ["ef/esd/us/*.esd", "ef/map/us/*.esp", "ef/esp/us/*.esp"], "Texturen in Effekt-Containern"),
    ("Kampf-Porträts", ["bat/bat_face/*.jpg"], ""),
    ("Datenbankbilder", ["jpg/us/*.jpg"], "dtimg_*"),
    ("Weitere Bilder", ["jpg/*.jpg"], "mcimg_*"),
]


def export_xtx(src: Path, dst: Path) -> list[tuple[Path, str]]:
    data = src.read_bytes()
    w, fmt, h, off = xtx_parse(data)
    if fmt != 0x08:
        return []
    canvas = data[off:off + w * h * 4]
    ow, oh = w * 2, h * 2
    try:
        idx = unswizzle8(canvas, w, ow, oh)
    except IndexError:                        # Breite passt nicht zum Swizzle -> als lineares RGBA zeigen
        rows = [bytes(v if i % 4 != 3 else min(v * 2, 255) for i, v in enumerate(canvas[y * w * 4:(y + 1) * w * 4]))
                for y in range(h)]
        write_png(dst.with_suffix(".png"), w, h, rows, rgba=True)
        return [(dst.with_suffix(".png"), f"{w}×{h}, als lineares RGBA gelesen (Swizzle passt nicht)")]
    cands = find_cluts(canvas, w, h)
    if cands:
        pal = clut_at(canvas, w, *cands[0])
        rows = [b"".join(bytes(pal[i]) for i in idx[y * ow:(y + 1) * ow]) for y in range(oh)]
        write_png(dst.with_suffix(".png"), ow, oh, rows, rgba=True)
        note = f"{ow}×{oh}, 8 Bit, Palette {cands[0]}"
    else:
        mx = max(idx) or 1
        rows = [bytes(min(255, v * 255 // mx) for v in idx[y * ow:(y + 1) * ow]) for y in range(oh)]
        write_png(dst.with_suffix(".png"), ow, oh, rows)
        note = f"{ow}×{oh}, 8 Bit, Indexbild (Graustufen, Palette nicht gefunden)"
    return [(dst.with_suffix(".png"), note)]


def export_tm2(src: Path, dst: Path) -> list[tuple[Path, str]]:
    data = src.read_bytes()
    res = []
    for n, pic in enumerate(tm2.parse(data)):
        p = dst.with_name(f"{dst.stem}{'_' + str(n) if n else ''}.png")
        write_png(p, pic.w, pic.h, tm2.to_rgba(data, pic), rgba=True)
        res.append((p, f"{pic.w}×{pic.h}, Typ {pic.img_type}"))
    return res


EF_SEEN: dict[bytes, Path] = {}


def export_ef(src: Path, dst: Path) -> list[tuple[Path, str]]:
    """Texte stecken in den Deckkraftmasken '<name>-a.bmp' (Farbe kommt aus dem Bild davor, z. B. moji.bmp).
    Gezeigt wird die Maske als Graustufen (weiß = deckend); gleiche Masken nur einmal."""
    data = src.read_bytes()
    res = []
    for n, r in enumerate(eftex.textures(data)):
        nm = r.name.lower()
        if not nm.endswith("-a.bmp") or r.w < 128 or nm.startswith("telopbg"):
            continue
        idx = bytes(eftex.indices(data, r))
        if idx in EF_SEEN:
            continue
        p = dst.with_name(f"{dst.stem}_{n:02d}_{r.name[:-4]}.png")
        EF_SEEN[idx] = p
        mx = (1 << r.bpp) - 1
        write_png(p, r.w, r.h, [bytes(v * 255 // mx for v in idx[y * r.w:(y + 1) * r.w]) for y in range(r.h)])
        res.append((p, f"Maske {r.name} {r.w}×{r.h}, {r.bpp} Bit, @{r.off:#x}"))
    return res


def export_bin_jpgs(src: Path, dst: Path) -> list[tuple[Path, str]]:
    data = src.read_bytes()
    starts = [i for i in range(0, len(data) - 4, 0x10) if data[i:i + 3] == b"\xff\xd8\xff"]
    res = []
    for n, s in enumerate(starts):
        e = data.find(b"\xff\xd9", s)
        nxt = starts[n + 1] if n + 1 < len(starts) else len(data)
        e = data.rfind(b"\xff\xd9", s, nxt) + 2
        p = dst.with_name(f"{dst.stem}_{n}.jpg")
        p.write_bytes(data[s:e])
        res.append((p, f"eingebettetes JPG {n} @{s:#x}"))
    return res


def export_one(src: Path, rel: str, out: Path) -> list[tuple[Path, str]]:
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower()
    if ext in (".png", ".jpg", ".bmp"):
        shutil.copyfile(src, dst)
        return [(dst, "")]
    if ext == ".xtx":
        return export_xtx(src, dst)
    if ext == ".tm2":
        return export_tm2(src, dst)
    if ext in (".esd", ".esp"):
        return export_ef(src, dst)
    if ext == ".bin":
        return export_bin_jpgs(src, dst)
    return []


def img_size(p: Path) -> str:
    b = p.read_bytes()[:64 * 1024]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "%d×%d" % struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return f"{w}×{h}"
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return ""


PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Grafik-Inventar</title>
<style>
:root{{--bg:#1b1d22;--card:#262a31;--fg:#e8e8e8;--mut:#9aa0a8;--acc:#6cc3ff}}
body{{background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;margin:0;padding:16px}}
h1{{font-size:20px}} h2{{font-size:17px;margin-top:28px;border-bottom:1px solid #444;padding-bottom:4px}}
nav a{{color:var(--acc);margin-right:12px;white-space:nowrap}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--min,200px),1fr));gap:10px}}
.c{{background:var(--card);border-radius:6px;padding:6px;overflow:hidden}}
.c img{{max-width:100%;display:block;margin:auto;background:repeating-conic-gradient(#333 0 25%,#3c3c3c 0 50%) 0 0/16px 16px;image-rendering:pixelated}}
.c div{{font-size:12px;color:var(--mut);word-break:break-all}} .c b{{color:var(--fg);font-weight:600}}
</style></head><body><h1>Grafik-Inventar Xenosaga III (Disc 1)</h1>
<p>{total} Bilder. Klick auf ein Bild öffnet es in Originalgröße.</p><nav>{nav}</nav>{body}</body></html>"""


# Kontaktbogen: kontakt.html?pfad=jpg/us/&von=0&n=100&w=160 (kleine Vorschaubilder einer Gruppe)
KONTAKT = r"""<!doctype html><meta charset="utf-8"><title>Kontaktbogen</title>
<style>body{background:#000;margin:0;display:flex;flex-wrap:wrap;gap:2px;font:11px sans-serif}
figure{margin:0;position:relative}img{width:var(--w,160px);display:block}
figcaption{position:absolute;left:0;top:0;background:#000c;color:#ff0;padding:0 3px}</style>
<script>
const q=new URLSearchParams(location.search);document.documentElement.style.setProperty('--w',(q.get('w')||160)+'px');
fetch('inventar.csv').then(r=>r.text()).then(t=>{const rows=t.trim().split('\n').slice(1).map(l=>l.split(';'));
const from=+(q.get('von')||0),n=+(q.get('n')||100);
rows.filter(r=>r[1].startsWith(q.get('pfad')||'')).slice(from,from+n).forEach(r=>{const f=document.createElement('figure');
const i=document.createElement('img');i.src=r[2];i.title=r[2];const c=document.createElement('figcaption');
c.textContent=r[2].split('/').pop().replace(/\.\w+$/,'').replace(/^dtimg_|^mcimg_/,'');f.append(i,c);document.body.append(f)})});
</script>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(ROOT / "extracted" / "disc1" / "files"))
    ap.add_argument("--out", default=str(ROOT / "build" / "grafik" / "inventar"))
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():                 # Inhalt leeren (Ordner selbst kann offen sein)
        if old.is_dir():
            shutil.rmtree(old)
        else:
            old.unlink()
    rows, nav, body, total, seen = [], [], [], 0, set()
    for gi, (title, patterns, desc) in enumerate(GROUPS):
        items = []
        for pat in patterns:
            for f in sorted(src.glob(pat)):
                rel = f.relative_to(src).as_posix()
                if rel in seen:
                    continue
                seen.add(rel)
                for p, note in export_one(f, rel, out):
                    items.append((rel, p, note))
        if not items:
            continue
        total += len(items)
        big = gi < 3 or "Ortseinblendungen" in title or "Minispiel" in title or "Film" in title
        nav.append(f'<a href="#g{gi}">{html.escape(title)} ({len(items)})</a>')
        cards = []
        for rel, p, note in items:
            r = p.relative_to(out).as_posix()
            size = img_size(p)
            rows.append({"gruppe": title, "datei": rel, "bild": r, "groesse": size, "hinweis": note,
                         "englischer_text": "", "uebersetzen": ""})
            cards.append(f'<div class="c"><a href="{html.escape(r)}" target="_blank"><img loading="lazy" src="{html.escape(r)}"></a>'
                         f'<div><b>{html.escape(p.name)}</b> {size}<br>{html.escape(rel)} {html.escape(note)}</div></div>')
        body.append(f'<h2 id="g{gi}">{html.escape(title)} – {len(items)}</h2><p>{html.escape(desc)}</p>'
                    f'<div class="g" style="--min:{"260px" if big else "150px"}">{"".join(cards)}</div>')
    (out / "kontakt.html").write_text(KONTAKT, encoding="utf-8")
    (out / "index.html").write_text(PAGE.format(total=total, nav="".join(nav), body="".join(body)), encoding="utf-8")
    with open(out / "inventar.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"{total} Bilder -> {out / 'index.html'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
