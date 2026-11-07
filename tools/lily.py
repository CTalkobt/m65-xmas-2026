"""lily.py — the little of LilyPond the demo's scores use, to notes.

    events = parse(r"\\relative c' { d8 | <d b>2 q4 r8 ... }")

Relative mode: a note's octave is the one that puts it within a fourth of
the note before (by letter name), then ' and , move it; in a chord each
note is relative to the one before it in the chord, the first to the
reference before the chord, and after the chord the reference is its first
note. `q` repeats the last chord. Durations 1 2 4 8 16, dotted, carry on to
the notes after (as LilyPond). `~` ties to the next. `r` a rest, `s` a
spacer (a rest). Note names are Dutch, as LilyPond's: bes, fis, and es, as
(E flat, A flat). `\\repeat volta N { ... }` and `\\repeat unfold N { ... }`
are written out N times; a volta repeat with `\\alternative { {A} {B} }` as
the body, A, the body, B (the last ending for any time past the endings').
`R2.` is a whole bar's rest (`R2.*3`: three). Pitches are worked out in the
order written, before the repeats are written out, as LilyPond does. Commands
(\\pp, \\global, \\bar "|." ...), strings, marks (^"Fine"), slurs, beams
and `|` are skipped.

An event is (pitches, ticks, tie): pitches a list of MIDI notes (empty: a
rest), ticks in sixteenths, tie whether it is tied on.
"""
import re

LETTERS = "cdefgab"
SEMI = [0, 2, 4, 5, 7, 9, 11]
NAMES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]
DUR = {1: 16, 2: 8, 4: 4, 8: 2, 16: 1}

TOKEN = re.compile(r'\\repeat\s+(?:volta|unfold)\s+\d+\s*\{|\\alternative\s*\{|R(?:\d+\.?)?(?:\*\d+)?|\\[a-zA-Z]+|"[^"]*"|\^|<|>(?:\d+\.?)?|~|q(?:\d+\.?)?|'
                   r"(?:as|es|[a-g])(?:isis|eses|is|es)?[',]*!?(?:\d+\.?)?|[rs](?:\d+\.?)?|\||\{|\}|\S")
NOTE = re.compile(r"(as|es|[a-g])((?:isis|eses|is|es)?)([',]*)!?(\d*)(\.?)")


def _step(prev, letter, marks):
    step = prev - prev % 7 + letter
    while step - prev > 3:
        step -= 7
    while prev - step > 3:
        step += 7
    return step + 7 * (marks.count("'") - marks.count(","))


def _midi(step, acc):
    return 12 * (step // 7 + 1) + SEMI[step % 7] + acc


def _dur(num, dot, last):
    if not num:
        return last
    t = DUR[int(num)]
    return t * 3 // 2 if dot else t


def parse(src):
    m = re.match(r"\s*\\relative c([',]*)\s*\{(.*)\}\s*$", src, re.S)
    if not m:
        raise ValueError("expected \\relative c... { ... }")
    prev = (3 + m.group(1).count("'") - m.group(1).count(",")) * 7
    events = []
    ticks = 4
    chord = None              # the pitches of a chord being read
    chord_first = None
    last_chord = []
    frames = []               # a brace each: [kind, first event, times, endings]
    pending = None            # a volta repeat just closed: (first event, times)

    def write_out(first, times):
        events[first:] = events[first:] * times

    for tok in TOKEN.findall(m.group(2)):
        if pending and not tok.startswith("\\alternative"):
            write_out(*pending)
            pending = None
        if tok.startswith("\\repeat"):
            n = int(re.search(r"(\d+)", tok).group(1))
            frames.append(["volta" if "volta" in tok else "unfold", len(events), n, None])
            continue
        if tok.startswith("\\alternative"):
            first, times = pending
            pending = None
            frames.append(["endings", first, times, []])
            continue
        if tok == "{":
            kind = "ending" if frames and frames[-1][0] == "endings" else "plain"
            frames.append([kind, len(events), 1, None])
            continue
        if tok == "}":
            kind, first, times, endings = frames.pop()
            if kind == "unfold":
                write_out(first, times)
            elif kind == "volta":
                pending = (first, times)
            elif kind == "ending":
                frames[-1][3].append(events[first:])
                del events[first:]
            elif kind == "endings":
                body = events[first:]
                del events[first:]
                for i in range(times):
                    events += body + endings[min(i, len(endings) - 1)]
            continue
        if tok[0] == "R":
            d = re.match(r"R(\d*)(\.?)(?:\*(\d+))?", tok)
            events.append([[], _dur(d.group(1), d.group(2), ticks) * int(d.group(3) or 1), False])
            continue
        if tok.startswith("\\") or tok.startswith('"') or tok in ("^", "|"):
            continue
        if tok == "<":
            chord, chord_ref = [], prev
            continue
        if tok.startswith(">"):
            d = re.match(r">(\d*)(\.?)", tok)
            ticks = _dur(d.group(1), d.group(2), ticks)
            events.append([sorted(chord, reverse=True), ticks, False])
            last_chord = chord
            prev = chord_first
            chord = None
            continue
        if tok == "~":
            if events:
                events[-1][2] = True
            continue
        if tok[0] == "q":
            d = re.match(r"q(\d*)(\.?)", tok)
            ticks = _dur(d.group(1), d.group(2), ticks)
            events.append([sorted(last_chord, reverse=True), ticks, False])
            continue
        if tok[0] in "rs":
            d = re.match(r"[rs](\d*)(\.?)", tok)
            ticks = _dur(d.group(1), d.group(2), ticks)
            events.append([[], ticks, False])
            continue
        n = NOTE.fullmatch(tok)
        if not n:
            continue
        acc = n.group(2).count("is") - n.group(2).count("es") - (n.group(1) in ("as", "es"))
        if chord is not None:
            ref = chord_ref if not chord else chord_prev
            step = _step(ref, LETTERS.index(n.group(1)[0]), n.group(3))
            if not chord:
                chord_first = step
            chord_prev = step
            chord.append(_midi(step, acc))
            continue
        step = _step(prev, LETTERS.index(n.group(1)[0]), n.group(3))
        prev = step
        ticks = _dur(n.group(4), n.group(5), ticks)
        events.append([[_midi(step, acc)], ticks, False])
    if pending:
        write_out(*pending)
    return [tuple(e) for e in events]


def length(events):
    return sum(t for _, t, _ in events)


def name(midi):
    return "%s%d" % (NAMES[midi % 12], midi // 12 - 1)


def voice(events, i, shift=0, scale=1, bottom=False):
    """tune45 tokens for the i-th note from the top of each event (from the
    bottom: a left hand's single notes are its bass), a rest where an event
    has fewer; a tie on to the same pitch is a ~"""
    out = []
    held = None
    for pitches, t, tie in events:
        t *= scale
        if bottom:
            pitches = pitches[::-1]
        p = pitches[i] + shift if i < len(pitches) else None
        if p is not None and held == p:
            out.append("~:%d" % t)
        elif p is None:
            out.append("r:%d" % t)
        else:
            out.append("%s:%d" % (name(p), t))
        held = p if tie else None
    return " ".join(out)
