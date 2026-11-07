#!/usr/bin/env python3
"""gen_scene.py — the village, drawn here as pixel art.

    python3 tools/gen_scene.py <build dir> <pack45> [--preview]

The picture is 320 x 200, cut into the 40 x 25 cells of the screen, each its
own full-colour character (64 bytes, a byte a pixel: the palette entry), in
screen order: cell (row, col) is character $1000 + row * 40 + col, at
$40000 + (row * 40 + col) * 64. All 64,000 bytes are packed by pack45
(--raw, to $40000) for unpack() (<unpack.h>).

Writes, in the build directory:
  scene.bin          the characters, unpacked (64,000 bytes)
  scene.pck          packed
  catch.pck          the catch map, packed: a bit a pixel (row by row, 40
                     bytes a row, bit 7 the left), set where snow can rest
  village.dat, .h    the scene's data (tools/blob.py): the packed streams,
                     then the palette and a byte a pixel column: eave (below it the near flakes catch too),
                     gtop (the top of the open ground), ctop (the top catch
                     pixel), ntop (the top one at or below the eave) and
                     fgtop (the foreground's top: the far flakes go behind)
  scene.png          (with --preview) the picture, twice the size
  catch.png          (with --preview) the classes, to look at

Every pixel has a class (cls, K_*):
  NONE    the sky, the moon, the hills, the smoke, haloes: flakes pass
  FACE    walls, windows, doors, posts: a face toward us, flakes fall in
          front of it
  TOP     roofs, chimney caps, trees, the tower's cornice: snow rests on
          them (from the middle layer, at the houses' depth)
  LEDGE   sills, the lintel, the fence, the lamps' caps: snow rests on them
          (the middle and the near layers)
  GROUND  the open ground (each layer settles at its own depth on it)

The palette starts with the entries snow.c draws with (P_SNOW ...); the
rest are the picture's colours in the order they are first used.
"""
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

RESERVED = [
    ("P_BLACK", (0, 0, 0)),
    ("P_SNOW", (250, 250, 255)),
    ("P_SNOW2", (196, 208, 236)),
    ("P_FAR", (120, 130, 164)),
    ("P_MID", (200, 204, 228)),
    ("P_NEAR", (255, 255, 255)),
]

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0

K_NONE, K_FACE, K_TOP, K_LEDGE, K_GROUND = range(5)

img = np.zeros((H, W, 3), dtype=np.uint8)
cls = np.zeros((H, W), dtype=np.uint8)
rng = random.Random(1225)


