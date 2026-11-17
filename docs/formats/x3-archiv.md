# X3 archives (catalogs X3.00 / X3.10 / X3.20)

Derived from hex dumps and verified against the Lybac lists in
[Xenosaga3PythonExtractor/lba](https://github.com/LinuxJessi/Xenosaga3PythonExtractor/tree/main/lba)
(all samples byte-identical, incl. the index column). Implementation: `tools/x3toc.py`.

## Chains

| Catalog | Data parts | Disc | Content |
|---|---|---|---|
| `X3.00` (55 sectors) | `X3.01` + `X3.02` | both (identical) | menus, scripts, models, effects, sound, faces |
| `X3.10` (26 sectors) | `X3.11` + `X3.12` + `X3.13` | 1 | cutscenes, movies, voice |
| `X3.20` (13 sectors) | `X3.21` + `X3.22` + `X3.23` | 2 | cutscenes, movies, voice |

Each chain of data parts forms one contiguous address space (X3.x1, then X3.x2, …).
The catalog counts its own sectors:
`offset in chain = (sector − catalog sectors) × 2048`.

## Catalog format

```
byte 0      number of catalog sectors (u8)
from byte 1 entries up to the first 00 byte, then padding
            ("MONOLITHSOFT Xenosaga Episode.2" repeated)
```

**Directory** – first byte has bit 7 set:

```
[0x80 | reclen] [up] [ctrl] [name data]       reclen = total length of the entry
```
- `up`: go up this many levels first.
- The name is compressed against the previous name **on the same level** (see ctrl).

**File:**

```
[reclen] [ctrl] [name data] [sector u24 LE] [size u32 LE]
```

**Name compression (ctrl):**
- `ctrl == 0`: name data = complete name (terminated by 00).
- otherwise: `start = len(previous name) − (ctrl >> 4) − 1`.
  - If the name data ends with `00`: `new = previous[:start] + data`, the rest is cut off.
  - otherwise: the data overwrites `previous` from `start`, characters after it remain.
- The low nibble of ctrl equals the data length (redundant, not needed).

Example: `s000100.xep` → entry `03 61 "3"` → start = 11 − 6 − 1 = 4 → `s000300.xep`.

The "INDEX" column of the Lybac lists is the byte position of the sector field in the catalog – which is exactly where
`tools/x3rebuild.py` writes the new sector and size.

## Verification (`tools/x3stats.py`)

| Catalog | Files | used / chain | outside | overlaps | duplicate paths |
|---|---|---|---|---|---|
| X3.00 | 9 867 | 1 559 / 1 571 MiB | 0 | 0 | 0 |
| X3.10 | 3 649 | 2 141 / 2 145 MiB | 0 | 0 | 0 |
| X3.20 | 1 709 | 2 708 / 2 710 MiB | 0 | 0 | 0 |

The archives are packed without gaps (only the remainder up to the next sector boundary is free). Files that grow are
therefore moved to the end of their chain – see [iso-neuaufbau.md](iso-neuaufbau.md).
