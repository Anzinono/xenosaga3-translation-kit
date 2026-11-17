# Tools and setup

Only needed if you want to analyse the game executable. For translating you only need Python (and Pillow, xdelta3, PCSX2).

| Tool | Version | Example location | Purpose |
|---|---|---|---|
| Ghidra | 12.2 | `C:\tools\ghidra_12.2_PUBLIC` | disassembler/decompiler |
| ghidra-emotionengine-reloaded | v2.1.39 for Ghidra 12.2 | `…\Ghidra\Extensions\ghidra-emotionengine-reloaded` | PS2 CPU (R5900 incl. MMI/VU0) |
| JDK | 21+ (25 for Ghidra 12.2) | `C:\Program Files\Java\jdk-25` | required by Ghidra |
| xdelta3 | 3.1.0 | `C:\tools\xdelta3\xdelta3.exe` or `PATH` | patches |

Environment variables used by `tools\ghidra-headless.bat`: `GHIDRA_INSTALL_DIR`, `JAVA_HOME`
(defaults: `C:\tools\ghidra_12.2_PUBLIC`, `C:\Program Files\Java\jdk-25`).

## Running Ghidra headless

Use `tools\ghidra-headless.bat`. It points Ghidra's settings folder to `C:\tools\ghidra-home`. This is needed when the
command runs inside an app that virtualises `%APPDATA%` (e.g. the Claude desktop app); otherwise Ghidra's OSGi framework
aborts with `The data file must be inside the data dir`.

```bat
tools\ghidra-headless.bat "<project folder>" <project name> -import <file> -processor r5900:LE:32:default
```

**gp register:** the PS2 start-up code sets `gp = 0x5571F0` (`daddu gp, a0, zero` at `0x1201C0`). Without this value Ghidra cannot
resolve gp-relative accesses (variables show up as `fGpffff8f24` etc.). Create the project like this:

```bat
tools\ghidra-headless.bat "<project>\re\ghidra" xs3 -import extracted\disc1\SLUS_213.89 -processor r5900:LE:32:default -overwrite -scriptPath re\scripts -preScript SetGp.java
```

Helper scripts in `re/scripts/` (run with `-process SLUS_213.89 -noanalysis -readOnly -scriptPath re\scripts -postScript <script> <args>`):

| Script | Purpose |
|---|---|
| `Uebersicht.java` | overview: function count, memory blocks, decompiled entry point |
| `StringXrefs.java <text>` | find strings and decompile the functions that reference them |
| `RefsTo.java <address>` | all references to an address and their functions |
| `DecompileAt.java <address> …` | decompile the function at an address, incl. callers |
| `SetGp.java` | set the gp value (as `-preScript` before analysis) |

GUI: `C:\tools\ghidra_12.2_PUBLIC\ghidraRun.bat`.

## Why not REA?

REA (Reverse Engineer Anything) was evaluated. It rejects the PS2 executable on Windows and Linux:
`SLUS_213.89` has `e_flags = 0x20924001` – ISA MIPS-III, machine R5900, ABI EABI64 – none of which REA's MIPS support
accepts, and it would force the generic `MIPS:LE:32` language, misreading the 128-bit MMI instructions. Ghidra with the
Emotion Engine plugin works.
