#!/usr/bin/env python3
"""Generate missing.txt: ONLY the parts needed to close Hant.txt's floor gaps.

Reuses hant_scan's raster model (levels, coverage, barriers, exclusions) and
greedily packs floor tiles into every enclosed gap region, largest class first
(the level's own floor type at its native size, then 2x2, then 1x1), matching
the height, colour and material of the nearest existing tile.  Sub-stud
slivers against walls may slide at most 0.75 studs under the wall so the floor
meets the wall with no hairline.

Usage: python3 tools/gen_missing.py [src] [out]
Exit 0 on success (always writes the file; prints a report).
"""
import os
import sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import parse, part_box, PART_SIZE  # noqa: E402
import hant_scan as hs  # noqa: E402

RES = hs.RES
MIN_AREA = 1.0
IDENTITY = "1.000000, 0.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000, 0.000000, 1.000000"

# sub-tile names by class size, used when the primary type has no smaller size
SUB = {2: "Floor2Small", 1: "Floor2Tiny"}


def top_of(p):
    cs = part_box(p)
    return max(c[1] for c in cs)


def nominal_top(p):
    """Deck top for a member: never let a vertically-placed panel's height
    inflate the floor level (Hant uses floor slabs as wall panels)."""
    h = PART_SIZE.get(p["name"], (2, 0.2, 2))[1]
    return min(top_of(p), p["pos"][1] + h / 2.0 + 0.05)


def xz_box(p):
    cs = part_box(p)
    xs = [c[0] for c in cs]
    zs = [c[2] for c in cs]
    return min(xs), max(xs), min(zs), max(zs)


def rasterize(parts, ylev, members, ys):
    """Coverage + barriers + exclusions + source map (tile ref per cell)."""
    band0, band1 = min(ys), max(ys)
    boxes = [xz_box(p) for p in members]
    x0 = min(b[0] for b in boxes) - 4
    x1 = max(b[1] for b in boxes) + 4
    z0 = min(b[2] for b in boxes) - 4
    z1 = max(b[3] for b in boxes) + 4
    nx = int((x1 - x0) / RES) + 1
    nz = int((z1 - z0) / RES) + 1

    covered = bytearray(nx * nz)
    barrier = bytearray(nx * nz)
    excluded = bytearray(nx * nz)
    source = [None] * (nx * nz)          # tile index per covered cell
    excl_parts = []                      # precise geometry of excluded parts
    bar_parts = []                       # precise geometry of barrier parts
    member_ids = {id(p) for p in members}
    mindex = {id(p): i for i, p in enumerate(members)}

    def mark(buf, bx0, bx1, bz0, bz1, src=None):
        i0 = max(0, int((bx0 - x0) / RES + 1e-6))
        i1 = min(nx, int((bx1 - x0) / RES + 1e-6) + 1)
        j0 = max(0, int((bz0 - z0) / RES + 1e-6))
        j1 = min(nz, int((bz1 - z0) / RES + 1e-6) + 1)
        for i in range(i0, i1):
            base = i * nz
            for j in range(j0, j1):
                buf[base + j] = 1
                if src is not None:
                    source[base + j] = src

    for pi, p in enumerate(parts):
        bx0, bx1, bz0, bz1 = xz_box(p)
        n = p["name"]
        if n.startswith(hs.SURFACE):
            if round(p["pos"][1], 2) in ys and id(p) in member_ids:
                mark(covered, bx0, bx1, bz0, bz1, mindex[id(p)])
        elif n.startswith(hs.BARRIER):
            cs = part_box(p)
            ymin = min(c[1] for c in cs)
            ymax = max(c[1] for c in cs)
            if ymin <= band1 + 0.8 and ymax >= band0 - 0.4:
                mark(barrier, bx0, bx1, bz0, bz1)
                bar_parts.append((bx0, bx1, bz0, bz1, ymin, ymax))
        elif n.startswith(hs.NOT_IN_FILL):
            cs = part_box(p)
            ymin = min(c[1] for c in cs)
            ymax = max(c[1] for c in cs)
            if ymin <= band1 + 0.3 and ymax >= band0 - 0.3:
                mark(excluded, bx0, bx1, bz0, bz1)
                excl_parts.append((bx0, bx1, bz0, bz1, ymin, ymax))
    return x0, z0, nx, nz, covered, barrier, excluded, source, excl_parts, bar_parts


