# Prior work and references

## Korean project XS3KOR

- Repository: https://github.com/poketony/XS3KOR
- Based on the **Japanese** release (SLPS_256.40 / 256.41), not the US release – file names, paths (`jp/` instead of `us/`) and offsets differ.
- **No license file** – used only as a reading reference; no code was taken from it.
- Useful hints: archive packs `X3.00`/`X3.10`/`X3.20` with LBA tables; text formats `.txd`, `.sb`, `njDataText.bin`, `DBC.bin`,
  `.mes`, `Message.Dat`, `batdat.bin`; subtitle files in `evt`/`mov`; font in `font0.bin`/`font1.bin`; textures `.xtx`/`.tm2`/`.jpg`.
  The Japanese release uses EUC-JIS-2004; the US release is single-byte (see [font.md](formats/font.md)).
- It ships the third-party "Xenosaga3WorkSpace" kit by *Lybac* (`Xenounpack.exe`, `XenoRepack.exe` …). This kit is **not needed** here.

## Xenosaga3PythonExtractor (US release)

- Repository: https://github.com/LinuxJessi/Xenosaga3PythonExtractor, **MIT license**.
- Works with the **US release**. It reads the archives through LBA lists produced by Lybac's tools; those lists served as
  reference data to verify `tools/x3toc.py`.
- `tools/xtx.py` is based on its `xtx_decode.py` (see `THIRD_PARTY_NOTICES.md`). It also has an LZSS decoder for `.map`
  files and notes on the "Xc" package format and textures.

## French fan patch

- TRAF: https://traf.romhack.org/?p=patchs&pid=1369 – v1.00 (2021) by "Noug" (hacking + translation), help by "RyleFury".
- Only xdelta patches were released, no tools or documentation. It shows that Latin accented characters work in this game.
- Its original-image CRC32 values (DVD 1 `8e73c8db`, DVD 2 `30819eeb`) differ from the images listed in `iso-pruefsummen.md`.

## Reverse-engineering tools

- **Ghidra 12** with **ghidra-emotionengine-reloaded** (PS2 Emotion Engine / R5900 incl. MMI) – used to analyse `SLUS_213.89`,
  e.g. the text renderer and the archive loader. Setup and the `gp` register value: [werkzeuge.md](werkzeuge.md).
- **REA (Reverse Engineer Anything)** was evaluated but cannot analyse PS2 MIPS executables (R5900, EABI64) – not needed.
