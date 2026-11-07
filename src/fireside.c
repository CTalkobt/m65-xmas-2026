/* fireside.c — scene 5, the fireside. A code overlay (main.c calls
 * fireside()).
 *
 * The picture (tools/gen_fire.py, fire.h): a hearth, close to. 40 cells a
 * row, no more: nothing moves over it but the palette and the fire.
 *
 * THE FIRE: a buffer of FIRE_W x FIRE_H pixels in the work area, laid out
 * as the fire's characters are (gen_fire.py: down the columns), so a column
 * of cells is one run of memory, 8 pixels wide: pixel (x, y) is byte
 * (x >> 3) * STRIP + y * 8 + (x & 7). A pixel is the palette entry P_FIRE +
 * its heat (0-63). A frame:
 *   the bottom row: heat, at random (the logs' coals, now and then dark)
 *   every row above it, from the top down: the mean of the three pixels
 *   below it and the one two below, a little cooler (at random): the heat
 *   rises, spreads and dies away: flames
 *   the buffer to the characters: one DMA
 * Done in the bottom border (the fire's rows are low on the screen: it has
 * till the beam gets there).
 *
 * The palette: the room lit by the fire (its level wavering with the
 * fire's, a step at a time), the garland's lights twinkling, all of it
 * times the fade.
 *
 * The music: Once in Royal David's City (tune royal).
 */
#pragma cc45 overlay(fireside)
#include <dma.h>
#include <unpack.h>
#include <audio_tune.h>
#include "vic.h"
#include "data.h"
#include "fire.h"
#include "music.h"
#include "scenes.h"

#define STRIP      (FIRE_H * 8)                  /* bytes a column of the fire's cells */
#define FIRE_BYTES (FIRE_COLS * STRIP)

#define scr screen_ram
#define fire scene_ram                           /* the fire's buffer */
#define fr (*(struct fire_tables *)(scene_ram + FIRE_BYTES))   /* from FIRE (fire.h) */
_Static_assert(FIRE_BYTES + sizeof(struct fire_tables) <= SCENE_RAM, "the fire and its tables in scene_ram");

static unsigned char rtab[256];                  /* random bytes, for the fire's inner loop */
static unsigned char ri;
static unsigned int t;
static unsigned char fade, room, room_to;
static unsigned char glow[4];
unsigned int fire_done;                          /* the raster line the fire was done at, at worst */

/* ---- the fire ---- */

static void fire_step(void) {
    unsigned char c, x, y, *p, *b, *l, *r, *b2;
    unsigned int s;
    p = fire + (FIRE_H - 1) * 8;                  /* the coals */
    for (c = 0; c < FIRE_COLS; c++, p += STRIP)
        for (x = 0; x < 8; x += 4) {              /* the coals in fours: tongues of flame */
            s = rtab[ri++];
            s = s & 1 ? 52 + (s >> 5) : (s & 6 ? 30 : 4);
            p[x] = p[x + 1] = p[x + 2] = p[x + 3] = (unsigned char)(P_FIRE + s);
        }
    for (c = 0; c < FIRE_COLS; c++) {
        p = fire + (unsigned int)c * STRIP;
        for (y = 0; y < FIRE_H - 1; y++, p += 8) {
            b = p + 8;
            b2 = y < FIRE_H - 2 ? b + 8 : b;
            for (x = 0; x < 8; x++) {
                l = x ? b + x - 1 : (c ? b - STRIP + 7 : b);
                r = x < 7 ? b + x + 1 : (c < FIRE_COLS - 1 ? b + STRIP - 7 : b + 7);
                s = (unsigned int)*l + b[x] + *r + b2[x] - 4 * P_FIRE;
                s >>= 2;
                s = s > 1 ? s - 1 - !(rtab[ri++] & 3) : 0;  /* cooling: flames, not a wall */
                p[x] = (unsigned char)(P_FIRE + s);
            }
        }
    }
    dma_copy_far(CHR_LIN + (unsigned long)(FIRE_CHAR - CH0) * 64, (unsigned long)(unsigned int)fire, FIRE_BYTES);
}

/* ---- the palette ---- */

static void palette(void) {
    unsigned char i, g, j, l;
    unsigned int v[3];
    const unsigned char *c;
    if (!(t & 3)) room_to = 200 + (rnd() & 55);   /* the fire's light */
    if (room < room_to) room += 3;
    else if (room > room_to + 2) room -= 3;
    for (j = 0; j < 4; j++)
        if (!(rnd() & 15)) glow[j] = glow[j] > 128 ? 60 : 255;
    for (i = 1; i < FIRE_COLOURS; i++) {
        g = fr.group[i];
        c = fr.pal[i];
        l = g == G_FIRE ? 255 : g >= G_LIGHT ? glow[g - G_LIGHT] : room;
        for (j = 0; j < 3; j++) v[j] = ((((unsigned int)c[j] * l) >> 8) * fade) >> 4;
        pal_rgb(i, (unsigned char)v[0], (unsigned char)v[1], (unsigned char)v[2]);
    }
}

/* the scene for frames frames (N sooner), then a fade out */
void fireside(unsigned int frames) {
    unsigned char k;
    unsigned int f, i;
    dma_copy_far((unsigned long)(unsigned int)&fr, FIRE_LIN + FIRE_TABLES, FIRE_TABLES_SIZE);
    unpack(FIRE_LIN + FIRE_CHR_PCK);
    unpack_to(FIRE_LIN + FIRE_MAP_PCK, (unsigned long)(unsigned int)scr);
    dma_fill_far(COLOR_LIN, ROWS * COLS * 2, 0);
    for (i = 0; i < FIRE_BYTES; i++) fire[i] = P_FIRE;
    for (i = 0; i < 256; i++) rtab[i] = (unsigned char)rnd();
    room = room_to = 230;
    for (k = 0; k < 4; k++) glow[k] = 255;
    vic_on(scr, COLS);
    t = 0;
    tune_volume(15);
    tune_play_far(MUSIC_LIN + TUNE_ROYAL_AT);
    for (f = 0; f < frames + FADE_FRAMES; f++) {
        while (raster() < 251) {}                 /* the bottom border */
        fire_step();
        i = raster();
        if (i < 251 && i > fire_done) fire_done = i;      /* into the next frame */
        tune_update();
        fade = f < FADE_FRAMES ? (unsigned char)(f >> 1)
             : f >= frames ? (unsigned char)((frames + FADE_FRAMES - 1 - f) >> 1) : 16;
        palette();
        t++;
        ri += 37;                                  /* the table read from elsewhere next time */
        k = key();
        if (k == 'n' || k == 'N') frames = f + 1;
        if (f + 1 == frames) tune_fade(FADE_FRAMES, 0);
        while (raster() >= 251) {}
    }
}
