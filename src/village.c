/* village.c — scene 1, the village: falling snow in RRB slots, settling
 * snow in the characters. A code overlay (main.c calls village()).
 *
 * The VIC-IV at 320 x 200, 16-bit characters, full colour above $FF.
 *
 * THE BACKGROUND is 40 x 25 cells, each its own character (1,000 of them,
 * $1000-$13E7, bank 4): the village under a night sky, pixel art from
 * tools/gen_scene.py, packed (pack45) in XMASDATA (village.h, data.h) and
 * unpacked by DMA when the scene begins; its tables are copied into vt. Every cell is unique, so snow plotted into one shows only
 * there. The tool also gives the palette and where snow can rest (below).
 *
 * THE FALLING SNOW: after a row's 40 cells come SLOTS flake slots, each a
 * transparent GOTOX and a glyph:
 *   screen byte 0      x, low 8 bits
 *   screen byte 1      x bits 8-9 | the character data Y offset (bits 5-7)
 *   screen bytes 2-3   the glyph: fixed for the slot (its layer's)
 * A flake's state is all there: x in the GOTOX, y = row * 8 + p, where the
 * Y offset is 7 - p. (The offset adds 8 bytes, one pixel row, a step: the
 * glyph's dot is on its last row, so offset v shows it at row 7 - v. Each
 * glyph is followed by a blank one in memory, for the rows read past it.)
 * x >= 320 is no flake (DEAD: drawn off the right of the screen).
 *
 * The slots are in LAYERS layers (far, middle, near) of PER_LAYER each. A
 * layer moves a pixel every so many frames (its speed). Slot k of a layer
 * is k pixels ahead of slot 0, so in any row the layer's flakes are at
 * every pixel row, not in lines; it is the same for every row, so a slot's
 * Y offset is one value for the whole column of it. When slot k's p wraps
 * 7 -> 0, its flakes have crossed into the next text row: its column is
 * moved down a row (the x bytes, row 24 up to row 1) and row 0 gets a new
 * flake, or none (the density). So one slot a layer hops a move.
 *
 * Its colour RAM never changes: written once.
 *
 * THE END OF A ROW is a GOTOX 320. After a row's last cell the VIC-IV
 * fills the rest of the line with the background colour from where it
 * stopped drawing: a row that ended with a flake at x would lose
 * everything right of x + 8. (So DEAD is 360: past the edge, but not so
 * far that the position wraps round the line.)
 *
 * THE SETTLED SNOW. The layers are depths, and each settles at its own:
 *   far     behind the village: hidden behind it (below a column's
 *           fgtop its slot shows the blank glyph, its x kept in the GOTOX),
 *           and only on the open ground's far edge (behind a building it
 *           is gone when it gets to the ground)
 *   middle  at the houses: on what the catch map has (roofs, chimney caps,
 *           trees, sills, the fence ...) and on the ground just in front
 *   near    in front of the roofs: on the catch map only below the eaves
 *           (sills, the lintel, the fence, the lamps), and on the ground
 *           nearest us, low on the screen
 * The catch map (tools/gen_scene.py) is a bit a pixel, set where snow can
 * rest. A flake whose next pixel down is set slides a pixel sideways where
 * the two pixels down that side are clear (so it runs off edges and down
 * anything steeper than 45 degrees: the spire), or else rests: its pixel
 * is set in the map (snow on snow builds up) and plotted into that cell's
 * character (DMA, one byte). Below the eaves a column holds LEDGE_MAX
 * pixels of it, so a sill gets a cap, not a drift over the window; when
 * it is full, flakes fall on past it.
 * On the ground a flake comes to rest somewhere in its layer's band below
 * the ground's top (gtop): a chance each pixel, sure at the band's end.
 * There it is only plotted: the ground whitens all over, at every depth.
 *
 * THE MUSIC (tools/gen_music.py: God Rest Ye Merry, Gentlemen, the church
 * bell tolling first) plays on SIDs 1-2, mirrored on 3-4 for the right:
 * tune_update once a frame, after the snow's pass.
 *
 * THE PALETTE is alive: each building's windows flicker on their own (a
 * fire's light), the tree's baubles change colours round, the street lamps
 * waver, the stars and the far windows twinkle.
 *
 * Keys:  + -    density
 *        W      wind: none, right, left
 *        T      the border shows the update's CPU time (white), row by row
 *        SPACE  the scene again, bare
 *        N      on to the next scene
 *
 * THE RRB BUDGET is assumed (not yet measured on a MEGA65: see budget.c):
 * about 100 cells a row, of which this uses 40 + 2 * SLOTS + 1 = 89.
 */
