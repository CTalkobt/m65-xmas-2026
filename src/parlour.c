/* parlour.c — scene 2: the tree. A code overlay (main.c calls parlour()).
 *
 * A parlour on Christmas Eve (tools/gen_tree.py): the tree in the middle,
 * the fire to its right, the snowy night through the window. The picture
 * is 1,000 full-colour cells, unpacked once; everything that happens after
 * is the palette. Each entry is in a group (tree.h); a frame sets each
 * group's level (0-256: the colour scaled) and white (0-255: the colour
 * taken toward white, a flash), and the whole palette is written from
 * them and the fade.
 *
 * The sequence (frames, 50 a second):
 *     0  the room fades in by the fire's light; the tree a silhouette
 *    64  the tiers light up in turn, from the bottom: the tree draws itself
 *   304  the tinsel shines
 *   344  the baubles, a colour at a time, each with a flash
 *   440  the fairy lights come on: chasing, twinkling, breathing in turn
 *   480  the star flares, then twinkles
 * The fire burns all along: its five flame bands' colours go round.
 *
 * Snow falls outside the window: WIN_FLAKES flakes, in RRB slots after
 * each row's 40 cells (SLOTS a row, GOTOX and a glyph, as the village's),
 * set afresh each frame in the vertical blank from a table (so few, it
 * needs no more). Two depths:
 *   far   dim and slow, over the houses across the way: it shows only
 *         where the window is glass with the sky behind (pt.glass), so it
 *         goes behind their roofs, the window's bars and the curtains
 *   near  bright and faster, just outside the glass: it shows wherever the
 *         window shows the world outside (pt.pane: in front of the roofs,
 *         behind the bars and curtains), and settles on the outside sill.
 *         sill[] is the snow's top in each of the window's columns: a near
 *         flake that reaches it slides down to a neighbour
 *         2 or more lower, if any (a few steps: a drift, not a column; half
 *         of them melt, so it builds slowly), then rests: a pixel plotted
 *         into the cell under it (DMA, one byte), sill[] a pixel higher.
 *         SILL_MAX pixels at most, then flakes melt there.
 *
 * The music: O Tannenbaum (tools/gen_music.py), on SIDs 1-2 and mirrored
 * on 3-4: tune_update once a frame.
 *
 * Keys: SPACE  the sequence (and the music) again.
 */
#pragma cc45 overlay(parlour)
#include <dma.h>
#include <unpack.h>
#include <audio_sid.h>
#include <audio_tune.h>
#include "vic.h"
#include "data.h"
#include "parlour.h"
#include "music.h"
#include "scenes.h"

#define SILHOUETTE 36                       /* a group's level before it is lit */

#define T_TIERS    64
#define T_TIER     40                       /* frames a tier */
#define T_TINSEL   (T_TIERS + TIERS * T_TIER)
#define T_BAUBLES  (T_TINSEL + 40)
#define T_LIGHTS   (T_BAUBLES + 96)
#define T_STAR     (T_LIGHTS + 40)

#define SLOTS      6                        /* window flakes a text row */
#define CELLS      (COLS + SLOTS * 2 + 1)      /* + the end: GOTOX 320 */
#define LS         (CELLS * 2)
#define DEAD       360                         /* past the right edge */
#define CH_FLAKE   (CH0 + 0x400)               /* after the scene: dim, blank, bright, blank */
#define WIN_FLAKES 40
#define WIN_R0     (WIN_Y0 / 8)
#define WIN_R1     ((WIN_Y0 + WIN_H - 1) / 8)

#define scr screen_ram                       /* the screen RAM (bank 0, vic.c) */
_Static_assert(CELLS <= SCREEN_CELLS, "the parlour's rows in screen_ram");
#define pt (*(struct parlour_tables *)scene_ram)   /* from PARLOUR (parlour.h), in the work area */
_Static_assert(sizeof(struct parlour_tables) <= SCENE_RAM, "the parlour's tables in scene_ram");
static unsigned char fade_max = 16;         /* the fade out: the most fade may be */
static unsigned char fx[WIN_FLAKES], fy[WIN_FLAKES], fl[WIN_FLAKES];   /* in the window; depth */
static unsigned char used[ROWS];
static unsigned char sill[WIN_W];           /* the snow's top on the sill, from WIN_Y0 */
#define SILL_MAX   6
static unsigned int lvl[NGROUPS];           /* 0-256 */
static unsigned char wht[NGROUPS];          /* 0-255 */
static unsigned char fade;                  /* 0-16 */
static unsigned int t;
static unsigned char chan[CHANNELS];        /* a light channel's level now */
static unsigned char fire_entry[5];         /* the entry of each flame band */

