/* scenes.h — the demo's scenes, each a code overlay that main.c calls in
 * turn: it sets itself up (its data from XMASDATA, its screen, its music),
 * fades in, runs for frames frames (or until N), fades out and returns.
 */
#pragma once

#define FADE_FRAMES 32                      /* the fades in and out */

void village(unsigned int frames);          /* village.c: the snow */
void parlour(unsigned int frames);          /* parlour.c: the tree */
void sleigh(unsigned int frames);           /* sleigh.c: the sleigh ride */
void flakes(unsigned int frames);           /* flakes.c: the snowflakes */
void fireside(unsigned int frames);         /* fireside.c: the fireside */
void finale(unsigned int frames);           /* finale.c: the snow globe */
