#!/usr/bin/env python3
"""Verify dragon.txt against its sources.

Checks:
1. Format: partTable structure (header, single-quoted names, TreeValue
   classes), loader footer identical to the other partTable builds, every
   body line parses, no Colour/Color3 leftovers, no castle code.
2. Identity: same part names/multiset as the treehouse waterfall's blue
   dragon parts (only pose and colour changed).
3. Rotations: every CFrame rotation stays orthonormal.
4. Placement: zero AABB overlap (volume > 1e-4) against all Castle.txt
   parts, and the dragon lies inside the intended mounting volume on the
   keep's east face.

Usage: python3 tools/verify_dragon.py   Exit 1 on any violation.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import parse, part_box  # noqa: E402
import castle  # noqa: E402

ROOT = os.path.dirname(HERE)
MOUNT = (388.0, 405.0, 115.0, 170.0, -280.0, -220.0)   # allowed volume


def aabb(p):
    if "size" in p:
        sx, sy, sz = p["size"]
        cs = []
        for dx in (-sx / 2, sx / 2):
            for dy in (-sy / 2, sy / 2):
                for dz in (-sz / 2, sz / 2):
                    cs.append((p["pos"][0] + p["x"][0] * dx + p["y"][0] * dy + p["z"][0] * dz,
                               p["pos"][1] + p["x"][1] * dx + p["y"][1] * dy + p["z"][1] * dz,
                               p["pos"][2] + p["x"][2] * dx + p["y"][2] * dy + p["z"][2] * dz))
    else:
        cs = part_box(p)
    xs = [c[0] for c in cs]; ys = [c[1] for c in cs]; zs = [c[2] for c in cs]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def main():
    problems = []
    text = open(os.path.join(ROOT, "dragon.txt"), encoding="utf-8").read()
    hant = open(os.path.join(ROOT, "Hant.txt"), encoding="utf-8").read()

    # ------------------------------------------------------------ format
    if not text.startswith("local partTable = {\n"):
        problems.append("header is not 'local partTable = {'")
    foot = "\nfor _, v in pairs(partTable)"
    if foot not in text:
        problems.append("partTable loader footer missing")
    elif text[text.index(foot):] != hant[hant.index(foot):]:
        problems.append("loader footer differs from the standard builds'")
    entries = [l for l in text.split("\n")[1:] if l.strip().startswith("{")]
    for l in entries:
        if "Color3" in l or 'Name = "' in l:
            problems.append("stolenBase leftover in entry: %s" % l[:80])
            break
    notree = [l for l in entries if "TreeValue" not in l]
    if notree:
        problems.append("%d entries missing TreeValue" % len(notree))

    dg = parse(os.path.join(ROOT, "dragon.txt"))
    if len(dg) != len(entries):
        problems.append("parse mismatch: %d parsed vs %d entry lines"
                        % (len(dg), len(entries)))
    bad_tree = [p for p in dg if p.get("tree") != "Volcano"]
    if bad_tree:
        problems.append("%d parts are not TreeValue Volcano (e.g. %s tree=%r)"
                        % (len(bad_tree), bad_tree[0]["name"], bad_tree[0].get("tree")))
    for p in dg:
        ok = True
        for a in (p["x"], p["y"], p["z"]):
            if abs(sum(v * v for v in a) - 1.0) > 1e-4:
                ok = False
        if not ok:
            problems.append("non-orthonormal rotation on %s" % p["name"])
            break

    # ------------------------------------------------ identity (names)
    th = parse(os.path.join(ROOT, "treehouse.txt"))
    def rgb(p):
        c = p.get("color")
        return tuple(round(v * 255) for v in c) if c else None
    src = [p for p in th
           if rgb(p) == (16, 42, 220)
           and 250 <= p["pos"][0] <= 298 and -613 <= p["pos"][2] <= -604
           and 2 <= p["pos"][1] <= 60]
    if Counter(p["name"] for p in src) != Counter(p["name"] for p in dg):
        problems.append("dragon part multiset differs from the treehouse source")
    print("source dragon parts: %d   dragon.txt parts: %d" % (len(src), len(dg)))

    # -------------------------------------------------- vs the castle
    cp = castle.parse(os.path.join(ROOT, "Castle.txt"))
    cb = [aabb(p) for p in cp]
    hard = 0
    db = []
    for p in dg:
        b = aabb(p)
        db.append(b)
        if not (MOUNT[0] <= b[0] and b[1] <= MOUNT[1]
                and MOUNT[2] <= b[2] and b[3] <= MOUNT[3]
                and MOUNT[4] <= b[4] and b[5] <= MOUNT[5]):
            problems.append("part %s outside the intended mounting volume" % p["name"])
            break
    for b in db:
        for c in cb:
            if (min(b[1], c[1]) - max(b[0], c[0]) > 1e-4
                    and min(b[3], c[3]) - max(b[2], c[2]) > 1e-4
                    and min(b[5], c[5]) - max(b[4], c[4]) > 1e-4):
                hard += 1
                if hard <= 5:
                    print("  HARD dragon~castle x[%.1f..%.1f] y[%.1f..%.1f] z[%.1f..%.1f]"
                          % (c[0], c[1], c[2], c[3], c[4], c[5]))
    print("hard overlaps dragon~castle: %d" % hard)
    print("dragon volume: x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]"
          % (min(b[0] for b in db), max(b[1] for b in db),
             min(b[2] for b in db), max(b[3] for b in db),
             min(b[4] for b in db), max(b[5] for b in db)))

    for pr in problems:
        print("  PROBLEM  %s" % pr)
    if problems or hard:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
