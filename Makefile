# Midwinter — a Christmas demo for the MEGA65 (cc45)
#
# The demo is one program on a D81 (build/xmas.d81):
#   XMAS       src/main.c, vic.c and load.c, resident in bank 0 (the tune player too); the
#              scenes' code in code overlays (src/village.c, parlour.c,
#              sleigh.c, flakes.c, fireside.c, finale.c)
#   XMAS.OV1   the overlays (ln45), loaded by the program's start-up code
#   MUSIC      every tune (gen_music.py, tune45 --bin), loaded at the start
#   GREETING   the snow globe's plaque (tools/card.py), loaded at the start
#   VILLAGE, PARLOUR, SLEIGH, FLAKES, FIRE, GLOBE
#              a scene's data (tools/gen_scene.py, gen_tree.py,
#              gen_sleigh.py, gen_flakes.py, gen_fire.py, gen_globe.py;
#              data.py), loaded as the scene begins
#
#   make              build build/xmas.d81 (and build/budget.prg)
#   make run          boot the demo in xemu-xmega65 (SCENE=n: start at scene
#                     n: 1 the village, 2 the tree, 3 the sleigh ride, 4 the
#                     snowflakes, 5 the fireside, 6 the snow globe)
#   make hw           put the disk on a MEGA65 and mount it (deploy45
#                     m65mount), then LOAD "XMAS" and RUN there
#   make shot         a headless xemu screenshot, build/shot.png, SHOT_DELAY
#                     seconds in (default 20; SCENE as for run)
#   make card         the greeting on the snow globe's plaque: make card
#                     LINE1="TO THE SMITHS" LINE2="LOVE FROM JO & SAM"
#                     (20 letters a line at most); the disk made again
#   make play         the music on this computer (tune45 play)
#   make budget       the RRB budget test (src/budget.c) in xemu; N its
#                     starting slot count. The emulator draws every RRB cell:
#                     only a MEGA65 shows the limit (make hw-budget)
#   make clean        remove build/
#
# Variables: M65 (the M65Compiler tree), XEMU, SCENE, SHOT_DELAY, N,
# M65_HOST (deploy45's MEGA65 address).

M65     ?= ../m65compiler
CC45    := $(M65)/bin/cc45
LN45    := $(M65)/bin/ln45
DISK45  := $(M65)/bin/disk45
DEPLOY45 := $(M65)/bin/deploy45
PACK45  := $(M65)/bin/pack45
TUNE45  := $(M65)/bin/tune45
STDLIB  := $(M65)/lib/build/c45.lib
XEMU    ?= xemu-xmega65
PYTHON  ?= python3
SHOT    := tools/shot.py

BUILD   ?= build
N       ?= 40
SCENE   ?= 1
SHOT_DELAY ?= 20

CFLAGS  := -O2 -I$(M65)/lib/include -Isrc -I$(BUILD)

# the overlays are kept in bank 5 from $58000: $50000 has the scenes' flake glyphs
LNFLAGS := -basic --overlay-store=0x58000-0x5FFFF

DISK    := $(BUILD)/xmas.d81

.PHONY: all run hw shot play card budget hw-budget clean FORCE

all: $(DISK) $(BUILD)/budget.prg

$(BUILD):
	mkdir -p $@

# ---- the scenes' data ----

$(BUILD)/village.h $(BUILD)/village.dat &: tools/gen_scene.py tools/blob.py | $(BUILD)
	$(PYTHON) tools/gen_scene.py $(BUILD) $(PACK45) --preview

$(BUILD)/parlour.h $(BUILD)/parlour.dat &: tools/gen_tree.py tools/blob.py | $(BUILD)
	$(PYTHON) tools/gen_tree.py $(BUILD) $(PACK45) --preview

$(BUILD)/sleigh.h $(BUILD)/sleigh.dat &: tools/gen_sleigh.py tools/blob.py | $(BUILD)
	$(PYTHON) tools/gen_sleigh.py $(BUILD) $(PACK45) --preview

$(BUILD)/flakes.h $(BUILD)/flakes.dat &: tools/gen_flakes.py tools/blob.py | $(BUILD)
	$(PYTHON) tools/gen_flakes.py $(BUILD) $(PACK45) --preview

$(BUILD)/fire.h $(BUILD)/fire.dat &: tools/gen_fire.py tools/blob.py | $(BUILD)
	$(PYTHON) tools/gen_fire.py $(BUILD) $(PACK45) --preview

$(BUILD)/globe.h $(BUILD)/globe.dat &: tools/gen_globe.py tools/blob.py tools/font5x7.py | $(BUILD)
	$(PYTHON) tools/gen_globe.py $(BUILD) $(PACK45) --preview

# the plaque's greeting (make card LINE1=... LINE2=...)
LINE1   ?= MERRY CHRISTMAS
LINE2   ?= AND A HAPPY NEW YEAR

$(BUILD)/greeting.prg: tools/card.py | $(BUILD)
	$(PYTHON) tools/card.py $@ "$(LINE1)" "$(LINE2)"

SCENE_DATA := village parlour sleigh flakes fire globe

DATA_FILES := $(SCENE_DATA) music

$(BUILD)/data.h $(DATA_FILES:%=$(BUILD)/%.prg) &: tools/data.py $(DATA_FILES:%=$(BUILD)/%.dat)
	$(PYTHON) tools/data.py $(BUILD) $(DATA_FILES)

