#!/usr/bin/env python3
"""Raster-scan every floor level of a build export and report gaps.

For each expected floor region, cells on a 0.25-stud grid are marked when a
floor slab at that level covers them; every uncovered cell inside the region
is a hole.  Connected hole regions are merged and reported as rectangles.

Usage: python3 tools/floor_scan.py [file]   (default: Halloween.txt)
Exit code 1 if any gap is found, 0 if all floors are solid.
"""
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build3d import parse, part_box  # noqa: E402

RES = 0.25

# (label, level_y, x0, x1, z0, z1, intentional holes [(x0,x1,z0,z1)])
LEVELS = [
    ("plot ground (whole plot)", 0.2, 303, 463, -330, -170, []),
    ("manor level 2", 12.4, 351, 415, -306, -266,
     [(359, 375, -306, -298), (391, 407, -306, -298)]),   # ladder hatches
    ("porch balcony", 12.4, 375, 391, -266, -250, []),
    ("manor roof", 20.5, 351, 415, -306, -266, []),
    ("tower W top deck", 28.5, 359, 375, -266, -250, []),
    ("tower E top deck", 28.5, 391, 407, -266, -250, []),
    ("crypt deck", 12.5, 371, 395, -330, -314, []),
    ("stone path", 0.4, 379, 387, -248, -176, []),
]

Y_TOL = 0.55          # a floor part belongs to a level if |dy| <= Y_TOL
TINY = 0.30           # ignore hole areas smaller than this (grid rounding)


def floor_boxes(parts, level_y):
    boxes = []
    for p in parts:
        if not p["name"].startswith("Floor"):
            continue
        if abs(p["pos"][1] - level_y) > Y_TOL:
            continue
        cs = part_box(p)
        xs = [c[0] for c in cs]
        zs = [c[2] for c in cs]
        boxes.append((min(xs), max(xs), min(zs), max(zs)))
    return boxes


def scan(label, y, x0, x1, z0, z1, holes, boxes):
    nx = int(round((x1 - x0) / RES))
    nz = int(round((z1 - z0) / RES))
    covered = bytearray(nx * nz)
    in_hole = bytearray(nx * nz)
    for bx0, bx1, bz0, bz1 in boxes:
        i0 = max(0, int((bx0 - x0) / RES + 1e-6))
        i1 = min(nx, int((bx1 - x0) / RES + 1e-6) + 1)
        j0 = max(0, int((bz0 - z0) / RES + 1e-6))
        j1 = min(nz, int((bz1 - z0) / RES + 1e-6) + 1)
        for i in range(i0, i1):
            base = i * nz
            for j in range(j0, j1):
                covered[base + j] = 1
    for hx0, hx1, hz0, hz1 in holes:
        i0 = max(0, int((hx0 - x0) / RES + 1e-6))
        i1 = min(nx, int((hx1 - x0) / RES + 1e-6) + 1)
        j0 = max(0, int((hz0 - z0) / RES + 1e-6))
        j1 = min(nz, int((hz1 - z0) / RES + 1e-6) + 1)
        for i in range(i0, i1):
            base = i * nz
            for j in range(j0, j1):
                in_hole[base + j] = 1

    gaps = []
    seen = bytearray(nx * nz)
    for i in range(nx):
        for j in range(nz):
            k = i * nz + j
            if covered[k] or in_hole[k] or seen[k]:
                continue
            # flood-fill this hole region
            q = deque([(i, j)])
            seen[k] = 1
            cells = []
            gi0, gi1, gj0, gj1 = i, i, j, j
            while q:
                a, b = q.popleft()
                cells.append((a, b))
                gi0, gi1 = min(gi0, a), max(gi1, a)
                gj0, gj1 = min(gj0, b), max(gj1, b)
                for na, nb in ((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)):
                    if 0 <= na < nx and 0 <= nb < nz:
                        nk = na * nz + nb
                        if not covered[nk] and not in_hole[nk] and not seen[nk]:
                            seen[nk] = 1
                            q.append((na, nb))
            area = len(cells) * RES * RES
            if area < TINY:
                continue
            rect = (x0 + gi0 * RES, x0 + (gi1 + 1) * RES,
                    z0 + gj0 * RES, z0 + (gj1 + 1) * RES)
            fills = abs((rect[1] - rect[0]) * (rect[3] - rect[2]) - area) < RES * RES
            gaps.append((rect, area, fills))
    return gaps


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Halloween.txt")
    parts = parse(path)
    print("scanning %s (%d parts)" % (os.path.basename(path), len(parts)))
    total = 0
    for label, y, x0, x1, z0, z1, holes in LEVELS:
        boxes = floor_boxes(parts, y)
        gaps = scan(label, y, x0, x1, z0, z1, holes, boxes)
        if not gaps:
            print("  OK    %-26s solid" % label)
            continue
        print("  GAP   %-26s %d hole(s):" % (label, len(gaps)))
        for (rx0, rx1, rz0, rz1), area, fills in sorted(gaps, key=lambda g: -g[1]):
            total += 1
            shape = "rect" if fills else "irregular"
            print("          x[%.2f..%.2f] z[%.2f..%.2f]  %.2f x %.2f  area %.2f  [%s]"
                  % (rx0, rx1, rz0, rz1, rx1 - rx0, rz1 - rz0, area, shape))
    if total:
        print("\n%d gap region(s) found" % total)
        return 1
    print("\nno floor gaps found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