/* 0 before start, 256 from start + len on, a ramp between */
static unsigned int ramp(unsigned int start, unsigned int len) {
    if (t < start) return 0;
    if (t >= start + len) return 256;
    return (unsigned int)(((unsigned long)(t - start) << 8) / len);
}

static unsigned int lit(unsigned int r) {   /* the silhouette to full */
    return SILHOUETTE + (((256 - SILHOUETTE) * r) >> 8);
}

/* ---- the groups, a frame ---- */

static void lights(void) {
    unsigned char c, target, mode = (unsigned char)((t - T_LIGHTS) / 400 % 3);
    unsigned int on = ramp(T_LIGHTS, 30);
    for (c = 0; c < CHANNELS; c++) {
        if (mode == 0)                          /* a chase */
            target = (((t >> 3) - c) & 7) < 3 ? 255 : 50;
        else if (mode == 1)                     /* twinkling */
            target = (rnd() & 31) == 0 ? 255 : (chan[c] > 60 ? chan[c] - 6 : 60);
        else {                                  /* breathing, all together */
            unsigned char p = (unsigned char)(t * 2);
            target = (unsigned char)(150 + ((p < 128 ? p : 255 - p) * 105 >> 7));
        }
        if (mode == 1) chan[c] = target;
        else if (chan[c] < target) chan[c] = chan[c] + 16 > target ? target : chan[c] + 16;
        else if (chan[c] > target) chan[c] = chan[c] < target + 12 ? target : chan[c] - 12;
        lvl[G_LIGHT + c] = t < T_LIGHTS ? SILHOUETTE : SILHOUETTE + (((unsigned int)chan[c] * on) >> 8);
    }
}

static void groups(void) {
    unsigned char i;
    unsigned int r;
    fade = t < 64 ? (unsigned char)(t >> 2) : 16;
    if (fade > fade_max) fade = fade_max;
    lvl[G_ROOM] = 232 + (rnd() & 15) + (rnd() & 7);   /* the fire's light wavers */
    for (i = 0; i < TIERS; i++)
        lvl[G_TIER + i] = lit(ramp(T_TIERS + i * T_TIER, T_TIER));
    r = ramp(T_TINSEL, 40);
    lvl[G_TINSEL] = lit(r);
    wht[G_TINSEL] = t >= T_TINSEL + 40 && (rnd() & 7) == 0 ? 90 : 0;   /* glints */
    for (i = 0; i < 4; i++) {
        unsigned int at = T_BAUBLES + i * 20;
        lvl[G_BAUBLE + i] = t < at ? SILHOUETTE : 256;
        wht[G_BAUBLE + i] = t < at || t >= at + 16 ? 0 : (unsigned char)(255 - (t - at) * 16);
    }
    lights();
    if (t < T_STAR) {
        lvl[G_STAR] = SILHOUETTE;
        wht[G_STAR] = 0;
    } else {
        lvl[G_STAR] = 256;
        r = t - T_STAR;                         /* a flare, then a twinkle */
        wht[G_STAR] = r < 64 ? (unsigned char)(255 - r * 3) : ((rnd() & 15) == 0 ? 120 : 40);
    }
    for (i = 0; i < 5; i++) {                   /* the flames: a little brighter, a little less */
        lvl[G_FIRE + i] = 192 + (rnd() & 63);
        wht[G_FIRE + i] = 0;
    }
}

