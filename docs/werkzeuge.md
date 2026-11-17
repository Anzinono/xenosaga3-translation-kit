# Werkzeuge & Einrichtung (Stand 2026-11-14)

| Werkzeug | Version | Ort | Zweck |
|---|---|---|---|
| Node.js (über nvm-windows) | 24.22.3 (aktiv), 22.23.1 bleibt installiert | `C:\nvm4w\nodejs` → `%LOCALAPPDATA%\nvm\v24.22.3` | Laufzeit für REA |
| REA (`rea-agents`) | 6.9.0, global per npm | `rea` im PATH, MCP-Server in `~/.claude.json`, Skill in `~/.claude/skills/reverse-engineer-anything` | Analyse-Werkzeug für Claude |
| Ghidra | 12.2 (SHA-256 gegen offizielles Release geprüft) | `C:\tools\ghidra_12.2_PUBLIC` | Disassembler/Decompiler |
| ghidra-emotionengine-reloaded | v2.1.39 für Ghidra 12.2 | `…\Ghidra\Extensions\ghidra-emotionengine-reloaded` | PS2-CPU (R5900 inkl. MMI/VU0) |
| JDK | 25.0.1 | `C:\Program Files\Java\jdk-25` | Für Ghidra |

Benutzer-Umgebungsvariablen: `GHIDRA_INSTALL_DIR=C:\tools\ghidra_12.2_PUBLIC`, `JAVA_HOME=C:\Program Files\Java\jdk-25`.

## Wichtig

- **Nicht per `nvm use 22` zurückschalten.** Die REA-Registrierung zeigt auf `C:\nvm4w\nodejs\node.exe`; mit Node 22.23.1 startet REA nicht (braucht ≥ 22.23.4).
- Sicherung der Claude-Konfiguration vor dem REA-Setup: `~/.claude.json.rea.backup`. Rückgängig machen: `rea uninstall`.
- Das Installationsskript von `frida` (npm) wurde nicht ausgeführt. Frida braucht REA nur zum Mitschneiden laufender Programme – für uns irrelevant.

## Einschränkung von REA für dieses Projekt

REA lehnt die SLUS-Datei ab:

> Windows Ghidra P0 accepts native PE, DOS MZ, and explicitly selected raw 6502 targets only.

REA kann unter Windows also keine PS2-Programme (MIPS-ELF) über Ghidra analysieren. IDA, Hopper und Kuna haben in REA ebenfalls keinen MIPS-Pfad.

### Linux/WSL hilft nicht (im REA-Code 6.9.0 geprüft)

ELF-Header von `SLUS_213.89`: `e_flags = 0x20924001`. REAs MIPS-Pfad (`dist/ghidra/GhidraMipsProfile.js`, `ghidraMipsUnsupportedReason`) lehnt die Datei auch unter Linux ab, und zwar aus drei unabhängigen Gründen:

| Feld | Wert | REA erlaubt |
|---|---|---|
| ISA (`EF_MIPS_ARCH`) | `0x20000000` = MIPS-III | nur MIPS-I, MIPS32, MIPS32r2 |
| Maschine (`EF_MIPS_MACH`) | `0x00920000` = R5900 | keine („need a separately supported processor profile“) |
| ABI | `0x4000` = EABI64 | nur o32 |

Der Modus für bestehende Ghidra-Projekte (`REA_GHIDRA_PROJECT_PATH`) umgeht das nicht: Die Prüfung in `GhidraProvider.js` läuft vorher. Außerdem würde REA die allgemeine Sprache `MIPS:LE:32` erzwingen, nicht `r5900`, und damit die 128-Bit-MMI-Befehle falsch lesen. → **WSL wird nicht eingerichtet.**

Wege:

1. **Ghidra direkt (headless) mit dem PS2-Plugin** – funktioniert, siehe unten. Claude steuert Ghidra über Skripte. **Aktueller Weg.**
2. Bei REA ein PS2-Profil anfragen (Issue auf GitHub). Für die PSP (Allegrex) gibt es bereits ein eigenes Profil, ein R5900-Profil über das EE-Plugin wäre ähnlich.

REA bleibt nützlich für Hilfsaufgaben (z. B. Windows-Tools wie das Lybac-Kit untersuchen).

## Ghidra headless starten

Immer über `tools\ghidra-headless.bat`. Das Skript leitet Ghidras Einstellungsordner nach `C:\tools\ghidra-home` um. Ohne diese Umleitung bricht Ghidra mit `The data file must be inside the data dir` ab. Ursache: Die Claude-Desktop-App virtualisiert `%APPDATA%`.

```bat
tools\ghidra-headless.bat "<Projektordner>" <Projektname> -import <Datei> -processor r5900:LE:32:default
```

Projekt der Hauptdatei: `re/ghidra/xs3.gpr` (nicht im Git).

**gp-Register:** Die PS2-Startroutine setzt `gp = 0x5571F0` (`daddu gp, a0, zero` bei `0x1201C0`). Ohne diesen Wert löst Ghidra keine gp-relativen Zugriffe auf (Variablen heißen dann `fGpffff8f24` o. ä.). Das Projekt neu anlegen:

```bat
tools\ghidra-headless.bat "<projekt>\re\ghidra" xs3 -import extracted\disc1\SLUS_213.89 -processor r5900:LE:32:default -overwrite -scriptPath re\scripts -preScript SetGp.java
```

Hilfsskripte in `re/scripts/` (Aufruf mit `-process SLUS_213.89 -noanalysis -readOnly -scriptPath re\scripts -postScript <Skript> <Argumente>`):

| Skript | Zweck |
|---|---|
| `Uebersicht.java` | Funktionsanzahl, Speicherblöcke, Einstiegspunkt dekompilieren |
| `StringXrefs.java <text>` | Strings suchen und verweisende Funktionen dekompilieren |
| `RefsTo.java <adresse>` | Alle Verweise auf eine Adresse und deren Funktionen |
| `DecompileAt.java <adresse> …` | Funktion an Adresse dekompilieren, inkl. Aufrufer |
| `SetGp.java` | gp-Wert setzen (als `-preScript` vor der Analyse) | In der Ghidra-Oberfläche öffnen: `C:\tools\ghidra_12.2_PUBLIC\ghidraRun.bat`.
