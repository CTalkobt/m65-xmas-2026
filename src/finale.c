/* finale.c — scene 6, the finale: a snow globe. A code overlay (main.c
 * calls finale()).
 *
 * The picture (tools/gen_globe.py, globe.h): a snow globe on its base on
 * a table, a gold plaque on the base, the room dark behind. Every row is
 *   cell 0        GOTOX 8 (8 + a jitter while the globe is shaken; the
 *                 credits' row: its fine scroll)
 *   cells 1-41    the row's picture, 41 cells (the plane's first and last
 *                 8 pixels are covered: picture x shows at screen x + 8)
 *   cells 42-53   SLOTS snow slots: a transparent GOTOX, the flake glyph
 *   cells 54-57   GOTOX 0, black, GOTOX 312, black (the edges)
 *
 * THE SNOW: FLAKES flakes, each where it is (8.8, picture pixels) and its
 * speed, or settled. Shaken, the snow already down is gone (the globe's
 * characters unpacked again: each cell touching the globe has its own)
 * and every flake is thrown up and about. Then they fall: gravity toward
 * a slow drift, the air slowing them sideways, the glass turning them back
 * in (span_l/span_r: the inside a pixel row). One that comes down on the
 * snow (ground[]: the top of what is solid a column) slides to a lower
 * neighbour, if one is 2 or more lower, and settles: a pixel plotted into
 * the cell's character, ground[] a pixel higher. They are placed in the
 * slots of their rows afresh each frame (the vertical blank).
 *
 * THE GREETING: two lines on the plaque, from GREETING (loaded by main.c at
 * the start: tools/card.py, make card), each centred; without it (or a bad
 * one), MERRY CHRISTMAS / AND A HAPPY NEW YEAR.
 *
 * THE CREDITS scroll along the bottom row, a pixel a frame.
 *
 * The music: Silent Night (tune silent).
 */
#pragma cc45 overlay(finale)
#include <dma.h>
#include <unpack.h>
#include <audio_tune.h>
#include "vic.h"
#include "data.h"
#include "globe.h"
#include "music.h"
#include "scenes.h"

#define SLOTS      6
#define PIC        1                              /* the picture's first cell */
#define SLOT0      (PIC + MAPW)
#define EDGE       (SLOT0 + SLOTS * 2)
#define CELLS      (EDGE + 4)
#define LS         (CELLS * 2)
#define DEAD       360
#define FLAKES     48
#define SHAKE      44                             /* frames the globe shakes */
#define SHAKE_EVERY 640
#define SETTLE_MAX 10                             /* the snow's depth at most */

#define scr screen_ram
_Static_assert(CELLS <= SCREEN_CELLS, "the finale's rows in screen_ram");

struct globe_work {
    struct globe_tables tb;                       /* from GLOBE (globe.h) */
    unsigned int x[FLAKES], y[FLAKES];            /* 8.8, picture pixels */
    signed int vx[FLAKES], vy[FLAKES];
    unsigned char on[FLAKES];                     /* 0: settled */
    unsigned char ground[GLOBE_COLS];             /* the snow's top now */
};
#define gw (*(struct globe_work *)scene_ram)
_Static_assert(sizeof(struct globe_work) <= SCENE_RAM, "the finale's work in scene_ram");

static const char __noescape credits[] =       /* kept with the code, in the overlay */
    "          midwinter - a christmas demo for the mega65 ...   "
    "made with the m65compiler tool suite: cc45, ca45, ln45, pack45, tune45, disk45 ...   "
    "the music, carols long in the public domain: god rest ye merry, gentlemen - "
    "o tannenbaum - ding dong merrily on high (arr. charles wood) - "
    "shchedryk (mykola leontovych) - once in royal david's city (henry gauntlett, arr. a. h. mann) - "
    "silent night (franz xaver gruber) ...   "
    "by craig taylor (ctalkobt@ctalkobt.net) and claude ai ...   "
    "thank you for watching, and a merry christmas to you all!          ";

static unsigned int t, credit_at, shake_t;
static unsigned char credit_x, fade;
static unsigned char used[ROWS];

/* ---- the screen ---- */

static void put(unsigned char row, unsigned char cell, unsigned int ch) {
    unsigned char *p = scr + (unsigned int)row * LS + cell * 2;
    p[0] = (unsigned char)ch;
    p[1] = (unsigned char)(ch >> 8);
}

static unsigned int glyph(unsigned int base, unsigned char c) {
    if (c >= 0xC1 && c <= 0xDA) c -= 0x80;        /* PETSCII shifted letters: as ASCII's */
    if (c >= 0x61 && c <= 0x7A) c -= 0x20;
    return base + gw.tb.text_map[c & 0x7F];
}

