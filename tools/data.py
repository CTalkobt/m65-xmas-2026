#!/usr/bin/env python3
"""data.py — the disk's data files: the music, and a file a scene, loaded
when the scene begins (main.c, with load.c).

    python3 tools/data.py <build dir> <scene> ... music

Reads <build dir>/<name>.dat (tools/blob.py's; music.dat tune45's), writes
  <name>.prg     the data after a two-byte load address (a PRG; load_far
                 skips it): a scene's for SLOT_LIN, the music's for MUSIC_LIN
  data.h         where they go and what they are called: MUSIC_LIN,
                 SLOT_LIN, SLOT_SIZE, <NAME>_LIN (every scene's is SLOT_LIN:
                 one is in memory at a time), <NAME>_FILE (its name on the
                 disk, PETSCII bytes) and <NAME>_FILE_LEN, SCRATCH_LIN

Bank 1 ($10000-$1FFFF) is BASIC's: free once the program runs, which never
goes back to it:
  $12000-$13DFF  the music, every tune (loaded once, at the start)
  $13E00-$13FFF  the greeting (GREETING, tools/card.py; loaded at the start)
  $14000-$1BFFF  the slot: the scene running's data
  $1C000-$1EFFF  the scratch area, a scene's own while it runs (the
                 sleigh's maps, unpacked)
"""
import os
import sys

MUSIC_LIN, MUSIC_END = 0x12000, 0x13E00
GREETING_LIN = 0x13E00                  # the plaque's greeting (tools/card.py), to $13FFF
SLOT_LIN, SLOT_END = 0x14000, 0x1C000
SCRATCH_LIN, SCRATCH_END = 0x1C000, 0x1F000


def petscii(name):
    return ", ".join("0x%02X" % ord(c) for c in name.upper())


def main():
    out, names = sys.argv[1], sys.argv[2:]
    lines = ["/* data.h — made by tools/data.py: the data files, where they go */",
             "#pragma once", "",
             "#define MUSIC_LIN    0x%05XUL   /* every tune (MUSIC, loaded at the start) */" % MUSIC_LIN,
             "#define SLOT_LIN     0x%05XUL   /* the scene running's data (its file) */" % SLOT_LIN,
             "#define SLOT_SIZE    %d" % (SLOT_END - SLOT_LIN),
             "#define SCRATCH_LIN  0x%05XUL   /* a scene's: what it unpacks to work from */" % SCRATCH_LIN,
             "#define SCRATCH_SIZE %d" % (SCRATCH_END - SCRATCH_LIN),
             "#define GREETING_LIN 0x%05XUL   /* \"GR\", two lines of 20 (tools/card.py) */" % GREETING_LIN,
             "#define GREETING_FILE {%s}" % petscii("greeting"),
             "#define GREETING_FILE_LEN 8", ""]
    for name in names:
        data = open(os.path.join(out, name + ".dat"), "rb").read()
        lin, end = (MUSIC_LIN, MUSIC_END) if name == "music" else (SLOT_LIN, SLOT_END)
        if lin + len(data) > end:
            raise SystemExit("%s: %d bytes, %d too many for $%X-$%X"
                             % (name, len(data), lin + len(data) - end, lin, end - 1))
        with open(os.path.join(out, name + ".prg"), "wb") as f:
            f.write(bytes([lin & 0xFF, (lin >> 8) & 0xFF]) + data)
        up = name.upper()
        if name != "music":
            lines.append("#define %-14s 0x%05XUL" % (up + "_LIN", lin))
        lines.append("#define %-14s {%s}" % (up + "_FILE", petscii(name)))
        lines.append("#define %-14s %d" % (up + "_FILE_LEN", len(name)))
        print("%-8s %6d bytes (%d free)" % (up, len(data), end - lin - len(data)))
    with open(os.path.join(out, "data.h"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
