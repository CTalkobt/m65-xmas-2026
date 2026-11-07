/* sleigh.c — scene 3, the sleigh ride. A code overlay (main.c calls
 * sleigh()).
 *
 * The VIC-IV at 320 x 200, 16-bit full-colour characters
 * (tools/gen_sleigh.py: sleigh.h). Every row is
 *   cell 0        GOTOX x0: the row's fine scroll (8 - the band's x & 7;
 *                 8 for the sky)
 *   cells 1-41    the row's window of its map, 41 cells from the band's
 *                 x >> 3 (DMA from the maps, unpacked into bank 1, when the
 *                 band moves a whole cell)
 *   cell 42       GOTOX, transparent: the text's fine scroll (row TEXT_ROW;
 *                 the others' at 320, off the screen)
 *   cells 43-83   the text: the greetings scroller's letters (the font,
 *                 clear around them, over the snow)
 *   cells 84-87   GOTOX 0, a black cell, GOTOX 312, a black cell: the
 *                 plane's first and last 8 pixels covered (where the scrolls
 *                 start and end), and the row ends at the right edge
 * The sky (rows 0-8) stands still; the three bands of hills scroll at
 * their own speeds (parallax), in the vertical blank.
 *
 * The team: hardware sprites, 16 colours (their own palette, bank 2): the
 * sleigh in two, four reindeer ahead of it, galloping (four frames, each
 * one out of step), the leader's nose red. They fly one path, a wave, the
 * reindeer ahead along it: the wave runs down the line. Across the sky,
 * past the moon, then a rest, then round again.
 *
 * Behind the sleigh two more sprites twinkle: a trail of sparkles. Before
 * the moon the team is in silhouette. A 16-colour sprite's pixel is the
 * sprite palette's entry sprite * 16 + its value, and 128 more when the
 * sprite's bit of SPRBPMEN ($D049 and $D04B, their high nibbles) is set:
 * entries 128-255 are all dark, and a sprite over the moon gets its bit.
 * (Its colour register, $D027 + n, is the value that is transparent: 0.)
 *
 * The greetings: a line of text along the bottom, over the snow, a pixel a
 * frame. When it has moved a whole cell its cells move along by one (DMA,
 * in bank 0) and the next letter comes in at the right.
 *
 * The music: Ding Dong Merrily on High (tune dingdong), sleigh bells on.
 */
#pragma cc45 overlay(sleigh)
#include <dma.h>
#include <unpack.h>
#include <audio_tune.h>
#include "vic.h"
#include "data.h"
#include "sleigh.h"
#include "music.h"
#include "scenes.h"

#define TEXT       (1 + MAPW)                    /* the text's GOTOX */
#define TEXT_CELLS MAPW
#define EDGE       (TEXT + 1 + TEXT_CELLS)
#define CELLS      (EDGE + 4)
#define LS         (CELLS * 2)
#define TEXT_ROW   23
#define MOON_X     82                            /* the moon on the screen (the sky is 8 to the right) */
#define MOON_Y     30
#define MOON_R     17
#define MAP_LIN    SCRATCH_LIN                   /* the maps, unpacked (bank 1) */
#define SPR_X0     24                            /* sprite x of screen pixel 0 */
#define TEAM       6                             /* sprites: the sleigh (2), four reindeer */
#define SPARKS     2                             /* and two sparkles */

static const char __noescape greetings[] =     /* kept with the code, in the overlay */
    "     merry christmas from midwinter, a christmas demo for the mega65 ...   "
    "snow on the roofs, a tree in the parlour, and santa over the hills tonight ...   "
    "season's greetings to all mega65 owners, coders, artists and musicians, "
    "and to everyone who keeps the 8-bit fires burning!   * * *   "
    "a happy new year to you all!          ";

#define scr screen_ram
_Static_assert(CELLS <= SCREEN_CELLS, "the sleigh's rows in screen_ram");
_Static_assert(MAP_BYTES <= SCRATCH_SIZE, "the maps in the scratch area");

