#!/usr/bin/env python3
"""shot.py — a screenshot of a PRG in headless xemu, booted as `make run`
boots it (no -fastboot): a fast boot leaves the VIC-IV in a state a normal
one does not, which hid a palette written too early.

    python3 tools/shot.py program.prg /abs/path/out.png [disk.d81]

A disk goes in drive 8 (the program loads its overlays and data from it).

CAPTURE_DELAY (seconds after the program is in memory) and PEEK as
witchingHour/tools/screenshot.py, whose capture() this uses.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "witchingHour", "tools"))
import screenshot  # noqa: E402

_popen = subprocess.Popen


def popen(args, **kw):
    return _popen([a for a in args if a != "-fastboot"], **kw)


screenshot.subprocess.Popen = popen
screenshot.OUT = os.path.dirname(os.path.abspath(sys.argv[2]))
name = os.path.splitext(os.path.basename(sys.argv[2]))[0]
sys.exit(0 if screenshot.capture(name, sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else None) else 1)
