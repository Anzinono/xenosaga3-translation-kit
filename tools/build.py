"""Build-Pipeline: deutsche Übersetzungstabellen -> fertige Disc-Images (+ xdelta-Patches).

Ablauf:
  1. Prüfen: Original-Images vorhanden, Prüfsummen bekannt, Quelldateien entpackt (sonst entpacken).
  2. Übersetzungsspeicher: In jeder Tabelle text/de/*.csv werden leere text_de-Zellen mit der
     Übersetzung eines identischen text_en aus derselben Tabelle gefüllt.
  3. Import: Jede vorhandene Tabelle wird mit ihrem Tool in Spieldateien umgesetzt (build/de/...).
  4. Prüfbericht build/pruefbericht.md: Fortschritt je Tabelle, Fehler, Längenwarnungen.
  5. Images: Für jede Disc tools/x3rebuild.py, danach tools/verify_rebuild.py.
  6. Patches: falls xdelta3 gefunden wird, patch/Xenosaga3_DE_DiscN.xdelta.

Aufruf (im Projekt-Root):
  python -I tools/build.py                 # alles, beide Discs
  python -I tools/build.py --disc 1        # nur Disc 1
  python -I tools/build.py --nur-dateien   # nur Schritte 1-4 (schnell, ohne Images)

Übersetzungstabellen (gleiche Spalten wie die Exporte in text/en, Spalte text_de ausgefüllt):
  text/de/skripte.csv, menue_txd.csv, datenbank.csv, menue_bin.csv,
  minispiel_rueckblick.csv, untertitel.csv, kampfdaten.csv – fehlende Tabellen werden übersprungen.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import os  # noqa: E402

# --sprache muss vor dem Import von sprache.py ausgewertet werden (gilt auch für alle aufgerufenen Tools)
for _i, _a in enumerate(sys.argv):
    if _a == "--sprache" and _i + 1 < len(sys.argv):
        os.environ["XS3_LANG"] = sys.argv[_i + 1]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL, LANG, TAG, TEXT_DIR  # noqa: E402
import pixelbreite  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DE = TEXT_DIR                      # Ordner der Übersetzungstabellen (text/<sprache>)
BUILD = ROOT / "build"
OUT = BUILD / LANG
EXTRACTED = ROOT / "extracted"
F1 = EXTRACTED / "disc1" / "files"
PY = [sys.executable, "-I", "-X", "utf8"]
TAG_RE = re.compile(r"<[^>]*>|\[[^\]]*\]|%[sd]|\$[^;]*;")
# Steuer-Tags; Wörter in <…> (Datenbank-Verweise, Hervorhebungen) dürfen übersetzt werden
CTRL_TAG = re.compile(r"<(?:f|wk?\d+|[lxs]\d+|cole|col[0-9a-f]+|\d+|[○□×△])>|%[sd]|\$[^;]*;")

ISOS = {
    1: ("Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 1).iso", "30a887e6942cef57099bc9c84de5b39974e62f9a"),
    2: ("Xenosaga Episode III - Also sprach Zarathustra (USA) (Disc 2).iso", "9902a798f2f4a7d7a4af6078ec3e5ec5107d5450"),
}
# Textdateien, die für den Import entpackt vorliegen müssen (Archiv X3.00 ist auf beiden Discs gleich)
EXTRACT_FILTERS = {
    1: ["\\cf\\us\\*", "\\bat\\us\\*", "\\mnu\\us\\*", "\\mnu\\pse\\us\\*", "\\mg1\\us\\*", "\\evt\\us\\*", "\\mov\\us\\*",
        "\\ef\\esd\\us\\*", "\\ef\\map\\us\\*", "\\mnu\\intm\\*", "\\mnu\\diskchg.bin", "\\jpg\\us\\*"],
    2: ["\\evt\\us\\*", "\\mov\\us\\*"],
}


def log(msg: str) -> None:
    print(msg, flush=True)


def run(args: list, what: str) -> str:
    r = subprocess.run([str(a) for a in args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        raise SystemExit(f"FEHLER bei {what}:\n{out}")
    return out


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        while chunk := fh.read(16 << 20):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 1. Voraussetzungen
def prepare(discs: list[int], check_hash: bool) -> dict[int, Path]:
    isos = {}
    for d in discs:
        iso = ROOT / "ISO" / ISOS[d][0]
        if not iso.exists():
            raise SystemExit(f"Original-Image fehlt: {iso}")
        if check_hash:
            log(f"  Prüfsumme Disc {d} …")
            if sha1(iso) != ISOS[d][1]:
                raise SystemExit(f"Prüfsumme von Disc {d} passt nicht (docs/iso-pruefsummen.md)")
        isos[d] = iso
        markers = ["mnu/us/DBC.bin", "ef/esd/us", "ef/map/us", "mnu/intm", "mnu/diskchg.bin", "jpg/us"] if d == 1 else ["evt/us"]
        if not all((EXTRACTED / f"disc{d}" / "files" / m).exists() for m in markers):
            log(f"  Entpacke Textdateien von Disc {d} …")
            args = [*PY, TOOLS / "x3extract.py", iso, "--out", EXTRACTED / f"disc{d}" / "files"]
            for f in EXTRACT_FILTERS[d]:
                args += ["--filter", f]
            run(args, f"Entpacken Disc {d}")
    if 1 not in isos and not F1.exists():
        raise SystemExit("Für Disc 2 werden die gemeinsamen Dateien von Disc 1 benötigt: erst Disc 1 entpacken")
    return isos


# ---------------------------------------------------------------- 2. Übersetzungsspeicher
def fill_memory(src: Path, dst: Path) -> tuple[list[dict], int]:
    with open(src, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames
    memory = {}
    for r in rows:
        if r.get(COL, "").strip() and r.get("text_en") is not None:
            memory.setdefault(r["text_en"], r[COL])
    filled = 0
    for r in rows:
        if not r.get(COL, "").strip() and r.get("text_en") in memory:
            r[COL] = memory[r["text_en"]]
            filled += 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    return rows, filled


# ---------------------------------------------------------------- 3. Import
def import_all(csvs: dict[str, Path], de_dir: Path = DE) -> list[str]:
    x3 = OUT / "x3"
    notes = []
    M = F1 / "mnu" / "us"
    if "skripte" in csvs:
        notes.append(run([*PY, TOOLS / "sbtext.py", "import", F1 / "cf/us", F1 / "bat/us", "--csv", csvs["skripte"], "--out", x3], "Skripte"))
    if "menue_txd" in csvs:
        notes.append(run([*PY, TOOLS / "txdtext.py", "import", *sorted(M.glob("*.txd")), "--csv", csvs["menue_txd"], "--out", x3 / "mnu/us"], "Menü .txd"))
    if "datenbank" in csvs:
        notes.append(run([*PY, TOOLS / "dbctext.py", "import", M / "DBC.bin", M / "DBC2.bin", "--csv", csvs["datenbank"], "--out", x3 / "mnu/us"], "Datenbank"))
    if "menue_bin" in csvs:
        files = [M / n for n in ("njBtlText.bin", "njDBcommon.bin", "SegmentFileData.bin", "MVtext.bin", "njDataText.bin")]
        notes.append(run([*PY, TOOLS / "bintext.py", "import", *files, "--csv", csvs["menue_bin"], "--out", x3 / "mnu/us"], "Menü .bin"))
    if "minispiel_rueckblick" in csvs:
        notes.append(run([*PY, TOOLS / "mestext.py", "import", F1 / "mg1/us/Message.Dat", "--csv", csvs["minispiel_rueckblick"], "--out", x3 / "mg1/us"], "Minispiel"))
        notes.append(run([*PY, TOOLS / "mestext.py", "import", *sorted((F1 / "mnu/pse/us").glob("*.mes")), "--csv", csvs["minispiel_rueckblick"], "--out", x3 / "mnu/pse/us"], "Rückblicke"))
    if "kampfdaten" in csvs:
        notes.append(run([*PY, TOOLS / "batdattext.py", "import", F1 / "bat/us/batdat.bin", "--csv", csvs["kampfdaten"], "--out", x3 / "bat/us"], "Kampfdaten"))
    if "untertitel" in csvs:
        notes.append(run([*PY, TOOLS / "subtitle_import.py", "--csv", csvs["untertitel"], "--out", OUT / "untertitel"], "Untertitel"))
    # Grafiken: Titelbildschirm (Menüpunkte + Credit-Zeile), Texte in grafik_titel.json
    titel_cfg = Path(de_dir) / "grafik_titel.json"
    if titel_cfg.exists():
        notes.append(run([*PY, TOOLS / "titelbild.py", "--out", x3 / "mnu/us", "--config", titel_cfg], "Titelbildschirm"))
    # Grafiken: Ortseinblendungen (Masken in ef/esd/us, ef/map/us), Texte in grafik_orte.json
    orte_cfg = Path(de_dir) / "grafik_orte.json"
    if orte_cfg.exists():
        notes.append(run([*PY, TOOLS / "ortstitel.py", "--out", x3, "--config", orte_cfg], "Ortseinblendungen"))
    # Grafiken: Figurenkarten height/weight (mnu/intm/*.jpg, mnu/diskchg.bin), Texte in grafik_figurenkarten.json
    karten_cfg = Path(de_dir) / "grafik_figurenkarten.json"
    if karten_cfg.exists():
        notes.append(run([*PY, TOOLS / "figurenkarten.py", "--out", x3, "--config", karten_cfg], "Figurenkarten"))
    # Grafiken: Datenbankbilder mit Text (jpg/us/dtimg_*), Texte in grafik_datenbank.json
    db_cfg = Path(de_dir) / "grafik_datenbank.json"
    if db_cfg.exists():
        notes.append(run([*PY, TOOLS / "dbbilder.py", "--out", x3, "--config", db_cfg], "Datenbankbilder"))
    return [n for n in notes if n]


# ---------------------------------------------------------------- 4. Prüfbericht
def line_stats(text: str) -> tuple[int, int]:
    parts = text.replace("\r\n", "\n").replace("\\n", "\n").split("\n")
    return len(parts), max((len(p) for p in parts), default=0)


DB_PX = {"kategorie": 150, "lang": 630, "extra2": 630, "extra4": 630, "titel": 370, "kurz": 248, "extra1": 243, "extra3": 215}


def report(tables: dict[str, tuple[list[dict], int]], notes: list[str]) -> tuple[Path, int]:
    lines = ["# Prüfbericht Build", "", "| Tabelle | Zeilen | übersetzt | davon per Übersetzungsspeicher | Fortschritt |", "|---|---|---|---|---|"]
    warnings: list[str] = []
    for name, (rows, filled) in tables.items():
        done = sum(1 for r in rows if r.get(COL, "").strip())
        pct = 100 * done / len(rows) if rows else 0
        lines.append(f"| {name} | {len(rows)} | {done} | {filled} | {pct:.1f} % |")
        # Länge: Grenze = längste Originalzeile derselben Tabelle/Kategorie
        limit_lines, limit_chars = defaultdict(int), defaultdict(int)
        for r in rows:
            k = r.get("kategorie", r.get("feld", ""))
            n, c = line_stats(r.get("text_en", ""))
            limit_lines[k] = max(limit_lines[k], n)
            limit_chars[k] = max(limit_chars[k], c)
        for r in rows:
            de = r.get(COL, "").strip()
            if not de:
                continue
            k = r.get("kategorie", r.get("feld", ""))
            n_en, c_en = line_stats(r.get("text_en", ""))
            n_de, c_de = line_stats(de)
            if "eintrag" in r:
                where = f"{name}: Eintrag {r['eintrag']} ({r.get('feld', '')}) „{r.get(COL, '')[:30]}“"
            else:
                where = f"{name}: {r.get('datei', '')} #{r.get('idx', r.get('zeile', r.get('schluessel', '')))}"
            if name == "datenbank" and pixelbreite.available():
                # Datenbank: Grenze in Pixeln (Langtext-Panel 630 px, sonst breiteste Originalzeile)
                lim_px = DB_PX.get(k, 0) or max(pixelbreite.width(l, True) for l in re.split(r"\\n|\n", r.get("text_en", "")))
                w_de = max(pixelbreite.width(l, True) for l in re.split(r"\\n|\n", de))
                if w_de > lim_px:
                    warnings.append(f"{where}: Zeile mit {w_de} px, Grenze {lim_px} px")
            elif c_de > limit_chars[k]:
                warnings.append(f"{where}: Zeile mit {c_de} Zeichen, längste Originalzeile hat {limit_chars[k]}")
            # Dialogboxen ohne feste Zeilenzahl (<lN>) fassen 3 Zeilen (in PCSX2 bestätigt)
            max_lines = max(n_en, 1)
            if name == "skripte" and r.get("kategorie") == "dialog" and not re.search(r"<l\d", r.get("text_en", "")):
                max_lines = max(n_en, 3)
            if n_de > max_lines and name != "datenbank":
                warnings.append(f"{where}: {n_de} Zeilen statt {n_en}")
            en = r.get("text_en", "")
            if de.count("<") - de.count(">") != en.count("<") - en.count(">"):
                warnings.append(f"{where}: Tag-Klammern < > unvollständig")
            # Steuerzeichen müssen erhalten bleiben; <k…>-Verweise und [Sprecher] dürfen übersetzt werden
            tags_en = Counter(t for t in CTRL_TAG.findall(r.get("text_en", "")))
            tags_de = Counter(t for t in CTRL_TAG.findall(de))
            if tags_en != tags_de:
                warnings.append(f"{where}: Steuerzeichen abweichend (EN {dict(tags_en)} / DE {dict(tags_de)})")
    lines += ["", f"## Warnungen ({len(warnings)})", ""]
    lines += [f"- {w}" for w in warnings[:500]] or ["keine"]
    if len(warnings) > 500:
        lines.append(f"- … und {len(warnings) - 500} weitere")
    lines += ["", "## Ausgaben der Import-Tools", "", "```", *notes, "```"]
    path = BUILD / "pruefbericht.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path, len(warnings)


# ---------------------------------------------------------------- 5./6. Images und Patches
def build_disc(d: int, iso: Path) -> Path:
    folder = OUT / f"disc{d}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    if (OUT / "x3").exists():
        shutil.copytree(OUT / "x3", folder, dirs_exist_ok=True)
    subs = OUT / "untertitel" / f"disc{d}"
    if subs.exists():
        shutil.copytree(subs, folder, dirs_exist_ok=True)
    target = BUILD / f"Xenosaga3_{TAG}_Disc{d}.iso"
    if not any(folder.rglob("*")):
        log(f"  Disc {d}: keine Änderungen – Image wird trotzdem neu gebaut (identisch zum Original)")
        src_arg = "-"
    else:
        src_arg = folder
    out = run([*PY, TOOLS / "x3rebuild.py", iso, src_arg, target], f"Image Disc {d}")
    log("  " + out.splitlines()[-1])
    out = run([*PY, TOOLS / "verify_rebuild.py", iso, target, src_arg], f"Prüfung Disc {d}")
    log("  " + out.splitlines()[-1])
    return target


def find_xdelta() -> str | None:
    for cand in (shutil.which("xdelta3"), shutil.which("xdelta"), r"C:\tools\xdelta3\xdelta3.exe"):
        if cand and Path(cand).exists():
            return cand
    return None


def make_patch(d: int, iso: Path, target: Path, release: bool) -> str:
    xd = find_xdelta()
    if not xd:
        return f"Disc {d}: xdelta3 nicht gefunden – kein Patch erzeugt"
    # Nur Builds aus text/de landen in patch/ (Repository); Probeläufe in build/patch_probe/
    folder = ROOT / "patch" if release else BUILD / "patch_probe"
    folder.mkdir(parents=True, exist_ok=True)
    patch = folder / f"Xenosaga3_{TAG}_Disc{d}.xdelta"
    run([xd, "-e", "-9", "-f", "-s", iso, target, patch], f"xdelta Disc {d}")
    # Gegenprobe: Patch auf das Original anwenden -> muss exakt das gebaute Image ergeben
    check = BUILD / f"_patchprobe_disc{d}.iso"
    try:
        run([xd, "-d", "-f", "-s", iso, patch, check], f"xdelta-Probe Disc {d}")
        ok = sha1(check) == sha1(target)
    finally:
        check.unlink(missing_ok=True)
    if not ok:
        raise SystemExit(f"Patch für Disc {d} ergibt nicht das gebaute Image!")
    return f"Disc {d}: {patch.relative_to(ROOT)} ({patch.stat().st_size / 1024:.0f} KiB), Gegenprobe ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disc", type=int, action="append", choices=(1, 2))
    ap.add_argument("--sprache", default=LANG, help="Sprachcode der Übersetzung, z. B. de, fr, es (Standard: de oder XS3_LANG)")
    ap.add_argument("--de", default=str(DE), help="Ordner mit den Übersetzungstabellen (Standard: text/<sprache>)")
    ap.add_argument("--nur-dateien", action="store_true", help="keine Images bauen")
    ap.add_argument("--ohne-pruefsumme", action="store_true", help="SHA1 der Originale nicht prüfen (schneller)")
    args = ap.parse_args()
    discs = sorted(set(args.disc or [1, 2]))

    log("1. Voraussetzungen")
    isos = prepare(discs, not args.ohne_pruefsumme and not args.nur_dateien)

    log("2. Übersetzungstabellen")
    if OUT.exists():
        shutil.rmtree(OUT)
    de = Path(args.de)
    tables, csvs = {}, {}
    for name in ("skripte", "menue_txd", "datenbank", "menue_bin", "minispiel_rueckblick", "untertitel", "kampfdaten"):
        src = de / f"{name}.csv"
        if not src.exists():
            continue
        dst = OUT / "csv" / f"{name}.csv"
        tables[name] = fill_memory(src, dst)
        csvs[name] = dst
        rows, filled = tables[name]
        log(f"  {name}: {sum(1 for r in rows if r.get(COL, '').strip())}/{len(rows)} übersetzt ({filled} per Übersetzungsspeicher)")
    if not csvs:
        log(f"  Keine Tabellen in {de} gefunden.")

    log("3. Import")
    notes = import_all(csvs, de)
    n_files = sum(1 for p in OUT.rglob("*") if p.is_file() and "csv" not in p.parts)
    log(f"  {n_files} Spieldateien erzeugt")

    log("4. Prüfbericht")
    path, nwarn = report(tables, notes)
    log(f"  {path.relative_to(ROOT)}: {nwarn} Warnungen")

    if args.nur_dateien:
        return 0
    log("5. Images")
    results = []
    for d in discs:
        target = build_disc(d, isos[d])
        results.append(make_patch(d, isos[d], target, release=Path(args.de).resolve() == DE.resolve()))
    log("6. Patches")
    for r in results:
        log("  " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
