# Recherche: Vorarbeiten und Werkzeuge (2026-11-14)

## Deutsche Fan-Übersetzung

Keine gefunden. Episode III ist nie in Europa erschienen, eine deutsche Fassung gibt es weder offiziell noch als Fanpatch.

## Koreanisches Projekt XS3KOR – wichtigste Quelle

- Repo: https://github.com/poketony/XS3KOR (aktiv, letzter Commit 2026-11-10, Rohübersetzung laut Commits seit 2026-10-28 fertig)
- **Basis ist die japanische Version (SLPS_256.40 / 256.41), nicht die US-Version.** Dateinamen und Pfade (`jp/` statt `us/`) und Offsets weichen ab.
- **Keine Lizenzdatei** → Code nicht kopieren, nur als Referenz lesen und eigene Tools schreiben. Ggf. den Autor um Erlaubnis fragen.
- Nützliche Erkenntnisse:
  - Archive: Packs `X3.00`/`X3.01`… (gemeinsam), `X3.10`… (Disc 1), `X3.20`… (Disc 2), mit LBA-/Tabellendateien (`.x0`). Teile werden per `copy /b X3.01 + X3.02 X3.big` zu einer „munge“-Datei verbunden.
  - Mitgeliefert ist das Drittanbieter-Kit „Xenosaga3WorkSpace“ von *Lybac* (`Xenounpack.exe`, `XenoRepack.exe`, `XenoLbar.exe`, `Xeno23Lbae.exe`) – laut Readme für alle Xenosaga-Teile, mit einer Anleitung für die **US-Version** (`cf/us/`).
  - Textformate: `.txd` (Menütexte, Synopsis), `.sb` (Skripte/Dialoge in `cf/` und `bat/`), `njDataText.bin`, `njBtlText.bin`, `DBC.bin` (Datenbank), `.mes` (PSE), `Message.Dat`/`World.Dat` (Minispiel), `batdat.bin` (Kampfdaten).
  - Untertitel der Zwischensequenzen: Disc 1 `evt` (35 Dateien) und `mov` (13), Disc 2 `evt` (18) und `mov` (15).
  - Font: `font0.bin`/`font1.bin`, als 4 Farbkanäle (RGBA-PNGs) bearbeitbar; die letzten 3072 Bytes bleiben erhalten.
  - Grafiken: `.xtx` (Noesis-Plugin im Repo), `.tm2`, `.jpg` (Synopsis, Datenbank).
  - Texte in ELF und Overlay `OV04.OVL`: nur feste Längen (Original + 8-Byte-Padding).
  - Japanische Version: Encoding EUC-JIS-2004. **Encoding der US-Version noch zu prüfen** (vermutlich ASCII-/Latin-basiert → Umlaute müssen in den Font).

## Xenosaga3PythonExtractor (US-Version) – zweite wichtige Quelle

- Repo: https://github.com/LinuxJessi/Xenosaga3PythonExtractor, **MIT-Lizenz**, Beta, letzter Commit 2026-09-25.
- Arbeitet mit der **US-Version**. Liest die Binärkataloge nicht selbst, sondern nutzt die von Lybacs Tools erzeugten Listen (`lba/Lba0.txt` … `Lba2.txt`). Diese Listen dienten als Prüfdaten für `tools/x3toc.py`.
- Nützlich für später: LZSS-Decoder (aus dem SLUS übernommen, für `.map`), „Xc“-Paketformat (`.chr/.map/.wpn/.sme`), Texturformate (XTX/TM2/TXY), Repack-Befehle, die in vorhandenen Platz zurückschreiben.

## Französischer Patch

- TRAF: https://traf.romhack.org/?p=patchs&pid=1369 – v1.00, 100 %, 2021, von „Noug“ (Hacking + Übersetzung), Hilfe „RyleFury“.
- Keine Tools oder Technikdoku veröffentlicht, nur xdelta-Patches.
- Original-CRC32 dort: DVD 1 `8e73c8db`, DVD 2 `30819eeb` – **passt nicht zu unseren Images** (siehe `iso-pruefsummen.md`). Ob der Patch auf einem anderen US-Dump basiert, ist unklar.
- Beweist aber: Lateinische Sonderzeichen (é, è, à, ç …) sind in diesem Spiel machbar. Kontakt zu Noug über romhack.org/Discord wäre für Font-Fragen wertvoll.

## REA (Reverse Engineer Anything)

- Repo: https://github.com/morluto/rea, MIT-Lizenz, npm-Paket `rea-agents`, MCP-Server + Skill + Claude-Code-Plugin.
- **REA ersetzt Ghidra nicht, sondern steuert es.** Native Dekompilierung läuft über Ghidra (bzw. IDA/Hopper). Für Code-Analyse braucht es weiterhin Ghidra 12.x.
- **PS2/R5900 wird nicht erwähnt.** MIPS nur als „bounded“ Ghidra-Pfad für ELF-Header. Ob die 128-Bit-MMI-Befehle und das EE-Plugin funktionieren, muss getestet werden.
- Ghidra auf Windows ist dort als „experimental“ markiert.
- Voraussetzungen auf diesem Rechner:
  - Node.js: **v22.23.1 installiert, REA braucht ≥ 22.23.4** → Update nötig.
  - Java: JDK 25.0.1 vorhanden → passt für Ghidra 12.1/12.2.
  - Ghidra: nicht installiert.
- Installation ändert die globale Claude-Konfiguration (`~/.claude.json`, `~/.claude/skills`) → nur nach ausdrücklicher Freigabe durch den Nutzer.
- Für Stufe A ist REA/Ghidra zunächst kaum nötig: Die Formate sind über das Lybac-Kit und XS3KOR bereits weitgehend bekannt. Code-Analyse wird erst relevant für Font-/Breiten-Tabellen im ELF, Längengrenzen und Stufe B.
