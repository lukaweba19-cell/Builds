#!/usr/bin/env python3
"""Raster-scan Hant.txt (and similar stolenBase exports) for floor gaps.

Method
------
1. Collect all floor-like parts (Floor*, CounterTop* = deck tiles) and cluster
   their y values into levels (gap <= 0.6 studs).
2. For each level with meaningful area, rasterise at 0.25 stud resolution:
   - COVERED: floor/deck tiles whose vertical span contains the level plane.
   - BARRIER: walls/posts/doors/rails whose footprint crosses the plane
     (a floor legitimately ends at a wall; the wall closes the region).
3. Every uncovered cell that cannot reach the raster border without crossing
   COVERED or BARRIER is an enclosed floor gap. Cells crossed by any other
   part (stairs, ladders, furniture) are excluded -- a floor there would
   collide or block the stairwell.
4. Prints per-level ASCII maps (2-stud display cells: '#'=floor, '|'=wall,
   'X'=GAP, 'x'=excluded, ' '=open) and a gap list.

Usage: python3 tools/hant_scan.py [file] [min_area_studs2]
Exit 1 when gaps are found.
"""
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build3d import parse, part_box  # noqa: E402

RES = 0.25
CLUSTER_GAP = 0.6
DEFAULT_MIN_AREA = 1.0

SURFACE = ("Floor", "CounterTop")      # counts as floor coverage
BARRIER = ("Wall", "Door", "Post", "Rail", "Fence", "Lever")
NOT_IN_FILL = ("Stair", "Ladder", "Chair", "Painting", "Utility", "Glass",
               "Wedge", "Lever")


def clusters(parts):
    ys = sorted({round(p["pos"][1], 2) for p in parts
                 if p["name"].startswith(SURFACE)})
    groups = []
    for y in ys:
        if groups and y - groups[-1][-1] <= CLUSTER_GAP:
            groups[-1].append(y)
        else:
            groups.append([y])
    return [(sum(g) / len(g), set(g)) for g in groups]


def xz(p):
    cs = part_box(p)
    xs = [c[0] for c in cs]
    zs = [c[2] for c in cs]
    return min(xs), max(xs), min(zs), max(zs)


def scan_level(parts, ylev, members, min_area, ys=None):
    ys = ys or {round(ylev, 2)}
    band0, band1 = min(ys), max(ys)
    boxes = [xz(p) for p in members]
    if not boxes:
        return None, []
    x0 = min(b[0] for b in boxes) - 4
    x1 = max(b[1] for b in boxes) + 4
    z0 = min(b[2] for b in boxes) - 4
    z1 = max(b[3] for b in boxes) + 4
    nx = int((x1 - x0) / RES) + 1
    nz = int((z1 - z0) / RES) + 1

    covered = bytearray(nx * nz)
    barrier = bytearray(nx * nz)
    excluded = bytearray(nx * nz)

    def mark(buf, bx0, bx1, bz0, bz1):
        i0 = max(0, int((bx0 - x0) / RES + 1e-6))
        i1 = min(nx, int((bx1 - x0) / RES + 1e-6) + 1)
        j0 = max(0, int((bz0 - z0) / RES + 1e-6))
        j1 = min(nz, int((bz1 - z0) / RES + 1e-6) + 1)
        for i in range(i0, i1):
            base = i * nz
            for j in range(j0, j1):
                buf[base + j] = 1

    member_ids = {id(p) for p in members}
    for p in parts:
        bx0, bx1, bz0, bz1 = xz(p)
        n = p["name"]
        if n.startswith(SURFACE):
            # every tile of this level's cluster counts as coverage
            # (freehand builds stack deck tiles at slightly different ys;
            # membership is decided by the level cluster, not span tests)
            if round(p["pos"][1], 2) in ys:
                mark(covered, bx0, bx1, bz0, bz1)
        elif n.startswith(BARRIER):
            cs = part_box(p)
            ymin = min(c[1] for c in cs)
            ymax = max(c[1] for c in cs)
            # a wall stands on this level if its base sits in the band
            if ymin <= band1 + 0.8 and ymax >= band0 - 0.4:
                mark(barrier, bx0, bx1, bz0, bz1)
        elif n.startswith(NOT_IN_FILL):
            cs = part_box(p)
            ymin = min(c[1] for c in cs)
            ymax = max(c[1] for c in cs)
            if ymin <= band1 + 0.3 and ymax >= band0 - 0.3:
                mark(excluded, bx0, bx1, bz0, bz1)

    # flood from border through cells that are neither covered nor barrier
    reach = bytearray(nx * nz)
    q = deque()
    for i in range(nx):
        for j in (0, nz - 1):
            k = i * nz + j
            if (not covered[k] and not barrier[k] and not excluded[k]
                    and not reach[k]):
                reach[k] = 1
                q.append((i, j))
    for j in range(nz):
        for i in (0, nx - 1):
            k = i * nz + j
            if (not covered[k] and not barrier[k] and not excluded[k]
                    and not reach[k]):
                reach[k] = 1
                q.append((i, j))
    while q:
        a, b = q.popleft()
        for na, nb in ((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)):
            if 0 <= na < nx and 0 <= nb < nz:
                nk = na * nz + nb
                if (not covered[nk] and not barrier[nk] and not excluded[nk]
                        and not reach[nk]):
                    reach[nk] = 1
                    q.append((na, nb))

    gaps = []
    seen = bytearray(nx * nz)
    for i in range(nx):
        for j in range(nz):
            k = i * nz + j
            if covered[k] or barrier[k] or reach[k] or seen[k]:
                continue
            if excluded[k]:
                # still flood it so it is one region, but mark as excluded
                pass
            q = deque([(i, j)])
            seen[k] = 1
            cells = []
            free = 0
            gi0, gi1, gj0, gj1 = i, i, j, j
            while q:
                a, b = q.popleft()
                cells.append((a, b))
                if not excluded[a * nz + b]:
                    free += 1
                gi0, gi1 = min(gi0, a), max(gi1, a)
                gj0, gj1 = min(gj0, b), max(gj1, b)
                for na, nb in ((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)):
                    if 0 <= na < nx and 0 <= nb < nz:
                        nk = na * nz + nb
                        if (not covered[nk] and not barrier[nk]
                                and not reach[nk] and not seen[nk]):
                            seen[nk] = 1
                            q.append((na, nb))
            area = free * RES * RES
            if area < min_area:
                continue
            gaps.append({
                "rect": (x0 + gi0 * RES, x0 + (gi1 + 1) * RES,
                         z0 + gj0 * RES, z0 + (gj1 + 1) * RES),
                "area": area,
                "cells": cells,
                "free_cells": free,
            })

    meta = (x0, z0, nx, nz, covered, barrier, excluded, reach, gaps)
    return meta, gaps