/* every entry from its group; the fire's bands take each other's colours */
static void palette(void) {
    unsigned char i, g, k;
    const unsigned char *c;
    unsigned int l, v[3];
    unsigned char w, j, shift = (unsigned char)((t >> 2) % 5);
    for (i = 1; i < TREE_COLOURS; i++) {
        g = pt.group[i];
        c = pt.pal[i];
        if (g >= G_FIRE) {
            k = g - G_FIRE + shift;
            if (k >= 5) k -= 5;
            c = pt.pal[fire_entry[k]];
        }
        l = lvl[g];
        if (l > 256) l = 256;                   /* 255 * 256 still fits 16 bits */
        w = wht[g];
        for (j = 0; j < 3; j++) {
            v[j] = (c[j] * l) >> 8;
            v[j] += ((255 - v[j]) * w) >> 8;
            v[j] = (v[j] * fade) >> 4;
        }
        pal_rgb(i, (unsigned char)v[0], (unsigned char)v[1], (unsigned char)v[2]);
    }
}

/* ---- the screen ---- */

static void screen_init(void) {
    static unsigned char crow[LS];
    static unsigned char glyph[64];
    unsigned char r, k;
    unsigned int i, ch;
    unsigned char *p;
    for (r = 0; r < ROWS; r++) {
        p = scr + (unsigned int)r * LS;
        for (k = 0; k < COLS; k++) {
            ch = CH0 + r * COLS + k;
            p[k * 2] = (unsigned char)ch;
            p[k * 2 + 1] = (unsigned char)(ch >> 8);
        }
        for (k = 0; k < SLOTS; k++) {
            p[(COLS + k * 2) * 2] = (unsigned char)DEAD;
            p[(COLS + k * 2) * 2 + 1] = (unsigned char)(DEAD >> 8);
            p[(COLS + k * 2) * 2 + 2] = (unsigned char)CH_FLAKE;
            p[(COLS + k * 2) * 2 + 3] = (unsigned char)(CH_FLAKE >> 8);
        }
        p[(CELLS - 1) * 2] = (unsigned char)W;
        p[(CELLS - 1) * 2 + 1] = (unsigned char)(W >> 8);
    }
    for (i = 0; i < LS; i++) crow[i] = 0;
    for (k = 0; k < SLOTS; k++) crow[(COLS + k * 2) * 2] = 0x90;    /* GOTOX, transparent */
    crow[(CELLS - 1) * 2] = 0x90;
    for (r = 0; r < ROWS; r++)
        dma_copy_far(COLOR_LIN + (unsigned long)r * LS, (unsigned long)(unsigned int)crow, LS);
    /* the flake glyphs: a dot on the last row (the GOTOX's Y offset moves
     * it up), each followed by a blank one for the rows read past it */
    for (k = 0; k < 4; k++) {
        dma_fill((void *)glyph, 64, 0);
        if (k == 0) glyph[56] = tree_white_dim;
        if (k == 2) glyph[56] = tree_white;
        dma_copy_far(CHR_LIN + (unsigned long)(0x400 + k) * 64, (unsigned long)(unsigned int)glyph, 64);
    }
}

/* ---- the snow outside ---- */

static void flakes_init(void) {
    unsigned char i;
    for (i = 0; i < WIN_W; i++) sill[i] = WIN_SILL;
    for (i = 0; i < WIN_FLAKES; i++) {
        fx[i] = (unsigned char)(rnd() % WIN_W);
        fy[i] = (unsigned char)(rnd() % WIN_H);
        fl[i] = i & 1;
    }
}

static unsigned char glass(unsigned char x, unsigned char y) {
    return pt.glass[y][x >> 3] & (0x80 >> (x & 7));
}

static unsigned char pane(unsigned char x, unsigned char y) {
    return pt.pane[y][x >> 3] & (0x80 >> (x & 7));
}

