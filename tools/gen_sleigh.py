#!/usr/bin/env python3
"""gen_sleigh.py — scene 3, the sleigh ride: drawn here.

    python3 tools/gen_sleigh.py <build dir> <pack45> [--preview]

THE SCREEN is 25 rows of 8-pixel full-colour cells:
  the sky       rows 0-8: still (stars, the moon)
  the bands     rows 9-24, three of them, each scrolling at its own speed:
                  mountains  rows  9-13, slow
                  hills      rows 14-18 (pines, a far village), middling
                  the near   rows 19-24 (drifts, pines, a fence), fast
Each band is a picture PERIOD pixels wide that repeats. Its top is drawn
in the flat colour of the band above it, and the sky's gradient is
dithered by line only (never by x): so where two bands meet, nothing shows
them sliding against each other.

THE CHARACTERS: every 8 x 8 cell of the sky and the bands, each different
one kept once, full colour (64 bytes, a byte a pixel), from character $1000
($40000) on. THE MAPS: a band's rows, each its period's cells and then its
first 41 again (so any 41-cell window is in one piece, copied by DMA as it
scrolls); the sky's rows, 41 cells. A map entry is a screen cell (the
character number, low byte first).

THE SPRITES (16 colours, 16 x 21, 8 bytes a row, 168 bytes, each from a
64-byte boundary (a pointer counts 64 bytes): 192 bytes apart; their own
palette): the sleigh in two (Santa, his sack, the runners), and a reindeer
in four frames of a gallop, the leader's nose red.

Writes, in the build directory: sleigh.dat and sleigh.h (tools/blob.py:
the packed characters, maps and sprites, the palettes, the bands' rows and
periods), sleigh.png (with --preview: the screen and a band's whole width).
"""
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blob  # noqa: E402
from font5x7 import FONT, FONT_ORDER  # noqa: E402

W, H = 320, 200
COLS, ROWS, MAPW = 40, 25, 41
CHAR_BASE = 0x1000                  # $40000 / 64
SPR_LIN = 0x57000                   # bank 5, below the overlays ($58000)
SPR_BYTES = 192                     # an image: 168 bytes, padded to three 64-byte blocks

SKY_ROWS = 9
BANDS = [  # name, first row, rows, period (pixels), speed (8.8 pixels a frame)
    ("mountains", 9, 5, 512, 0x40),
    ("hills", 14, 5, 384, 0x80),
    ("near", 19, 6, 256, 0x100),
]

rng = random.Random(1612)