#pragma cc45 overlay(village)
#include <dma.h>
#include <unpack.h>
#include <audio_sid.h>
#include <audio_tune.h>
#include "vic.h"
#include "data.h"
#include "village.h"
#include "music.h"
#include "scenes.h"


#define CH_FLAKE   (CH0 + 0x400)    /* after the 1,000 scene cells: glyph, blank, ... */


#define LAYERS     3
#define PER_LAYER  8
#define SLOTS      (LAYERS * PER_LAYER)
#define CELLS      (COLS + SLOTS * 2 + 1)   /* + the end: GOTOX 320 */
#define END        (CELLS - 1)
#define LS         (CELLS * 2)      /* LINESTEP */
#define DEAD       360              /* past the right edge, not past the line */
#define TOP        16               /* snow piles up no higher than this */

/* the palette: village.h (P_SNOW, P_SNOW2, P_FAR, P_MID, P_NEAR first) */

#define scr screen_ram                       /* the screen RAM (bank 0, vic.c) */
_Static_assert(CELLS <= SCREEN_CELLS, "the village's rows in screen_ram");
static struct village_tables vt;            /* from XMASDATA (village.h) */
#define catchmap scene_ram                  /* a bit a pixel, bit 7 the left (vic.c's work area) */
_Static_assert(W / 8 * H <= SCENE_RAM, "the catch map in scene_ram");
static unsigned char ledge[W];             /* snow resting below the eaves, a column */
static unsigned char ctop[W];              /* the top catch pixel of a column (H: none) */
static unsigned char ntop[W];              /* the same at or below the eave: the near layer's */
static unsigned int rowoff[H];             /* y * 40: a catch map row */
#define LEDGE_MAX  3
/* the ground bands, each layer's: from gtop + lo to gtop + hi */
static const unsigned char band_lo[LAYERS] = {0, 4, 11};
static const unsigned char band_hi[LAYERS] = {4, 12, 40};
static unsigned char cellbuf[64];
static unsigned char P[LAYERS];             /* each layer's moves, mod 256 */
#ifndef DENSITY
#define DENSITY 96
#endif
#ifndef TIMING
#define TIMING 0
#endif
static unsigned char t, density = DENSITY, timing = TIMING;
static signed char wind;

/* a layer moves when (t & mask) == 0: far, middle, near */
static const unsigned char speed_mask[LAYERS] = {3, 1, 0};
/* the sway, a step a move now and then */
static const signed char sway[16] = {0, 1, 1, 0, 1, 0, 0, -1, 0, -1, -1, 0, -1, 0, 0, 1};

/* ---- the scene ---- */

static void scene(void) {
    unsigned int x;
    unpack(VILLAGE_LIN + VILLAGE_SCENE_PCK);
    unpack_to(VILLAGE_LIN + VILLAGE_CATCH_PCK, (unsigned long)(unsigned int)catchmap);
    for (x = 0; x < W; x++) {
        ledge[x] = 0;
        ctop[x] = vt.ctop[x];
        ntop[x] = vt.ntop[x];
    }
    for (x = 0; x < H; x++) rowoff[x] = x * (W / 8);
}

static const unsigned char bit[8] = {0x80, 0x40, 0x20, 0x10, 8, 4, 2, 1};

/* the catch map at (x, y); off the screen's sides it counts as set */
static unsigned char caught(signed int x, unsigned char y) {
    if (x < 0 || x >= W) return 1;
    return catchmap[rowoff[y] + ((unsigned int)x >> 3)] & bit[x & 7];
}

static void plot(unsigned int x, unsigned char y, unsigned char c) {
    dma_fill_far(CHR_LIN + ((unsigned long)(y >> 3) * COLS + (x >> 3)) * 64
                 + (y & 7) * 8 + (x & 7), 1, c);
}