#define st (*(struct sleigh_tables *)scene_ram)    /* from SLEIGH (sleigh.h), in the work area */
_Static_assert(sizeof(struct sleigh_tables) <= SCENE_RAM, "the sleigh's tables in scene_ram");
static unsigned int band_px[NBANDS];             /* the scroll, 0 .. period * 8 - 1 */
static unsigned char band_frac[NBANDS];
static unsigned char spr_top;
static unsigned char silhouette;                 /* the sprites over the moon, a bit each */
static unsigned char text_x;                     /* 0-7: the text's fine scroll */
static unsigned int text_at;                     /* the next letter of greetings */
static unsigned int t;
_Alignas(16) static unsigned int spr_ptr[8];

static unsigned int word(const unsigned char *p) {
    return p[0] | (unsigned int)p[1] << 8;
}

/* ---- the screen ---- */

static void row_from(unsigned char row, unsigned long src) {
    dma_copy_far((unsigned long)(unsigned int)(scr + (unsigned int)row * LS + 2), src, MAPW * 2);
}

static void band_copy(unsigned char b) {
    unsigned char r;
    unsigned int stride = word(st.band_stride[b]);
    unsigned long src = MAP_LIN + word(st.band_map[b]) + (band_px[b] >> 3) * 2;
    for (r = 0; r < st.band_rows[b]; r++, src += stride)
        row_from(st.band_row[b] + r, src);
}

static void set_fine(unsigned char b) {
    unsigned char r, x = (unsigned char)(8 - (band_px[b] & 7));
    for (r = 0; r < st.band_rows[b]; r++)
        scr[(unsigned int)(st.band_row[b] + r) * LS] = x;
}

static void screen_init(void) {
    static unsigned char crow[LS];
    unsigned char r, b, *p;
    unsigned int i;
    for (r = 0; r < ROWS; r++) {
        p = scr + (unsigned int)r * LS;
        p[0] = 8;                                 /* GOTOX 8 */
        p[1] = 0;
        p[TEXT * 2] = (unsigned char)320;         /* the text off the screen */
        p[TEXT * 2 + 1] = (unsigned char)(320 >> 8);
        for (b = 0; b < TEXT_CELLS; b++) {
            p[(TEXT + 1 + b) * 2] = (unsigned char)CH_FONT;     /* a space: clear */
            p[(TEXT + 1 + b) * 2 + 1] = (unsigned char)(CH_FONT >> 8);
        }
        p[EDGE * 2] = 0;                          /* GOTOX 0, black */
        p[EDGE * 2 + 1] = 0;
        p[EDGE * 2 + 2] = (unsigned char)CH_BLACK;
        p[EDGE * 2 + 3] = (unsigned char)(CH_BLACK >> 8);
        p[EDGE * 2 + 4] = (unsigned char)312;     /* GOTOX 312, black */
        p[EDGE * 2 + 5] = (unsigned char)(312 >> 8);
        p[EDGE * 2 + 6] = (unsigned char)CH_BLACK;
        p[EDGE * 2 + 7] = (unsigned char)(CH_BLACK >> 8);
    }
    for (r = 0; r < SKY_ROWS; r++)
        row_from(r, MAP_LIN + (unsigned int)r * MAPW * 2);
    for (b = 0; b < NBANDS; b++) {
        band_px[b] = 0;
        band_frac[b] = 0;
        band_copy(b);
    }
    for (i = 0; i < LS; i++) crow[i] = 0;
    crow[0] = 0x10;                               /* the GOTOX cells */
    crow[TEXT * 2] = 0x90;                        /* the text's: transparent */
    crow[EDGE * 2] = 0x10;
    crow[EDGE * 2 + 4] = 0x10;
    for (r = 0; r < ROWS; r++)
        dma_copy_far(COLOR_LIN + (unsigned long)r * LS, (unsigned long)(unsigned int)crow, LS);
}

/* the bands on by their speeds; a band's rows copied again when it moves a cell */
static void scroll(void) {
    unsigned char b;
    unsigned int old, step, period;
    for (b = 0; b < NBANDS; b++) {
        step = word(st.band_speed[b]);
        old = band_px[b];
        band_frac[b] += (unsigned char)step;
        band_px[b] += (step >> 8) + ((unsigned char)step > band_frac[b] ? 1 : 0);
        period = st.band_cells[b] * 8;
        if (band_px[b] >= period) band_px[b] -= period;
        if ((band_px[b] >> 3) != (old >> 3)) band_copy(b);
        set_fine(b);
    }
}

