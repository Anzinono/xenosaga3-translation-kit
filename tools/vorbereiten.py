"""Einstieg für eine neue Übersetzung: Texte aus der eigenen Disc exportieren und Vorlagen anlegen.

  1. prüft die Original-Images in ISO/ (Prüfsumme) und entpackt die benötigten Textdateien
  2. exportiert alle englischen Texte nach text/en/*.csv
  3. legt text/<sprache>/ an: Kopien der Tabellen mit leerer Spalte text_<sprache>,
     Grafik-Konfigurationen aus vorlagen/ (bestehende Dateien werden NIE überschrieben)

Aufruf (im Projekt-Root):
  python -I tools/vorbereiten.py --sprache fr
  python -I tools/vorbereiten.py --sprache fr --disc 1      # nur Disc 1 (Untertitel von Disc 2 fehlen dann)
"""
from __future__ import annotations

import os
import sys

for _i, _a in enumerate(sys.argv):           # Sprache vor dem Import der übrigen Module setzen
    if _a == "--sprache" and _i + 1 < len(sys.argv):
        os.environ["XS3_LANG"] = sys.argv[_i + 1]

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import COL, LANG, ROOT, TEXT_DIR  # noqa: E402
import build  # noqa: E402

EN = ROOT / "text" / "en"
VORLAGEN = ROOT / "vorlagen"


def export_all(discs: list[int]) -> None:
    py, tools, f1 = build.PY, build.TOOLS, build.F1
    m = f1 / "mnu" / "us"
    EN.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("skripte", [tools / "sbtext.py", "export", f1 / "cf/us", f1 / "bat/us", "--out", EN / "skripte.csv"]),
        ("menue_txd", [tools / "txdtext.py", "export", *sorted(m.glob("*.txd")), "--out", EN / "menue_txd.csv"]),
        ("datenbank", [tools / "dbctext.py", "export", m / "DBC.bin", "--out", EN / "datenbank.csv"]),
        ("menue_bin", [tools / "bintext.py", "export", *[m / n for n in ("njBtlText.bin", "njDBcommon.bin",
                       "SegmentFileData.bin", "MVtext.bin", "njDataText.bin")], "--out", EN / "menue_bin.csv"]),
        ("minispiel_rueckblick", [tools / "mestext.py", "export", f1 / "mg1/us/Message.Dat",
                                  *sorted((f1 / "mnu/pse/us").glob("*.mes")), "--out", EN / "minispiel_rueckblick.csv"]),
        ("kampfdaten", [tools / "batdattext.py", "export", f1 / "bat/us/batdat.bin", "--out", EN / "kampfdaten.csv"]),
        ("untertitel", [ROOT / "pySkript" / "subtitle_export.py", "--out", EN / "untertitel.csv"]
         + [a for d in discs for a in ("--dir", f"extracted/disc{d}/files/evt/us", "--dir", f"extracted/disc{d}/files/mov/us")]),
    ]
    for name, args in jobs:
        out = build.run([*py, *args], f"Export {name}")
        print(f"  {name}: {out.splitlines()[-1] if out else 'ok'}")


def make_templates() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    for src in sorted(EN.glob("*.csv")):
        dst = TEXT_DIR / src.name
        if dst.exists():
            print(f"  {dst.relative_to(ROOT)} existiert – nicht überschrieben")
            continue
        shutil.copyfile(src, dst)
        print(f"  {dst.relative_to(ROOT)} angelegt (Spalte {COL} ausfüllen)")
    for src in sorted(VORLAGEN.glob("grafik_*.json")):
        dst = TEXT_DIR / src.name
        if dst.exists():
            print(f"  {dst.relative_to(ROOT)} existiert – nicht überschrieben")
            continue
        text = src.read_text(encoding="utf-8").replace('"xx":', f'"{LANG}":')
        json.loads(text)                                         # Gültigkeit prüfen
        dst.write_text(text, encoding="utf-8")
        print(f"  {dst.relative_to(ROOT)} angelegt (Felder \"{LANG}\" ausfüllen)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sprache", required=True, help="Sprachcode der Übersetzung, z. B. fr, es, it, pt-br")
    ap.add_argument("--disc", type=int, action="append", choices=(1, 2))
    ap.add_argument("--ohne-pruefsumme", action="store_true")
    args = ap.parse_args()
    discs = sorted(set(args.disc or [1, 2]))
    print("1. Original-Images prüfen und Textdateien entpacken")
    build.prepare(discs, not args.ohne_pruefsumme)
    print("2. Englische Texte exportieren -> text/en/")
    export_all(discs)
    print(f"3. Vorlagen für '{LANG}' anlegen -> text/{LANG}/")
    make_templates()
    print(f"\nFertig. Nächste Schritte: Spalte {COL} in text/{LANG}/*.csv ausfüllen, dann\n"
          f"  python -I tools/build.py --sprache {LANG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