/* the flake glyphs: a dot on the last row, then a blank glyph */
static void glyphs(void) {
    static const unsigned char colour[LAYERS] = {P_FAR, P_MID, P_NEAR};
    unsigned char l;
    for (l = 0; l < LAYERS; l++) {
        dma_fill((void *)cellbuf, 64, 0);
        cellbuf[56] = colour[l];
        if (l == LAYERS - 1) cellbuf[57] = colour[l];   /* the near ones 2 wide */
        dma_copy_far(CHR_LIN + (unsigned long)(0x400 + l * 2) * 64, (unsigned long)(unsigned int)cellbuf, 64);
        dma_fill((void *)cellbuf, 64, 0);
        dma_copy_far(CHR_LIN + (unsigned long)(0x401 + l * 2) * 64, (unsigned long)(unsigned int)cellbuf, 64);
    }
}

/* ---- the screen ---- */

#define SLOT(r, s) (scr + (unsigned int)(r) * LS + (COLS + (s) * 2) * 2)

static unsigned int new_x(void) {
    return (unsigned char)rnd() < density ? rnd() % W : DEAD;
}

static void screen_init(void) {
    static unsigned char crow[LS];
    unsigned char r, s, l, *q;
    unsigned int k, x, ch;
    for (k = 0; k < LS; k++) crow[k] = 0;
    for (s = 0; s < SLOTS; s++) crow[(COLS + s * 2) * 2] = 0x90;   /* GOTOX, transparent */
    crow[END * 2] = 0x90;
    for (r = 0; r < ROWS; r++) {
        dma_copy_far(COLOR_LIN + (unsigned long)r * LS, (unsigned long)(unsigned int)crow, LS);
        for (k = 0; k < COLS; k++) {
            ch = CH0 + r * COLS + k;
            scr[r * LS + k * 2] = (unsigned char)ch;
            scr[r * LS + k * 2 + 1] = (unsigned char)(ch >> 8);
        }
        for (s = 0; s < SLOTS; s++) {
            l = s / PER_LAYER;
            q = SLOT(r, s);
            x = new_x();
            if (x != DEAD && r * 8 + 8 >= vt.gtop[x]) x = DEAD;  /* none in the ground */
            q[0] = (unsigned char)x;
            q[1] = (unsigned char)(x >> 8);
            ch = CH_FLAKE + l * 2;
            q[2] = (unsigned char)ch;
            q[3] = (unsigned char)(ch >> 8);
        }
        scr[r * LS + END * 2] = (unsigned char)W;
        scr[r * LS + END * 2 + 1] = (unsigned char)(W >> 8);
    }
}

/* ---- the snow ---- */

/* a flake at (x, y) of layer l: 0 it falls on, 1 it rests (and is gone),
 * or it slides a pixel sideways (*px changed) and falls on */
static unsigned char settle(signed int *px, unsigned char y, unsigned char l) {
    signed int x = *px;
    signed char d;
    unsigned char g = vt.gtop[x];
    if (l && y + 1 < H && (l == 1 || y >= vt.eave[x])
        && caught(x, y + 1) && !caught(x, y)) {
        /* off an edge, or down anything steeper than 45 degrees: a side
         * where the next two pixels down are both clear */
        d = (rnd() & 1) ? 1 : -1;
        if (!caught(x + d, y + 1) && (y + 2 >= H || !caught(x + d, y + 2))) *px = x + d;
        else if (!caught(x - d, y + 1) && (y + 2 >= H || !caught(x - d, y + 2))) *px = x - d;
        else {
            if (y < TOP) return 0;
            if (y >= vt.eave[x]) {
                if (ledge[x] >= LEDGE_MAX) return 0;    /* full: it falls on past */
                ledge[x]++;
            }
            catchmap[rowoff[y] + ((unsigned int)x >> 3)] |= bit[x & 7];
            if (y < ctop[x]) ctop[x] = y;
            if (y >= vt.eave[x] && y < ntop[x]) ntop[x] = y;
            plot((unsigned int)x, y, (rnd() & 3) ? P_SNOW : P_SNOW2);
            return 1;
        }
        return 0;
    }
    if (y >= g + band_lo[l] && (y >= g + band_hi[l] || y == H - 1 || !(rnd() & 3))) {
        if (l == 0 && vt.fgtop[x] < g) return 1;     /* behind a building: unseen */
        plot((unsigned int)x, y, l == 0 || (rnd() & 7) == 0 ? P_SNOW2 : P_SNOW);
        return 1;
    }
    return 0;
}