/* ---- the greetings ---- */

static unsigned int glyph(unsigned char c) {
    if (c >= 0xC1 && c <= 0xDA) c -= 0x80;        /* PETSCII shifted letters: as ASCII's */
    return CH_FONT + st.text_map[c & 0x7F];
}

static void text(void) {
    unsigned char *row = scr + (unsigned int)TEXT_ROW * LS;
    unsigned int ch;
    if (++text_x == 8) {                          /* a whole cell: along by one */
        text_x = 0;
        dma_copy(row + (TEXT + 1) * 2, row + (TEXT + 2) * 2, (TEXT_CELLS - 1) * 2);
        ch = glyph((unsigned char)greetings[text_at]);
        if (!greetings[++text_at]) text_at = 0;
        row[(TEXT + TEXT_CELLS) * 2] = (unsigned char)ch;
        row[(TEXT + TEXT_CELLS) * 2 + 1] = (unsigned char)(ch >> 8);
    }
    row[TEXT * 2] = (unsigned char)(8 - text_x);
    row[TEXT * 2 + 1] = 0;
}

/* ---- the team ---- */

static const unsigned char bit[8] = {1, 2, 4, 8, 16, 32, 64, 128};
static const signed char wave[32] = {
    0, 2, 4, 6, 7, 9, 10, 11, 12, 11, 10, 9, 7, 6, 4, 2,
    0, -2, -4, -6, -7, -9, -10, -11, -12, -11, -10, -9, -7, -6, -4, -2};

static void spr_put(unsigned char n, signed int x, signed int y, unsigned int img) {
    unsigned char b = bit[n];
    unsigned int px, py;
    signed int dx, dy;
    if (x <= -16 || x >= 320) {
        REG(0xD015) &= (unsigned char)~b;
        return;
    }
    dx = x + 8 - MOON_X;                          /* over the moon: a silhouette */
    dy = y + 10 - MOON_Y;
    if (dx > -MOON_R - 6 && dx < MOON_R + 6 && dy > -MOON_R - 6 && dy < MOON_R + 6
        && dx * dx + dy * dy < (MOON_R + 6) * (MOON_R + 6))
        silhouette |= b;
    px = (unsigned int)(x + SPR_X0);
    py = (unsigned int)((y + spr_top) * 2);       /* V400: physical lines */
    REG(0xD000 + n * 2) = (unsigned char)px;
    REG(0xD001 + n * 2) = (unsigned char)py;
    if (px & 0x100) REG(0xD010) |= b; else REG(0xD010) &= (unsigned char)~b;
    if (py & 0x100) REG(0xD077) |= b; else REG(0xD077) &= (unsigned char)~b;
    spr_ptr[n] = img;
    REG(0xD015) |= b;
}

/* the path: a wave across the sky, y at x */
static signed int path_y(signed int x) {
    return 22 + wave[((unsigned int)(x + 512) >> 3) & 31];      /* across the moon */
}

#define LAP 520                                   /* frames from one crossing to the next */

static void team(void) {
    unsigned int lap = t % LAP;
    signed int x = (signed int)lap * 3 / 2 - 110;   /* the sleigh's left */
    unsigned char i;
    signed int dx;
    silhouette = 0;
    spr_put(0, x, path_y(x + 16), SPR_SLEIGH);           /* the sleigh's halves: one height */
    spr_put(1, x + 16, path_y(x + 16), SPR_SLEIGH + SPR_STEP);
    for (i = 0; i < 4; i++) {
        dx = x + 34 + i * 18;
        spr_put(2 + i, dx, path_y(dx) - 4,
                (i == 3 ? SPR_DEER : SPR_DEER2) + ((t >> 2) + i * 3 & 3) * SPR_STEP);
    }
    for (i = 0; i < SPARKS; i++) {               /* the sparkles: behind, lower, twinkling */
        dx = x - 12 - i * 18 - (signed int)((t >> 1) & 7);
        spr_put(TEAM + i, dx, path_y(dx) + 6 + i * 3, SPR_SPARK + ((t >> 2) + i * 2 & 3) * SPR_STEP);
    }
    if (silhouette & 3) silhouette |= 3;          /* the sleigh's halves together */
    REG(0xD049) = (REG(0xD049) & 0x0F) | (unsigned char)(silhouette << 4);    /* SPRBPMEN 0-3 */
    REG(0xD04B) = (REG(0xD04B) & 0x0F) | (silhouette & 0xF0);                 /* SPRBPMEN 4-7 */
}

