#!/usr/bin/env python3
"""Verify a gap-fill file against its source build.

Checks:
1. Format (OUTPUT_FORMAT.md - the working Musseum v1 blueprint format):
   'local partTable = {' header, every entry {CFrame (12 numbers), Name,
   TreeValue} with a wood class the loader's colour chain handles, and
   the footer byte-exact from Musseum v1.lua.txt (tools/museum_loader.lua)
   so the blueprint knows which wood to fill each part with.
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
import re
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


ENTRY_RE = re.compile(
    r"^    \{CFrame = CFrame\.new\((.*)\), Name = '([A-Za-z0-9_]+)', "
    r"TreeValue = '([A-Za-z0-9_]+)'\}(,)?$")


def check_format(fills_text, fills):
    problems = []
    with open(os.path.join(HERE, "museum_loader.lua"), encoding="utf-8") as fh:
        footer_ref = fh.read()
    if not fills_text.startswith("local partTable = {\n"):
        problems.append("header is not 'local partTable = {'")
    sep = fills_text.find("\n}\n\n")
    if sep == -1:
        problems.append("'}' not followed by a blank line + loader footer")
        return problems
    if fills_text[sep + 4:] != footer_ref:
        problems.append("loader footer differs from the Musseum v1 loader "
                        "(tools/museum_loader.lua)")
    body = fills_text[:sep].split("\n")[1:]
    if len(body) != len(fills):
        problems.append("parse mismatch: %d parsed vs %d body lines"
                        % (len(fills), len(body)))
    known = set(re.findall(r'v\.TreeValue == "(\w+)"', footer_ref))
    classes = set()
    for l in body:
        m = ENTRY_RE.match(l)
        if not m:
            problems.append("entry does not match the {CFrame, Name, "
                            "TreeValue} pattern: %s" % l[:90])
            continue
        nums = [s.strip() for s in m.group(1).split(",")]
        if len(nums) != 12:
            problems.append("CFrame.new has %d numbers (must be 12): %s"
                            % (len(nums), l[:90]))
            continue
        classes.add(m.group(3))
        if m.group(3) not in known:
            problems.append("wood class %r not handled by the loader "
                            "colour chain" % m.group(3))
    print("fills wood classes: %s" % ", ".join(sorted(classes)))
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

    problems = check_format(fills_text, fills)
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
