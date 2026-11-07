/* flakes.c — scene 4, the snowflakes. A code overlay (main.c calls
 * flakes()).
 *
 * The picture (tools/gen_flakes.py, flakes.h): an icy plasma round a dark
 * disc with a Koch snowflake in it. Every row is its 40 cells, then SLOTS
 * object slots (a transparent GOTOX and two characters: a falling flake's
 * columns), then GOTOX 320 (the end).
 *
 * Everything else is the palette, written whole each frame:
 *   the plasma   its 64 entries turned round a step a frame: it flows
 *   the snowflake  level L's four shades go from the disc's colour to
 *                its own over REVEAL frames, at T_LEVELS + L * T_LEVEL:
 *                the snowflake grows from a triangle, an iteration at a
 *                time; then they shimmer, each level a little apart
 *   the rest     as drawn
 * all of it times the fade.
 *
 * The falling flakes: FLAKES crystals, 16 x 16, drifting down and turning
 * (four frames), set afresh in the slots each vertical blank from a table
 * (so few need no more). A flake at y covers the text rows y >> 3 to
 * (y + 15) >> 3: in each a slot, its strips from the character that row
 * starts at (8 + row * 8 - y: >> 3 the character, & 7 the GOTOX's Y offset;
 * as Witching Hour's objects).
 *
 * The music: Shchedryk (tune shchedryk), the tune of Carol of the Bells.
 */
#pragma cc45 overlay(flakes)
#include <dma.h>
#include <unpack.h>
#include <audio_tune.h>
#include "vic.h"
#include "data.h"
#include "flakes.h"
#include "music.h"
#include "scenes.h"

#define SLOTS      5
#define CELLS      (COLS + SLOTS * 3 + 1)
#define LS         (CELLS * 2)
#define END        (CELLS - 1)
#define DEAD       360
#define FLAKES     10
#define T_LEVELS   80
#define T_LEVEL    100
#define REVEAL     48

#define scr screen_ram
_Static_assert(CELLS <= SCREEN_CELLS, "the snowflakes' rows in screen_ram");
#define ft (*(struct flakes_tables *)scene_ram)  /* from FLAKES (flakes.h), in the work area */
_Static_assert(sizeof(struct flakes_tables) <= SCENE_RAM, "the snowflakes' tables in scene_ram");

static signed int fx[FLAKES], fy[FLAKES];
static unsigned char fspeed[FLAKES], fphase[FLAKES], fturn[FLAKES];
static unsigned char used[ROWS];
static unsigned int t;
static unsigned char fade;

/* ---- the screen ---- */

static void screen_init(void) {
    static unsigned char crow[LS];
    unsigned char r, k, *p;
    unsigned int i;
    for (r = 0; r < ROWS; r++) {
        p = scr + (unsigned int)r * LS;
        dma_copy_far((unsigned long)(unsigned int)p, SCRATCH_LIN + (unsigned int)r * COLS * 2, COLS * 2);
        for (k = 0; k < SLOTS; k++) {
            p[(COLS + k * 3) * 2] = (unsigned char)DEAD;
            p[(COLS + k * 3) * 2 + 1] = (unsigned char)(DEAD >> 8);
        }
        p[END * 2] = (unsigned char)W;
        p[END * 2 + 1] = (unsigned char)(W >> 8);
    }
    for (i = 0; i < LS; i++) crow[i] = 0;
    for (k = 0; k < SLOTS; k++) crow[(COLS + k * 3) * 2] = 0x90;     /* GOTOX, transparent */
    crow[END * 2] = 0x90;
    for (r = 0; r < ROWS; r++)
        dma_copy_far(COLOR_LIN + (unsigned long)r * LS, (unsigned long)(unsigned int)crow, LS);
}

/* ---- the falling flakes ---- */

static void flake_new(unsigned char i, signed int y) {
    fx[i] = (signed int)(rnd() % 296);
    fy[i] = y;
    fspeed[i] = 1 + (unsigned char)(rnd() & 1);
    fphase[i] = (unsigned char)rnd();
    fturn[i] = (unsigned char)(rnd() & 3);
}

static const signed char sway[16] = {0, 1, 1, 1, 0, 0, -1, -1, -1, -1, 0, 0, 1, 1, 0, 0};

