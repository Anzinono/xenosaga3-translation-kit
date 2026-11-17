"""Target language of the translation – central setting for all tools.

The language is chosen via the environment variable XS3_LANG (default: "de").
tools/build.py sets it with --sprache; individual tools read it at start-up.

  XS3_LANG=fr  ->  tables in text/fr/, column "text_fr", graphics fields "fr",
                   output build/fr/, images Xenosaga3_FR_DiscN.iso
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANG = os.environ.get("XS3_LANG", "de").strip().lower()
if not re.fullmatch(r"[a-z]{2,3}(-[a-z0-9]{2,8})?", LANG):
    raise SystemExit(f"Invalid language code in XS3_LANG: {LANG!r} (e.g. de, fr, es, pt-br)")

TEXT_DIR = ROOT / "text" / LANG          # translation tables and graphics configuration
COL = f"text_{LANG}"                     # column holding the translation in the CSV tables
TAG = LANG.upper().replace("-", "")      # tag in file names, e.g. Xenosaga3_DE_Disc1.iso
