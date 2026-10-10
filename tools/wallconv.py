#!/usr/bin/env python3
"""For every build file, find runs of wall/pane/door parts stepping 4 along an
axis and report which rotation is used for X-runs vs Z-runs."""
import os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from build3d import parse

WALLS = {"Wall2Tall", "Wall2Short", "Wall2", "GlassPane4", "GlassPane2",
         "GlassDoor1", "Wall2TallThin", "Wall2ShortThin", "Wall3TallThin"}

KNOWN = {
    (1, 0, 0, 0, 1, 0, 0, 0, 1): "ID",
    (0, 0, -1, 0, 1, 0, 1, 0, 0): "R90",
    (-1, 0, 0, 0, 1, 0, 0, 0, -1): "R180",
    (0, 0, 1, 0, 1, 0, -1, 0, 0): "R270",
}


def rotsig(p):
    flat = tuple(round(v) for ax in (p["x"], p["y"], p["z"]) for v in ax)
    return KNOWN.get(flat, "other")


root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(f for f in os.listdir(root) if f.endswith(".txt"))
for f in files:
    parts = parse(os.path.join(root, f))
    groups = defaultdict(list)
    for p in parts:
        if p["name"] not in WALLS:
            continue
        groups[(p["name"], round(p["pos"][1], 1))].append(p)
    xrun = Counter()
    zrun = Counter()
    for key, ps in groups.items():
        bypos = {(round(p["pos"][0], 1), round(p["pos"][2], 1)): p for p in ps}
        for (x, z), p in bypos.items():
            if (x + 4, z) in bypos:
                xrun[rotsig(p)] += 1
            if (x, z + 4) in bypos:
                zrun[rotsig(p)] += 1
    print("%-24s X-runs: %-42s Z-runs: %s" % (f, dict(xrun), dict(zrun)))
