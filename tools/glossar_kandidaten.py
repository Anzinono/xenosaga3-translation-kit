"""Collects glossary candidates and writes text/<lang>/glossar.csv.

Sources:
  - database titles (text/en/datenbank.csv, field "titel") with their category
  - speaker names [Name] at the start of dialogue lines (text/en/skripte.csv)
  - game-system terms used in menus (see SYSTEM)

Columns: term_en; term_<lang>; type; source; count; status; note
  status "keep"  = proper noun of the series or a character name – usually left in English
  status "open"  = still to be decided by the translator
An existing glossar.csv is never discarded: rows whose status you changed by hand
(anything other than "keep"/"open") win, and terms you added yourself are kept.

Run after tools/vorbereiten.py:   python -I tools/glossar_kandidaten.py   (language via XS3_LANG, default de)
"""
import collections
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import LANG, TEXT_DIR  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EN = ROOT / "text" / "en"
OUT = TEXT_DIR / "glossar.csv"
COLUMNS = ["term_en", f"term_{LANG}", "type", "source", "count", "status", "note"]

CATEGORY_TYPE = {
    "Characters": "person", "Cultural": "term", "Events": "event", "Locations": "place",
    "Weapons": "weapon/technology", "Organizations": "organisation", "Unknown": "myth/technology",
    "Town Report": "side story", "Story": "story recap", "Tutorial": "battle system",
}

# Proper nouns and abbreviations of the series that most translations keep in English.
KEEP = [
    "KOS-MOS", "chaos", "MOMO", "T-elos", "Gnosis", "Zohar", "U-DO", "U-TIC", "U.M.N.", "E.S.", "URTV",
    "A.G.W.S.", "A.M.W.S.", "M.W.S.", "D.S.S.S.", "V.L.V.", "J.M.I.", "C.S.R.C.", "C.P.C.", "F.S.I.",
    "E.A.P.F.", "UNP", "ECM", "ECCM", "NATARAJA", "Nexus", "Testament", "Anima", "Ormus", "Scientia",
    "Vector", "Vector Industries", "Hyams", "Labyrinthos", "Merkabah", "Proto Merkabah", "Omega",
    "Proto Omega", "Pleroma", "Rennes-le-Château", "Dämmerung", "Erde Kaiser", "Wellgunde", "Woglinde",
    "Floßhilde", "Durandal", "Elsa", "Lemegeton", "Yeshua", "Zarathustra", "Abyss", "Encephalon",
    "Prodigium", "Salvator", "Interlink", "Archon", "Miltia", "Abraxas", "Michtam", "Y-Data", "Pellegri",
]

# Game-system terms (menus) that are not database titles
SYSTEM = ["HP", "EP", "Ether", "Items", "Equip", "Skill", "Formation", "Database", "Save Point",
          "Segment Address", "Characters", "Cultural", "Events", "Locations", "Weapons", "Organizations",
          "Unknown", "Town Report", "Story", "Tutorial"]

GENERIC_SINGLE_WORDS = {"Boy", "Child", "Soldier", "Console", "Information", "Warning", "Ropeway", "Professor"}


def read(name: str) -> list[dict]:
    with open(EN / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main() -> None:
    db = read("datenbank.csv")
    scripts = read("skripte.csv")
    all_text = []
    for n in ["skripte.csv", "datenbank.csv", "menue_txd.csv", "menue_bin.csv",
              "minispiel_rueckblick.csv", "untertitel.csv"]:
        if (EN / n).exists():
            all_text += [r["text_en"].replace("\\n", " ") for r in read(n)]
    corpus = "\n".join(all_text)

    cand = collections.OrderedDict()  # en -> (type, source)
    category = None
    for r in sorted(db, key=lambda r: int(r["eintrag"])):
        if r["feld"] == "kategorie":
            category = r["text_en"]
        if r["feld"] == "titel":
            t = r["text_en"].strip()
            if "�" in t or not t or t.startswith(("History of Abraxas", "Federal Report", "EPISODE")):
                continue
            cand.setdefault(t, (CATEGORY_TYPE.get(category, "?"), "database:" + (category or "?")))
    speakers = collections.Counter()
    for r in scripts:
        m = re.match(r"\[([^\]]+)\]", r["text_en"])
        if m:
            speakers[m.group(1).strip()] += 1
    for s, _ in speakers.most_common():
        if s in cand:
            cand[s] = (cand[s][0], cand[s][1] + "+speaker")
            continue
        if re.match(r"(Federal Report|Observation Regarding) ", s):
            continue
        single = " " not in s and s[:1].isupper() and not s.isupper() and s not in GENERIC_SINGLE_WORDS
        cand[s] = ("person" if single else "speaker/object", "speaker")
    for t in SYSTEM:
        cand.setdefault(t, ("game system", "menu"))

    old = {}
    if OUT.exists():
        with open(OUT, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                old[r.get("term_en", "")] = r

    rows = []
    for en, (typ, source) in cand.items():
        if en in KEEP or typ == "person" or en.split()[0] == "E.S.":
            target, status, note = en, "keep", "proper noun / name – usually kept"
        else:
            target, status, note = "", "open", ""
        row = {"term_en": en, f"term_{LANG}": target, "type": typ, "source": source,
               "count": str(corpus.count(en)), "status": status, "note": note}
        if en in old and old[en].get("status") not in ("keep", "open", None, ""):
            row.update({k: old[en].get(k, "") for k in (f"term_{LANG}", "status", "note")})
        rows.append(row)
    for en, r in old.items():                     # keep terms added by hand
        if en and en not in cand:
            rows.append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} terms -> {OUT.relative_to(ROOT)}  ({dict(collections.Counter(r['status'] for r in rows))})")


if __name__ == "__main__":
    main()
