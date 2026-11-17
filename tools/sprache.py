"""Zielsprache der Übersetzung – zentrale Einstellung für alle Werkzeuge.

Die Sprache wird über die Umgebungsvariable XS3_LANG gewählt (Standard: "de").
tools/build.py setzt sie mit --sprache selbst; einzelne Werkzeuge lesen sie beim Start.

  XS3_LANG=fr  ->  Tabellen in text/fr/, Spalte "text_fr", Grafikfelder "fr",
                   Ausgabe build/fr/, Images Xenosaga3_FR_DiscN.iso
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANG = os.environ.get("XS3_LANG", "de").strip().lower()
if not re.fullmatch(r"[a-z]{2,3}(-[a-z0-9]{2,8})?", LANG):
    raise SystemExit(f"Ungültiger Sprachcode in XS3_LANG: {LANG!r} (z. B. de, fr, es, pt-br)")

TEXT_DIR = ROOT / "text" / LANG          # Übersetzungstabellen und Grafik-Konfiguration
COL = f"text_{LANG}"                     # Spalte mit der Übersetzung in den CSV-Tabellen
TAG = LANG.upper().replace("-", "")      # Kennung in Dateinamen, z. B. Xenosaga3_DE_Disc1.iso
