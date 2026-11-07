#!/usr/bin/env python3
"""gen_fire.py — scene 5, the fireside: drawn here.

    python3 tools/gen_fire.py <build dir> <pack45> [--preview]

A hearth close to: the stone fireplace, the mantel (a clock, candles, a
garland with lights), three stockings, an armchair, a cat asleep on the rug,
a basket of logs. The fire itself is fireside.c's: a region FIRE_W x FIRE_H
of cells at (FIRE_COL, FIRE_ROW) whose characters it writes every frame.

THE FIRE'S CHARACTERS go down the columns: cell (FIRE_COL + c, FIRE_ROW +
r) is character FIRE_CHAR + c * FIRE_ROWS + r. So a column of cells is one
run of memory, 8 pixels wide and FIRE_H tall, a pixel row 8 bytes on from
the last, and the whole fire is one buffer (column, then row, then pixel)
fireside.c copies by DMA. A pixel is the palette entry P_FIRE + its heat
(0-63: black, embers, red, orange, yellow, white).

The rest is cells of the picture, each different one kept once; its
palette entries are in groups: the room (lit by the fire: it flickers with
it), the garland's four light channels.

Writes, in the build directory: fire.dat and fire.h (tools/blob.py), and
fire.png (with --preview).
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

W, H = 320, 200
COLS, ROWS = 40, 25
CHAR_BASE = 0x1000
FIRE_COL, FIRE_ROW, FIRE_COLS, FIRE_ROWS = 16, 14, 8, 7
G_ROOM, G_LIGHT, G_FIRE = 0, 1, 255

img = np.zeros((H, W, 3), dtype=np.uint8)
grp = np.zeros((H, W), dtype=np.uint8)
rng = random.Random(2412)


def C(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def px(x, y, c, g=G_ROOM):
    if 0 <= x < W and 0 <= y < H:
        img[y, x] = c
        grp[y, x] = g


def rect(x0, y0, x1, y1, c, g=G_ROOM):
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            px(x, y, c, g)


WALL, WALL2, WALL3 = C("#1c3a2c"), C("#163024"), C("#24483a")
STONE, STONE2, STONE3, STONE4 = C("#a89a86"), C("#8c7e6c"), C("#c4b8a4"), C("#6e6254")
SOOT, SOOT2, BRICK = C("#120c0a"), C("#1c1210"), C("#3a1a14")
WOOD, WOOD2, WOOD3 = C("#5a3420"), C("#44261a"), C("#76482c")
LOG, LOG2, EMBER = C("#4a2c1a"), C("#2e1a10"), C("#c03010")
FLOOR, FLOOR2 = C("#3a2418"), C("#2c1a12")
RUG, RUG2, RUG3 = C("#7a1e22"), C("#5a1418"), C("#c89a3a")
CHAIR, CHAIR2, CHAIR3 = C("#8a1c24"), C("#64121a"), C("#a83038")
CAT, CAT2, CAT3, CATW = C("#7a6a5c"), C("#5a4c40"), C("#9a8a7a"), C("#e8e0d4")
GOLD, GOLD2, CREAM = C("#d8b048"), C("#9a7a2a"), C("#f0e8d0")
NEEDLE, NEEDLE2 = C("#1e5a34"), C("#143e24")
STOCKS = [(C("#c02020"), C("#f0f0f0")), (C("#20803c"), C("#f0f0f0")), (C("#c02020"), C("#20803c"))]
LIGHTS = [C("#ff4040"), C("#40ff60"), C("#ffd040"), C("#60a0ff")]
FLAME = [C("#ffb040"), C("#ffe080")]


def fire_colours():
    stops = [(0, (8, 4, 4)), (10, (60, 8, 4)), (22, (170, 30, 8)), (34, (240, 90, 16)),
             (46, (255, 170, 40)), (56, (255, 230, 120)), (63, (255, 255, 230))]
    out = []
    for h in range(64):
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= h <= b:
                out.append(mix(ca, cb, (h - a) / (b - a)))
                break
    return out


def draw():
    # the wall: panels of striped paper
    for y in range(0, 176):
        for x in range(W):
            c = WALL3 if x % 12 == 0 else (WALL2 if (x // 12 + y // 40) % 2 and x % 12 == 6 else WALL)
            px(x, y, c)
    rect(0, 120, W, 123, WOOD3)                 # the dado rail
    for x0 in range(0, W, 48):
        for y in range(128, 172):
            px(x0 + 4, y, WALL3)
            px(x0 + 44, y, WALL2)
        for x in range(x0 + 4, x0 + 45):
            px(x, 128, WALL3)
            px(x, 171, WALL2)
    # the fireplace: dressed stone
    for y in range(64, 176):
        for x in range(80, 240):
            row = (y - 64) // 10
            joint = (y - 64) % 10 == 9 or (x + row * 13) % 26 == 0
            c = STONE4 if joint else (STONE2 if (x // 26 + row) % 3 == 0 else STONE)
            if not joint and (x * 7 + y * 3) % 17 == 0:
                c = STONE3
            px(x, y, c)
    # the firebox: an arch, soot and old bricks
    for y in range(96, 176):
        for x in range(112, 208):
            if y < 112 and ((x - 160) / 48) ** 2 + ((y - 112) / 16) ** 2 > 1:
                continue
            b = (y - 96) // 6
            c = SOOT2 if (y - 96) % 6 == 5 or (x + b * 6) % 12 == 0 else SOOT
            if (x * 5 + y) % 23 == 0:
                c = BRICK
            px(x, y, c)
    # the fire's region: fireside.c's (its cells written every frame)
    for y in range(FIRE_ROW * 8, (FIRE_ROW + FIRE_ROWS) * 8):
        for x in range(FIRE_COL * 8, (FIRE_COL + FIRE_COLS) * 8):
            grp[y, x] = G_FIRE
    # the logs, glowing at their ends
    for y in range(168, 176):
        for x in range(122, 198):
            if ((x - 160) / 38) ** 2 + ((y - 172) / 4) ** 2 <= 1:
                c = LOG2 if (x + y * 2) % 7 == 0 else LOG
                if abs(x - 160) > 32:
                    c = EMBER
                px(x, y, c)
    # the hearth and the floor
    rect(70, 176, 250, 184, STONE3)
    rect(70, 183, 250, 184, STONE4)
    for y in range(184, H):
        for x in range(W):
            px(x, y, FLOOR2 if (y - 184) % 5 == 4 or (x + (y // 5) * 29) % 53 == 0 else FLOOR)
    # the mantel
    rect(66, 56, 254, 64, WOOD)
    rect(66, 63, 254, 65, WOOD2)
    rect(66, 56, 254, 57, WOOD3)
    # the clock
    rect(148, 22, 172, 56, WOOD2)
    rect(150, 24, 170, 56, WOOD)
    for y in range(28, 48):
        for x in range(150, 171):
            d = (x - 160) ** 2 + (y - 38) ** 2
            if d <= 64:
                px(x, y, CREAM if d < 56 else GOLD)
    for i in range(6):
        px(160, 38 - i, SOOT)
    for i in range(4):
        px(160 + i, 38, SOOT)
    rect(156, 50, 165, 53, GOLD2)                  # the pendulum's window
    # candles
    for cx in (96, 224):
        rect(cx - 2, 36, cx + 3, 56, CREAM)
        rect(cx - 4, 54, cx + 5, 56, GOLD)
        px(cx, 33, FLAME[1])
        px(cx, 34, FLAME[0])
        px(cx, 35, FLAME[0])
        px(cx, 32, FLAME[1])
    # the garland along the mantel's front, its lights
    for x in range(66, 254):
        y = 64 + int(3 * abs(math.sin(x * math.pi / 30)))
        px(x, y, NEEDLE)
        px(x, y + 1, NEEDLE2)
        if x % 10 == 5:
            c = (x // 10) % 4
            px(x, y + 1, LIGHTS[c], G_LIGHT + c)
            px(x, y + 2, LIGHTS[c], G_LIGHT + c)
    # stockings
    for i, sx in enumerate((96, 168, 216)):
        body, cuff = STOCKS[i]
        rect(sx, 66, sx + 10, 70, cuff)
        rect(sx + 1, 70, sx + 9, 88, body)
        for y in range(84, 93):
            for x in range(sx + 1, sx + 17):
                if (x - sx - 8) ** 2 / 64 + (y - 88) ** 2 / 16 <= 1:
                    px(x, y, body)
        for y in range(72, 88, 4):
            rect(sx + 2, y, sx + 8, y + 1, cuff)
    # the armchair, at the left
    for y in range(96, 192):
        for x in range(0, 64):
            back = y < 140 and x < 44
            arm = 128 <= y < 150 and x < 62
            seat = y >= 150 and x < 60
            if back or arm or seat:
                c = CHAIR
                if back and (x % 11 == 5 or (y - 96) % 11 == 5):
                    c = CHAIR2                      # buttoned
                if arm and y < 132:
                    c = CHAIR3
                if seat and y >= 184:
                    c = WOOD2
                px(x, y, c)
    # the rug, and the cat asleep on it
    for y in range(184, 200):
        for x in range(60, 150):
            e = ((x - 105) / 45) ** 2 + ((y - 192) / 9) ** 2
            if e <= 1:
                px(x, y, RUG3 if e > 0.8 else (RUG2 if (x // 4 + y // 2) % 4 == 0 else RUG))
    for y in range(176, 196):
        for x in range(84, 126):
            e = ((x - 104) / 19) ** 2 + ((y - 188) / 8) ** 2
            if e <= 1:
                c = CAT if (x // 3) % 3 else CAT2          # tabby stripes
                if y < 184:
                    c = CAT3
                px(x, y, c)
    for y in range(180, 189):                       # the head, tucked in
        for x in range(112, 126):
            if ((x - 119) / 7) ** 2 + ((y - 185) / 5) ** 2 <= 1:
                px(x, y, CAT3)
    for dx, dy in ((113, 180), (114, 179), (123, 180), (124, 179)):  # the ears
        px(dx, dy, CAT2)
    for x in range(116, 122):                       # the eyes, shut
        if x in (116, 117, 120, 121):
            px(x, 185, CAT2)
    for t in range(14):                             # the tail round its paws
        x = 86 + t * 2
        px(x, 193 - abs(t - 7) // 3, CAT2)
        px(x + 1, 193 - abs(t - 7) // 3, CAT2)
    px(118, 188, CATW)
    # the log basket and the fire irons, at the right
    for y in range(156, 190):
        for x in range(262, 312):
            if y > 166 and (x - 287) ** 2 / 625 + (y - 178) ** 2 / 144 <= 1.2:
                px(x, y, WOOD2 if (x + y) % 4 == 0 else WOOD3)
    for lx, ly in ((272, 162), (286, 158), (300, 163)):
        rect(lx - 6, ly, lx + 7, ly + 5, LOG)
        px(lx - 6, ly + 2, WOOD3)
    for x in (252, 256, 260):
        for y in range(120, 182):
            px(x, y, SOOT2)
        px(x, 119, GOLD)
    rect(250, 182, 262, 184, SOOT2)


def main():
    out, pack45 = sys.argv[1], sys.argv[2]
    draw()
    fire = fire_colours()
    pal, group, where = [(0, 0, 0)], [G_ROOM], {((0, 0, 0), G_ROOM): 0}
    P_FIRE = 1
    pal += fire
    group += [G_FIRE] * 64
    idx = np.zeros((H, W), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            if grp[y, x] == G_FIRE:
                idx[y, x] = P_FIRE
                continue
            key = (tuple(int(v) for v in img[y, x]), int(grp[y, x]))
            if key not in where:
                where[key] = len(pal)
                pal.append(key[0])
                group.append(key[1])
            idx[y, x] = where[key]
    if len(pal) > 256:
        raise SystemExit("palette full: %d" % len(pal))

    chars, char_of = [], {}

    def cell(block):
        key = bytes(block.flatten())
        if key not in char_of:
            char_of[key] = len(chars)
            chars.append(key)
        return CHAR_BASE + char_of[key]

    fire_char = None
    screen = bytearray()
    for r in range(ROWS):
        for c in range(COLS):
            if FIRE_ROW <= r < FIRE_ROW + FIRE_ROWS and FIRE_COL <= c < FIRE_COL + FIRE_COLS:
                ch = 0                              # the fire's: filled in below
            else:
                ch = cell(idx[r * 8:r * 8 + 8, c * 8:c * 8 + 8])
            screen += bytes([ch & 0xFF, ch >> 8])
    fire_char = len(chars)
    for c in range(FIRE_COLS):                      # down the columns
        for r in range(FIRE_ROWS):
            ch = CHAR_BASE + fire_char + c * FIRE_ROWS + r
            o = ((FIRE_ROW + r) * COLS + FIRE_COL + c) * 2
            screen[o:o + 2] = bytes([ch & 0xFF, ch >> 8])
            chars.append(bytes([P_FIRE]) * 64)

    def pack(name, data, dest):
        raw, pck = os.path.join(out, name + ".bin"), os.path.join(out, name + ".pck")
        open(raw, "wb").write(data)
        subprocess.run([pack45, "--raw", "--best", "-d", "0x%X" % dest, raw, pck], check=True,
                       stdout=subprocess.DEVNULL)
        return open(pck, "rb").read()

    chr_pck = pack("fire_chr", b"".join(chars), CHAR_BASE * 64)
    map_pck = pack("fire_map", bytes(screen), 0)
    defs = [("FIRE_COLOURS", len(pal)), ("P_FIRE", "%d  /* the fire's 64: by heat */" % P_FIRE),
            ("G_ROOM", G_ROOM), ("G_LIGHT", G_LIGHT), ("G_FIRE", G_FIRE),
            ("FIRE_COL", FIRE_COL), ("FIRE_ROW", FIRE_ROW), ("FIRE_COLS", FIRE_COLS), ("FIRE_ROWS", FIRE_ROWS),
            ("FIRE_W", FIRE_COLS * 8), ("FIRE_H", FIRE_ROWS * 8),
            ("FIRE_CHAR", "(CH0 + %d)  /* down the columns: + c * FIRE_ROWS + r */" % fire_char)]
    blob.write(out, "fire", streams=[("chr_pck", chr_pck), ("map_pck", map_pck)],
               tables=[("pal", "[FIRE_COLOURS][3]", bytes(v for c in pal for v in c)),
                       ("group", "[FIRE_COLOURS]  /* G_ROOM, G_LIGHT + c, G_FIRE */", group)],
               defines=defs, comment="the fireside (tools/gen_fire.py)")
    print("fire: %d colours, %d characters (%d bytes packed), map %d packed"
          % (len(pal), len(chars), len(chr_pck), len(map_pck)))
    if "--preview" in sys.argv:
        rgb = np.array(pal, dtype=np.uint8)[idx]
        # a still of a fire, for the look of it
        for y in range(FIRE_ROW * 8, (FIRE_ROW + FIRE_ROWS) * 8):
            for x in range(FIRE_COL * 8, (FIRE_COL + FIRE_COLS) * 8):
                hgt = (FIRE_ROW + FIRE_ROWS) * 8 - y
                v = 63 - hgt * 1.1 - abs(x - 160) * 0.9 + 12 * math.sin(x * 0.4 + y * 0.2)
                rgb[y, x] = fire[max(0, min(63, int(v)))]
        Image.fromarray(rgb).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, "fire.png"))


if __name__ == "__main__":
    main()