# ---- the music: God Rest Ye Merry, Gentlemen, O Tannenbaum ----

$(BUILD)/music.txt: tools/gen_music.py tools/lily.py | $(BUILD)
	$(PYTHON) tools/gen_music.py $@

# one blob in XMASDATA (bank 1), played from there: tune_play_far(MUSIC_LIN + TUNE_<NAME>_AT)
$(BUILD)/music.dat $(BUILD)/music.h &: $(BUILD)/music.txt
	$(TUNE45) convert --bin --coded $< -o $(BUILD)/music.dat --header $(BUILD)/music.h

# ---- the program ----

HEADERS := src/vic.h src/load.h src/scenes.h $(BUILD)/data.h $(BUILD)/music.h $(SCENE_DATA:%=$(BUILD)/%.h)

$(BUILD)/vic.o45: src/vic.c src/vic.h | $(BUILD)
	$(CC45) $(CFLAGS) -c $< -o $@

$(BUILD)/load.o45: src/load.c src/load.h | $(BUILD)
	$(CC45) $(CFLAGS) -c $< -o $@

# main.o45 is rebuilt each time: SCENE may have changed
$(BUILD)/main.o45: src/main.c $(HEADERS) FORCE
	$(CC45) $(CFLAGS) -DSTART_SCENE=$(SCENE) -c $< -o $@

$(BUILD)/village.o45: src/village.c $(HEADERS)
	$(CC45) $(CFLAGS) -c $< -o $@

$(BUILD)/parlour.o45: src/parlour.c $(HEADERS)
	$(CC45) $(CFLAGS) -c $< -o $@

$(BUILD)/sleigh.o45: src/sleigh.c $(HEADERS)
	$(CC45) $(CFLAGS) -c $< -o $@

$(BUILD)/flakes.o45: src/flakes.c $(HEADERS)
	$(CC45) $(CFLAGS) -c $< -o $@

$(BUILD)/fireside.o45: src/fireside.c $(HEADERS)
	$(CC45) $(CFLAGS) -c $< -o $@

$(BUILD)/finale.o45: src/finale.c $(HEADERS)
	$(CC45) $(CFLAGS) -c $< -o $@

SCENE_OBJS := village parlour sleigh flakes fireside finale
OBJS := $(BUILD)/main.o45 $(BUILD)/vic.o45 $(BUILD)/load.o45 $(SCENE_OBJS:%=$(BUILD)/%.o45)

$(BUILD)/xmas.prg $(BUILD)/xmas.ov1 &: $(OBJS) $(STDLIB)
	$(LN45) $(LNFLAGS) -M $(BUILD)/xmas.map -o $(BUILD)/xmas.prg $(OBJS) $(STDLIB)

$(DISK): $(BUILD)/xmas.prg $(BUILD)/xmas.ov1 $(DATA_FILES:%=$(BUILD)/%.prg) $(BUILD)/greeting.prg
	rm -f $@
	$(DISK45) create $@ -n "MIDWINTER" -i "XM"
	$(DISK45) add $@ $(BUILD)/xmas.prg XMAS
	$(DISK45) add $@ $(BUILD)/xmas.ov1 XMAS.OV1
	$(DISK45) add $@ $(BUILD)/music.prg MUSIC
	$(DISK45) add $@ $(BUILD)/village.prg VILLAGE
	$(DISK45) add $@ $(BUILD)/parlour.prg PARLOUR
	$(DISK45) add $@ $(BUILD)/sleigh.prg SLEIGH
	$(DISK45) add $@ $(BUILD)/flakes.prg FLAKES
	$(DISK45) add $@ $(BUILD)/fire.prg FIRE
	$(DISK45) add $@ $(BUILD)/globe.prg GLOBE
	$(DISK45) add $@ $(BUILD)/greeting.prg GREETING

$(STDLIB):
	$(MAKE) -C $(M65) lib

run: $(DISK)
	$(XEMU) -8 $(abspath $(DISK)) -autoload

hw: $(DISK)
	$(DEPLOY45) m65mount $(DISK)

shot: $(DISK)
	CAPTURE_DELAY=$(SHOT_DELAY) $(PYTHON) $(SHOT) $(BUILD)/xmas.prg $(abspath $(BUILD)/shot.png) $(DISK)

# a Christmas card: your own greeting on the plaque (two lines, 20 letters
# at most each), the disk made again with it
card:
	$(PYTHON) tools/card.py $(BUILD)/greeting.prg "$(LINE1)" "$(LINE2)"
	$(MAKE) $(DISK)

play: $(BUILD)/music.txt
	$(TUNE45) play $<

# ---- the RRB budget test ----

# rebuilt each time: N may have changed
$(BUILD)/budget.o45: src/budget.c FORCE | $(BUILD)
	$(CC45) $(CFLAGS) -DSTART_N=$(N) -c $< -o $@

$(BUILD)/budget.prg: $(BUILD)/budget.o45 $(STDLIB)
	$(LN45) -basic -M $(BUILD)/budget.map -o $@ $< $(STDLIB)

budget: $(BUILD)/budget.prg
	$(XEMU) -prg $(abspath $<) -prgmode 65

hw-budget: $(BUILD)/budget.prg
	$(DEPLOY45) m65ether $<

clean:
	rm -rf $(BUILD)

FORCE:
