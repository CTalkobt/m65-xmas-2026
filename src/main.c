/* main.c — Midwinter, a Christmas demo for the MEGA65: what stays in
 * bank 0 while the scenes come and go
 *
 * The program (XMAS) is this, vic.c, load.c, the tune player and the
 * scenes' variables; each scene's code is a code overlay (village.c,
 * parlour.c, sleigh.c: ln45 keeps them in bank 5 from $58000 and copies
 * the one called into its region), loaded with the program by crt0 from
 * XMAS.OV1.
 *
 * The data is on the disk too (tools/data.py, data.h): MUSIC, every tune,
 * loaded once at the start into bank 1, the player playing it from there
 * (tune_play_far); and a file a scene (VILLAGE, PARLOUR, SLEIGH), loaded
 * into the slot in bank 1 just before the scene runs.
 *
 * Then the scenes in turn, round and round: each sets itself up, fades
 * in, runs, fades out and returns (scenes.h). Between them, with the
 * screen black and the music stopped, the machine is the KERNAL's again
 * while the next scene's file loads (load_scene): its interrupts on, then
 * off again. Whatever the KERNAL touched meanwhile (its cursor blinks in
 * the colour RAM) the next scene sets up afresh.
 *
 * Built with -DSTART_SCENE=n (make run SCENE=n) it starts at scene n:
 * 1 the village, 2 the tree, 3 the sleigh ride, 4 the snowflakes, 5 the
 * fireside, 6 the finale (the snow globe).
 *
 * GREETING (tools/card.py: make card) is loaded at the start too: the
 * plaque's two lines in the finale. Without it the finale has its own.
 */
#include <dma.h>
#include <audio_sid.h>
#include <audio_tune.h>
#include "vic.h"
#include "load.h"
#include "data.h"
#include "scenes.h"

#ifndef START_SCENE
#define START_SCENE 1
#endif
#ifndef VILLAGE_FRAMES
#define VILLAGE_FRAMES (50 * 60)
#endif
#ifndef PARLOUR_FRAMES
#define PARLOUR_FRAMES (50 * 45)
#endif
#ifndef SLEIGH_FRAMES
#define SLEIGH_FRAMES (50 * 45)
#endif
#ifndef FLAKES_FRAMES
#define FLAKES_FRAMES (50 * 45)
#endif
#ifndef FIRESIDE_FRAMES
#define FIRESIDE_FRAMES (50 * 45)
#endif
#ifndef FINALE_FRAMES
#define FINALE_FRAMES (50 * 60)
#endif
#define SCENES 6

/* the files' names, PETSCII (cc45's string literals would be shifted letters) */
static const char music_file[] = MUSIC_FILE;
static const char village_file[] = VILLAGE_FILE;
static const char parlour_file[] = PARLOUR_FILE;
static const char sleigh_file[] = SLEIGH_FILE;
static const char flakes_file[] = FLAKES_FILE;
static const char fire_file[] = FIRE_FILE;
static const char globe_file[] = GLOBE_FILE;
static const char greeting_file[] = GREETING_FILE;

static void fail(void) {
    __asm__("sei");
    REG(0xD020) = 2;                            /* a red border, and stop */
    for (;;) {}
}

/* the scene's file into the slot, the KERNAL's interrupts on meanwhile */
static void load_scene(unsigned char scene) {
    unsigned int n;
    tune_stop();
    pal_black();
    __asm__("cli");
    if (scene == 1) n = load_far(village_file, VILLAGE_FILE_LEN, 0, SLOT_LIN);
    else if (scene == 2) n = load_far(parlour_file, PARLOUR_FILE_LEN, 0, SLOT_LIN);
    else if (scene == 3) n = load_far(sleigh_file, SLEIGH_FILE_LEN, 0, SLOT_LIN);
    else if (scene == 4) n = load_far(flakes_file, FLAKES_FILE_LEN, 0, SLOT_LIN);
    else if (scene == 5) n = load_far(fire_file, FIRE_FILE_LEN, 0, SLOT_LIN);
    else n = load_far(globe_file, GLOBE_FILE_LEN, 0, SLOT_LIN);
    __asm__("sei");
    if (!n) fail();
    while (key()) {}
}

int main(void) {
    unsigned char scene = START_SCENE;
    if (!load_far(music_file, MUSIC_FILE_LEN, 0, MUSIC_LIN)) fail();
    if (!load_far(greeting_file, GREETING_FILE_LEN, 0, GREETING_LIN))
        dma_fill_far(GREETING_LIN, 2, 0);                 /* none: the finale has its own */
    __asm__("sei");                             /* the KERNAL stays out, but to load */
    while (key()) {}
    vic_on(screen_ram, COLS);
    pal_black();
    sid_init();
    sid_set_mirror(1);                          /* SIDs 1-2 on the right too (3-4) */
    for (;;) {
        load_scene(scene);
        if (scene == 1) village(VILLAGE_FRAMES);
        else if (scene == 2) parlour(PARLOUR_FRAMES);
        else if (scene == 3) sleigh(SLEIGH_FRAMES);
        else if (scene == 4) flakes(FLAKES_FRAMES);
        else if (scene == 5) fireside(FIRESIDE_FRAMES);
        else finale(FINALE_FRAMES);
        scene = scene == SCENES ? 1 : scene + 1;
    }
    return 0;
}