static void plaque(void) {
    static unsigned char g[42];
    static const char line1[] = "merry christmas", line2[] = "and a happy new year";
    unsigned char l, i, n, c0;
    const unsigned char *s;
    dma_copy_far((unsigned long)(unsigned int)g, GREETING_LIN, 42);
    for (l = 0; l < 2; l++) {
        if (g[0] == 0x47 && g[1] == 0x52) {      /* "GR" (cc45's 'G' would be PETSCII's shifted G) */
            s = g + 2 + l * PLAQUE_W;
            for (n = PLAQUE_W; n && s[n - 1] == ' '; n--) {}
        } else {
            s = (const unsigned char *)(l ? line2 : line1);
            for (n = 0; s[n]; n++) {}
        }
        c0 = PLAQUE_COL + (PLAQUE_W - n) / 2;
        for (i = 0; i < n; i++) put(PLAQUE_ROW + l, PIC + c0 + i, glyph(CH_PLAQUE, s[i]));
    }
}

static void screen_init(void) {
    static unsigned char crow[LS];
    unsigned char r, k, *p;
    unsigned int i;
    for (r = 0; r < ROWS; r++) {
        p = scr + (unsigned int)r * LS;
        p[0] = 8;
        p[1] = 0;
        dma_copy_far((unsigned long)(unsigned int)(p + PIC * 2), SCRATCH_LIN + (unsigned int)r * MAPW * 2, MAPW * 2);
        for (k = 0; k < SLOTS; k++) {
            put(r, SLOT0 + k * 2, DEAD);
            put(r, SLOT0 + k * 2 + 1, CH_FLAKE);
        }
        put(r, EDGE, 0);
        put(r, EDGE + 1, CH_BLACK);
        put(r, EDGE + 2, 312);
        put(r, EDGE + 3, CH_BLACK);
    }
    for (k = 0; k < MAPW; k++) put(CREDIT_ROW, PIC + k, CH_CREDIT);
    for (i = 0; i < LS; i++) crow[i] = 0;
    crow[0] = 0x10;
    for (k = 0; k < SLOTS; k++) crow[(SLOT0 + k * 2) * 2] = 0x90;      /* transparent */
    crow[EDGE * 2] = 0x10;
    crow[(EDGE + 2) * 2] = 0x10;
    for (r = 0; r < ROWS; r++)
        dma_copy_far(COLOR_LIN + (unsigned long)r * LS, (unsigned long)(unsigned int)crow, LS);
    plaque();
}

static void credits_step(void) {
    unsigned char *row = scr + (unsigned int)CREDIT_ROW * LS;
    credit_x += 2;                               /* 2 pixels a frame: all of it in the scene's minute */
    if (credit_x == 8) {
        credit_x = 0;
        dma_copy(row + PIC * 2, row + (PIC + 1) * 2, (MAPW - 1) * 2);
        put(CREDIT_ROW, PIC + MAPW - 1, glyph(CH_CREDIT, (unsigned char)credits[credit_at]));
        if (!credits[++credit_at]) credit_at = 0;
    }
    row[0] = (unsigned char)(8 - credit_x);
}

/* ---- the snow ---- */

static void shake(void) {
    unsigned char i, r;
    unpack(GLOBE_LIN + GLOBE_CHR_PCK);            /* the snow that was down: gone */
    for (i = 0; i < GLOBE_COLS; i++) gw.ground[i] = gw.tb.ground[i];
    for (i = 0; i < FLAKES; i++) {
        r = 40 + (unsigned char)(rnd() % (GLOBE_ROWS - 50));
        gw.y[i] = (unsigned int)(GLOBE_TOP + r) << 8;
        gw.x[i] = (unsigned int)(gw.tb.span_l[r] + rnd() % (gw.tb.span_r[r] - gw.tb.span_l[r] + 1)) << 8;
        gw.vy[i] = -(signed int)(200 + (rnd() & 511));
        gw.vx[i] = (signed int)(rnd() & 511) - 256;
        gw.on[i] = 1;
    }
    shake_t = 0;
}

/* a flake comes down on the snow at picture column x */
static void settle(unsigned char i, unsigned char x) {
    unsigned char c = x - GLOBE_LEFT, k, y;
    unsigned char *cell;
    unsigned int ch;
    signed char d = (rnd() & 1) ? 1 : -1;
    for (k = 0; k < 3; k++) {
        if ((unsigned char)(c + d) < GLOBE_COLS && gw.ground[c + d] > gw.ground[c] + 1) c += d;
        else if ((unsigned char)(c - d) < GLOBE_COLS && gw.ground[c - d] > gw.ground[c] + 1) c -= d;
        else break;
    }
    gw.on[i] = 0;
    if (gw.ground[c] <= gw.tb.ground[c] - SETTLE_MAX || gw.ground[c] <= GLOBE_TOP + 2) return;
    y = --gw.ground[c];
    x = c + GLOBE_LEFT;
    cell = scr + (unsigned int)(y >> 3) * LS + (PIC + (x >> 3)) * 2;
    ch = cell[0] | (unsigned int)cell[1] << 8;
    dma_fill_far(CHR_LIN + (unsigned long)(ch - CH0) * 64 + (y & 7) * 8 + (x & 7), 1, P_SNOW);
}