def C(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


SKY = [C(h) for h in ("#04061c", "#080c2c", "#0e143c", "#141c4c", "#1c265c", "#26326c", "#323e78", "#3e4a84")]
STAR, STAR2 = C("#e8ecff"), C("#8890c0")
MOON, MOON2, MOON3, HALO = C("#f6f2da"), C("#dcd6b8"), C("#bcb69c"), C("#3a4684")
MTN, MTN2, MTN3, MCAP, MCAP2 = C("#3c4670"), C("#2e3660"), C("#4c5884"), C("#dfe6ff"), C("#a8b4dc")
MBASE = C("#2a3258")                 # the mountains' foot: flat, the hills' sky
HILL, HILL2, HSNOW, HSNOW2 = C("#202848"), C("#1a203c"), C("#8a98c8"), C("#6a78a8")
PINE, PINE2, PSNOW = C("#0e2a24"), C("#163a30"), C("#b8c4e8")
HBASE = C("#1a203a")                 # the hills' foot: flat, the near band's sky
LIT, LIT2, WALL = C("#ffd070"), C("#d09040"), C("#2a2030")
SNOW, SNOW2, SNOW3 = C("#eef2ff"), C("#c8d2f0"), C("#98a6d0")
FENCE, FENCE2 = C("#5a4636"), C("#3e2e24")
NPINE, NPINE2, NPINE3 = C("#123a2c"), C("#1c5038"), C("#0a261c")


def sky_colour(y):
    """the gradient by line: dithered between two shades by y alone"""
    t = y / 150 * (len(SKY) - 1)
    i = min(int(t), len(SKY) - 2)
    return SKY[i + 1] if (y * 7 % 8) / 8 < (t - i) else SKY[i]


# ------------------------------------------------------------------ the sky

def draw_sky():
    img = np.zeros((SKY_ROWS * 8, W, 3), dtype=np.uint8)
    for y in range(SKY_ROWS * 8):
        img[y, :] = sky_colour(y)
    for _ in range(70):
        x, y = rng.randrange(W), rng.randrange(SKY_ROWS * 8 - 4)
        img[y, x] = STAR if rng.random() < 0.3 else STAR2
    cx, cy, r = 74, 30, 17
    for y in range(max(0, cy - r - 9), cy + r + 10):
        for x in range(cx - r - 9, cx + r + 10):
            d = math.hypot(x - cx, y - cy)
            if d <= r:
                c = MOON if not (d > r - 2 and x < cx) else MOON2
                for mx, my, mr in ((-5, -3, 3.5), (6, 4, 3), (-2, 8, 2), (7, -6, 1.8), (-8, 5, 1.5)):
                    if (x - cx - mx) ** 2 + (y - cy - my) ** 2 <= mr * mr:
                        c = MOON3 if x - cx - mx < 0 else MOON2
                img[y, x] = c
            elif d <= r + 8 and (x + y) % 2 == 0 and d < r + 8 * (0.5 + 0.5 * ((x * 3 + y) % 3 == 0)):
                img[y, x] = HALO
    return img

# ------------------------------------------------------------------ the bands


def periodic(x, period, terms):
    return sum(a * math.sin(2 * math.pi * (k * x / period) + ph) for a, k, ph in terms)


def draw_mountains(period):
    """peaks: overlapping triangles (each wrapping round the period), lit
    on the moon's side (the left), shaded on the other, snow at the top"""
    h = 5 * 8
    y0 = 9 * 8
    img = np.zeros((h, period, 3), dtype=np.uint8)
    peaks = []
    x = 0
    while x < period - 20:
        peaks.append((x + rng.randrange(10, 30), 74 + rng.randrange(0, 18), 0.55 + rng.random() * 0.5))
        x += rng.randrange(36, 70)

    def at(x):
        """the top at x and the peak that makes it"""
        best, who = 999, None
        for px, py, sl in peaks:
            d = min(abs(x - px), period - abs(x - px))
            y = py + d * sl
            if y < best:
                best, who = y, (px, py, sl)
        return int(best), who

    for x in range(period):
        top, (px, py, sl) = at(x)
        dx = (x - px + period // 2) % period - period // 2
        for yy in range(h):
            y = y0 + yy
            if yy >= h - 8:
                c = MBASE                        # the foot: flat, the hills' sky
            elif y < top:
                c = sky_colour(y)
            else:
                d = y - top
                cap = y < py + 9 + int(2 * math.sin(x * 0.7)) and d < 7
                lit = dx < 0                      # the moon is on the left
                if cap:
                    c = MCAP if lit else MCAP2
                else:
                    c = MTN3 if lit else MTN2
                    if (x * 5 + y * 3) % 13 == 0:
                        c = MTN
                    if y >= y0 + h - 14:
                        c = mix(c, MBASE, min(1, (y - (y0 + h - 14)) / 6))
            img[yy, x] = c
    return img


def pine(img, cx, base, height, width, colours, snow, y0):
    dark, mid, cap = colours
    for t in range(3):
        ty0 = base - height + t * height // 4
        ty1 = base - height + (t + 2) * height // 4
        for y in range(ty0, min(ty1, base - 1)):
            hw = width / 2 * (0.4 + 0.6 * (t + 1) / 3) * (y - ty0 + 1) / (ty1 - ty0)
            for x in range(int(cx - hw), int(cx + hw) + 1):
                if 0 <= y - y0 < img.shape[0]:
                    c = mid if x > cx else dark
                    if y - ty0 < 2 and snow:
                        c = cap
                    img[y - y0, x % img.shape[1]] = c
    for y in range(base - 2, base + 1):
        if 0 <= y - y0 < img.shape[0]:
            img[y - y0, cx % img.shape[1]] = colours[0]


def draw_hills(period):
    h = 5 * 8
    y0 = 14 * 8
    img = np.zeros((h, period, 3), dtype=np.uint8)
    terms = [(6, 1, 0.5), (4, 2, 2.2), (2, 5, 1.0)]
    tops = []
    for x in range(period):
        top = int(126 - periodic(x, period, terms))
        tops.append(top)
        for yy in range(h):
            y = y0 + yy
            if yy >= h - 8:
                c = HBASE
            elif y < top:
                c = MBASE
            elif y < top + 3:
                c = HSNOW if (x + y) % 5 else HSNOW2
            else:
                c = HILL if (x * 3 + y * 5) % 11 else HILL2
                if y >= y0 + h - 12:
                    c = mix(c, HBASE, (y - (y0 + h - 12)) / 4)
            img[yy, x] = c
    # a forest along the ridge, and a far village with its windows lit
    for cx in range(4, period, 9):
        if 150 <= cx <= 230:
            continue
        hgt = 8 + rng.randrange(6)
        pine(img, cx, tops[cx] + 3, hgt, 6, (PINE, PINE2, PSNOW), True, y0)
    for hx in (160, 178, 200, 216):
        base = tops[hx] + 4
        w, hh = 10, 7
        for y in range(base - hh, base):
            for x in range(hx, hx + w):
                img[y - y0, x] = WALL
        for y in range(base - hh - 5, base - hh):
            for x in range(hx - 1 + (base - hh - y) - 0, hx + w + 1 - (base - hh - y)):
                if hx - 1 <= x <= hx + w:
                    img[y - y0, x] = HSNOW
        for wx in (hx + 2, hx + 6):
            img[base - 4 - y0, wx] = LIT
            img[base - 4 - y0, wx + 1] = LIT2
            img[base - 3 - y0, wx] = LIT2
    return img


def draw_near(period):
    h = 6 * 8
    y0 = 19 * 8
    img = np.zeros((h, period, 3), dtype=np.uint8)
    terms = [(4, 1, 0.0), (3, 3, 1.3), (1.5, 7, 2.1)]
    tops = []
    for x in range(period):
        top = int(172 - periodic(x, period, terms))
        tops.append(top)
        for yy in range(h):
            y = y0 + yy
            if y < top:
                c = HBASE
            else:
                d = y - top
                c = SNOW if d < 2 else (SNOW2 if d < 7 or (x * 7 + y * 3) % 13 == 0 else SNOW3)
                if d > 20 and (x + y * 3) % 17 == 0:
                    c = SNOW2
            img[yy, x] = c
    # a fence, its posts in the snow, and the snow on its rails
    for x in range(period):
        if 70 <= x < 190:
            t = tops[x]
            for ry in (t - 7, t - 3):
                img[ry - y0, x] = FENCE2
            if x % 12 == 0:
                for y in range(t - 10, t + 2):
                    img[y - y0, x] = FENCE
                    img[y - y0, x + 1] = FENCE2
                img[t - 11 - y0, x] = SNOW
                img[t - 11 - y0, x + 1] = SNOW
            img[t - 8 - y0, x] = SNOW2 if x % 3 else SNOW
    # pines, close: big and snowy
    for cx, w in ((30, 20), (220, 22), (244, 14)):
        base = tops[cx] + 2
        pine(img, cx, base, base - y0 - 1, w, (NPINE3, NPINE2, SNOW), True, y0)   # as tall as the band lets it
    return img


# ------------------------------------------------------------------ the sprites

SPAL = [(0, 0, 0), C("#101010"), C("#3a2214"), C("#6a4024"), C("#a0703c"), C("#d02020"), C("#801010"),
        C("#f4f4f4"), C("#a8a8b8"), C("#f0c030"), C("#9a7418"), C("#208040"), C("#f0c8a0"), C("#ff3020"),
        C("#fff8a0"), C("#80a0e0")]
KEY = ".KbBtRrWgYyGsNSl"   # a character a colour: . transparent

SLEIGH = [
    "................................",
    "...............WW...............",
    "..............WRRW..............",
    ".............WRRRRW.............",
    "....bbbb......WsssW.............",
    "...bBBBBb.....sKsK..............",
    "..bBBYBBBb....WWWW..............",
    "..bBBBBBBb...RRRRRR.............",
    ".bBBBYBBBBb.RRRRRRRR............",
    ".bBBBBBBBBbRRWRRRRWRR...........",
    "..RRRRRRRRRRRRRRRRRRRRRR........",
    "..RrRRRRRRRRRRRRRRRRRRRRR.......",
    "..RrYYYYYYYYYYYYYYYYYYRRRR......",
    "...RrRRRRRRRRRRRRRRRRRRRRR......",
    "....RrrRRRRRRRRRRRRRRRRRR.......",
    ".....rrrrrrrrrrrrrrrrrrr........",
    "......Y.....Y.......Y...........",
    ".....YY.....Y.......Y......Y....",
    "..YYYYYYYYYYYYYYYYYYYYYYYYYY....",
    "...........................YY...",
    "................................",
]

DEER_BODY = [
    "...........b..b.",
    "............bb..",
    "...........bB...",
    "..........BBBK..",
    "..........BBBBN.",
    ".........BBB....",
    "..BBBBBBBBB.....",
    ".BtBBBBBBBB.....",
    "BBBBBBBBBBB.....",
    ".BBBBBBBBBB.....",
    "..tttttttt......",
]
LEGS = [  # four frames of a gallop: the legs below the body (rows 11-16)
    ["..b.b.....b.b...", ".b...b...b...b..", "b.....b.b.....b.", "................",
     "................", "................"],
    ["...b.b...b.b....", "...b..b..b..b...", "..b....bb....b..", "................",
     "................", "................"],
    ["...bb.....bb....", "...bb.....bb....", "...b.b....b.b...", "................",
     "................", "................"],
    ["..b.b....b.b....", "..b..b..b...b...", ".b....bb.....b..", "................",
     "................", "................"],
]


def sprite(rows, nose=True):
    """16 x 21, 4 bits a pixel (the left pixel the low nibble), 8 bytes a row"""
    rows = [r.ljust(16, ".")[:16] for r in rows] + ["." * 16] * (21 - len(rows))
    out = bytearray()
    for r in rows[:21]:
        for i in range(0, 16, 2):
            a = KEY.index(r[i] if nose or r[i] != "N" else "B")
            b = KEY.index(r[i + 1] if nose or r[i + 1] != "N" else "B")
            out.append(a | b << 4)
    return out + bytes(SPR_BYTES - len(out))          # a pointer counts 64 bytes: 3 of them an image


SPARKS = [  # four frames of a twinkle
    ["", "", "", "", "", "", "", "", "Y", "", ""],
    ["", "", "", "", "", "", "", ".Y", "YSY", ".Y", ""],
    ["", "", "", "", "", "", "..Y", ".YSY", "YSWSY", ".YSY", "..Y"],
    ["", "", "", "", "", "", "", "..Y", ".YWY", "..Y", ""],
]


def sprites():
    imgs = bytearray()
    left = [r[:16] for r in SLEIGH]
    right = [r[16:] for r in SLEIGH]
    imgs += sprite(left) + sprite(right)
    for nose in (True, False):               # the leader's frames, then the others'
        for f in range(4):
            rows = ["................"] * 3 + DEER_BODY + LEGS[f]
            # the harness: a line through the chest to the one behind
            rows[3 + 8] = rows[3 + 8][:0] + "y" + rows[3 + 8][1:]
            imgs += sprite(rows, nose)
    for f in SPARKS:                         # the sparkles behind the sleigh
        imgs += sprite([("....." + r).ljust(16, ".") if r else "" for r in f])
    return imgs


# ------------------------------------------------------------------ the font
# 5 x 7, drawn here (in the manner of an LCD's), a shadow below and to the
# right so it reads on the snow; the glyph's rows shade from bright to dark.


TEXT_SHADES = [C("#ff6040"), C("#f04030"), C("#e02828"), C("#c81e1e"), C("#b01818"), C("#981414"), C("#801010")]
TEXT_SHADOW = C("#1a1030")


def font_cells():
    """a cell a glyph: 64 rgb tuples, None where it is clear (transparent)"""
    cells = []
    for ch in FONT_ORDER:
        rows = FONT[ch].split()
        px = [[None] * 8 for _ in range(8)]
        for y, r in enumerate(rows):
            for x, b in enumerate(r):
                if b == "1" and px[y + 1][x + 2] is None:
                    px[y + 1][x + 2] = TEXT_SHADOW
        for y, r in enumerate(rows):
            for x, b in enumerate(r):
                if b == "1":
                    px[y][x + 1] = TEXT_SHADES[y]
        cells.append(px)
    return cells

# ------------------------------------------------------------------ build


def main():
    out, pack45 = sys.argv[1], sys.argv[2]
    sky = draw_sky()
    bands = {"mountains": draw_mountains, "hills": draw_hills, "near": draw_near}
    band_imgs = [bands[name](period) for name, _, _, period, _ in BANDS]

    pal, where = [(0, 0, 0)], {(0, 0, 0): 0}
    chars, char_of = [], {}

    def cell(block):
        key = []
        for y in range(8):
            for x in range(8):
                c = tuple(int(v) for v in block[y, x])
                if c not in where:
                    where[c] = len(pal)
                    pal.append(c)
                key.append(where[c])
        key = bytes(key)
        if key not in char_of:
            char_of[key] = len(chars)
            chars.append(key)
        return CHAR_BASE + char_of[key]

    def put(m, ch):
        m.append(ch & 0xFF)
        m.append(ch >> 8)

    maps = bytearray()
    sky_map = bytearray()
    for r in range(SKY_ROWS):
        for c in range(MAPW):
            put(sky_map, cell(sky[r * 8:r * 8 + 8, (c % COLS) * 8:(c % COLS) * 8 + 8]))
    maps += sky_map
    band_info = []
    for (name, row0, rows, period, speed), img in zip(BANDS, band_imgs):
        pc = period // 8
        start = len(maps)
        for r in range(rows):
            for c in range(pc + MAPW):
                cc = c % pc
                put(maps, cell(img[r * 8:r * 8 + 8, cc * 8:cc * 8 + 8]))
        band_info.append((name, row0, rows, pc, speed, start, (pc + MAPW) * 2))
    if len(pal) > 255:
        raise SystemExit("palette full: %d" % len(pal))
    if CHAR_BASE * 64 + len(chars) * 64 > SPR_LIN:
        raise SystemExit("%d characters: past the sprites at $%X" % (len(chars), SPR_LIN))

    def pack(name, data, dest):
        raw = os.path.join(out, name + ".bin")
        pck = os.path.join(out, name + ".pck")
        open(raw, "wb").write(data)
        subprocess.run([pack45, "--raw", "--best", "-d", "0x%X" % dest, raw, pck], check=True,
                       stdout=subprocess.DEVNULL)
        return open(pck, "rb").read()

    scene_chars = len(chars)
    chars.append(bytes(64))                  # black (the edges), then the font
    for px in font_cells():
        key = []
        for row in px:
            for c in row:
                if c is None:
                    key.append(0)
                else:
                    if c not in where:
                        where[c] = len(pal)
                        pal.append(c)
                    key.append(where[c])
        chars.append(bytes(key))
    if len(pal) > 255:
        raise SystemExit("palette full: %d" % len(pal))
    if CHAR_BASE * 64 + len(chars) * 64 > SPR_LIN:
        raise SystemExit("%d characters: past the sprites at $%X" % (len(chars), SPR_LIN))
    text_map = [0] * 128                     # a character (ASCII, upper case) to its glyph
    for i, ch in enumerate(FONT_ORDER):
        text_map[ord(ch)] = i
    chr_pck = pack("sleigh_chr", b"".join(chars), CHAR_BASE * 64)
    map_pck = pack("sleigh_map", bytes(maps), 0)
    spr = sprites()
    spr_pck = pack("sleigh_spr", bytes(spr), SPR_LIN)

    defs = [("SLEIGH_COLOURS", len(pal)), ("SLEIGH_CHARS", scene_chars), ("SKY_ROWS", SKY_ROWS),
            ("CH_BLACK", "(CH0 + %d)  /* a black cell */" % scene_chars),
            ("CH_FONT", "(CH0 + %d)  /* the font's glyphs, in text_map's order */" % (scene_chars + 1)),
            ("MAPW", MAPW), ("NBANDS", len(BANDS)), ("MAP_BYTES", len(maps)),
            ("SPR_LIN", "0x%XUL" % SPR_LIN), ("SPR_SLEIGH", "0x%X  /* the sprite pointers: SPR_LIN / 64 + ... */"
                                               % (SPR_LIN // 64)),
            ("SPR_STEP", "%d  /* pointers an image (192 bytes) */" % (SPR_BYTES // 64)),
            ("SPR_DEER", "(SPR_SLEIGH + 2 * SPR_STEP)  /* four frames: the leader's (the red nose) */"),
            ("SPR_DEER2", "(SPR_SLEIGH + 6 * SPR_STEP)  /* four frames: the others' */"),
            ("SPR_SPARK", "(SPR_SLEIGH + 10 * SPR_STEP)  /* four frames: a twinkle */")]
    tables = [("pal", "[SLEIGH_COLOURS][3]", bytes(v for c in pal for v in c)),
              ("spal", "[16][3]  /* the sprites' palette */", bytes(v for c in SPAL for v in c)),
              ("text_map", "[128]  /* ASCII (upper case) to the font's glyph: CH_FONT + it */", text_map),
              ("band_row", "[NBANDS]", [b[1] for b in band_info]),
              ("band_rows", "[NBANDS]", [b[2] for b in band_info]),
              ("band_cells", "[NBANDS]  /* the period, in cells */", [b[3] for b in band_info]),
              ("band_speed", "[NBANDS][2]  /* 8.8 pixels a frame, low byte first */",
               b"".join(bytes([b[4] & 0xFF, b[4] >> 8]) for b in band_info)),
              ("band_map", "[NBANDS][2]  /* its rows' offset in the maps */",
               b"".join(bytes([b[5] & 0xFF, b[5] >> 8]) for b in band_info)),
              ("band_stride", "[NBANDS][2]  /* bytes a map row */",
               b"".join(bytes([b[6] & 0xFF, b[6] >> 8]) for b in band_info))]
    blob.write(out, "sleigh", streams=[("chr_pck", chr_pck), ("map_pck", map_pck), ("spr_pck", spr_pck)],
               tables=tables, defines=defs, comment="the sleigh ride (tools/gen_sleigh.py)")
    print("sleigh: %d colours, %d characters (%d bytes packed), maps %d (%d packed), sprites %d (%d packed)"
          % (len(pal), len(chars), len(chr_pck), len(maps), len(map_pck), len(spr), len(spr_pck)))
    if "--preview" in sys.argv:
        screen = np.zeros((H, W, 3), dtype=np.uint8)
        screen[:SKY_ROWS * 8] = sky
        for (name, row0, rows, period, _), img in zip(BANDS, band_imgs):
            screen[row0 * 8:(row0 + rows) * 8] = np.tile(img, (1, 2, 1))[:, :W]
        # the team over it, at a place in the sky
        sp = np.zeros((21, 16 * 6, 4), dtype=np.uint8)
        frames = [SLEIGH] + [["................"] * 3 + DEER_BODY + LEGS[i % 4] for i in range(4)]
        x = 0
        for i, rows in enumerate([[r[:32] for r in SLEIGH]] + frames[1:]):
            for y, r in enumerate(rows[:21]):
                for xx, ch in enumerate(r):
                    if ch != "." and ch in KEY:
                        screen[60 + y, 120 + x + xx] = SPAL[KEY.index(ch)]
            x += 32 if i == 0 else 18
        Image.fromarray(screen).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, "sleigh.png"))


if __name__ == "__main__":
    main()