def bfs_source(nx, nz, covered, barrier, excluded, gap_cells, source, members):
    """Multi-source BFS from covered cells into the gap region -> per-cell src."""
    region = set(gap_cells)
    dist = {}
    src = {}
    q = deque()
    for (i, j) in gap_cells:
        for na, nb in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if 0 <= na < nx and 0 <= nb < nz:
                k = na * nz + nb
                if covered[k] and source[k] is not None:
                    nk = i * nz + j
                    if nk not in dist:
                        dist[nk] = 1
                        src[nk] = source[k]
                        q.append((i, j))
    while q:
        a, b = q.popleft()
        ka = a * nz + b
        for na, nb in ((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)):
            nk = na * nz + nb
            if nk in region and nk not in dist:
                dist[nk] = dist[ka] + 1
                src[nk] = src[ka]
                q.append((na, nb))
    return src, dist


def _fill(parts, members, x0, z0, nx, nz, covered, barrier, excluded,
          cells, primary_name, src_of, report, excl_parts=(), bar_parts=()):
    free = set(i * nz + j for (i, j) in cells)
    used = set()
    gi0 = min(i for i, j in cells)
    gi1 = max(i for i, j in cells)
    gj0 = min(j for i, j in cells)
    gj1 = max(j for i, j in cells)
    margin = int(0.75 / RES)                     # wall slide (0.75 studs)
    placed = []
    mtops = [nominal_top(p) for p in members]
    level_top = Counter(mtops).most_common(1)[0][0] if mtops else 1.0

    # spatial buckets of excluded and barrier parts (exact solid geometry)
    reach_pad = 3
    buckets = {}
    bbuckets = {}
    for kind, lst, store in ((0, excl_parts, buckets), (1, bar_parts, bbuckets)):
        for (ex0, ex1, ez0, ez1, ey0, ey1) in lst:
            if ex1 < x0 + (gi0 - reach_pad) * RES or ex0 > x0 + (gi1 + reach_pad) * RES:
                continue
            if ez1 < z0 + (gj0 - reach_pad) * RES or ez0 > z0 + (gj1 + reach_pad) * RES:
                continue
            a = int((ex0 - x0) / RES) - 1
            b = int((ex1 - x0) / RES) + 1
            for ix in range(max(a, 0), b + 1):
                store.setdefault(ix, []).append((ex0, ex1, ez0, ez1, ey0, ey1))

    sizes = {PART_SIZE.get(p["name"], (2, 2, 2))[0] for p in members}
    psx = max(sizes) if sizes else 4
    # name for a class: primary when it matches, else a type the file proves
    def cname(sz):
        if PART_SIZE.get(primary_name, (0, 0, 0))[0] == sz:
            return primary_name
        return {8: "Floor1Large", 4: "Floor2", 2: SUB[2], 1: SUB[1]}[sz]
    want = sorted(sizes | {s for s in (4, 2, 1) if s < psx} | {psx},
                  reverse=True)
    classes = [(sz, cname(sz)) for sz in want]

    for size, name in classes:
        h = PART_SIZE.get(name, (size, 0.2, size))[1]
        res = RES
        step = max(1, int(round((size / 2) / res)))
        si = int(round(size / res))
        # candidate span starts, expanded by the wall margin
        i_rng = range(gi0 - margin, gi1 + 1, max(1, step))
        j_rng = range(gj0 - margin, gj1 + 1, max(1, step))
        while True:
            best = None
            best_score = -1
            for i in i_rng:
                for j in j_rng:
                    score = 0
                    ext = 0
                    cov = 0
                    ok = True
                    cells_list = []
                    exc = []
                    bar = []
                    tops_p = []
                    for di in range(si):
                        for dj in range(si):
                            a, b = i + di, j + dj
                            k = a * nz + b
                            if k in free:
                                score += 1
                                cells_list.append(k)
                                s = src_of.get(k)
                                if s is not None:
                                    tops_p.append(s["top"])
                            elif k in used:
                                # already consumed by an earlier fill tile
                                ok = False
                                break
                            elif covered[k]:
                                # coplanar slide into existing tiles, at most
                                # 0.75 studs (outer 3-cell ring) and capped
                                if not (di < 3 or di >= si - 3
                                        or dj < 3 or dj >= si - 3):
                                    ok = False
                                    break
                                cov += 1
                                if cov > 3 * si:
                                    ok = False
                                    break
                                cells_list.append(k)
                            elif excluded[k]:
                                # tentative: accepted only after an exact
                                # solid-overlap test with the tile's height
                                exc.append(k)
                                cells_list.append(k)
                            elif barrier[k]:
                                # wall slide: only inside the 0.75-stud margin
                                if not (gi0 - margin <= a <= gi1 + margin
                                        and gj0 - margin <= b <= gj1 + margin):
                                    ok = False
                                    break
                                ext += 1
                                bar.append(k)
                                cells_list.append(("e", k))
                            else:
                                # open (reachable) cell: never fill
                                ok = False
                                break
                        if not ok:
                            break
                    if not ok or score == 0:
                        continue
                    # always precise-test the real solids whose xz touches the
                    # span (walls can stand on floor-covered cells too)
                    near = any((ix in buckets or ix in bbuckets)
                               for ix in range(i, i + si))
                    if near:
                        if tops_p:
                            tp = Counter(tops_p).most_common(1)[0][0]
                        else:
                            tp = level_top
                        ybot = tp - h
                        ytop = tp
                        xs0 = x0 + i * RES
                        xs1 = xs0 + size
                        zs0 = z0 + j * RES
                        zs1 = zs0 + size
                        bad = False
                        checked = set()
                        for bx in (buckets, bbuckets):
                            for ix in range(i, i + si):
                                for pr in bx.get(ix, ()):
                                    if id(pr) in checked:
                                        continue
                                    checked.add(id(pr))
                                    ex0, ex1, ez0, ez1, ey0, ey1 = pr
                                    if ex1 <= xs0 or ex0 >= xs1:
                                        continue
                                    if ez1 <= zs0 or ez0 >= zs1:
                                        continue
                                    if ey1 <= ybot + 0.02 or ey0 >= ytop - 0.02:
                                        continue
                                    bad = True
                                    break
                                if bad:
                                    break
                            if bad:
                                break
                        if bad:
                            continue
                    # prefer covering free cells; slides are a costly tiebreak
                    sc = score * 10 - ext - cov * 2
                    if sc > best_score:
                        best_score = sc
                        best = cells_list
            if best is None or best_score <= 0:
                break
            # geometry + height + colour from nearest sources
            solid = [k for k in best if not isinstance(k, tuple)]
            cov_cells = [k for k in solid if covered[k]]
            rows = []
            cols = []
            ext_count = 0
            for e in best:
                if isinstance(e, tuple):
                    ext_count += 1
                    k = e[1]
                else:
                    k = e
                rows.append(k % nz)
                cols.append(k // nz)
            ii = min(cols)
            jj = min(rows)
            cx = x0 + (ii + si / 2.0) * RES
            cz = z0 + (jj + si / 2.0) * RES
            tops = []
            ysrcs = []
            cols_ = []
            for k in solid:
                if covered[k]:
                    continue
                s = src_of.get(k)
                if s is None:
                    continue
                tops.append(s["top"])
                ysrcs.append(s["y"])
                cols_.append(s["color"])
            top = Counter(tops).most_common(1)[0][0] if tops else None
            ysrc = Counter(ysrcs).most_common(1)[0][0] if ysrcs else None
            color = Counter(cols_).most_common(1)[0][0] if cols_ else None
            if top is not None:
                y = round(top - h / 2.0, 3)
            else:
                # no reachable source tile: use the level's dominant deck top
                y = round(level_top - h / 2.0, 3)
            # graze-fix: pick y so the tile clears every solid its footprint
            # brushes -- the slot between the highest solid below and the
            # lowest solid above must hold the tile; when the slot is tighter
            # than the tile (freehand noise: walls cap 0.01-0.03 low), centre
            # it so the penetration is minimal and equal on both sides
            yb = y - h / 2.0
            yt = y + h / 2.0
            xs0f = x0 + ii * RES
            xs1f = xs0f + size
            zs0f = z0 + jj * RES
            zs1f = zs0f + size
            floor_top = None                  # highest solid top below tile
            ceil_bot = None                   # lowest solid bottom above tile
            deep = False
            for bx in (buckets, bbuckets):
                for ix in range(ii, ii + si):
                    for pr in bx.get(ix, ()):
                        ex0, ex1, ez0, ez1, ey0, ey1 = pr
                        if ex1 <= xs0f or ex0 >= xs1f:
                            continue
                        if ez1 <= zs0f or ez0 >= zs1f:
                            continue
                        if ey1 <= yb + 0.05:
                            # its top clears the tile's bottom -> solid below
                            if floor_top is None or ey1 > floor_top:
                                floor_top = ey1
                        elif ey0 >= yt - 0.05:
                            # its bottom clears the tile's top -> solid above
                            if ceil_bot is None or ey0 < ceil_bot:
                                ceil_bot = ey0
                        elif min(yt, ey1) - max(yb, ey0) <= 0.05:
                            # tiny graze (freehand 0.01-0.05 noise): the side
                            # it touches decides floor vs ceiling
                            if yt - ey0 <= ey1 - yb:
                                if ceil_bot is None or ey0 < ceil_bot:
                                    ceil_bot = ey0
                            else:
                                if floor_top is None or ey1 > floor_top:
                                    floor_top = ey1
                        else:
                            deep = True
            if not deep:
                lo = (floor_top + h / 2.0 + 0.01) if floor_top is not None else None
                hi = (ceil_bot - h / 2.0 - 0.01) if ceil_bot is not None else None
                if lo is not None and hi is not None:
                    if lo <= hi:
                        y = round((lo + hi) / 2.0, 3)
                    else:
                        # slot tighter than the tile: centre it, penetration
                        # is then minimal and equal on both sides
                        y = round((floor_top + ceil_bot) / 2.0, 3)
                elif lo is not None:
                    y = round(max(y, lo), 3)
                elif hi is not None:
                    y = round(min(y, hi), 3)
            if cov_cells:
                # coplanar-slide guard: dip a hair to avoid z-fighting with
                # the neighbour slab, but never into a brushing solid
                cu = (ceil_bot - (y + h / 2.0)) if ceil_bot is not None else 1.0
                cd = ((y - h / 2.0) - floor_top) if floor_top is not None else 1.0
                dip = min(0.01, max(0.0, min(cu, cd) - 0.005))
                if dip > 0:
                    y = round(y - dip, 3)
            placed.append({"name": name, "x": cx, "y": y, "z": cz,
                           "color": color, "ext": ext_count})
            for e in best:
                k = e[1] if isinstance(e, tuple) else e
                free.discard(k)
                used.add(k)
    leftover = len(free)
    report.append((len(placed), leftover))
    return placed, list(free)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "Hant.txt"
    out = sys.argv[2] if len(sys.argv) > 2 else "missing.txt"
    parts = parse(src)
    text = open(src, encoding="utf-8").read()

    all_placed = []
    report = []
    levs = hs.clusters(parts)
    for ylev, ys in levs:
        members = [p for p in parts
                   if p["name"].startswith(hs.SURFACE)
                   and round(p["pos"][1], 2) in ys]
        if len(members) < 6:
            continue
        meta, gaps = hs.scan_level(parts, ylev, members, MIN_AREA, ys)
        if not gaps:
            continue
        (x0, z0, nx, nz, covered, barrier, excluded, source,
         excl_parts, bar_parts) = rasterize(parts, ylev, members, ys)
        primary = Counter(p["name"] for p in members).most_common(1)[0][0]
        srcdesc = [None] * (nx * nz)
        member_desc = {}
        for pi, p in enumerate(members):
            # nominal_top: a Floor1Large used as a vertical wall panel must
            # not report a +8 top -- fills would climb out of the band
            member_desc[pi] = {"name": p["name"], "y": p["pos"][1],
                               "top": nominal_top(p), "color": p["color"]}
        for k, v in enumerate(source):
            if v is not None:
                srcdesc[k] = member_desc[v]
        # gap cells (free only) per region + BFS sources
        for gap in gaps:
            cells = [(i, j) for (i, j) in gap["cells"]
                     if not excluded[i * nz + j]]
            if not cells:
                continue
            region = set(i * nz + j for i, j in cells)
            srcmap = {}
            q = deque()
            for k in region:
                i, j = k // nz, k % nz
                for na, nb in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                    if 0 <= na < nx and 0 <= nb < nz:
                        kk = na * nz + nb
                        if covered[kk] and srcdesc[kk] is not None and k not in srcmap:
                            srcmap[k] = srcdesc[kk]
                            q.append((i, j))
            while q:
                a, b = q.popleft()
                ka = a * nz + b
                for na, nb in ((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)):
                    nk = na * nz + nb
                    if nk in region and nk not in srcmap:
                        srcmap[nk] = srcmap[ka]
                        q.append((na, nb))
            placed, left = _fill(parts, members, x0, z0, nx, nz, covered,
                                  barrier, excluded, cells, primary, srcmap,
                                  report, excl_parts, bar_parts)
            if left and len(left) >= 4:
                li = [k // nz for k in left]
                lj = [k % nz for k in left]
                print("  LEFT region x[%.2f..%.2f] z[%.2f..%.2f] cells=%d "
                      "bbox x[%.2f..%.2f] z[%.2f..%.2f]"
                      % (x0 + min(i for i, j in cells) * RES,
                         x0 + (max(i for i, j in cells) + 1) * RES,
                         z0 + min(j for i, j in cells) * RES,
                         z0 + (max(j for i, j in cells) + 1) * RES,
                         len(left),
                         x0 + min(li) * RES, x0 + (max(li) + 1) * RES,
                         z0 + min(lj) * RES, z0 + (max(lj) + 1) * RES))
            for pl in placed:
                pl["level"] = (min(ys), max(ys))
            all_placed.extend(placed)

    # ---------------------------------------------------------------- emit
    n = len(all_placed)
    head = text.split("\n", 1)[0] + "\n"          # "local stolenBase = {"
    foot_i = text.index("\nfor _, v in pairs(stolenBase)")
    lines = []
    for k, pl in enumerate(all_placed):
        color = ("" if pl["color"] is None else
                 ", Color = Color3.new(%.6f, %.6f, %.6f)" % pl["color"])
        comma = "," if k < n - 1 else ""
        lines.append(
            '    {CFrame = CFrame.new(%.6f, %.6f, %.6f, %s), Name = "%s"%s}%s'
            % (pl["x"], pl["y"], pl["z"], IDENTITY, pl["name"], color, comma))
    body = "\n".join(lines) + "\n" if lines else ""
    footer = text[foot_i:]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(head + body + footer)

    total_left = sum(r[1] for r in report)
    print("levels with gaps: %d" % len({r[0] for r in report}))
    print("placed %d fill parts -> %s" % (n, out))
    print("leftover uncovered cells (sub-stud or unreachable): %d" % total_left)
    by = Counter(p["name"] for p in all_placed)
    for k, v in by.most_common():
        print("   %-14s %d" % (k, v))
    ext = sum(p["ext"] for p in all_placed)
    print("wall-slide cells (<=0.75 stud under wall): %d" % ext)
    return 0


if __name__ == "__main__":
    sys.exit(main())
