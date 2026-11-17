"""Starting point for a new translation: export the text from your own disc and create templates.

  1. checks the original images in ISO/ (checksum) and extracts the required text files
  2. exports all English text to text/en/*.csv
  3. creates text/<lang>/: copies of the tables with an empty column text_<lang>,
     graphics configurations from vorlagen/ (existing files are NEVER overwritten)

Usage (in the project root):
  python -I tools/vorbereiten.py --sprache fr
  python -I tools/vorbereiten.py --sprache fr --disc 1      # disc 1 only (disc 2 subtitles are then missing)
"""
from __future__ import annotations

import os
import sys

for _i, _a in enumerate(sys.argv):           # set the language before importing the other modules
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
            print(f"  {dst.relative_to(ROOT)} exists – not overwritten")
            continue
        shutil.copyfile(src, dst)
        print(f"  {dst.relative_to(ROOT)} created (fill column {COL})")
    for src in sorted(VORLAGEN.glob("grafik_*.json")):
        dst = TEXT_DIR / src.name
        if dst.exists():
            print(f"  {dst.relative_to(ROOT)} exists – not overwritten")
            continue
        text = src.read_text(encoding="utf-8").replace('"xx":', f'"{LANG}":')
        json.loads(text)                                         # validate
        dst.write_text(text, encoding="utf-8")
        print(f"  {dst.relative_to(ROOT)} created (fill fields \"{LANG}\")")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sprache", required=True, help="language code of the translation, e.g. fr, es, it, pt-br")
    ap.add_argument("--disc", type=int, action="append", choices=(1, 2))
    ap.add_argument("--ohne-pruefsumme", action="store_true", help="skip the SHA1 check of the original images")
    args = ap.parse_args()
    discs = sorted(set(args.disc or [1, 2]))
    print("1. Checking original images and extracting text files")
    build.prepare(discs, not args.ohne_pruefsumme)
    print("2. Exporting English text -> text/en/")
    export_all(discs)
    print(f"3. Creating templates for '{LANG}' -> text/{LANG}/")
    make_templates()
    print(f"\nDone. Next steps: fill column {COL} in text/{LANG}/*.csv, then\n"
          f"  python -I tools/build.py --sprache {LANG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
