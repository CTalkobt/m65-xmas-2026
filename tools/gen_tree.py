#!/usr/bin/env python3
"""gen_tree.py — scene 2, the tree: a parlour on Christmas Eve, drawn here.

    python3 tools/gen_tree.py <build dir> <pack45> [--preview]

As gen_scene.py: 320 x 200 cut into the 40 x 25 cells, each its own
full-colour character in screen order ($40000 + (row * 40 + col) * 64),
packed by pack45 (--raw, to $40000). Writes, in the build directory:

  tree.bin, tree.pck   the characters, unpacked and packed
  parlour.dat, .h      the scene's data (tools/blob.py): the packed
                       stream, the palette, its groups, the window's glass
                       (where the snow outside shows)
  tree.png             (with --preview) the picture, twice the size

THE PALETTE IS IN GROUPS, for tree.c to bring to life. Every pixel is
drawn with a colour and a group; a colour in two groups is two entries.
  G_ROOM       the room: always as drawn (the fade aside)
  G_TIER+0..5  the tree's tiers, from the bottom: they light up in turn
               ("the tree draws itself")
  G_LIGHT+0..7 the fairy lights' eight channels (a light and its glow)
  G_BAUBLE+0..3 the baubles' four colours
  G_TINSEL     the tinsel swags
  G_STAR       the star at the top
  G_FIRE+0..4  the fire's flames by height: their colours go round
tree.h gives each entry's group (tree_group[]) and the group numbers.
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
DEST = 0x40000

G_ROOM = 0
G_TIER = 1          # 6
G_LIGHT = 7         # 8
G_BAUBLE = 15       # 4
G_TINSEL = 19
G_STAR = 20
G_FIRE = 21         # 5
NGROUPS = 26
TIERS, CHANNELS = 6, 8

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0

img = np.zeros((H, W, 3), dtype=np.uint8)
grp = np.zeros((H, W), dtype=np.uint8)
rng = random.Random(2512)


def C(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def px(x, y, c, g=G_ROOM):
    if 0 <= x < W and 0 <= y < H:
        img[y, x] = c
        grp[y, x] = g


def rect(x0, y0, x1, y1, c, g=G_ROOM):
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            px(x, y, c, g)


def dither(x, y, t):
    return t > BAYER[y & 3, x & 3]


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

# ------------------------------------------------------------------ colours

WALL, WALL2, WALL3 = C("#5a1820"), C("#4a1218"), C("#6e2228")
RAIL, RAIL2 = C("#5a3820"), C("#3e2614")
PANEL, PANEL2, PANEL3 = C("#3a2416"), C("#2c1a10"), C("#4a3020")
FLOOR, FLOOR2, FLOOR3 = C("#4a3020"), C("#3c2618"), C("#58382a")
RUG, RUG2, RUGGOLD = C("#1c4a30"), C("#163a26"), C("#b08a3a")
SKY = [C(h) for h in ("#06082a", "#0c1240", "#141c56", "#1c286a")]
NSTAR, ROOF, ROOF2, SNOW, SNOW2 = C("#d8dcff"), C("#1a1830"), C("#121024"), C("#e8ecff"), C("#a8b4d8")
FRAME, FRAME2 = C("#e0d8c8"), C("#a89c88")
CURT, CURT2, CURT3 = C("#1e5a34"), C("#144226"), C("#2a7444")
GOLD, GOLD2 = C("#d8b048"), C("#9a7a2a")
STONE, STONE2, STONE3 = C("#8a8278"), C("#6e675e"), C("#a8a094")
HEARTH, SOOT = C("#2a2420"), C("#120e0c")
LOG, LOG2 = C("#5a3a22"), C("#3e2816")
FLAME = [C("#ff4010"), C("#ff7a18"), C("#ffaa30"), C("#ffd860"), C("#fff4b0")]
STOCK = [(C("#c02020"), C("#f0f0f0")), (C("#20803c"), C("#f0f0f0")), (C("#c02020"), C("#20803c"))]
NEEDLE = [C("#0e3a22"), C("#165030"), C("#1e6a3c"), C("#2a8048")]
TRUNK, TUB, TUB2 = C("#4a2e1a"), C("#7a2a22"), C("#5a1e18")
BAUBLES = [(C("#e02828"), C("#901414"), C("#ffb0a0")),
           (C("#e0b030"), C("#906a14"), C("#fff0b0")),
           (C("#3060e0"), C("#183890"), C("#b0c8ff")),
           (C("#c8c8d8"), C("#7a7a90"), C("#ffffff"))]
TINSEL, TINSEL2 = C("#f0d070"), C("#b09040")
LIGHTS = [C("#ff3030"), C("#30ff50"), C("#4080ff"), C("#ffd030"),
          C("#ffffff"), C("#ff8020"), C("#ff60c0"), C("#40f0f0")]
STAR, STAR2, STAR3 = C("#fff8c0"), C("#ffd040"), C("#c09020")
PRESENTS = [(C("#b02030"), C("#f0d060")), (C("#2050a0"), C("#f0f0f0")),
            (C("#208040"), C("#e03030")), (C("#e0c040"), C("#c02030")),
            (C("#6a2a90"), C("#f0d060"))]

# ------------------------------------------------------------------ the room


def wall():
    for y in range(0, 132):
        for x in range(W):
            # a damask: a diamond lattice with a motif in each
            u, v = (x + 8) % 24 - 12, (y + (12 if (x + 8) // 24 % 2 else 0)) % 24 - 12
            d = abs(u) + abs(v)
            c = WALL
            if d in (11, 12):
                c = WALL3
            elif d < 4 and (u * u + v * v) < 10:
                c = WALL3 if (u + v) % 2 == 0 else WALL
            elif (x * 3 + y * 5) % 23 == 0:
                c = WALL2
            px(x, y, c)
    rect(0, 128, W, 132, RAIL)
    rect(0, 131, W, 133, RAIL2)
    for y in range(133, 160):              # the wainscot: panels
        for x in range(W):
            px(x, y, PANEL)
    for x0 in range(4, W, 40):
        for x in range(x0, x0 + 34):
            px(x, 137, PANEL3)
            px(x, 155, PANEL2)
        for y in range(137, 156):
            px(x0, y, PANEL3)
            px(x0 + 33, y, PANEL2)
    rect(0, 158, W, 160, RAIL2)


def floor():
    for y in range(160, H):
        for x in range(W):
            row = (y - 160) // 5
            joint = (y - 160) % 5 == 4 or (x + row * 37) % 64 == 0
            c = FLOOR2 if joint else (FLOOR3 if (x * 7 + y * 3) % 29 == 0 else FLOOR)
            px(x, y, c)
    # the rug under the tree
    for y in range(168, 198):
        for x in range(70, 240):
            e = ((x - 155) / 85) ** 2 + ((y - 183) / 15) ** 2
            if e <= 1:
                c = RUGGOLD if e > 0.82 else (RUG2 if (x // 4 + y // 3) % 5 == 0 else RUG)
                if 0.55 < e < 0.62:
                    c = RUGGOLD
                px(x, y, c)


WIN = (16, 24, 72, 116)                     # the glass: x0, y0, x1, y1 (outside the frame)


def window():
    x0, y0, x1, y1 = WIN
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0) * (len(SKY) - 1)
        i = min(int(t), len(SKY) - 2)
        for x in range(x0, x1):
            px(x, y, SKY[i + 1] if dither(x, y, t - i) else SKY[i])
    for _ in range(18):
        px(rng.randrange(x0, x1), rng.randrange(y0, y0 + 50), NSTAR)
    # rooftops outside, snow on them
    for x in range(x0, x1):
        top = int(92 + 6 * math.sin(x / 7) + (8 if 40 < x < 56 else 0))
        for y in range(top, y1):
            px(x, y, ROOF if (x // 9) % 2 else ROOF2)
        for y in range(top, top + 2):
            px(x, y, SNOW)
        if (x * 5) % 13 == 0:
            px(x, top + 2, SNOW2)
    for x in range(44, 50):                 # a lit window in a house over the way
        for y in range(104, 110):
            px(x, y, C("#e0a040"))
    # the frame and its bars
    rect(x0 - 3, y0 - 3, x1 + 3, y0, FRAME)
    rect(x0 - 3, y1, x1 + 3, y1 + 3, FRAME)
    rect(x0 - 3, y0, x0, y1, FRAME)
    rect(x1, y0, x1 + 3, y1, FRAME2)
    rect((x0 + x1) // 2 - 1, y0, (x0 + x1) // 2 + 1, y1, FRAME)
    rect(x0, 68, x1, 70, FRAME)
    rect(x0, y1 - 3, x1, y1, FRAME2)         # the outside sill
    rect(x0, y1 - 4, x1, y1 - 3, SNOW2)      # a skin of snow on it: parlour.c piles more on
    rect(x0 - 6, y1 + 3, x1 + 6, y1 + 6, FRAME2)
    # curtains and a pelmet
    for side in (0, 1):
        for y in range(12, 126):
            w = 10 + (y - 12) // 14
            for i in range(w):
                x = (x0 - 12 + i) if side == 0 else (x1 + 12 - i)
                fold = (i + (y // 30)) % 5
                c = CURT3 if fold == 0 else (CURT2 if fold == 3 else CURT)
                px(x, y, c)
        ty = 80
        for i in range(-2, 12):
            x = (x0 - 12 + i) if side == 0 else (x1 + 12 - i)
            px(x, ty, GOLD)
            px(x, ty + 1, GOLD2)
    for x in range(x0 - 14, x1 + 15):
        for y in range(10, 18):
            c = CURT2 if y == 17 else (GOLD if y == 10 else CURT)
            if y == 16 and x % 6 == 0:
                c = GOLD
            px(x, y, c)


def fireplace():
    x0, x1 = 232, 316
    for y in range(100, 160):              # the surround: dressed stone
        for x in range(x0, x1):
            row = (y - 100) // 6
            c = STONE3 if (y - 100) % 6 == 5 or (x + row * 7) % 14 == 0 else (STONE2 if (x // 14 + row) % 3 == 0 else STONE)
            px(x, y, c)
    rect(x0 - 6, 94, x1 + 4, 100, RAIL)     # the mantel
    rect(x0 - 6, 99, x1 + 4, 101, RAIL2)
    ox0, ox1, oy0 = 248, 300, 116
    for y in range(oy0, 160):
        for x in range(ox0, ox1):
            arch = y < oy0 + 8 and ((x - 274) / 26) ** 2 + ((y - oy0 - 8) / 8) ** 2 > 1
            if not arch:
                px(x, y, SOOT if y < 130 else HEARTH)
    # logs
    for y in range(150, 158):
        for x in range(256, 294):
            if (x - 275) ** 2 / 400 + (y - 154) ** 2 / 14 <= 1:
                px(x, y, LOG2 if (x + y) % 6 == 0 else LOG)
    # the fire: bands by height, flickering by palette
    for x in range(258, 292):
        h = 18 + 12 * math.sin((x - 258) / 34 * math.pi) + rng.randrange(-4, 5)
        for y in range(int(150 - h), 152):
            f = (150 - y) / h
            band = min(4, int(f * 5))
            if dither(x, y, 1 - abs(((x - 258) % 8) - 4) / 6 - f * 0.25) or f < 0.5:
                px(x, y, FLAME[4 - band], G_FIRE + band)
    # stockings from the mantel
    for i, sx in enumerate((240, 268, 296)):
        body, cuff = STOCK[i]
        rect(sx, 101, sx + 9, 104, cuff)
        rect(sx + 1, 104, sx + 8, 120, body)
        for y in range(116, 124):
            for x in range(sx + 1, sx + 15):
                if (x - sx - 7) ** 2 / 49 + (y - 120) ** 2 / 14 <= 1:
                    px(x, y, body)
        for y in range(106, 120, 4):
            rect(sx + 2, y, sx + 7, y + 1, cuff)
    # candles on the mantel
    for cx in (236, 312):
        rect(cx - 1, 82, cx + 2, 94, C("#f0e8d0"))
        px(cx, 79, FLAME[3], G_FIRE + 3)
        px(cx, 80, FLAME[2], G_FIRE + 2)
        px(cx, 81, FLAME[1], G_FIRE + 1)
    # a garland along the mantel
    for x in range(x0 - 6, x1 + 4):
        y = 92 + int(2 * math.sin(x / 5))
        px(x, y, NEEDLE[2])
        px(x, y + 1, NEEDLE[1])
        if x % 9 == 0:
            px(x, y, LIGHTS[x // 9 % CHANNELS], G_LIGHT + x // 9 % CHANNELS)

# ------------------------------------------------------------------ the tree

CX, TOP, BASE = 156, 22, 168


def tier_bounds(t):
    """tier t from the bottom: (top y, bottom y, half width at the bottom)"""
    span = (BASE - TOP) / (TIERS - 0.6)
    y1 = int(BASE - t * span)
    y0 = int(y1 - span * 1.6)
    hw = 16 + (TIERS - 1 - t) * 13
    return max(TOP, y0), y1, hw


def tree():
    # the tub and the trunk
    rect(CX - 3, BASE - 4, CX + 4, BASE + 2, TRUNK)
    for y in range(BASE + 2, BASE + 16):
        w = 14 - (y - BASE - 2) // 4
        for x in range(CX - w, CX + w + 1):
            c = TUB2 if x < CX - w + 3 or (y - BASE) % 5 == 0 else TUB
            px(x, y, c)
    rect(CX - 15, BASE + 2, CX + 16, BASE + 4, GOLD)
    inside = np.zeros((H, W), dtype=bool)
    # from the bottom tier up: each tier is drawn over the top of the one
    # below, and its scalloped lower edge (the branches' drooping tips)
    # hangs over it, with a shadow under it
    for t in range(TIERS):
        y0, y1, hw = tier_bounds(t)
        for x in range(CX - hw - 3, CX + hw + 4):
            dx = x - CX
            # the lower edge: a droop a branch, deeper toward the sides
            k = abs(dx) / max(1, hw)
            tip = y1 + int(2 + 3 * k + 2 * abs(math.sin(x * math.pi / 9)))
            for y in range(y0, tip + 1):
                f = (y - y0) / max(1, y1 - y0)
                half = hw * min(1.0, f) ** 0.85 + (1 if y > y1 else 0)
                ragged = 1.5 * math.sin(x * 1.3 + y * 0.7) + 1.5 * math.sin(y * 2.1)
                if abs(dx) > half + ragged:
                    continue
                shade = 1.3 + (dx / max(1, hw)) * 1.3 \
                    + (0.7 if (x * 3 + y * 7) % 5 == 0 else 0) - (0.9 if (x * 5 + y * 3) % 7 == 0 else 0)
                if f < 0.25 and t < TIERS - 1:
                    shade -= 1.2                  # in the shadow of the tier above
                if y >= tip - 1:
                    shade += 1                    # the tips catch the light
                c = NEEDLE[max(0, min(3, int(shade)))]
                px(x, y, c, G_TIER + t)
                inside[y, x] = True
    return inside


def tinsel(inside):
    for t in range(TIERS - 1):
        y0, y1, hw = tier_bounds(t)
        a = y0 + (y1 - y0) * 0.45
        swags = 3 if hw > 40 else 2
        span = 2 * hw / swags
        for x in range(CX - hw, CX + hw):
            i = min(swags - 1, int((x - (CX - hw)) / span))
            c0 = CX - hw + (i + 0.5) * span
            u = (x - c0) / (span / 2)
            y = int(a + 6 * (1 - u * u) + (abs(x - CX) / hw) * 4)
            if 0 <= y < H and inside[y, x]:
                px(x, y, TINSEL if x % 3 else TINSEL2, G_TINSEL)
                if inside[y + 1, x] and x % 2:
                    px(x, y + 1, TINSEL2, G_TINSEL)


def baubles(inside, spots):
    for (x, y), k in spots:
        main, shadow, hi = BAUBLES[k]
        px(x, y - 3, GOLD2, G_BAUBLE + k)     # the cap
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if dx * dx + dy * dy <= 5:
                    c = shadow if dx + dy >= 2 else main
                    if (dx, dy) == (-1, -1):
                        c = hi
                    px(x + dx, y + dy, c, G_BAUBLE + k)


def lights(inside, taken):
    n = 0
    for _ in range(4000):
        x, y = rng.randrange(CX - 90, CX + 90), rng.randrange(TOP + 10, BASE - 2)
        if not inside[y, x] or any(abs(x - a) < 4 and abs(y - b) < 4 for a, b in taken):
            continue
        c = n % CHANNELS
        col = LIGHTS[c]
        glow = mix(col, NEEDLE[1], 0.55)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if inside[y + dy, x + dx]:
                px(x + dx, y + dy, glow, G_LIGHT + c)
        px(x, y, col, G_LIGHT + c)
        taken.append((x, y))
        n += 1
        if n == 72:
            break
    return n


def star():
    cx, cy = CX, TOP - 4
    for y in range(cy - 11, cy + 12):
        for x in range(cx - 11, cx + 12):
            dx, dy = x - cx, y - cy
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx) + math.pi / 2
            spike = 4 + 5 * abs(math.cos(a * 2.5)) ** 3
            if r <= spike:
                c = STAR if r < 2.5 else (STAR2 if r < spike - 1.2 else STAR3)
                px(x, y, c, G_STAR)
            elif (dx == 0 or dy == 0) and r <= 11 and dither(x, y, 1 - r / 11):
                px(x, y, STAR2, G_STAR)          # rays


def presents():
    boxes = [(96, 172, 26, 16), (122, 178, 20, 14), (176, 174, 28, 18), (204, 180, 18, 12), (146, 184, 22, 12)]
    for i, (x, y, w, h) in enumerate(boxes):
        paper, ribbon = PRESENTS[i]
        dark = mix(paper, (0, 0, 0), 0.3)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                c = paper
                if (xx - x + yy - y) % 6 == 0:
                    c = dark
                if xx in (x, x + w - 1) or yy == y + h - 1:
                    c = dark
                if abs(xx - (x + w // 2)) <= 1 or abs(yy - (y + h // 3)) <= 0:
                    c = ribbon
                px(xx, yy, c)
        bx, by = x + w // 2, y - 1
        for dx, dy in ((-3, -1), (-2, -2), (-1, -1), (1, -1), (2, -2), (3, -1), (-2, 0), (2, 0), (0, 0)):
            px(bx + dx, by + dy, ribbon)


def draw():
    wall()
    floor()
    window()
    fireplace()
    inside = tree()
    tinsel(inside)
    spots = []
    for t in range(TIERS):
        y0, y1, hw = tier_bounds(t)
        for j in range(2 + (TIERS - t) // 2):
            for _ in range(200):
                x, y = rng.randrange(CX - hw + 6, CX + hw - 6), rng.randrange(y0 + (y1 - y0) // 2, y1 - 3)
                if inside[y, x] and inside[y - 4, x] and all(abs(x - a) > 9 or abs(y - b) > 7 for (a, b), _ in spots):
                    spots.append(((x, y), (t * 3 + j) % 4))
                    break
    baubles(inside, spots)
    n = lights(inside, [p for p, _ in spots])
    star()
    presents()
    return n


def glass_mask():
    """a bit a pixel of the window, set where it is glass with the sky
    behind (not a roof, a bar, the frame or a curtain): the falling snow
    shows there only. 8 pixels a byte, bit 7 the left."""
    x0, y0, x1, y1 = WIN
    sky = set(SKY) | {NSTAR}
    rows = []
    for y in range(y0, y1):
        bits = [tuple(int(v) for v in img[y, x]) in sky for x in range(x0, x1)]
        rows.append(np.packbits(bits).tobytes())
    return rows


def pane_mask():
    """a bit a pixel of the window, set where it shows the world outside
    (the sky, the roofs over the way, the snow on the sill): not the bars,
    the frame or the curtains. The near flakes, just outside the glass,
    show there; the far ones only where it is glass with the sky behind."""
    x0, y0, x1, y1 = WIN
    inside = {FRAME, FRAME2, CURT, CURT2, CURT3, GOLD, GOLD2}
    rows = []
    for y in range(y0, y1):
        bits = [tuple(int(v) for v in img[y, x]) not in inside for x in range(x0, x1)]
        rows.append(np.packbits(bits).tobytes())
    return rows


def main():
    out, pack45 = sys.argv[1], sys.argv[2]
    nlights = draw()
    glass = glass_mask()
    pane = pane_mask()
    # entries 1 and 2: the window's falling snow (parlour.c's flake glyphs)
    pal, group = [(0, 0, 0), SNOW, SNOW2], [G_ROOM, G_ROOM, G_ROOM]
    where = {((0, 0, 0), G_ROOM): 0, (SNOW, G_ROOM): 1, (SNOW2, G_ROOM): 2}
    idx = np.zeros((H, W), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            key = (tuple(int(v) for v in img[y, x]), int(grp[y, x]))
            if key not in where:
                if len(pal) >= 256:
                    raise SystemExit("palette full")
                where[key] = len(pal)
                pal.append(key[0])
                group.append(key[1])
            idx[y, x] = where[key]
    chars = bytearray()
    for r in range(ROWS):
        for c in range(COLS):
            chars += idx[r * 8:r * 8 + 8, c * 8:c * 8 + 8].tobytes()
    binf = os.path.join(out, "tree.bin")
    with open(binf, "wb") as f:
        f.write(chars)
    pck = os.path.join(out, "tree.pck")
    subprocess.run([pack45, "--raw", "--best", "-d", "0x%X" % DEST, binf, pck], check=True, stdout=subprocess.DEVNULL)
    packed = open(pck, "rb").read()

    x0, y0, x1, y1 = WIN
    defs = [("G_ROOM", G_ROOM), ("G_TIER", G_TIER), ("G_LIGHT", G_LIGHT), ("G_BAUBLE", G_BAUBLE),
            ("G_TINSEL", G_TINSEL), ("G_STAR", G_STAR), ("G_FIRE", G_FIRE), ("NGROUPS", NGROUPS),
            ("TIERS", TIERS), ("CHANNELS", CHANNELS),
            ("tree_white", "1  /* the falling snow's colours */"), ("tree_white_dim", 2),
            ("TREE_COLOURS", len(pal)), ("TREE_LIGHTS", nlights),
            ("WIN_X0", x0), ("WIN_Y0", y0), ("WIN_W", x1 - x0), ("WIN_H", y1 - y0), ("WIN_BYTES", len(glass[0])),
            ("WIN_SILL", "%d  /* the snow's top on the outside sill, from WIN_Y0 */" % (y1 - 4 - y0))]
    blob.write(out, "parlour",
               streams=[("tree_pck", packed)],
               tables=[("pal", "[TREE_COLOURS][3]", bytes(v for c in pal for v in c)),
                       ("group", "[TREE_COLOURS]", group),
                       ("glass", "[WIN_H][WIN_BYTES] /* the window: the snow shows where it is glass */",
                        b"".join(glass)),
                       ("pane", "[WIN_H][WIN_BYTES] /* where it shows outside: the near flakes */",
                        b"".join(pane))],
               defines=defs, comment="the tree (tools/gen_tree.py)")
    print("tree: %d colours, %d lights, %d bytes packed from %d" % (len(pal), nlights, len(packed), len(chars)))
    if "--preview" in sys.argv:
        Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, "tree.png"))


if __name__ == "__main__":
    main()
