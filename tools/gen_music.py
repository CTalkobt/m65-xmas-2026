#!/usr/bin/env python3
"""gen_music.py — the demo's music, as tune45 text: every tune in one file
(one music.c, linked by every part; each plays its own).

    python3 tools/gen_music.py <out.txt>

THE VILLAGE (tune carol). God Rest Ye Merry, Gentlemen: the traditional English carol (the London
tune, printed in the 18th century) in the four-part harmony of the
Victorian hymnals (Stainer's, 1871), long in the public domain. The four
parts are below as LilyPond wrote them (relative pitches, E minor, 4/4,
a crotchet's pickup); this turns them into absolute notes, a tick a
quaver, and arranges them for the SIDs:

  v1  soprano   the tune: a soft organ (pulse, slow vibrato)
  v2  alto      a quieter reed (pulse)
  v3  tenor     a flute (triangle)
  v4  bass      a saw through the low-pass filter (SID 1's)
  v5  bell      the church bell: it tolls before the carol and at its end
  v6  glock     verse 2: the tune an octave up, a glockenspiel

The bell tolls four times, then the verses go round: verse 1 (the four
parts), verse 2 (the glockenspiel with them). |: is at verse 1, so the
tolling is heard once.

THE TREE (tune tannenbaum). O Tannenbaum: the German folk song (the
melody as Ernst Anschütz's 1824 words have it, older still), public
domain, as the Wikipedia article sets it: the tune over a piano
accompaniment, two notes in each hand, G major, 3/4, a quaver's pickup.
Its form, the chorus, the verse, the chorus again (D.C. al fine), twice:

  v1      the tune: a flute
  v2, v3  the right hand: a soft electric piano
  v4, v5  the left hand: the bass and the note above it
  v6      the second time: a celesta, the tune an octave up (a nod to
          the Sugar Plum Fairy, the tree's other dance)

THE SNOWFLAKES (tune shchedryk): Leontovych's Shchedryk (1916), the tune
of Carol of the Bells, in its four parts; THE FIRESIDE (tune royal): Once
in Royal David's City, Gauntlett (1849) in A. H. Mann's harmony; THE
FINALE (tune silent): Silent Night, Gruber (1818), the tune, the voice
under it and our bass. Each twice through, a celesta joining the tune an
octave up the second time (arrange()).

THE SLEIGH RIDE (tune dingdong). Ding Dong Merrily on High: the tune is
the Branle de l'Official from Thoinot Arbeau's Orchésographie (1588), in
Charles Wood's four parts (1924), public domain, as the Wikipedia article
sets them (B flat, 4/4, a crotchet 144):

  v1-v4   soprano, alto, tenor, bass: lead, reed, flute, the bass
  v5      sleigh bells: a jingle of noise every quaver
  v6      the second time: the glockenspiel, the tune an octave up

tools/lily.py reads the LilyPond (chords, q, ties, rests, dots).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lily  # noqa: E402

# ------------------------------------------------------------------ the score

SOPRANO = r"""\relative c' {
  \repeat volta 2 { e4 | e b' b a | g fis e
    d | e fis g a | b2. }
  b4 | c a b c | d e b
  a | g e fis g a2
  g4 (a) | b2 c4 b | b (a) g fis | e2 g8 fis e4 | a2
  g4 (a) | b (c) d e | b (a) g fis | e2.
}"""

ALTO = r"""\relative c' {
  \repeat volta 2 { e4 | e g fis dis | e d! c
    b | e dis e e | dis2. }
  e4 | e d d g | f e d
  dis | e cis d g | fis2
  g4 (d) | d2 e4 d | g (fis) e dis | e2 b8 b cis4 | d2
  e4 (fis) g2 g4 g | g (fis) e dis | e2.
}"""

TENOR = r"""\relative c {
  \repeat volta 2 { e4 | g e fis b | b b g
    g | g b b e, | fis2. }
  gis4 | a a g g | g g g
  fis | g g a d | d (c)
  b4 (a) | g2 g4 g | d' (c) b b | g2 g8 g g4 | fis (a)
  d c | b (g) d' c | d (c) b b | g2.
}"""

BASS = r"""\relative c {
  \repeat volta 2 { e4 | e e dis b | e b c
    g | c b e c | b2. }
  e4 | a fis g c, | b c g
  b | e e d b | d2
  e4 (fis) | g2 c,4 g' | g, (a) b b | e2 e8 e e4 | d (c)
  b a | g (e') b c | g (a) b b | e2.
}"""

LETTERS = "cdefgab"
SEMI = [0, 2, 4, 5, 7, 9, 11]
NAMES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]


def parse(src):
    """LilyPond relative mode (the little of it these use) -> [(midi, ticks)]"""
    m = re.match(r"\\relative c([',]*)\s*\{(.*)\}\s*$", src.strip(), re.S)
    octave = 3 + m.group(1).count("'") - m.group(1).count(",")
    prev = octave * 7                 # c of that octave, as a diatonic step
    body = m.group(2)
    notes = []
    ticks = 2                         # a crotchet: two quavers
    repeat_from = None
    for tok in re.findall(r"\\repeat volta 2 \{|\}|[a-g](?:is|es)*[',]*!?\d*\.?", body):
        if tok.startswith("\\repeat"):
            repeat_from = len(notes)
            continue
        if tok == "}":
            notes += notes[repeat_from:]
            repeat_from = None
            continue
        n = re.match(r"([a-g])((?:is|es)*)([',]*)!?(\d*)(\.?)", tok)
        letter = LETTERS.index(n.group(1))
        # the octave that puts it within a fourth of the note before
        step = prev - prev % 7 + letter
        while step - prev > 3:
            step -= 7
        while prev - step > 3:
            step += 7
        step += 7 * (n.group(3).count("'") - n.group(3).count(","))
        prev = step
        acc = n.group(2).count("is") - n.group(2).count("es")
        midi = 12 * (step // 7 + 1) + SEMI[step % 7] + acc
        if n.group(4):
            ticks = {1: 8, 2: 4, 4: 2, 8: 1}[int(n.group(4))]
            if n.group(5):
                ticks = ticks * 3 // 2
        notes.append((midi, ticks))
    return notes


def name(midi):
    return "%s%d" % (NAMES[midi % 12], midi // 12 - 1)


def text(notes, shift=0):
    return " ".join("%s:%d" % (name(m + shift), t) for m, t in notes)


# ------------------------------------------------------------------ the tune

# ------------------------------------------------------------------ O Tannenbaum
# (the score's sections: C the chorus, V the verse; a part each, as written)

TANNENBAUM = {
    "melody": (r"""\relative c' { d8 | g8. g16 g4 a | b8. b16 b4. b8 | a b c4 fis, | a g r8 }""",
               r"""\relative c' { d'8 | d b e4. d8 | d c c4. c8 | c a d4. c8 | c b b4 r8 }"""),
    "right": (r"""\relative c' { d8~ | <d b>2 <fis d>4 | <g d> <gis e>2 | e4 <a e> d, | c8. b16 b4 r8 }""",
              r"""\relative c' { g'8~ | g4 <c g>2 | <a fis>4 <fis d>2 | <fis d>4 <a fis>2 | <g d>4 q r8 }"""),
    "left": (r"""\relative c' { d,8 | <b' g>2 <fis d>4 | f e d | <a' c,>2 <a d,>4 | <fis g,> <g g,> r8 }""",
             r"""\relative c' { r8 | <g g,>4 q q | <a a,> q q | <d, d,> q q | <g g,> q r8 }"""),
}


