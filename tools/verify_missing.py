#!/usr/bin/env python3
"""Verify a gap-fill file against its source build.

Checks:
1. Format: same header/footer as the source, every line parses as a part.
2. Hard overlaps: a fill may overlap existing floor tiles by design (the
   <=0.75-stud coplanar slide) and may tuck under a wall slide, but it must
   NEVER overlap another fill, nor any solid part (walls, wedges, furniture).
3. Coverage: re-scan every level with the fills added and report how many
   enclosed gap cells remain (should be only sub-stud slivers / cells that are
   physically blocked by other solids).

Usage: python3 tools/verify_missing.py [src] [fills]   (default Hant.txt missing.txt)
Exit 1 on hard violations.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import parse, part_box  # noqa: E402
import hant_scan as hs  # noqa: E402

EPS = 1e-6
MIN_AREA = 1.0


def aabb(p):
    cs = part_box(p)
    xs = [c[0] for c in cs]
    ys = [c[1] for c in cs]
    zs = [c[2] for c in cs]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def overlap(a, b):
    """(volume, per-axis overlap) of two AABBs; volume 0 when disjoint."""
    ox = min(a[1], b[1]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[2], b[2])
    oz = min(a[5], b[5]) - max(a[4], b[4])
    if ox <= EPS or oy <= EPS or oz <= EPS:
        return 0.0, (0.0, 0.0, 0.0)
    return ox * oy * oz, (ox, oy, oz)


def check_format(src_text, fills_text, fills):
    problems = []
    if fills_text.split("\n", 1)[0] != src_text.split("\n", 1)[0]:
        problems.append("header differs from source")
    sf = src_text.split("\nfor _, v in pairs(partTable)", 1)
    ff = fills_text.split("\nfor _, v in pairs(partTable)", 1)
    if len(sf) != 2 or len(ff) != 2 or sf[1] != ff[1]:
        problems.append("footer differs from source")
    lines = [l for l in ff[0].split("\n")[1:] if l.strip()]
    if len(lines) != len(fills):
        problems.append("parse mismatch: %d parsed vs %d body lines"
                        % (len(fills), len(lines)))
    return problems


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "Hant.txt"
    fills_path = sys.argv[2] if len(sys.argv) > 2 else "missing.txt"
    src_text = open(src, encoding="utf-8").read()
    fills_text = open(fills_path, encoding="utf-8").read()
    src_parts = parse(src)
    fills = parse(fills_path)
    print("source: %s (%d parts)   fills: %s (%d parts)"
          % (os.path.basename(src), len(src_parts),
             os.path.basename(fills_path), len(fills)))

    problems = check_format(src_text, fills_text, fills)
    for p in problems:
        print("  FORMAT  %s" % p)

    fboxes = [aabb(p) for p in fills]
    hbox = [aabb(p) for p in src_parts]
    hsurf = [p["name"].startswith(hs.SURFACE) for p in src_parts]

    hard = 0
    slide = 0
    max_slide = 0.0
    # fill vs fill
    for i in range(len(fills)):
        for j in range(i + 1, len(fills)):
            v, o = overlap(fboxes[i], fboxes[j])
            if v > 1e-4:
                hard += 1
                if hard <= 5:
                    print("  HARD fill~fill %s x %s  ov=%.3f"
                          % (fills[i]["name"], fills[j]["name"], v))
    # fill vs source
    for i, fb in enumerate(fboxes):
        near = [k for k, hb in enumerate(hbox)
                if not (fb[1] <= hb[0] + EPS or fb[0] >= hb[1] - EPS
                or fb[3] <= hb[2] + EPS or fb[2] >= hb[3] - EPS
                or fb[5] <= hb[4] + EPS or fb[4] >= hb[5] - EPS)]
        for k in near:
            v, o = overlap(fb, hbox[k])
            if v <= 1e-4:
                continue
            if hsurf[k]:
                slide += 1
                d = min(o[0], o[2])
                max_slide = max(max_slide, d)
            else:
                hard += 1
                if hard <= 8:
                    print("  HARD fill~%s %s x %s ov=%.3f axes=%.2f/%.2f/%.2f"
                          % ("solid", fills[i]["name"], src_parts[k]["name"],
                             v, o[0], o[1], o[2]))
    print("designed floor-tile slides: %d (max depth %.2f studs)" % (slide, max_slide))
    print("hard overlaps: %d" % hard)

    # --------------------------------------------------------- coverage
    combined = src_parts + fills
    levs = hs.clusters(combined)
    before = after = 0.0
    for ylev, ys in levs:
        members = [p for p in combined
                   if p["name"].startswith(hs.SURFACE)
                   and round(p["pos"][1], 2) in ys]
        if len(members) < 6:
            continue
        meta, gaps = hs.scan_level(combined, ylev, members, MIN_AREA, ys)
        if meta is None:
            continue
        after += sum(g["area"] for g in gaps)
    levs0 = hs.clusters(src_parts)
    for ylev, ys in levs0:
        members = [p for p in src_parts
                   if p["name"].startswith(hs.SURFACE)
                   and round(p["pos"][1], 2) in ys]
        if len(members) < 6:
            continue
        meta, gaps = hs.scan_level(src_parts, ylev, members, MIN_AREA, ys)
        if meta is None:
            continue
        before += sum(g["area"] for g in gaps)
    print("enclosed gap area: before %.1f studs2 -> after %.1f studs2 "
          "(%.1f%% closed)" % (before, after,
                               100.0 * (before - after) / before if before else 0))

    if problems or hard:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