static void snow(signed char jitter) {
    unsigned char i, r, k, ry, px, py, *q;
    unsigned int sx;
    for (r = 0; r < ROWS; r++) {
        used[r] = 0;
        q = scr + (unsigned int)r * LS + SLOT0 * 2;
        for (k = 0; k < SLOTS; k++, q += 4) {
            q[0] = (unsigned char)DEAD;
            q[1] = (unsigned char)(DEAD >> 8);
        }
    }
    for (i = 0; i < FLAKES; i++) {
        if (!gw.on[i]) continue;
        gw.vy[i] += (64 - gw.vy[i]) >> 4;                       /* toward a slow fall */
        gw.vx[i] -= gw.vx[i] >> 4;                              /* the water slows it */
        if (!((t + i * 5) & 15)) gw.vx[i] += (signed int)(rnd() & 63) - 32;
        gw.x[i] += gw.vx[i];
        gw.y[i] += gw.vy[i];
        py = (unsigned char)(gw.y[i] >> 8);
        if (py < GLOBE_TOP || gw.y[i] >= 0xC000) {        /* above the glass (or round past 0) */
            gw.y[i] = (unsigned int)GLOBE_TOP << 8;
            gw.vy[i] = -gw.vy[i] / 2;
            py = GLOBE_TOP;
        }
        ry = py - GLOBE_TOP;
        if (ry >= GLOBE_ROWS) ry = GLOBE_ROWS - 1;
        px = (unsigned char)(gw.x[i] >> 8);
        if (px < gw.tb.span_l[ry]) {
            gw.x[i] = (unsigned int)gw.tb.span_l[ry] << 8;
            gw.vx[i] = -gw.vx[i] / 2;
            px = gw.tb.span_l[ry];
        } else if (px > gw.tb.span_r[ry]) {
            gw.x[i] = (unsigned int)gw.tb.span_r[ry] << 8;
            gw.vx[i] = -gw.vx[i] / 2;
            px = gw.tb.span_r[ry];
        }
        if (gw.vy[i] > 0 && px >= GLOBE_LEFT && px < GLOBE_LEFT + GLOBE_COLS
            && py + 1 >= gw.ground[px - GLOBE_LEFT]) {
            settle(i, px);
            continue;
        }
        r = py >> 3;
        if (used[r] == SLOTS) continue;
        q = scr + (unsigned int)r * LS + (SLOT0 + used[r]++ * 2) * 2;
        sx = px + 8 + jitter;
        q[0] = (unsigned char)sx;
        q[1] = (unsigned char)((sx >> 8) & 3) | (unsigned char)((7 - (py & 7)) << 5);
    }
}

/* ---- the palette ---- */

static void palette(void) {
    unsigned char i, j, l;
    const unsigned char *c;
    for (i = 1; i < GLOBE_COLOURS; i++) {
        c = gw.tb.pal[i];
        l = 255;
        if (gw.tb.group[i] == G_BOKEH) {          /* the lights out of focus: a slow pulse */
            j = (unsigned char)(t + i * 9);
            l = 180 + ((j < 128 ? j : 255 - j) >> 1);
        }
        pal_rgb(i, (unsigned char)((((unsigned int)c[0] * l) >> 8) * fade >> 4),
                (unsigned char)((((unsigned int)c[1] * l) >> 8) * fade >> 4),
                (unsigned char)((((unsigned int)c[2] * l) >> 8) * fade >> 4));
    }
}

/* the scene for frames frames (N sooner), then a fade out */
void finale(unsigned int frames) {
    unsigned char k, r;
    unsigned int f;
    signed char jitter;
    dma_copy_far((unsigned long)(unsigned int)&gw.tb, GLOBE_LIN + GLOBE_TABLES, GLOBE_TABLES_SIZE);
    unpack(GLOBE_LIN + GLOBE_CHR_PCK);
    unpack_to(GLOBE_LIN + GLOBE_MAP_PCK, SCRATCH_LIN);
    for (k = 0; k < GLOBE_COLS; k++) gw.ground[k] = gw.tb.ground[k];
    for (k = 0; k < FLAKES; k++) gw.on[k] = 0;
    screen_init();
    vic_on(scr, CELLS);
    t = 0;
    credit_x = 0;
    credit_at = 0;
    shake_t = SHAKE;
    tune_volume(15);
    tune_play_far(MUSIC_LIN + TUNE_SILENT_AT);
    for (f = 0; f < frames + FADE_FRAMES; f++) {
        while (raster() < 251) {}                 /* the bottom border */
        if (f % SHAKE_EVERY == 50) shake();
        jitter = 0;
        if (shake_t < SHAKE) {
            jitter = (shake_t & 2) ? 2 : -2;
            if (shake_t > SHAKE - 12) jitter /= 2;
            shake_t++;
        }
        for (r = 0; r < CREDIT_ROW; r++) scr[(unsigned int)r * LS] = (unsigned char)(8 + jitter);
        snow(jitter);
        credits_step();
        tune_update();
        fade = f < FADE_FRAMES ? (unsigned char)(f >> 1)
             : f >= frames ? (unsigned char)((frames + FADE_FRAMES - 1 - f) >> 1) : 16;
        palette();
        t++;
        k = key();
        if (k == ' ') shake();
        else if (k == 'n' || k == 'N') frames = f + 1;
        if (f + 1 == frames) tune_fade(FADE_FRAMES, 0);
        while (raster() >= 251) {}
    }
}