def tannenbaum():
    parts = {}
    for k, (chorus, verse) in TANNENBAUM.items():
        c, v = lily.parse(chorus), lily.parse(verse)
        parts[k] = c + v + c                    # chorus, verse, the chorus again
    lengths = {k: lily.length(p) for k, p in parts.items()}
    if len(set(lengths.values())) != 1:
        raise SystemExit("O Tannenbaum's parts differ in length: %s" % lengths)
    once = lengths["melody"]
    v = {
        1: "@flute2 " + lily.voice(parts["melody"], 0),
        2: "@epiano " + lily.voice(parts["right"], 0),
        3: "@epiano " + lily.voice(parts["right"], 1),
        4: "@bass2 " + lily.voice(parts["left"], 0, bottom=True),
        5: "@epiano " + lily.voice(parts["left"], 1, bottom=True),
    }
    out = ["tune tannenbaum 9 loop"]
    for i in range(1, 6):
        out.append("v%d: %s %s" % (i, v[i], v[i].split(" ", 1)[1]))
    out.append("v6: @celesta r:%d %s" % (once, lily.voice(parts["melody"], 0, 12)))
    return out, once


# ------------------------------------------------------------------ Ding Dong Merrily on High

DINGDONG = {
    "soprano": r"""\relative c'' { \repeat volta 2 { bes4 bes c8 [bes] a [g] | f2. f4 g bes bes a | bes2 bes | }
  f'4. (es8 d es f d | es4. d8 c d es c | d4. c8 bes c d bes | c4. bes8 a bes c a | bes4. a8 g a bes g |a4.) g8 f4
  f | g bes bes a | bes2 bes }""",
    "alto": r"""\relative c' { \repeat volta 2 { f4 f g8 [g] es [es] | c2. f4 | f es c f | f2 f | }
  r4 f2 (bes4~ | bes8 a g f g f es4) | r4 f8 (es d4 f | g8 f es d es d c4) | r4 d8 (c bes4 d | c bes c)
  d | f es c f | f2 f2 }""",
    "tenor": r"""\relative c' { \repeat volta 2 { d4 bes g8 [g] c [bes] | a2. bes4 | bes bes c c | d2 d2 }
  r4 c (d bes | c bes2 c4) | r4 a (bes g | a g2 a4) | r4 f (g2 f4) bes c
  d | bes bes c c | d2 d2 }""",
    "bass": r"""\relative c { \repeat volta 2 { bes4 d es8 [es] c [c] | f2. d4 | es g f f | bes,2 bes | }
  r4 a' (bes d, | c d es8 d c4) | r4 f (g bes, | a bes c8 bes a4) | r4 d (es c | f) g a
  bes | es, g f f | bes,2 bes }""",
}


