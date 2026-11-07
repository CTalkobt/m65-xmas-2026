/* vic.c — see vic.h */
#include "vic.h"

unsigned char screen_ram[ROWS * SCREEN_CELLS * 2];
unsigned char scene_ram[SCENE_RAM];

static unsigned int seed = 0xACE1;

unsigned int rnd(void) {
    seed ^= seed << 7;
    seed ^= seed >> 9;
    seed ^= seed << 8;
    return seed;
}

static unsigned char nib(unsigned char v) {
    return (unsigned char)(v << 4 | v >> 4);
}

void pal_rgb(unsigned char i, unsigned char r, unsigned char g, unsigned char b) {
    REG(0xD100 + i) = nib(r);
    REG(0xD200 + i) = nib(g);
    REG(0xD300 + i) = nib(b);
}

void pal_black(void) {
    unsigned int i;
    for (i = 0; i < 256; i++) pal_rgb((unsigned char)i, 0, 0, 0);
}

unsigned int raster(void) {
    unsigned char hi, lo;
    do {
        hi = REG(0xD011);
        lo = REG(0xD012);
    } while (hi != REG(0xD011));
    return lo | (unsigned int)(hi & 0x80) << 1;
}

unsigned char key(void) {
    unsigned char k = REG(0xD610);
    if (k) REG(0xD610) = 0;
    return k;
}

unsigned char vic_on(unsigned char *scr, unsigned int cells) {
    unsigned int a = (unsigned int)scr, ls = cells * 2;
    REG(0xD02F) = 0x47;                         /* the VIC-IV's registers */
    REG(0xD02F) = 0x53;
    REG(0xD015) = 0;
    REG(0xD020) = 0;
    REG(0xD021) = 0;
    REG(0xD070) = 0;                            /* palette bank 0, shown and edited */
    REG(0xD05D) = REG(0xD05D) & 0x7F;           /* hot registers off */
    REG(0xD031) = (REG(0xD031) & 0x77) | 0x40;  /* 320 x 200, FAST */
    REG(0xD054) = (REG(0xD054) & 0xEF) | 0x45;  /* CHR16 + FCLRHI, VFAST */
    REG(0xD058) = (unsigned char)ls;
    REG(0xD059) = (unsigned char)(ls >> 8);
    REG(0xD05E) = (unsigned char)cells;
    REG(0xD063) = (unsigned char)((cells >> 8) << 4);
    REG(0xD07B) = ROWS;
    REG(0xD060) = (unsigned char)a;
    REG(0xD061) = (unsigned char)(a >> 8);
    REG(0xD062) = 0;
    REG(0xD064) = 0;
    REG(0xD065) = 0;
    /* TEXTYPOS is in physical lines, two to a raster line */
    return (unsigned char)((REG(0xD04E) | (unsigned int)(REG(0xD04F) & 0x0F) << 8) >> 1);
}
