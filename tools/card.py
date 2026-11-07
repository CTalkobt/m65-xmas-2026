#!/usr/bin/env python3
"""card.py — the greeting on the snow globe's plaque: the GREETING file.

    python3 tools/card.py <out.prg> "<line 1>" "<line 2>"

Two lines of at most 20 characters each, of the font's: letters, digits,
space and . , ! ? ' - : & * ( ) @ (lower case is made upper; anything else is a
space). The file: a load address (GREETING_LIN's low 16 bits, data.py's),
"GR", then each line, 20 bytes, space-padded. The program loads it at its
start; the finale (finale.c) shows it, each line centred. Without the file
(or with a bad one) it shows its own: MERRY CHRISTMAS / AND A HAPPY NEW
YEAR.

    make card LINE1="TO THE SMITHS" LINE2="LOVE FROM JO & SAM"

writes it and puts it on the disk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from font5x7 import FONT_ORDER  # noqa: E402

GREETING_LIN = 0x13E00
WIDTH = 20


def line(s):
    s = s.upper()
    if len(s) > WIDTH:
        raise SystemExit("a line of the greeting is %d characters: %d at most (%r)" % (len(s), WIDTH, s))
    return bytes(ord(c) if c in FONT_ORDER else 32 for c in s.ljust(WIDTH))


def main():
    out, l1, l2 = sys.argv[1], sys.argv[2], sys.argv[3]
    data = b"GR" + line(l1) + line(l2)
    with open(out, "wb") as f:
        f.write(bytes([GREETING_LIN & 0xFF, (GREETING_LIN >> 8) & 0xFF]) + data)
    print("greeting: %r / %r" % (l1.upper(), l2.upper()))


if __name__ == "__main__":
    main()