def dingdong():
    parts = {k: lily.parse(v) for k, v in DINGDONG.items()}
    lengths = {k: lily.length(p) for k, p in parts.items()}
    if len(set(lengths.values())) != 1:
        raise SystemExit("Ding Dong's parts differ in length: %s" % lengths)
    once = lengths["soprano"] // 2              # in quavers: a tick each
    vo = {k: lily.voice(p, 0, scale=1) for k, p in parts.items()}
    half = lambda k, shift=0: lily.voice([(ps, t // 2, tie) for ps, t, tie in parts[k]], 0, shift)
    sop, alto, ten = half("soprano"), half("alto"), half("tenor")
    bass = half("bass", -12)
    out = ["pattern jingle: " + " ".join(["c7:1"] * 8),     # a bar of sleigh bells
           "tune dingdong 10 loop",
           "v1: @lead %s %s" % (sop, sop),
           "v2: @reed %s %s" % (alto, alto),
           "v3: @flute %s %s" % (ten, ten),
           "v4: @bass %s %s" % (bass, bass),
           "v5: @jingle *jingle*%d" % (2 * once // 8),
           "v6: @glock r:%d %s" % (once, half("soprano", 12))]
    return out, once


# ------------------------------------------------------------------ Shchedryk
# Mykola Leontovych, 1916 (Carol of the Bells' tune), the Wikipedia article's
# four parts: G minor, 3/4. (Its \set and \tempo lines left out.)

SHCHEDRYK = {
    "soprano": r"""\relative c'' {
  bes4 a8 bes g4 \repeat volta 2 { \repeat unfold 15 { bes4 a8 bes g4 | }
  \repeat unfold 4 { d'4 c8 d bes4 | }
  g'4 g8 g f ([es]) | d4 d8 d c ([bes]) | c4 c8 c d ([c]) | g4 g8 g g4 |
  d8 ([e fis g a bes]) | c ([d]) c4 bes |
  d,8 ([e fis g a bes]) | c ([d]) c4 bes |
  \repeat unfold 4 { bes4 a8 bes g4 | } }
  \alternative { { bes4 a8 bes g4 } { g2.~ | g2.~ | g2. |
    d'4 c8 d g,4 } } }""",
    "alto": r"""\relative c' {
  R2. | \repeat volta 2 { R2.*3 | \repeat unfold 2 { g'2. | f | es | d | }
  \repeat unfold 4 { g4 g8 g g4 | }
  \repeat unfold 4 { bes4 a8 bes g4 | }
  \repeat unfold 4 { g4 g8 g g4 | }
  d2. | e4 fis g | d2. | e4 fis g |
  d2.( | c | f | es | }
  \alternative { { d2) r4 } { d2.~ | d~ | d | bes'4 a8 bes g4 } } }""",
    "tenor": r"""\relative c' {
  R2. | \repeat volta 2 { \repeat unfold 7 { R2. } es2. | bes | c | g |
  c4 c8 c c4 | d4 d8 d d4 | es4 es8 es es4 | d4 d8 d d4 |
  d2. | e | f4 (es) d | g8 ([f]) es4 d |
  d4 es8 es d ([c]) | d4 d8 d d4 | es es8 es f ([es]) | d4 d8 d d4 |
  \repeat unfold 4 { bes4 a8 bes g4 | }
  g2.~ | g~ | g~ | g~ | }
  \alternative { { g2 r4 } { \repeat unfold 3 { bes4 a8 bes g4 } R2. } } }""",
    "bass": r"""\relative c {
  R2. | \repeat volta 2 { \repeat unfold 11 { R2. }
  es4 es8 es es4 | g g8 g g4 | c c8 c c4 | g g8 g g4 |
  \repeat unfold 4 { g g8 g g4 | }
  \repeat unfold 4 { bes a8 bes g4 | }
  d2. | d | d~ | d2 es4 |
  f2.( | es | d | c | }
  \alternative { { g2) r4 } { g2.~ | g~ |g | R2. } } }""",
}

# ------------------------------------------------------------------ Once in Royal David's City
# Henry Gauntlett's tune (1849) in A. H. Mann's harmony, the Wikipedia
# article's four parts: F major, 4/4, a minim's pickup.

ROYAL = {
    "rightOne": r"""\relative c' {
  \repeat volta 2 { c4 e | f4. f8 f [(e)] f [(g)] | g4 f f a | c4. a8 a [(g)] f [(e)] | f2 }
  d'4 d | c4. f,8 bes4 bes | a2 d4 d | c4. a8 a [(g)] f [(e)] | f2 }""",
    "rightTwo": r"""\relative c' {
  \repeat volta 2 { c4 e | c c b b | c8 [(bes!)] a4 c f | c c d c | c2 }
  d8 [(e)] f [(g)] | c,4 c d e | f2 d8 [(e)] f [(g)] | c, ([e] f) [f] d4 c | c2 }""",
    "leftOne": r"""\relative c' {
  \repeat volta 2 { a4 bes |c a g f | e f a c | g a8 ([c]) c ([bes]) a ([g]) | a2 }
  f4 bes | a a bes c | c2 bes4 bes | a8 ([bes] c) c c ([bes]) a ([g]) | <a f>2 }""",
    "leftTwo": r"""\relative c' {
  \repeat volta 2 { a4 g | a f d g, | c f, f' f | e f bes, c | f2 }
  bes,8 ([c]) d ([e]) | f4 a g c, | f2 bes,8 ([c]) d ([e]) | f ([g] a) [f] bes,4 c | f,2 }""",
}

# ------------------------------------------------------------------ Silent Night
# Franz Xaver Gruber, 1818: the Wikipedia article's first score, the tune
# and a voice under it, D major, 6/8 (its German names: h is B; its rests
# at h written as rests). The bass is ours: the tune's chords, I, V and IV,
# as every hymnal has them, root and fifth a bar.

SILENT = {
    "melody": r"""\relative c'' {
    a8. [ b16 ] a8 fis4 r8
    a8. b16 a8 fis4 r8
    e'8. [ dis16 ] e8 cis4 r8
    d8. [ cis16 ] d8 a4 r8
    b4 b8 d8. [ cis16 ] b8
    a8. b16 a8 fis4 r8
    b4 b8 d8. [ cis16 ] b8
    a8. b16 a8 fis4 r8
    e'8. e16 e8 g8. fis16 e8
    fis4. ( d4 ) r8
    d8. a16 fis8 a8. g16 e8
    d4.~ d4 r8 }""",
    "second": r"""\relative c' {
    fis8. [ g16 ] fis8 d4 s8
    fis8. g16 fis8 d4 s8
    g8. [ fis16 ] g8 e4 s8
    fis8. [ e16 ] fis8 fis4 s8
    g4 g8 b8. [ a16 ] g8
    fis8. g16 fis8 d4 s8
    g4 g8 b8. [ a16 ] g8
    fis8. g16 fis8 d4 s8
    e8. e16 e8 g8. fis16 e8
    fis4. ( a4 ) s8
    fis8. fis16 d8 fis8. e16 cis8
    d4.~ d4 s8 }""",
    "bass": r"""\relative c {
    d4. a | d a | a e' | d a | g d' | d a | g d' | d a |
    a e' | d a | d a | d4.~ d4 r8 }""",
}


def arrange(name, parts, voices, frames, scale, passes=2, double=None):
    """voices: (instrument, part, index from the top, semitones; bottom) a
    voice; ticks of `scale` sixteenths; played `passes` times through, with
    double = (instrument, part, semitones) joining from the second time"""
    lengths = {k: lily.length(p) for k, p in parts.items()}
    if len(set(lengths.values())) != 1:
        raise SystemExit("%s: the parts differ in length: %s" % (name, lengths))
    once = lengths[next(iter(parts))] // scale

    def part(k, i=0, shift=0, bottom=False):
        evs = [(ps, t // scale, tie) for ps, t, tie in parts[k]]
        if any(t == 0 for _, t, _ in evs):
            raise SystemExit("%s: a note shorter than a tick" % name)
        return lily.voice(evs, i, shift, bottom=bottom)

    out = ["tune %s %s loop" % (name, frames)]
    for n, (instr, k, i, shift, bottom) in enumerate(voices, 1):
        text = part(k, i, shift, bottom)
        out.append("v%d: @%s %s" % (n, instr, " ".join([text] * passes)))
    if double:
        instr, k, shift = double
        out.append("v%d: @%s r:%d %s" % (len(voices) + 1, instr, once * (passes - 1),
                                         " ".join([part(k, 0, shift)] * (passes - 1))))
    return out, once


HEADER = """; the demo's music (tune45 text), made by tools/gen_music.py: God Rest
; Ye Merry, Gentlemen (the village; a tick a quaver) and O Tannenbaum (the
; tree; a tick a semiquaver), both traditional.

instrument organ  pulse 26 a9 0600 2 0 pwm=18 vdelay=20 hr=1
instrument reed   pulse 26 87 0400 0 0 pwm=-14 hr=1
instrument flute  tri   26 98 0000 1 0 vdelay=24 hr=1
instrument bass   saw   06 a8 0800 0 0 filter=lp res=5 cutoff=1c0 hr=1
instrument bell   tri   09 0b 0000 0 0
instrument glock  tri   05 05 0000 0 0 hr=1
instrument flute2 tri   36 a8 0000 2 0 vdelay=20 hr=1
instrument epiano pulse 04 6a 0300 0 0 pwm=10 hr=1
instrument bass2  tri   05 a9 0000 0 0 hr=1
instrument celesta tri  01 69 0000 0 0 hr=1
instrument lead   pulse 06 a8 0600 2 0 pwm=24 vdelay=12 hr=1
instrument jingle noise 00 82 0800 0 0
instrument bellp  pulse 02 6a 0400 0 0 hr=1
"""


def main():
    parts = [parse(p) for p in (SOPRANO, ALTO, TENOR, BASS)]
    lengths = [sum(t for _, t in p) for p in parts]
    if len(set(lengths)) != 1:
        raise SystemExit("the parts differ in length: %s" % lengths)
    verse = lengths[0]
    toll = 8                          # a bar a stroke
    strokes = 4
    intro = toll * strokes

    v = {}
    sop, alto, ten, bass = (text(p) for p in parts)
    v[1] = "@organ r:%d |: %s %s" % (intro, sop, sop)
    v[2] = "@reed r:%d |: %s %s" % (intro, alto, alto)
    v[3] = "@flute r:%d |: %s %s" % (intro, ten, ten)
    bass = text(parts[3], -12)        # an octave down: the SIDs go low
    v[4] = "@bass r:%d |: %s %s" % (intro, bass, bass)
    bell = " ".join("e3:%d" % toll for _ in range(strokes))
    # the bell: still through the verses, then it tolls at verse 2's last chord
    last = parts[0][-1][1]
    v[5] = "@bell %s |: r:%d r:%d e3:%d" % (bell, verse, verse - last, last)
    v[6] = "@glock r:%d |: r:%d %s" % (intro, verse, text(parts[0], 12))

    out = [HEADER, "tune carol 14 loop"]
    for i in range(1, 7):
        out.append("v%d: %s" % (i, v[i]))
    t2, once = tannenbaum()
    out += [""] + t2
    t3, once3 = dingdong()
    out += [""] + t3
    parts = {k: lily.parse(v) for k, v in SHCHEDRYK.items()}
    t4, _ = arrange("shchedryk", parts, [("bellp", "soprano", 0, 0, False), ("reed", "alto", 0, 0, False),
                                         ("flute", "tenor", 0, 0, False), ("bass", "bass", 0, -12, False)],
                    9, 2, double=("celesta", "soprano", 12))
    parts = {k: lily.parse(v) for k, v in ROYAL.items()}
    t5, _ = arrange("royal", parts, [("organ", "rightOne", 0, 0, False), ("reed", "rightTwo", 0, 0, False),
                                     ("flute", "leftOne", 0, 0, False), ("bass2", "leftTwo", 0, 0, True)],
                    15, 2, double=("celesta", "rightOne", 12))
    parts = {k: lily.parse(v) for k, v in SILENT.items()}
    t6, _ = arrange("silent", parts, [("organ", "melody", 0, 0, False), ("reed", "second", 0, 0, False),
                                      ("bass2", "bass", 0, 0, False)],
                    12, 1, double=("celesta", "melody", 12))
    out += [""] + t4 + [""] + t5 + [""] + t6
    with open(sys.argv[1], "w") as f:
        f.write("\n".join(out) + "\n")
    print("carol: a verse %d ticks, the tolling %d; tannenbaum: %d ticks once through"
          % (verse, intro, once))


if __name__ == "__main__":
    main()
