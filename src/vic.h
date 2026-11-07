/* vic.h — what every part of the demo shares: the VIC-IV in 320 x 200 with
 * 16-bit full-colour characters, the palette, the raster, the keys, a
 * random number
 */
#pragma once

#define REG(a) (*(volatile unsigned char *)(a))

#define COLOR_LIN  0xFF80000UL       /* the colour RAM */
#define CHR_LIN    0x0040000UL       /* a scene's characters: 64 bytes each */
#define CH0        0x1000            /* CHR_LIN / 64: cell (r, c) is CH0 + r * 40 + c */
#define COLS       40
#define ROWS       25
#define W          320
#define H          200

/* The screen RAM, every scene's (one runs at a time): ROWS rows of up to
 * SCREEN_CELLS cells (the village's: 40, 24 flake slots, the end). */
#define SCREEN_CELLS (COLS + 24 * 2 + 1)
extern unsigned char screen_ram[ROWS * SCREEN_CELLS * 2];

/* The scene running's work area (one runs at a time): its big tables and
 * buffers, which bank 0 has no room for every scene's of (the village's
 * catch map, the others' tables, the fire ...). Scene code puts a struct or
 * array there with a #define. */
#define SCENE_RAM 8192
extern unsigned char scene_ram[SCENE_RAM];

/* the VIC-IV on: 320 x 200, CHR16 + full colour above $FF, 40 MHz; screen
 * RAM at scr (bank 0), cells a row (LINESTEP cells * 2), the colour RAM
 * from its start; palette bank 0 shown and edited; no sprites, black
 * border and background. Gives the first text row's raster line. */
unsigned char vic_on(unsigned char *scr, unsigned int cells);

/* palette entry i: r, g, b 0-255 (the VIC-IV's nibbles swapped). Only
 * after vic_on: before it the palette registers may not be the VIC-IV's
 * bank 0 (a normal boot leaves them elsewhere) and the writes are lost. */
void pal_rgb(unsigned char i, unsigned char r, unsigned char g, unsigned char b);

/* every palette entry black (after vic_on) */
void pal_black(void);

/* the raster line (9 bits) */
unsigned int raster(void);

/* $D610: the hardware keyboard queue; 0 none */
unsigned char key(void);

/* 16-bit xorshift */
unsigned int rnd(void);
