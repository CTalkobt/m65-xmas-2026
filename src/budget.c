/* budget.c — how many RRB cells a text row can draw
 *
 * The VIC-IV at 320 x 200, 16-bit characters, full colour above $FF (as in
 * Witching Hour). Every row is the same:
 *   cells 0-39     the background: 40 opaque full-colour cells (the sky)
 *   then N slots   a flake each: a transparent GOTOX to x, then one
 *                  full-colour glyph whose pixel column 0 is lit. The slots'
 *                  x go evenly from 8 to 304, left to right, so a row
 *                  makes a comb across the screen. Every 10th tooth is
 *                  yellow and taller, to count by.
 *   then 2 cells   GOTOX 312 and a green block: the marker
 * CHRCOUNT is 40 + 2N + 2. The RRB draws a row's cells in order and stops
 * when its time runs out, so a row that does not fit loses the end of its
 * comb and its marker: the green column down the right edge breaks up.
 * The last N where it stays whole is the budget.
 *
 * Row 0 shows the settings (its flakes are invisible, the same cost).
 *
 * Keys:  + -               N by 1
 *        cursor up / down  N by 10
 *        D                 DBLRR ($D051 bit 6: the RRB renders every 2nd
 *                          raster line, with twice the time)
 *        R                 NORRDEL ($D051 bit 7: RRB double buffering off)
 * Reset to leave.
 *
 * The screen is in bank 5, the glyphs in bank 4: a row is built in bank 0
 * and copied to every row by DMA. The emulator draws every cell however
 * many there are, so only a real MEGA65 shows the limit.
 */
#include <dma.h>

#define REG(a) (*(volatile unsigned char *)(a))

#define CHR_LIN    0x0040000UL      /* the glyphs: bank 4, 64 bytes each */
#define SCR_LIN    0x0050000UL      /* the screen RAM: bank 5 */
#define COLOR_LIN  0xFF80000UL      /* the colour RAM */

#define CH0        0x1000           /* CHR_LIN / 64: the first glyph */
enum {
    G_SKY, G_NONE, G_FLAKE, G_FLAKE10, G_MARK,
    G_DIGIT,                        /* 0-9 */
    G_N = G_DIGIT + 10, G_D, G_R, G_EQ,
    NGLYPHS
};

#define ROWS       25
#define BGCELLS    40
#define MAXN       250
#define MAXCELLS   (BGCELLS + MAXN * 2 + 2)
#define LINESTEP   (MAXCELLS * 2)   /* bytes a row: the most cells, always */

#ifndef START_N
#define START_N    40
#endif

/* palette entries (the default C64 colours) */
#define C_WHITE    1
#define C_GREEN    5
#define C_BLUE     6
#define C_YELLOW   7

_Static_assert((unsigned long)ROWS * LINESTEP <= 0x8000, "the colour RAM is 32K");

static unsigned char srow[LINESTEP];
static unsigned char crow[LINESTEP];
static unsigned char glyph[64];
static unsigned int n = START_N;
static unsigned char dbl, nodel;

/* ---- the glyphs ---- */

/* 3 x 5, a row a byte (bit 2 the left): 0-9, N, D, R, = */
static const unsigned char font[14][5] = {
    {7, 5, 5, 5, 7}, {2, 6, 2, 2, 7}, {7, 1, 7, 4, 7}, {7, 1, 7, 1, 7},
    {5, 5, 7, 1, 1}, {7, 4, 7, 1, 7}, {7, 4, 7, 5, 7}, {7, 1, 1, 1, 1},
    {7, 5, 7, 5, 7}, {7, 5, 7, 1, 7},
    {6, 5, 5, 5, 5}, {6, 5, 5, 5, 6}, {6, 5, 6, 5, 5}, {0, 7, 0, 7, 0},
};

static void put_glyph(unsigned char g) {
    dma_copy_far(CHR_LIN + (unsigned long)g * 64, (unsigned long)(unsigned int)glyph, 64);
}

static void make_glyphs(void) {
    unsigned char g, y, x, bits;
    dma_fill((void *)glyph, 64, C_BLUE);
    put_glyph(G_SKY);
    dma_fill((void *)glyph, 64, 0);
    put_glyph(G_NONE);
    for (y = 2; y < 6; y++) glyph[y * 8] = C_WHITE;
    put_glyph(G_FLAKE);
    for (y = 0; y < 8; y++) glyph[y * 8] = C_YELLOW;
    put_glyph(G_FLAKE10);
    dma_fill((void *)glyph, 64, C_GREEN);
    put_glyph(G_MARK);
    /* the text: the font doubled across, white on the sky */
    for (g = 0; g < 14; g++) {
        dma_fill((void *)glyph, 64, C_BLUE);
        for (y = 0; y < 5; y++) {
            bits = font[g][y];
            for (x = 0; x < 3; x++)
                if (bits & (4 >> x)) {
                    glyph[(y + 1) * 8 + 1 + x * 2] = C_WHITE;
                    glyph[(y + 1) * 8 + 2 + x * 2] = C_WHITE;
                }
        }
        put_glyph(G_DIGIT + g);
    }
}