/* ---- the update, chasing the beam ----
 *
 * A text row the VIC-IV has drawn is not read again until the next frame,
 * so it can be rewritten all that time. The update goes down the screen
 * behind the beam: row r is changed only when the raster is MARGIN lines
 * past its last line (the RRB renders a line ahead: one is enough). So it
 * has nearly a whole frame, not only the vertical blank.
 *
 * It is done a row at a time, every moving slot in it. A slot that hops
 * (its flakes crossing into the next text row) takes, in row r, row r - 1's
 * flake from before this frame's change: carry[s] holds it, the old value
 * of the row above, so nothing is written ahead of the beam. Row 0 takes a
 * new flake (or none); row 24's goes off the bottom.
 *
 * If the beam comes round again before the update is done (late), it does
 * not wait any more: that frame shows rows of both.
 */
#define MARGIN 2

static unsigned char row0;                  /* the first text row's raster line */
static unsigned int prev_line;
static unsigned char late;
unsigned char lates;                        /* frames the update ran late */
unsigned int finish;                        /* the latest raster line it ended on (+ 312: the next frame's) */

/* the slots that move this frame: their layer, phase and Y offset */
static unsigned char nmove, mv_s[SLOTS], mv_l[SLOTS], mv_p[SLOTS], mv_v[SLOTS], mv_sw[SLOTS], mv_hop[SLOTS];
static unsigned char ph_l[LAYERS];
static signed char w_l[LAYERS];
static unsigned int carry[SLOTS];

/* until the beam is past line (or it has gone round: late) */
static void wait_past(unsigned int line) {
    unsigned int rv;
    if (late) return;
    for (;;) {
        rv = raster();
        if (rv < prev_line) {
            late = 1;
            return;
        }
        prev_line = rv;
        if (rv >= line) return;
    }
}

static void frame_begin(void) {
    unsigned char l, k, p, s;
    nmove = 0;
    for (l = 0; l < LAYERS; l++) {
        if (t & speed_mask[l]) continue;
        ph_l[l] = ++P[l];
        w_l[l] = (ph_l[l] & 1) ? 0 : wind;
        for (k = 0; k < PER_LAYER; k++) {
            s = l * PER_LAYER + k;
            p = (ph_l[l] + k) & 7;
            mv_s[nmove] = s;
            mv_l[nmove] = l;
            mv_p[nmove] = p;
            mv_v[nmove] = (unsigned char)((7 - p) << 5);
            mv_sw[nmove] = (ph_l[l] >> 4) + s * 3;
            mv_hop[nmove] = !p;
            nmove++;
        }
    }
}

/* A flake needs settle() only near something: at or past its layer's
 * ground band, or a pixel above its column's top catch pixel (ctop for the
 * middle layer, ntop for the near). Everything else just falls: most of
 * them, in the sky. */
static void row_update(unsigned char r) {
    unsigned char i, l, s, y, hi, lim;
    unsigned char *row = scr + (unsigned int)r * LS + COLS * 2, *q;
    signed int x;
    unsigned int old;
    signed char dx;
    for (i = 0; i < nmove; i++) {
        s = mv_s[i];
        l = mv_l[i];
        q = row + s * 4;
        hi = q[1] & 3;
        old = q[0] | (unsigned int)hi << 8;
        if (mv_hop[i]) {
            x = r ? (signed int)carry[s] : (signed int)new_x();
            carry[s] = old;
        } else
            x = (signed int)old;
        if (x >= W) {                           /* none (DEAD) */
            if (mv_hop[i]) {
                q[0] = (unsigned char)DEAD;
                q[1] = (unsigned char)(DEAD >> 8);
            }
            continue;
        }
        y = r * 8 + mv_p[i];
        dx = w_l[l];
        if (!((ph_l[l] + r) & 3)) dx += sway[(mv_sw[i] + r * 5) & 15];
        if (dx) {
            x += dx;
            if (x < 0) x += W;
            else if (x >= W) x -= W;
        }
        lim = vt.gtop[x] + band_lo[l];
        if (l == 1 && ctop[x] <= lim) lim = ctop[x] - 1;
        else if (l == 2 && ntop[x] <= lim) lim = ntop[x] - 1;
        if (y >= lim && settle(&x, y, l)) x = DEAD;
        q[0] = (unsigned char)x;
        q[1] = (unsigned char)((unsigned int)x >> 8) | mv_v[i];
        if (!l && x < W)                        /* far: behind the foreground, the blank glyph */
            q[2] = (unsigned char)(CH_FLAKE + (y >= vt.fgtop[x]));
    }
}