def C(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def px(x, y, c, k=K_FACE):
    if 0 <= x < W and 0 <= y < H:
        img[y, x] = c
        cls[y, x] = k


def rect(x0, y0, x1, y1, c, k=K_FACE):
    """x0..x1-1, y0..y1-1"""
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            px(x, y, c, k)


def dither(x, y, t):
    """t 0..1: true on that share of the pixels (ordered)"""
    return t > BAYER[y & 3, x & 3]


# ------------------------------------------------------------------ colours

SKY = [C(h) for h in ("#03031a", "#05072a", "#0a0e38", "#101646",
                      "#161e54", "#1e2862", "#283270", "#323c7c")]
STAR, STAR2 = C("#e8e8ff"), C("#8a90c0")
MOON, MOON2, MOON3, HALO = C("#f2eed2"), C("#d8d2b0"), C("#b8b296"), C("#3c4682")
HILL, HILL2, HILLTOP = C("#1a2040"), C("#141834"), C("#5a6488")
FARLIGHT = C("#c09040")
SMOKE = C("#4a5070")
GROUND, GROUND2, GROUND3 = C("#26222a"), C("#1e1a22"), C("#302a30")
PATH, PATH2 = C("#3a3436"), C("#2e2a2e")

PLASTER, PLASTER2 = C("#9a907a"), C("#7e7664")
BEAM, BEAM2 = C("#34241c"), C("#281a14")
TILE, TILE2, TILE3 = C("#7a3028"), C("#602620"), C("#461a18")
BRICK, BRICK2, MORTAR = C("#70342a"), C("#5a2a22"), C("#463e3e")
SLATE, SLATE2, SLATE3 = C("#465066"), C("#384054"), C("#2a3040")
PLANK, PLANK2, PLANK3 = C("#62463a"), C("#523a30"), C("#3e2c24")
STONE, STONE2, STONE3 = C("#646674"), C("#545664"), C("#424452")
TRIM = C("#d0c8b0")

GLOW, GLOW2, GLOW3 = C("#ffe08a"), C("#ffc060"), C("#e09040")
# each building's windows their own entries (a shade apart), to flicker apart
HOUSES = 3


def glows(k):
    return tuple((r, g, max(0, b - k)) for r, g, b in (GLOW, GLOW2, GLOW3))
FRAME = C("#2a1c16")
CURTAIN, CURTAIN2 = C("#a02828"), C("#781e1e")
DOOR, DOOR2, KNOB = C("#5a2a1e"), C("#44201a"), C("#d0a040")
WREATH, WREATH2, BOW = C("#1e6e32"), C("#145024"), C("#e02828")
CLOCK, HANDS = C("#e0d4a8"), C("#201810")
GLASS = [C("#f0be50"), C("#c83c32"), C("#3c78c8"), C("#50aa5a")]

PINE, PINE2, PINE3 = C("#164a30"), C("#1e6038"), C("#0e3420")
TRUNK = C("#3c2818")
BAUBLE = [C("#e83030"), C("#f0c040"), C("#4080f0"), C("#f0f0f0"), C("#c040c0")]
STARGOLD = C("#ffe060")

IRON = C("#1c1c24")
LAMP, LAMPHALO = C("#fff0b0"), C("#5a5470")
FENCE, FENCE2 = C("#6e5a48"), C("#504034")

# ------------------------------------------------------------------ the sky


def sky():
    for y in range(H):
        t = y / 150 * (len(SKY) - 1)
        i = min(int(t), len(SKY) - 2)
        f = t - i
        for x in range(W):
            c = SKY[i + 1] if dither(x, y, f) else SKY[i]
            px(x, y, c, K_NONE)
    for _ in range(90):
        x, y = rng.randrange(W), rng.randrange(120)
        px(x, y, STAR if rng.random() < 0.35 else STAR2, K_NONE)
    for x, y in ((60, 18), (150, 10), (236, 46), (108, 52)):   # bright ones: a cross
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            px(x + dx, y + dy, STAR if (dx, dy) == (0, 0) else STAR2, K_NONE)


def moon(cx, cy, r):
    for y in range(cy - r - 10, cy + r + 11):
        for x in range(cx - r - 10, cx + r + 11):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d <= r:
                c = MOON
                if d > r - 2 and x < cx:
                    c = MOON2
                for mx, my, mr in ((-3, -2, 2.5), (4, 3, 2), (-1, 5, 1.5), (5, -4, 1.2)):
                    if (x - cx - mx) ** 2 + (y - cy - my) ** 2 <= mr * mr:
                        c = MOON3 if (x - cx - mx) < 0 else MOON2
                px(x, y, c, K_NONE)
            elif d <= r + 10 and dither(x, y, (1 - (d - r) / 10) * 0.6):
                px(x, y, HALO, K_NONE)


def hills():
    for x in range(W):
        h1 = 128 + 10 * np.sin(x / 41) + 6 * np.sin(x / 17 + 1)
        h2 = 142 + 8 * np.sin(x / 29 + 2) + 4 * np.sin(x / 11)
        for y in range(int(h1), H):
            px(x, y, HILLTOP if y == int(h1) else HILL, K_NONE)
        for y in range(int(h2), H):
            px(x, y, HILL2, K_NONE)
    for _ in range(14):                      # a far village's windows
        x = rng.randrange(W)
        y = int(142 + 8 * np.sin(x / 29 + 2) + 4 * np.sin(x / 11)) + rng.randrange(2, 6)
        px(x, y, FARLIGHT, K_NONE)


def ground_line(x):
    return int(176 + 2 * np.sin(x / 23) + np.sin(x / 7))


def ground():
    for x in range(W):
        top = ground_line(x)
        for y in range(top, H):
            r = (x * 7 + y * 13) % 11
            c = GROUND3 if y == top else (GROUND2 if r < 3 else GROUND)
            px(x, y, c, K_GROUND)
    # a path to the church
    for y in range(182, H):
        w = 6 + (y - 182) // 2
        for x in range(150 - w, 150 + w):
            px(x, y, PATH2 if (x + y) % 5 == 0 else PATH, K_GROUND)


def smoke(x, y):
    for i in range(7):
        cx = x + int(3 * np.sin(i * 0.9)) + i
        cy = y - i * 5
        r = 2 + i * 0.5
        for yy in range(int(cy - r), int(cy + r) + 1):
            for xx in range(int(cx - r), int(cx + r) + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r and dither(xx, yy, 0.55 - i * 0.06):
                    if 0 <= xx < W and 0 <= yy < H:
                        px(xx, yy, SMOKE, cls[yy, xx])   # in front of what is there

# ------------------------------------------------------------------ parts


def roof(xl, xr, apex, base, kind, overhang=3):
    """a gable seen from the front: a triangle from (cx, apex) to the
    eaves at base, xl - overhang .. xr + overhang"""
    cx = (xl + xr) / 2
    half = (xr - xl) / 2 + overhang
    hgt = base - apex
    for y in range(apex, base):
        w = half * (y - apex + 1) / hgt
        x0, x1 = int(cx - w), int(cx + w)
        for x in range(x0, x1 + 1):
            if x in (x0, x1) or y == base - 1:
                c = BEAM if kind != "slate" else SLATE3
            elif kind == "tile":
                band = (y - apex) % 4
                joint = (x + ((y - apex) // 4) * 3) % 6 == 0
                c = TILE3 if band == 0 else (TILE2 if joint or band == 3 else TILE)
            elif kind == "slate":
                band = (y - apex) % 3
                joint = (x + ((y - apex) // 3) * 2) % 5 == 0
                c = SLATE3 if band == 0 else (SLATE2 if joint else SLATE)
            else:                            # thatch-like shingles
                c = PLANK3 if (y - apex) % 3 == 0 else (PLANK2 if (x * 3 + y) % 7 == 0 else PLANK)
            px(x, y, c, K_TOP)


def window(x, y, w, h, curtains=True, cross=True, house=0):
    GLOW, GLOW2, GLOW3 = glows(house)
    rect(x - 1, y - 1, x + w + 1, y + h + 1, FRAME)
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            d = min(xx - x, x + w - 1 - xx, yy - y, y + h - 1 - yy)
            c = GLOW if d >= 2 else (GLOW2 if d == 1 else GLOW3)
            px(xx, yy, c)
    if cross:
        for yy in range(y, y + h):
            px(x + w // 2, yy, FRAME)
        for xx in range(x, x + w):
            px(xx, y + h // 2, FRAME)
    if curtains:
        for yy in range(y, y + h):
            k = 2 if yy < y + h - 2 else 1
            for i in range(k):
                px(x + i, yy, CURTAIN if i == 0 else CURTAIN2)
                px(x + w - 1 - i, yy, CURTAIN if i == 0 else CURTAIN2)
    rect(x - 2, y + h + 1, x + w + 2, y + h + 2, TRIM, K_LEDGE)   # the sill


def door(x, y, w, h, wreath=False):
    rect(x - 1, y - 1, x + w + 1, y + h, FRAME)
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            px(xx, yy, DOOR2 if (xx - x) % 3 == 2 else DOOR)
    px(x + w - 2, y + h // 2, KNOB)
    if wreath:
        cx, cy = x + w // 2, y + 5
        for yy in range(cy - 4, cy + 5):
            for xx in range(cx - 4, cx + 5):
                d = (xx - cx) ** 2 + (yy - cy) ** 2
                if 5 <= d <= 16:
                    px(xx, yy, WREATH2 if (xx + yy) % 3 == 0 else WREATH)
        for dx, dy in ((0, 4), (-1, 4), (1, 4), (-1, 5), (1, 5)):
            px(cx + dx, cy + dy, BOW)
        for dx in (-2, 2):
            px(cx + dx, cy - 2 + (dx > 0), BOW)


def chimney(x, top, w, h):
    for y in range(top, top + h):
        for xx in range(x, x + w):
            row = (y - top) // 3
            mort = (y - top) % 3 == 2 or (xx + row * 2) % 5 == 0
            px(xx, y, MORTAR if mort else BRICK)
    rect(x - 1, top - 2, x + w + 1, top, STONE2, K_TOP)
    smoke(x + w // 2, top - 5)


def timber(x0, y0, x1, y1):
    """plaster between dark beams: posts, rails, braces"""
    rect(x0, y0, x1, y1, PLASTER)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if (x * 5 + y * 3) % 17 == 0:
                px(x, y, PLASTER2)
    for x in range(x0, x1, 12):
        rect(x, y0, x + 2, y1, BEAM)
    rect(x1 - 2, y0, x1, y1, BEAM)
    for y in (y0, (y0 + y1) // 2, y1 - 2):
        rect(x0, y, x1, y + 2, BEAM2)
    for px0 in range(x0 + 2, x1 - 10, 12):
        for i in range(10):
            yy = (y0 + y1) // 2 + 2 + i * ((y1 - 2) - ((y0 + y1) // 2 + 2)) // 10
            px(px0 + i, yy, BEAM)


def bricks(x0, y0, x1, y1):
    for y in range(y0, y1):
        row = (y - y0) // 3
        for x in range(x0, x1):
            if (y - y0) % 3 == 2 or (x + (row % 2) * 3) % 6 == 0:
                c = MORTAR
            else:
                c = BRICK2 if (x // 6 + row) % 4 == 0 else BRICK
            px(x, y, c)


def planks(x0, y0, x1, y1):
    for y in range(y0, y1):
        for x in range(x0, x1):
            c = PLANK3 if (y - y0) % 3 == 0 else (PLANK2 if (x * 7 + y) % 13 == 0 else PLANK)
            px(x, y, c)


def stones(x0, y0, x1, y1):
    for y in range(y0, y1):
        row = (y - y0) // 4
        for x in range(x0, x1):
            if (y - y0) % 4 == 3 or (x + (row % 2) * 4) % 8 == 0:
                c = STONE3
            else:
                c = STONE2 if ((x // 8) * 3 + row) % 5 == 0 else STONE
            px(x, y, c)


def pine(cx, base, h, w, decorated=False):
    trunk_h = 5
    rect(cx - 1, base - trunk_h, cx + 2, base, TRUNK)
    tiers = 4
    top = base - trunk_h - h
    lights = []
    for t in range(tiers):
        ty0 = top + t * h // (tiers + 1)
        ty1 = top + (t + 2) * h // (tiers + 1)
        for y in range(ty0, min(ty1, base - trunk_h)):
            hw = (w / 2) * (0.35 + 0.65 * (t + 1) / tiers) * (y - ty0 + 1) / (ty1 - ty0)
            for x in range(int(cx - hw), int(cx + hw) + 1):
                side = x - cx
                c = PINE2 if side > hw * 0.3 else (PINE3 if side < -hw * 0.5 else PINE)
                if y == ty1 - 1 or (y - ty0) % 4 == 3 and abs(side) > hw - 2:
                    c = PINE3
                px(x, y, c, K_TOP)
                if decorated and y > top + 3 and abs(side) < hw - 1 and rng.random() < 0.05:
                    lights.append((x, y))
    for i, (x, y) in enumerate(lights):
        px(x, y, BAUBLE[i % len(BAUBLE)], K_TOP)
    if decorated:
        sy = top - 2
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (0, -2)):
            px(cx + dx, sy + dy, STARGOLD, K_TOP)


def lamp(x, base):
    for y in range(base - 30, base):
        px(x, y, IRON)
    rect(x - 2, base - 2, x + 3, base, IRON)
    top = base - 37
    rect(x - 3, top, x + 4, top + 1, IRON, K_LEDGE)
    rect(x - 2, top + 1, x + 3, top + 6, LAMP)
    rect(x - 3, top + 6, x + 4, top + 7, IRON)
    for y in range(top - 8, top + 15):
        for xx in range(x - 11, x + 12):
            d = ((xx - x) ** 2 + (y - top - 3) ** 2) ** 0.5
            if 5 < d < 11 and cls[y, xx] == K_NONE and dither(xx, y, (1 - d / 11) * 0.7):
                px(xx, y, LAMPHALO, K_NONE)


def fence(x0, x1, base):
    for x in range(x0, x1):
        if (x - x0) % 4 == 0:
            for y in range(base - 9, base):
                px(x, y, FENCE, K_LEDGE)
            px(x, base - 10, FENCE2, K_LEDGE)
        for y in (base - 7, base - 3):
            px(x, y, FENCE2 if (x - x0) % 4 else FENCE, K_LEDGE)


# ------------------------------------------------------------------ buildings


def church():
    # the nave, behind the cottage
    stones(118, 118, 196, 178)
    roof(118, 196, 100, 118, "slate", overhang=2)
    for wx in (128, 176):
        arch_window(wx, 128, 8, 16)
    # the tower and the spire
    stones(146, 70, 168, 178)
    rect(144, 68, 170, 72, STONE3, K_TOP)
    roof(146, 168, 22, 68, "slate", overhang=1)
    px(157, 20, IRON)
    px(157, 19, IRON)
    px(156, 18, IRON)
    px(158, 18, IRON)
    px(157, 17, IRON)
    # the clock
    cx, cy = 157, 84
    for y in range(cy - 6, cy + 7):
        for x in range(cx - 6, cx + 7):
            d = (x - cx) ** 2 + (y - cy) ** 2
            if d <= 36:
                px(x, y, STONE3 if d > 25 else CLOCK)
    for i in range(4):
        px(cx, cy - i, HANDS)
    for i in range(3):
        px(cx + i, cy, HANDS)
    arch_window(152, 98, 10, 22)
    door(152, 160, 10, 18)


def arch_window(x, y, w, h):
    rect(x - 1, y + w // 2, x + w + 1, y + h + 1, STONE3)
    for yy in range(y - 1, y + w // 2):
        for xx in range(x - 1, x + w + 1):
            if (xx - x - (w - 1) / 2) ** 2 + (yy - y - w / 2) ** 2 <= (w / 2 + 1) ** 2:
                px(xx, yy, STONE3)
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            inside = yy >= y + w // 2 or (xx - x - (w - 1) / 2) ** 2 + (yy - y - w / 2) ** 2 <= (w / 2) ** 2
            if inside:
                k = ((xx - x) // 2 + (yy - y) // 3) % len(GLASS)
                c = GLASS[k]
                if (xx - x) % (w // 2) == w // 2 - 1 or (yy - y) % 6 == 5:
                    c = FRAME
                px(xx, yy, c)


def tudor():
    x0, x1, top, base = 4, 72, 126, 178
    chimney(56, 84, 7, 30)
    roof(x0, x1, 92, top, "tile")
    timber(x0, top, x1, base)
    window(10, 134, 12, 10)
    window(52, 134, 12, 10)
    window(10, 156, 10, 9)
    door(32, 154, 12, 24, wreath=True)
    # a dormer
    rect(30, 104, 46, 118, PLASTER)
    roof(30, 46, 96, 106, "tile", overhang=2)
    window(33, 108, 10, 7, curtains=False)


def cottage():
    x0, x1, top, base = 104, 146, 150, 180
    roof(x0, x1, 128, top, "thatch")
    planks(x0, top, x1, base)
    window(110, 158, 10, 9, house=1)
    door(128, 160, 10, 20, wreath=True)
    chimney(136, 124, 5, 12)


def brick_house():
    x0, x1, top, base = 206, 274, 122, 178
    chimney(214, 82, 8, 30)
    roof(x0, x1, 86, top, "slate")
    bricks(x0, top, x1, base)
    for wx in (212, 254):
        window(wx, 130, 12, 12, house=2)
        window(wx, 156, 12, 12, house=2)
    door(234, 150, 12, 28, wreath=True)
    rect(232, 148, 248, 150, TRIM, K_LEDGE)     # the lintel
    # a round attic window
    cx, cy = 240, 108
    for y in range(cy - 5, cy + 6):
        for x in range(cx - 5, cx + 6):
            d = (x - cx) ** 2 + (y - cy) ** 2
            if d <= 25:
                px(x, y, FRAME if d > 13 or x == cx or y == cy else glows(2)[1])


# ------------------------------------------------------------------ build


def draw():
    sky()
    moon(290, 32, 12)
    hills()
    church()
    ground()
    tudor()
    pine(88, 178, 46, 26, decorated=True)
    cottage()
    pine(190, 180, 30, 16)
    brick_house()
    pine(292, 179, 54, 30)
    pine(312, 181, 36, 20)
    lamp(98, 184)
    lamp(200, 184)
    fence(0, 30, 190)
    fence(254, 320, 191)


def main():
    out = sys.argv[1]
    pack45 = sys.argv[2]
    draw()

    pal = [c for _, c in RESERVED]
    where = {}
    for i, c in enumerate(pal):
        where.setdefault(c, i)
    idx = np.zeros((H, W), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            c = tuple(int(v) for v in img[y, x])
            if c not in where:
                if len(pal) >= 256:
                    raise SystemExit("palette full")
                where[c] = len(pal)
                pal.append(c)
            idx[y, x] = where[c]

    chars = bytearray()
    for r in range(ROWS):
        for c in range(COLS):
            chars += idx[r * 8:r * 8 + 8, c * 8:c * 8 + 8].tobytes()
    with open(os.path.join(out, "scene.bin"), "wb") as f:
        f.write(chars)

    pck = os.path.join(out, "scene.pck")
    subprocess.run([pack45, "--raw", "--best", "-d", "0x%X" % DEST,
                    os.path.join(out, "scene.bin"), pck], check=True, stdout=subprocess.DEVNULL)
    packed = open(pck, "rb").read()

    catch = np.isin(cls, (K_TOP, K_LEDGE))
    cbits = np.packbits(catch, axis=1).tobytes()          # 40 bytes a row, bit 7 the left
    assert len(cbits) == W * H // 8
    cbin = os.path.join(out, "catch.bin")
    with open(cbin, "wb") as f:
        f.write(cbits)
    cpck = os.path.join(out, "catch.pck")
    subprocess.run([pack45, "--raw", "--best", "-d", "0", cbin, cpck], check=True, stdout=subprocess.DEVNULL)
    cpacked = open(cpck, "rb").read()

    eave, gtop, ctop, ntop, fgtop = [], [], [], [], []
    for x in range(W):
        ys = np.nonzero(cls[:, x] == K_TOP)[0]
        eave.append(int(ys[-1]) + 1 if len(ys) else 0)
        ys = np.nonzero(cls[:, x] == K_GROUND)[0]
        gtop.append(int(ys[0]) if len(ys) else H - 1)
        ys = np.nonzero(catch[:, x])[0]
        ctop.append(int(ys[0]) if len(ys) else H)
        ys = ys[ys >= eave[-1]]
        ntop.append(int(ys[0]) if len(ys) else H)
        ys = np.nonzero(cls[:, x] != K_NONE)[0]
        fgtop.append(int(ys[0]) if len(ys) else H)

    win = [where[c] for k in range(HOUSES) for c in glows(k)]
    defs = [(name, i) for i, (name, _) in enumerate(RESERVED)]
    defs += [("SCENE_COLOURS", len(pal)), ("SCENE_HOUSES", HOUSES),
             ("P_STAR", where[STAR]), ("P_STAR2", where[STAR2]),
             ("P_LAMP", where[LAMP]), ("P_FARLIGHT", where[FARLIGHT])]
    blob.write(out, "village",
               streams=[("scene_pck", packed), ("catch_pck", cpacked)],
               tables=[("pal", "[SCENE_COLOURS][3]", bytes(v for c in pal for v in c)),
                       ("eave", "[%d]  /* below: the near flakes catch too */" % W, eave),
                       ("gtop", "[%d]  /* the open ground's top */" % W, gtop),
                       ("ctop", "[%d]  /* the top catch pixel (%d: none) */" % (W, H), ctop),
                       ("ntop", "[%d]  /* the same, at or below the eave */" % W, ntop),
                       ("fgtop", "[%d] /* the foreground's top: far flakes behind it */" % W, fgtop),
                       ("win", "[SCENE_HOUSES][3] /* each building's window glow entries */", win),
                       ("bauble", "[%d]" % len(BAUBLE), [where[c] for c in BAUBLE])],
               defines=defs, comment="the village (tools/gen_scene.py)")

    print("scene: %d colours, %d bytes packed from %d; the catch map %d from %d"
          % (len(pal), len(packed), len(chars), len(cpacked), len(cbits)))
    if "--preview" in sys.argv:
        Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, "scene.png"))
        look = np.array([(0, 0, 0), (70, 70, 90), (255, 255, 255), (255, 80, 80), (60, 120, 60)], dtype=np.uint8)
        Image.fromarray(look[cls]).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, "catch.png"))


if __name__ == "__main__":
    main()
