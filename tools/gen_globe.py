#!/usr/bin/env python3
"""gen_globe.py — scene 6, the finale: a snow globe, drawn here.

    python3 tools/gen_globe.py <build dir> <pack45> [--preview]

A snow globe on a turned wooden base, on a table, the room dark behind it
with lights out of focus. In the globe: a night sky, a tiny village (a
church, cottages with their windows lit, pines) on the snow. On the base,
a gold plaque: the greeting goes there (finale.c writes it, two lines of
PLAQUE_W letters, in the plaque's glyphs: engraved). The bottom row is
black: the credits scroll along it (the credits' glyphs: pale on black).

THE PICTURE is 41 cells (328 pixels) wide (a cell touching the globe has a
character of its own: snow settles into them; the rest are kept once): every row starts with a GOTOX
8, and the plane's first and last 8 pixels on the screen are covered
black (as the sleigh ride's rows), so picture x shows at screen x + 8 and
x 0-303 is what is seen. Cells are kept once each; the map is the screen's
rows, 41 cells each.

FOR THE SNOW: span_l[y], span_r[y] (y from GLOBE_TOP, GLOBE_ROWS of them):
the globe's inside on that pixel row, picture x; ground[x] (x from
GLOBE_LEFT, GLOBE_COLS of them): the top of what is solid in the globe in
that column (the snow, the roofs, the trees), where the snow settles.

Writes, in the build directory: globe.dat and globe.h (tools/blob.py),
globe.png (with --preview).
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
from font5x7 import FONT, FONT_ORDER, text_map  # noqa: E402

PW, H = 328, 200                     # the picture: 41 cells
MAPW, ROWS = 41, 25
CHAR_BASE = 0x1000
GX, GY, GR = 152, 78, 66             # the globe: its middle and radius
PLAQUE_ROW, PLAQUE_COL, PLAQUE_W = 19, 9, 20
G_ROOM, G_BOKEH = 0, 1

img = np.zeros((H, PW, 3), dtype=np.uint8)
grp = np.zeros((H, PW), dtype=np.uint8)
solid = np.zeros((H, PW), dtype=bool)
rng = random.Random(1225)


def C(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def px(x, y, c, g=G_ROOM, s=False):
    if 0 <= x < PW and 0 <= y < H:
        img[y, x] = c
        grp[y, x] = g
        solid[y, x] = s


ROOM, ROOM2 = C("#120a1c"), C("#1e1230")
BOKEH = [C("#c08030"), C("#a04040"), C("#d0a050"), C("#3a6a9a")]
TABLE, TABLE2, TABLE3 = C("#3a2014"), C("#2a160e"), C("#5a3420")
SKY = [C("#060a28"), C("#0c143c"), C("#142050"), C("#1e2c64")]
STAR = C("#e0e8ff")
SNOW, SNOW2, SNOW3 = C("#f0f4ff"), C("#c4d0f0"), C("#8c9cc8")
WALL, ROOF, LIT, PINE, PINE2 = C("#4a3a48"), C("#6a2a2a"), C("#ffd070"), C("#164a30"), C("#0e3420")
STONE = C("#7a7a88")
GLASS, GLINT = C("#d8e8ff"), C("#ffffff")
BASE, BASE2, BASE3 = C("#5a2e18"), C("#3e1e10"), C("#7a4426")
GOLD, GOLD2, GOLD3, ENGRAVE = C("#e0b850"), C("#b08a30"), C("#f8e090"), C("#5a3a10")
CREDIT = C("#c8dcff")


def inside(x, y, r=GR):
    return (x - GX) ** 2 + (y - GY) ** 2 < r * r


def draw():
    # the room: dark, a glow behind the globe, lights out of focus
    for y in range(H):
        for x in range(PW):
            d = math.hypot(x - GX, (y - GY) * 1.3)
            c = mix(ROOM2, ROOM, min(1, d / 170))
            if (x + y * 3) % 7 == 0 and d > 120:
                c = ROOM
            px(x, y, c)
    for _ in range(14):
        bx, by, br = rng.randrange(10, 300), rng.randrange(10, 120), rng.randrange(4, 9)
        if math.hypot(bx - GX, by - GY) < GR + br + 6:
            continue
        col = rng.choice(BOKEH)
        for y in range(by - br, by + br + 1):
            for x in range(bx - br, bx + br + 1):
                d = math.hypot(x - bx, y - by)
                if d <= br and ((x + y) % 2 == 0 or d < br - 2):
                    px(x, y, mix(col, ROOM, 0.35 + 0.4 * d / br), G_BOKEH)
    # the table
    for y in range(160, 192):
        for x in range(PW):
            c = TABLE3 if y == 160 else (TABLE2 if (x + (y - 160) * 11) % 37 == 0 or y > 186 else TABLE)
            px(x, y, c)
    # the globe's inside: the sky, the stars
    for y in range(GY - GR, GY + GR):
        for x in range(GX - GR, GX + GR):
            if inside(x, y):
                t = (y - (GY - GR)) / (2 * GR) * (len(SKY) - 1)
                i = min(int(t), len(SKY) - 2)
                px(x, y, SKY[i + 1] if ((x + y) % 2 == 0 and t - i > 0.5) else SKY[i])
    for _ in range(30):
        x, y = rng.randrange(GX - GR, GX + GR), rng.randrange(GY - GR, GY)
        if inside(x, y, GR - 4):
            px(x, y, STAR)
    # the village in it
    ground = lambda x: int(GY + 30 + 4 * math.sin((x - GX) / 14))
    for x in range(GX - GR, GX + GR):
        for y in range(ground(x), GY + GR):
            if inside(x, y):
                px(x, y, SNOW if y - ground(x) < 2 else (SNOW2 if (x + y) % 5 else SNOW3), s=True)
    for hx, hw, hh in ((112, 14, 10), (164, 12, 9), (180, 16, 11)):
        base = ground(hx + hw // 2) + 1
        for y in range(base - hh, base):
            for x in range(hx, hx + hw):
                px(x, y, WALL, s=True)
        for y in range(base - hh - hw // 2, base - hh):
            k = base - hh - y
            for x in range(hx - 1 + k, hx + hw + 1 - k):
                px(x, y, ROOF if y > base - hh - hw // 2 + 1 else SNOW, s=True)
        for wx in range(hx + 2, hx + hw - 3, 5):
            px(wx, base - hh + 3, LIT, s=True)
            px(wx + 1, base - hh + 3, LIT, s=True)
            px(wx, base - hh + 4, LIT, s=True)
            px(wx + 1, base - hh + 4, LIT, s=True)
    # the church: a tower and a spire
    cx, base = 140, ground(140) + 1
    for y in range(base - 22, base):
        for x in range(cx - 5, cx + 5):
            px(x, y, STONE, s=True)
    for y in range(base - 36, base - 22):
        w = (y - (base - 36)) * 5 // 14
        for x in range(cx - w, cx + w + 1):
            px(x, y, ROOF, s=True)
    px(cx, base - 37, GOLD3, s=True)
    px(cx, base - 16, LIT, s=True)
    px(cx, base - 15, LIT, s=True)
    for tx, th in ((124, 14), (202, 16), (96, 11)):
        tb = ground(tx) + 1
        for y in range(tb - th, tb):
            w = (y - (tb - th)) * 4 // th + 1
            for x in range(tx - w, tx + w + 1):
                px(x, y, SNOW if (y - (tb - th)) % 4 == 0 and abs(x - tx) == w else (PINE if x <= tx else PINE2),
                   s=True)
    # the glass: its rim, a glint
    for y in range(GY - GR - 2, GY + GR + 2):
        for x in range(GX - GR - 2, GX + GR + 2):
            d = math.hypot(x - GX, y - GY)
            if GR - 1.5 <= d < GR + 1:
                a = math.atan2(y - GY, x - GX)
                lit = -2.6 < a < -1.2
                px(x, y, GLINT if lit else mix(GLASS, ROOM2, 0.6), s=True)
            elif GR - 12 <= d < GR - 8 and -2.5 < math.atan2(y - GY, x - GX) < -1.6 and (x + y) % 2 == 0:
                px(x, y, GLASS)
    # the base: turned wood, a gold trim, and the plaque
    for y in range(GY + GR - 8, 160):
        t = (y - (GY + GR - 8)) / (160 - (GY + GR - 8))
        hw = 50 + t * 34
        for x in range(int(GX - hw), int(GX + hw) + 1):
            if y < GY + GR - 2 and inside(x, y, GR + 1):
                continue
            c = BASE3 if x < GX - hw * 0.6 else (BASE2 if x > GX + hw * 0.6 else BASE)
            if y in (GY + GR - 2, 157):
                c = GOLD
            px(x, y, c)
    for y in range(160, 166):                         # the base's shadow on the table
        for x in range(GX - 90, GX + 91):
            if (x + y) % 2 == 0:
                px(x, y, TABLE2)
    x0, x1 = PLAQUE_COL * 8 - 6, (PLAQUE_COL + PLAQUE_W) * 8 + 6
    y0, y1 = PLAQUE_ROW * 8 - 4, (PLAQUE_ROW + 2) * 8 + 4
    for y in range(y0, y1):
        for x in range(x0, x1):
            edge = y in (y0, y1 - 1) or x in (x0, x1 - 1)
            px(x, y, GOLD3 if edge and y == y0 else (GOLD2 if edge else GOLD))
    # the bottom row: black, for the credits
    for y in range(192, 200):
        for x in range(PW):
            px(x, y, (0, 0, 0))


def glyphs(fg, bg, shadow=None, light=None):
    """the font's cells: a glyph a cell, fg on bg, an engraving's shadow
    above it and light below it (the plaque's) if given"""
    cells = []
    for ch in FONT_ORDER:
        rows = FONT[ch].split()
        c = [[bg] * 8 for _ in range(8)]
        for y, r in enumerate(rows):
            for x, b in enumerate(r):
                if b == "1":
                    if light and c[y + 1][x + 2] == bg:
                        c[y + 1][x + 2] = light
                    if shadow and y > 0 and c[y - 1][x + 1] == bg:
                        c[y - 1][x + 1] = shadow
        for y, r in enumerate(rows):
            for x, b in enumerate(r):
                if b == "1":
                    c[y][x + 1] = fg
        cells.append(c)
    return cells


def main():
    out, pack45 = sys.argv[1], sys.argv[2]
    draw()
    # the globe's inside a row at a time, and the top of the solid a column
    top, bottom = GY - GR + 2, GY + GR - 2
    span_l, span_r = [], []
    for y in range(top, bottom):
        w = math.sqrt(max(0, (GR - 3) ** 2 - (y - GY) ** 2))
        span_l.append(int(math.ceil(GX - w)))
        span_r.append(int(GX + w))
    left, right = GX - GR + 3, GX + GR - 3
    ground = []
    for x in range(left, right):
        ys = [y for y in range(top, bottom) if solid[y, x] and inside(x, y, GR - 2)]
        ground.append(ys[0] if ys else bottom)

    pal, group, where = [(0, 0, 0)], [G_ROOM], {((0, 0, 0), G_ROOM): 0}
    P_SNOW = 1
    pal.append(SNOW)
    group.append(G_ROOM)
    where[(SNOW, G_ROOM)] = 1

    def entry(c, g=G_ROOM):
        key = (tuple(int(v) for v in c), g)
        if key not in where:
            where[key] = len(pal)
            pal.append(key[0])
            group.append(g)
        return where[key]

    chars, char_of = [], {}

    def char(key, unique=False):
        key = bytes(key)
        if unique:                                  # the globe's: snow is plotted into them
            chars.append(key)
            return CHAR_BASE + len(chars) - 1
        if key not in char_of:
            char_of[key] = len(chars)
            chars.append(key)
        return CHAR_BASE + char_of[key]

    screen = bytearray()
    for r in range(ROWS):
        for c in range(MAPW):
            key = [entry(img[r * 8 + y, c * 8 + x], int(grp[r * 8 + y, c * 8 + x]))
                   for y in range(8) for x in range(8)]
            near = abs(c * 8 + 4 - GX) < GR + 6 and abs(r * 8 + 4 - GY) < GR + 6 and \
                math.hypot(max(0, abs(c * 8 + 4 - GX) - 4), max(0, abs(r * 8 + 4 - GY) - 4)) < GR
            ch = char(key, unique=near)
            screen += bytes([ch & 0xFF, ch >> 8])
    scene_chars = len(chars)
    extra = [bytes(64)]                                            # black
    flake = [0] * 64
    flake[56] = P_SNOW
    extra += [bytes(flake), bytes(64)]                             # the flake, a blank after it
    for cell in glyphs(ENGRAVE, GOLD, shadow=GOLD2, light=GOLD3):  # the plaque's
        extra.append(bytes(entry(c) for row in cell for c in row))
    for cell in glyphs(CREDIT, (0, 0, 0)):                         # the credits'
        extra.append(bytes(entry(c) for row in cell for c in row))
    chars += extra
    if len(pal) > 256:
        raise SystemExit("palette full: %d" % len(pal))

    def pack(name, data, dest):
        raw, pck = os.path.join(out, name + ".bin"), os.path.join(out, name + ".pck")
        open(raw, "wb").write(data)
        subprocess.run([pack45, "--raw", "--best", "-d", "0x%X" % dest, raw, pck], check=True,
                       stdout=subprocess.DEVNULL)
        return open(pck, "rb").read()

    chr_pck = pack("globe_chr", b"".join(chars), CHAR_BASE * 64)
    map_pck = pack("globe_map", bytes(screen), 0)
    nf = len(FONT_ORDER)
    defs = [("GLOBE_COLOURS", len(pal)), ("P_SNOW", P_SNOW), ("G_ROOM", G_ROOM), ("G_BOKEH", G_BOKEH),
            ("MAPW", MAPW), ("GLOBE_X", GX), ("GLOBE_Y", GY), ("GLOBE_R", GR),
            ("GLOBE_TOP", top), ("GLOBE_ROWS", bottom - top), ("GLOBE_LEFT", left), ("GLOBE_COLS", right - left),
            ("PLAQUE_ROW", PLAQUE_ROW), ("PLAQUE_COL", PLAQUE_COL), ("PLAQUE_W", PLAQUE_W),
            ("CREDIT_ROW", ROWS - 1),
            ("CH_BLACK", "(CH0 + %d)" % scene_chars),
            ("CH_FLAKE", "(CH0 + %d)  /* a dot on its last row, a blank after it */" % (scene_chars + 1)),
            ("CH_PLAQUE", "(CH0 + %d)  /* the plaque's glyphs: + text_map[c] */" % (scene_chars + 3)),
            ("CH_CREDIT", "(CH0 + %d)  /* the credits' glyphs */" % (scene_chars + 3 + nf))]
    blob.write(out, "globe", streams=[("chr_pck", chr_pck), ("map_pck", map_pck)],
               tables=[("pal", "[GLOBE_COLOURS][3]", bytes(v for c in pal for v in c)),
                       ("group", "[GLOBE_COLOURS]", group),
                       ("text_map", "[128]  /* ASCII (upper case) to a glyph */", text_map()),
                       ("span_l", "[GLOBE_ROWS]  /* the globe's inside: picture x */", span_l),
                       ("span_r", "[GLOBE_ROWS]", span_r),
                       ("ground", "[GLOBE_COLS]  /* the top of the solid in the globe */", ground)],
               defines=defs, comment="the finale (tools/gen_globe.py)")
    print("globe: %d colours, %d characters (%d bytes packed), map %d packed"
          % (len(pal), len(chars), len(chr_pck), len(map_pck)))
    if "--preview" in sys.argv:
        prev = img[:, :304].copy()
        msg = ["MERRY CHRISTMAS", "AND A HAPPY NEW YEAR"]
        gl = glyphs(ENGRAVE, GOLD, shadow=GOLD2, light=GOLD3)
        for li, line in enumerate(msg):
            c0 = PLAQUE_COL + (PLAQUE_W - len(line)) // 2
            for i, ch in enumerate(line):
                cell = gl[FONT_ORDER.index(ch)]
                for y in range(8):
                    for x in range(8):
                        prev[(PLAQUE_ROW + li) * 8 + y, (c0 + i) * 8 + x] = cell[y][x]
        Image.fromarray(prev).resize((304 * 2, H * 2), Image.NEAREST).save(os.path.join(out, "globe.png"))


if __name__ == "__main__":
    main()