/* a near flake at window column x comes to rest on the sill's snow */
static void settle(unsigned char x) {
    unsigned char i, y;
    signed char d = (rnd() & 1) ? 1 : -1;
    if (rnd() & 1) return;                              /* half of them melt */
    for (i = 0; i < 4; i++) {                           /* down a step of 2 or more */
        if ((unsigned char)(x + d) < WIN_W && sill[x + d] > sill[x] + 1) x += d;
        else if ((unsigned char)(x - d) < WIN_W && sill[x - d] > sill[x] + 1) x -= d;
        else break;
    }
    if (sill[x] <= WIN_SILL - SILL_MAX) return;       /* deep enough: it melts */
    y = --sill[x];
    if (!pane(x, y)) return;                            /* behind the bar */
    x += WIN_X0;
    y += WIN_Y0;
    dma_fill_far(CHR_LIN + ((unsigned long)(y >> 3) * COLS + (x >> 3)) * 64 + (y & 7) * 8 + (x & 7),
                 1, tree_white);
}

/* in the vertical blank: every window row's slots off, then each flake on */
static void flakes(void) {
    unsigned char i, r, k, ay, *q;
    unsigned int x;
    for (r = WIN_R0; r <= WIN_R1; r++) {
        used[r] = 0;
        q = scr + (unsigned int)r * LS + COLS * 2;
        for (k = 0; k < SLOTS; k++, q += 4) {
            q[0] = (unsigned char)DEAD;
            q[1] = (unsigned char)(DEAD >> 8);
        }
    }
    for (i = 0; i < WIN_FLAKES; i++) {
        if (fl[i] || !(t & 1)) fy[i]++;         /* near: a pixel a frame; far: every other */
        if ((rnd() & 15) == 0) fx[i] = fx[i] == 0 ? WIN_W - 1 : fx[i] - 1;
        else if ((rnd() & 15) == 0) fx[i] = fx[i] == WIN_W - 1 ? 0 : fx[i] + 1;
        if (fl[i] && fy[i] + 1 >= sill[fx[i]]) {        /* near: on the sill */
            settle(fx[i]);
            fy[i] = WIN_H;
        }
        if (fy[i] >= WIN_H) {
            fy[i] = 0;
            fx[i] = (unsigned char)(rnd() % WIN_W);
        }
        if (fl[i] ? !pane(fx[i], fy[i]) : !glass(fx[i], fy[i])) continue;
        ay = WIN_Y0 + fy[i];
        r = ay >> 3;
        if (used[r] == SLOTS) continue;
        q = scr + (unsigned int)r * LS + (COLS + used[r]++ * 2) * 2;
        x = WIN_X0 + fx[i];
        q[0] = (unsigned char)x;
        q[1] = (unsigned char)(x >> 8) | (unsigned char)((7 - (ay & 7)) << 5);
        q[2] = (unsigned char)(CH_FLAKE + fl[i] * 2);
    }
}

static void begin(void) {
    unsigned char i;
    t = 0;
    tune_play_far(MUSIC_LIN + TUNE_TANNENBAUM_AT);
    for (i = 0; i < CHANNELS; i++) chan[i] = 0;
    for (i = 0; i < NGROUPS; i++) {
        lvl[i] = 256;
        wht[i] = 0;
    }
}

/* the scene for frames frames (N sooner), then a fade out */
void parlour(unsigned int frames) {
    unsigned char i, k;
    unsigned int f;
    dma_copy_far((unsigned long)(unsigned int)scene_ram, PARLOUR_LIN + PARLOUR_TABLES, PARLOUR_TABLES_SIZE);
    unpack(PARLOUR_LIN + PARLOUR_TREE_PCK);
    for (i = 1; i < TREE_COLOURS; i++)
        if (pt.group[i] >= G_FIRE) fire_entry[pt.group[i] - G_FIRE] = i;
    screen_init();
    flakes_init();
    vic_on(scr, CELLS);
    fade_max = 16;
    tune_volume(15);
    begin();
    for (f = 0; f < frames + FADE_FRAMES; f++) {
        while (raster() < 251) {}               /* the bottom border */
        flakes();
        tune_update();
        if (f >= frames) fade_max = (unsigned char)((frames + FADE_FRAMES - 1 - f) >> 1);
        groups();
        palette();
        t++;
        k = key();
        if (k == ' ') begin();
        else if (k == 'n' || k == 'N') frames = f + 1;
        if (f + 1 == frames) tune_fade(FADE_FRAMES, 0);
        while (raster() >= 251) {}
    }
}