static void sprites_on(void) {
    unsigned char s;
    unsigned int i;
    for (s = 0; s < 8; s++) REG(0xD027 + s) = 0;
    REG(0xD06C) = (unsigned char)(unsigned int)spr_ptr;
    REG(0xD06D) = (unsigned char)((unsigned int)spr_ptr >> 8);
    REG(0xD06E) = 0x80;                           /* 16-bit pointers */
    REG(0xD06B) = 0xFF;                           /* 16 colours */
    REG(0xD057) = 0xFF;                           /* 16 pixels: 8 bytes a row */
    REG(0xD055) = 0;                              /* 21 rows */
    REG(0xD076) = 0xFF;                           /* Y in physical lines */
    REG(0xD017) = 0xFF;                           /* each row doubled */
    REG(0xD01D) = 0;
    REG(0xD01B) = 0;                              /* in front of the characters */
    REG(0xD05F) = 0;
    REG(0xD077) = 0;
    REG(0xD010) = 0;
    REG(0xD015) = 0;
    for (i = 0; i < 8; i++) spr_ptr[i] = SPR_SLEIGH;
}

static void sprites_off(void) {
    REG(0xD015) = 0;
    REG(0xD049) &= 0x0F;
    REG(0xD04B) &= 0x0F;
    REG(0xD070) = 0;
}

/* ---- the palettes, at level 0-16 ---- */

static void palette_at(unsigned char level) {
    unsigned int i;
    for (i = 0; i < SLEIGH_COLOURS; i++)
        pal_rgb((unsigned char)i, (unsigned char)((st.pal[i][0] * level) >> 4),
                (unsigned char)((st.pal[i][1] * level) >> 4), (unsigned char)((st.pal[i][2] * level) >> 4));
    REG(0xD070) = 0x80 | 0x08;                    /* edit bank 2, the sprites' (and shown) */
    for (i = 0; i < 256; i++)
        if (i & 0x80)                             /* SPRBPMEN's: the silhouette's */
            pal_rgb((unsigned char)i, (unsigned char)(6 * level >> 4), (unsigned char)(6 * level >> 4),
                    (unsigned char)(16 * level >> 4));
        else
            pal_rgb((unsigned char)i, (unsigned char)((st.spal[i & 15][0] * level) >> 4),
                    (unsigned char)((st.spal[i & 15][1] * level) >> 4),
                    (unsigned char)((st.spal[i & 15][2] * level) >> 4));
    REG(0xD070) = 0x08;                           /* edit bank 0 again; sprites from bank 2 */
}

/* the scene for frames frames (N sooner), then a fade out */
void sleigh(unsigned int frames) {
    unsigned char k;
    unsigned int f;
    dma_copy_far((unsigned long)(unsigned int)scene_ram, SLEIGH_LIN + SLEIGH_TABLES, SLEIGH_TABLES_SIZE);
    unpack(SLEIGH_LIN + SLEIGH_CHR_PCK);
    unpack_to(SLEIGH_LIN + SLEIGH_MAP_PCK, MAP_LIN);
    unpack(SLEIGH_LIN + SLEIGH_SPR_PCK);
    screen_init();
    spr_top = vic_on(scr, CELLS);
    sprites_on();
    t = 0;
    text_x = 0;
    text_at = 0;
    tune_volume(15);
    tune_play_far(MUSIC_LIN + TUNE_DINGDONG_AT);
    for (f = 0; f < frames + FADE_FRAMES; f++) {
        while (raster() < 251) {}                 /* the bottom border */
        scroll();
        text();
        team();
        tune_update();
        if (f < FADE_FRAMES) palette_at((unsigned char)(f >> 1));
        else if (f >= frames) palette_at((unsigned char)((frames + FADE_FRAMES - 1 - f) >> 1));
        t++;
        k = key();
        if (k == 'n' || k == 'N') frames = f + 1;
        if (f + 1 == frames) tune_fade(FADE_FRAMES, 0);
        while (raster() >= 251) {}
    }
    sprites_off();
}