static void flakes_move(void) {
    unsigned char i, r, k, *q;
    signed int row, last, s;
    unsigned int gx, ch;
    for (r = 0; r < ROWS; r++) {
        used[r] = 0;
        q = scr + (unsigned int)r * LS + COLS * 2;
        for (k = 0; k < SLOTS; k++, q += 6) {
            q[0] = (unsigned char)DEAD;
            q[1] = (unsigned char)(DEAD >> 8);
        }
    }
    for (i = 0; i < FLAKES; i++) {
        if ((t & 1) || fspeed[i] == 2) fy[i]++;
        if (!(t & 7)) fx[i] += sway[(fphase[i] + (t >> 3)) & 15];
        if (fy[i] >= H) flake_new(i, -16);
        if (fx[i] < 0 || fx[i] > 303) continue;
        ch = CH_STRIPS + (((t >> 3) + fturn[i]) & 3) * 8;          /* turning */
        gx = (unsigned int)fx[i];
        row = fy[i] < 0 ? 0 : fy[i] >> 3;
        last = (fy[i] + 15) >> 3;
        if (last >= ROWS) last = ROWS - 1;
        for (; row <= last; row++) {
            if (used[row] == SLOTS) continue;
            s = 8 + row * 8 - fy[i];
            q = scr + (unsigned int)row * LS + (COLS + used[row]++ * 3) * 2;
            q[0] = (unsigned char)gx;
            q[1] = (unsigned char)((gx >> 8) & 3) | (unsigned char)((s & 7) << 5);
            q[2] = (unsigned char)(ch + (s >> 3));
            q[3] = (unsigned char)((ch + (s >> 3)) >> 8);
            q[4] = (unsigned char)(ch + 4 + (s >> 3));
            q[5] = (unsigned char)((ch + 4 + (s >> 3)) >> 8);
        }
    }
}

/* ---- the palette ---- */

static unsigned char tri(unsigned char p) {      /* a triangle wave, 0-255 */
    return p < 128 ? p * 2 : (255 - p) * 2;
}

static void palette(void) {
    unsigned char i, g, j, base;
    unsigned int a, v[3];
    const unsigned char *c, *d = ft.pal[P_DISC];
    for (i = 1; i < FLAKES_COLOURS; i++) {
        g = ft.group[i];
        if (g == 255)                             /* the plasma: round */
            c = ft.pal[P_PLASMA + ((i - P_PLASMA + t) & 63)];
        else
            c = ft.pal[i];
        if (g && g != 255) {                      /* a level: the disc's colour to its own */
            base = T_LEVELS / 2 + (g - 1) * (T_LEVEL / 2);
            a = t < base * 2u ? 0 : (t - base * 2u >= REVEAL ? 256 : ((t - base * 2u) << 8) / REVEAL);
            if (a == 256)                         /* revealed: a shimmer */
                a = 200 + (tri((unsigned char)(t * 2 + g * 40)) >> 2) + 1;
            for (j = 0; j < 3; j++) {
                v[j] = (d[j] * (256 - (a > 256 ? 256 : a)) + c[j] * (a > 256 ? 256 : a)) >> 8;
            }
        } else
            for (j = 0; j < 3; j++) v[j] = c[j];
        pal_rgb(i, (unsigned char)((v[0] * fade) >> 4), (unsigned char)((v[1] * fade) >> 4),
                (unsigned char)((v[2] * fade) >> 4));
    }
}

/* the scene for frames frames (N sooner), then a fade out */
void flakes(unsigned int frames) {
    unsigned char i, k;
    unsigned int f;
    dma_copy_far((unsigned long)(unsigned int)scene_ram, FLAKES_LIN + FLAKES_TABLES, FLAKES_TABLES_SIZE);
    unpack(FLAKES_LIN + FLAKES_CHR_PCK);
    unpack_to(FLAKES_LIN + FLAKES_MAP_PCK, SCRATCH_LIN);
    screen_init();
    for (i = 0; i < FLAKES; i++) flake_new(i, (signed int)(rnd() % H) - 16);
    vic_on(scr, CELLS);
    t = 0;
    tune_volume(15);
    tune_play_far(MUSIC_LIN + TUNE_SHCHEDRYK_AT);
    for (f = 0; f < frames + FADE_FRAMES; f++) {
        while (raster() < 251) {}                 /* the bottom border */
        flakes_move();
        tune_update();
        fade = f < FADE_FRAMES ? (unsigned char)(f >> 1)
             : f >= frames ? (unsigned char)((frames + FADE_FRAMES - 1 - f) >> 1) : 16;
        palette();
        t++;
        k = key();
        if (k == 'n' || k == 'N') frames = f + 1;
        if (f + 1 == frames) tune_fade(FADE_FRAMES, 0);
        while (raster() >= 251) {}
    }
}
