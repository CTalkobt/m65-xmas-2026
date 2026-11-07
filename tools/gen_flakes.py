#!/usr/bin/env python3
"""gen_flakes.py — scene 4, the snowflakes: drawn here.

    python3 tools/gen_flakes.py <build dir> <pack45> [--preview]

THE BACKGROUND: an icy plasma, 320 x 200 of full-colour cells. Each pixel's
value is a sum of waves that all repeat every 64 pixels, so the cells repeat
every 8 across and down: few different characters. The pixel is palette
entry PLASMA + value (0-63): flakes.c turns those 64 entries round, and the
plasma flows.

THE SNOWFLAKE: in the middle, a dark frosted disc, and in it a Koch
snowflake. Each pixel inside it is in the group of the first iteration
(0-4) whose curve takes it in (the curve only grows outward: each takes in
all the last did); flakes.c reveals them in turn, so the snowflake grows
from a triangle. A level's entries are its four shades, shown as the disc's
colour until it is revealed.

THE FALLING FLAKES: six-armed crystals, 16 x 16, in four frames turning
(15 degrees apart: a quarter of the 60 their arms repeat in), as RRB
objects. A frame is two columns, each a strip of four characters: blank,
the top half, the bottom half, blank (a GOTOX's character Y offset shows a
strip from any pixel row).

Writes, in the build directory: flakes.dat and flakes.h (tools/blob.py:
the characters and the screen's map packed, the palette and its groups),
flakes.png (with --preview).
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blob  # noqa: E402

W, H = 320, 200
COLS, ROWS = 40, 25
CHAR_BASE = 0x1000
CX, CY, DISC_R, KOCH_R = 160, 100, 92, 78
LEVELS = 5
FRAMES = 4


def C(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# the plasma's 64 colours: deep blue, teal, ice, white, and back
PLASMA_STOPS = [C("#020a2a"), C("#06306a"), C("#0a6aa0"), C("#40b8d8"), C("#c8f0ff"), C("#40b8d8"),
                C("#0a6aa0"), C("#06306a")]
DISC, DISC_RIM = C("#060c26"), C("#283c78")
SHADES = [C("#ffffff"), C("#d8f0ff"), C("#a8d4f4"), C("#78a8e0")]       # a level's four
FLAKE_COLS = [C("#ffffff"), C("#c8e4ff"), C("#90b8f0")]


def plasma_colours():
    out = []
    n = len(PLASMA_STOPS)
    for i in range(64):
        t = i / 64 * n
        k = int(t)
        out.append(mix(PLASMA_STOPS[k % n], PLASMA_STOPS[(k + 1) % n], t - k))
    return out


def plasma(x, y):
    v = (math.sin(2 * math.pi * x / 64) + math.sin(2 * math.pi * y / 64)
         + math.sin(2 * math.pi * (x + y) / 64) + math.sin(2 * math.pi * (x - 2 * y) / 64))
    return int((v + 4) / 8 * 63.999) & 63


def koch(level, r):
    pts = [(CX + r * math.cos(math.radians(90 + 120 * k)), CY - r * math.sin(math.radians(90 + 120 * k)))
           for k in range(3)]
    pts = pts[::-1]
    for _ in range(level):
        nxt = []
        for i in range(len(pts)):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
            dx, dy = (x1 - x0) / 3, (y1 - y0) / 3
            a = (x0 + dx, y0 + dy)
            b = (x0 + 2 * dx, y0 + 2 * dy)
            # the bump outward (the points go round clockwise on the screen)
            px = a[0] + dx * 0.5 + dy * math.sqrt(3) / 2
            py = a[1] + dy * 0.5 - dx * math.sqrt(3) / 2
            nxt += [(x0, y0), a, (px, py), b]
        pts = nxt
    return pts


def koch_levels():
    """a byte a pixel: the first level whose curve takes it in, 255 none"""
    lev = np.full((H, W), 255, dtype=np.uint8)
    # the triangle at level 0 has its points at the circle KOCH_R * 3/4 out:
    # the finished snowflake reaches KOCH_R
    for level in range(LEVELS - 1, -1, -1):
        im = Image.new("L", (W, H), 0)
        ImageDraw.Draw(im).polygon(koch(level, KOCH_R * 0.86), fill=1)
        lev[np.array(im) > 0] = level
    return lev


def crystal(angle):
    """a 16 x 16 snowflake: 0 clear, 1-3 its colours (1 brightest)"""
    px = np.zeros((16, 16), dtype=np.uint8)
    c = 7.5
    for arm in range(6):
        a = math.radians(angle + arm * 60)
        ca, sa = math.cos(a), math.sin(a)
        for i in range(0, 15):
            r = i / 2
            x, y = c + ca * r, c - sa * r
            px[int(round(y)), int(round(x))] = 1 if r < 6 else 2
            if 2.5 < r < 6 and i % 3 == 0:          # the side branches
                for side in (-1, 1):
                    b = a + side * math.radians(60)
                    for j in (1, 2):
                        xx, yy = x + math.cos(b) * j * 0.8, y - math.sin(b) * j * 0.8
                        if 0 <= xx < 16 and 0 <= yy < 16:
                            if px[int(round(yy)), int(round(xx))] == 0:
                                px[int(round(yy)), int(round(xx))] = 3
    px[7:9, 7:9] = 1
    return px


def main():
    out, pack45 = sys.argv[1], sys.argv[2]
    pcols = plasma_colours()
    lev = koch_levels()

    # the palette: 0 black, 1-3 the falling flakes', 4-67 the plasma's, then
    # the disc's two, then each level's four shades
    pal = [(0, 0, 0)] + FLAKE_COLS + pcols + [DISC, DISC_RIM]
    group = [0] * len(pal)
    P_FLAKE, P_PLASMA, P_DISC = 1, 4, 4 + 64
    P_LEVEL = len(pal)
    for level in range(LEVELS):
        for s in SHADES:
            pal.append(s)
            group.append(1 + level)
    group[P_PLASMA:P_PLASMA + 64] = [255] * 64        # the plasma: turned round, not faded by level

    idx = np.zeros((H, W), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - CX, y - CY)
            if d < DISC_R - 2:
                if lev[y, x] != 255:
                    # an ice crystal: bright edges where the levels meet and
                    # round the outside, facets in twelve sectors between
                    L = lev[y, x]
                    edge = any(lev[y + dy, x + dx] != L for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                    ang = math.atan2(y - CY, x - CX)
                    sector = int((ang + math.pi) / (math.pi / 6)) % 2
                    k = 0 if edge else 1 + sector + (1 if d > KOCH_R * 0.55 else 0)
                    idx[y, x] = P_LEVEL + L * 4 + min(3, k)
                else:
                    idx[y, x] = P_DISC
            elif d < DISC_R:
                idx[y, x] = P_DISC + 1                 # the rim
            else:
                idx[y, x] = P_PLASMA + plasma(x, y)

    chars, char_of = [], {}

    def cell(block):
        key = bytes(block.flatten())
        if key not in char_of:
            char_of[key] = len(chars)
            chars.append(key)
        return CHAR_BASE + char_of[key]

    screen = bytearray()
    for r in range(ROWS):
        for c in range(COLS):
            ch = cell(idx[r * 8:r * 8 + 8, c * 8:c * 8 + 8])
            screen += bytes([ch & 0xFF, ch >> 8])
    scene_chars = len(chars)
    # the falling flakes' strips: a frame, two columns of [blank, top, bottom, blank]
    for f in range(FRAMES):
        px = crystal(f * 15)
        for col in range(2):
            strip = [np.zeros((8, 8), dtype=np.uint8)]
            for half in range(2):
                b = px[half * 8:half * 8 + 8, col * 8:col * 8 + 8]
                strip.append(np.where(b > 0, P_FLAKE - 1 + b, 0).astype(np.uint8))
            strip.append(np.zeros((8, 8), dtype=np.uint8))
            for s in strip:
                chars.append(bytes(s.flatten()))

    def pack(name, data, dest):
        raw, pck = os.path.join(out, name + ".bin"), os.path.join(out, name + ".pck")
        open(raw, "wb").write(data)
        subprocess.run([pack45, "--raw", "--best", "-d", "0x%X" % dest, raw, pck], check=True,
                       stdout=subprocess.DEVNULL)
        return open(pck, "rb").read()

    chr_pck = pack("flakes_chr", b"".join(chars), CHAR_BASE * 64)
    map_pck = pack("flakes_map", bytes(screen), 0)
    defs = [("FLAKES_COLOURS", len(pal)), ("P_FLAKE", P_FLAKE), ("P_PLASMA", P_PLASMA), ("P_DISC", P_DISC),
            ("P_LEVEL", "%d  /* level L's four shades: P_LEVEL + L * 4 ... */" % P_LEVEL),
            ("LEVELS", LEVELS), ("FLAKE_FRAMES", FRAMES),
            ("CH_STRIPS", "(CH0 + %d)  /* frame f, column c: CH_STRIPS + f * 8 + c * 4: blank, top, bottom, blank */"
             % scene_chars)]
    blob.write(out, "flakes", streams=[("chr_pck", chr_pck), ("map_pck", map_pck)],
               tables=[("pal", "[FLAKES_COLOURS][3]", bytes(v for c in pal for v in c)),
                       ("group", "[FLAKES_COLOURS]  /* 0 still, 1 + L level L, 255 the plasma */", group)],
               defines=defs, comment="the snowflakes (tools/gen_flakes.py)")
    print("flakes: %d colours, %d characters (%d bytes packed), map %d packed"
          % (len(pal), len(chars), len(chr_pck), len(map_pck)))
    if "--preview" in sys.argv:
        rgb = np.array(pal, dtype=np.uint8)[idx]
        for i, f in enumerate(range(FRAMES)):                       # the crystals, top left
            px = crystal(f * 15)
            for y in range(16):
                for x in range(16):
                    if px[y, x]:
                        rgb[8 + y, 8 + i * 20 + x] = FLAKE_COLS[px[y, x] - 1]
        Image.fromarray(rgb).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, "flakes.png"))


if __name__ == "__main__":
    main()