static void snow_frame(void) {
    unsigned char r;
    unsigned int f;
    while (raster() >= row0) {}                 /* the top border: row 0 not yet drawn */
    prev_line = raster();
    late = 0;
    t++;
    frame_begin();
    for (r = 0; r < ROWS; r++) {
        wait_past(row0 + r * 8 + 8 + MARGIN);
        if (timing) REG(0xD020) = 1;
        row_update(r);
        if (timing) REG(0xD020) = 0;
    }
    f = raster();
    if (late) {
        lates++;
        f += 312;
    }
    if (f > finish) finish = f;
}

/* ---- the palette's life ---- */

static unsigned char flick[SCENE_HOUSES], flick_to[SCENE_HOUSES];

static void pal_set(unsigned char i, unsigned char from, unsigned char level) {
    pal_rgb(i, (unsigned char)((vt.pal[from][0] * level) >> 8),
            (unsigned char)((vt.pal[from][1] * level) >> 8),
            (unsigned char)((vt.pal[from][2] * level) >> 8));
}

static void palette_life(void) {
    static unsigned char bauble_at;
    unsigned char k, j, i;
    for (k = 0; k < SCENE_HOUSES; k++) {        /* firelight: toward a new level now and then */
        if (!(rnd() & 7)) flick_to[k] = 190 + (unsigned char)(rnd() % 66);
        if (flick[k] < flick_to[k]) flick[k] += 4;
        else if (flick[k] > flick_to[k] + 3) flick[k] -= 4;
        for (j = 0; j < 3; j++) pal_set(vt.win[k][j], vt.win[k][j], flick[k]);
    }
    if (!(t & 31)) {                            /* the baubles: their colours round */
        bauble_at = bauble_at == 4 ? 0 : bauble_at + 1;
        for (i = 0; i < 5; i++) {
            j = i + bauble_at;
            if (j >= 5) j -= 5;
            pal_set(vt.bauble[i], vt.bauble[j], 255);
        }
    }
    if (!(t & 3)) {
        pal_set(P_LAMP, P_LAMP, 220 + (unsigned char)(rnd() & 31));
        pal_set(P_STAR2, P_STAR2, (rnd() & 3) ? 255 : 150);
        pal_set(P_FARLIGHT, P_FARLIGHT, (rnd() & 1) ? 255 : 170);
    }
}

/* ---- the display ---- */

static void start(void) {
    REG(0xD011) = REG(0xD011) & 0xEF;           /* the screen off while it is drawn */
    scene();
    screen_init();
    REG(0xD011) = REG(0xD011) | 0x10;
}

/* the palette at level 0-16 (the fade in and out) */
static void palette_at(unsigned char level) {
    unsigned int i;
    for (i = 0; i < SCENE_COLOURS; i++)
        pal_rgb((unsigned char)i, (unsigned char)((vt.pal[i][0] * level) >> 4),
                (unsigned char)((vt.pal[i][1] * level) >> 4), (unsigned char)((vt.pal[i][2] * level) >> 4));
}

/* the scene for frames frames (N sooner), then a fade out */
void village(unsigned int frames) {
    unsigned char k;
    unsigned int f;
    dma_copy_far((unsigned long)(unsigned int)&vt, VILLAGE_LIN + VILLAGE_TABLES, VILLAGE_TABLES_SIZE);
    glyphs();
    start();
    row0 = vic_on(scr, CELLS);
    for (k = 0; k < SCENE_HOUSES; k++) flick[k] = flick_to[k] = 240;
    tune_volume(15);
    tune_play_far(MUSIC_LIN + TUNE_CAROL_AT);
    for (f = 0; f < frames + FADE_FRAMES; f++) {
        snow_frame();
        tune_update();
        if (f < FADE_FRAMES) palette_at((unsigned char)(f >> 1));       /* in */
        else if (f >= frames) {                                         /* out */
            palette_at((unsigned char)((frames + FADE_FRAMES - 1 - f) >> 1));
            continue;
        } else palette_life();
        k = key();
        if (k == '+' && density < 240) density += 16;
        else if (k == '-' && density >= 16) density -= 16;
        else if (k == 'w' || k == 'W') wind = wind == 0 ? 1 : wind == 1 ? -1 : 0;
        else if (k == 't' || k == 'T') timing ^= 1;
        else if (k == ' ') start();
        else if (k == 'n' || k == 'N') {
            frames = f + 1;
            tune_fade(FADE_FRAMES, 0);
        }
        if (f + 1 == frames) tune_fade(FADE_FRAMES, 0);
    }
}
