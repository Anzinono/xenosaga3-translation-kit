# ISO rebuild (files may grow)

Tools: `tools/x3rebuild.py` (build), `tools/verify_rebuild.py` (verify).

## How the game reads the archives

`FUN_00188148` (SLUS_213.89) looks up a path in the three loaded catalogs (`x3.00`, `x3.10`, `x3.20`, descriptors at
`0x89B5E0/0x89B600/0x89B640`). Reading starts at **chain base + sector from the catalog**. The base is the LBA of the catalog,
found via the file system (`\X3.00;1`).
→ The catalog and its data parts (`X3.00`, `X3.01`, `X3.02` …) must lie **contiguously** on the disc. The split into 1 GiB files
is only a file-system limit.

## Physical layout of disc 1 (original)

| LBA | Content |
|---|---|
| 16–20 | ISO 9660 PVD, terminator, UDF recognition (`BEA01`, `NSR02`, `TEA01`) |
| 32–37, 48–53 | UDF volume descriptors (main and reserve copy) |
| 64 | UDF Logical Volume Integrity Descriptor |
| 256 | UDF anchor |
| 257–262 | ISO path tables and directories (root 261, IOP 262) |
| 263–290 | UDF partition start (263), file entries 267–290 |
| 291–3113 | SYSTEM.CNF, SLUS, OVLs, IOP modules |
| 3114–807413 | **chain 1:** X3.00 (55) + X3.01 + X3.02 |
| 807414–1905668 | **chain 2:** X3.10 (26) + X3.11 + X3.12 + X3.13 |
| 1905669–1915918 | 10 251 empty padding sectors |
| 1915919 | UDF anchor (end) |

## Procedure

1. A replacement file that fits its old sector slot is written in place.
2. Otherwise it is appended to the end of its chain (after `X3.02` or `X3.13`/`X3.23`). The last data part grows and all later
   sectors move back.
3. Updated:
   - catalog: sector (u24) and size;
   - ISO 9660: location and size in the directory records (LE and BE), volume size in the PVD;
   - UDF: file entries (allocation descriptor, information length, recorded blocks), partition length (main and reserve copy),
     size table in the LVID, location of the end anchor – each with recomputed tag checksum and CRC-CCITT.

## Verification

- **Rebuilding without changes → byte-identical to the original.** This also confirms the UDF CRC calculation.
- `verify_rebuild.py`: ISO 9660 and UDF agree for every file; volume size, partition and end anchor match. All files outside the
  archives are unchanged. **Every** archive file (13 516 on disc 1) matches its replacement or the original.
- Tested in PCSX2 with 20 moved files incl. `DBC.bin` +24 % (831 sectors inserted): the game finds the moved chain 2 and loads the
  larger database.

## Notes

- Disc 2 has the same structure (`X3.20`–`X3.23`). The shared archive `X3.00`–`X3.02` must be patched identically on both discs –
  `tools/build.py` does this.
- Size: disc 2 is 4.516 GB, a single-layer DVD holds 4.700 GB → about 184 MB reserve. Text changes only need a few MB.
- Not yet tested in the game: a file moved to the end **within chain 2** (subtitles). Procedure and code are the same as for chain 1.