def ascii_level(meta, step_cells=8):
    x0, z0, nx, nz, covered, barrier, excluded, reach, gaps = meta
    gapset = set()
    for g in gaps:
        for c in g["cells"]:
            gapset.add(c)
    dw = nx // step_cells
    dh = nz // step_cells
    lines = []
    for dj in range(dh):
        row = []
        for di in range(dw):
            ch = " "
            best = " "
            for cj in range(step_cells):
                for ci in range(step_cells):
                    i, j = di * step_cells + ci, dj * step_cells + cj
                    if i >= nx or j >= nz:
                        continue
                    k = i * nz + j
                    if (i, j) in gapset:
                        c = "X" if not excluded[k] else "x"
                    elif covered[k]:
                        c = "#"
                    elif barrier[k]:
                        c = "|"
                    else:
                        c = " "
                    if c in ("X", "x"):
                        best = c
                    elif best == " " and c != " ":
                        best = c
            row.append(best)
        lines.append("%6.0f " % (z0 + dj * step_cells * RES) + "".join(row))
    header = "       " + "".join(
        (str(int((x0 + di * step_cells * RES) // 10) % 10)
         if di % 4 == 0 else " ") for di in range(dw))
    return header + "\n" + "\n".join(lines)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "Hant.txt"
    min_area = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MIN_AREA
    parts = parse(path)
    print("scanning %s (%d parts)" % (os.path.basename(path), len(parts)))
    levs = clusters(parts)
    total = 0
    for ylev, ys in levs:
        members = [p for p in parts
                   if p["name"].startswith(SURFACE)
                   and round(p["pos"][1], 2) in ys]
        if len(members) < 6:
            continue
        meta, gaps = scan_level(parts, ylev, members, min_area, ys)
        if meta is None:
            continue
        label = "y=%.2f..%.2f (tiles=%d, ys=%d)" % (
            min(ys), max(ys), len(members), len(ys))
        if not gaps:
            print("  OK    %s solid" % label)
            continue
        area_sum = sum(g["area"] for g in gaps)
        print("  GAP   %s  %d hole(s), %.1f studs2" % (
            label, len(gaps), area_sum))
        total += len(gaps)
        print(ascii_level(meta))
        for g in sorted(gaps, key=lambda g: -g["area"])[:8]:
            r = g["rect"]
            print("        x[%.2f..%.2f] z[%.2f..%.2f]  area %.2f"
                  % (r[0], r[1], r[2], r[3], g["area"]))
    print("\n%d gap region(s)" % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