/* ---- the screen ---- */

static void cell(unsigned int i, unsigned int ch, unsigned char c0, unsigned char c1) {
    srow[i * 2] = (unsigned char)ch;
    srow[i * 2 + 1] = (unsigned char)(ch >> 8);
    crow[i * 2] = c0;
    crow[i * 2 + 1] = c1;
}

static void gotox(unsigned int i, unsigned int x) {
    cell(i, x & 0x3FF, 0x90, 0x00);     /* GOTOX, transparent */
}

/* the row for rows 1-24 (top 0) or row 0 (top 1: the text, flakes unseen);
 * the number of cells */
static unsigned int build(unsigned char top) {
    unsigned int k, c = 0, x;
    for (k = 0; k < BGCELLS; k++) cell(c++, CH0 + G_SKY, 0, 0);
    for (k = 0; k < n; k++) {
        x = n > 1 ? 8 + (unsigned int)((unsigned long)k * 296 / (n - 1)) : 8;
        gotox(c++, x);
        cell(c++, CH0 + (top ? G_NONE : (k % 10 == 9 ? G_FLAKE10 : G_FLAKE)), 0, 0);
    }
    gotox(c++, 312);
    cell(c++, CH0 + G_MARK, 0, 0);
    return c;
}

static void text(unsigned char col, unsigned char g) {
    srow[(1 + col) * 2] = (unsigned char)(CH0 + g);
    srow[(1 + col) * 2 + 1] = (unsigned char)((CH0 + g) >> 8);
}

static void status(void) {
    text(0, G_N);
    text(1, G_EQ);
    text(2, G_DIGIT + n / 100);
    text(3, G_DIGIT + n / 10 % 10);
    text(4, G_DIGIT + n % 10);
    text(6, G_D);
    text(7, G_EQ);
    text(8, G_DIGIT + dbl);
    text(10, G_R);
    text(11, G_EQ);
    text(12, G_DIGIT + nodel);
}

static void row_out(unsigned char r, unsigned int bytes) {
    unsigned long off = (unsigned long)r * LINESTEP;
    dma_copy_far(SCR_LIN + off, (unsigned long)(unsigned int)srow, bytes);
    dma_copy_far(COLOR_LIN + off, (unsigned long)(unsigned int)crow, bytes);
}

static void wait_bottom(void) {
    while (!(REG(0xD011) & 0x80)) {}    /* raster 256+: in the bottom border */
}

static void redraw(void) {
    unsigned char r;
    unsigned int cells = build(1);
    status();
    wait_bottom();
    REG(0xD05E) = (unsigned char)cells;
    REG(0xD063) = (REG(0xD063) & 0xC0) | (unsigned char)((cells >> 8) << 4);
    REG(0xD051) = (REG(0xD051) & 0x3F) | (nodel ? 0x80 : 0) | (dbl ? 0x40 : 0);
    row_out(0, cells * 2);
    build(0);
    for (r = 1; r < ROWS; r++) row_out(r, cells * 2);
}

static void video_on(void) {
    REG(0xD02F) = 0x47;                         /* the VIC-IV's registers */
    REG(0xD02F) = 0x53;
    REG(0xD015) = 0;                            /* no sprites */
    REG(0xD020) = 0;
    REG(0xD021) = 0;
    REG(0xD05D) = REG(0xD05D) & 0x7F;           /* hot registers off */
    REG(0xD031) = (REG(0xD031) & 0x77) | 0x40;  /* 320 x 200, FAST */
    REG(0xD054) = (REG(0xD054) & 0xEF) | 0x45;  /* CHR16 + FCLRHI, VFAST */
    REG(0xD058) = (unsigned char)LINESTEP;
    REG(0xD059) = (unsigned char)(LINESTEP >> 8);
    REG(0xD07B) = ROWS;
    REG(0xD060) = (unsigned char)SCR_LIN;
    REG(0xD061) = (unsigned char)(SCR_LIN >> 8);
    REG(0xD062) = (unsigned char)(SCR_LIN >> 16);
    REG(0xD064) = 0;                            /* the colour RAM from its start */
    REG(0xD065) = 0;
}

/* $D610: the hardware keyboard queue (0: empty; a write takes the key) */
static unsigned char key(void) {
    unsigned char k = REG(0xD610);
    if (k) REG(0xD610) = 0;
    return k;
}

int main(void) {
    unsigned char k;
    __asm__("sei");                             /* the KERNAL stays out */
    while (key()) {}
    make_glyphs();
    video_on();
    redraw();
    for (;;) {
        k = key();
        if (!k) continue;
        if (k == '+' && n < MAXN) n++;
        else if (k == '-' && n > 0) n--;
        else if (k == 0x91) n = n + 10 > MAXN ? MAXN : n + 10;     /* cursor up */
        else if (k == 0x11) n = n < 10 ? 0 : n - 10;               /* cursor down */
        else if (k == 'd' || k == 'D') dbl ^= 1;
        else if (k == 'r' || k == 'R') nodel ^= 1;
        else continue;
        redraw();
    }
    return 0;
}
