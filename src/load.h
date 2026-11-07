/* load.h — a file from disk to anywhere in memory: chip RAM, attic RAM,
 * packed or not
 *
 * Made for the demo, to go into m65compiler's library (it is the overlay
 * loader's work, __ovl_init's, for any file): it needs nothing of the
 * demo's.
 *
 *   load_far("TILES", 5, 0, 0x40000UL)       the file's bytes to $40000
 *   load_far("MUSIC", 5, 0, 0x8000000UL)     to attic RAM, through the stage
 *   load_unpack("SCENE", 5, 0, 0x50000UL)    a pack45 file: loaded to $50000,
 *                                            unpacked to its own destination
 *
 * The file's first two bytes are its load address (a PRG): they are
 * skipped, as cbm_load_far skips them; the rest goes to lin. The name is in
 * bank 0, PETSCII; device 0 is the drive the program was loaded from (8 when
 * none is known). It is a KERNAL LOAD: the KERNAL must be able to run (its
 * interrupts on, its memory as it left it) while it does; a program that has
 * taken the machine over gives it back around the call.
 *
 * Attic RAM ($8000000-$87FFFFF): the KERNAL loads chip RAM only, so the file
 * is loaded into the stage (load_stage; default $40000-$4FFFF) and copied up
 * by DMA. One LOAD reaches one 64 KB bank: a file is at most 64 KB less its
 * start's offset in the bank.
 */
#pragma once

/* the bytes loaded (0: an error, load_error says which) */
unsigned int load_far(const char *name, unsigned char len, unsigned char device, unsigned long lin);

/* a pack45 stream (pack45 --raw -d DEST, or a pack45 file: its load
 * address first) loaded to at (chip RAM, or attic RAM through the stage)
 * and unpacked there to the destination in its header; the bytes unpacked
 * (0: an error) */
unsigned long load_unpack(const char *name, unsigned char len, unsigned char device, unsigned long at);

/* where files for attic RAM are loaded first (chip RAM; size bytes, which a
 * file must fit) */
void load_stage(unsigned long lin, unsigned int size);

/* the last error: 0 none, else the KERNAL's (4 file not found, 5 device
 * not present, ...), LOAD_TOO_BIG (a file for attic RAM over the stage) or
 * LOAD_NOT_PACKED (load_unpack: not a pack45 stream) */
#define LOAD_TOO_BIG    0xFF
#define LOAD_NOT_PACKED 0xFE
extern unsigned char load_error;
