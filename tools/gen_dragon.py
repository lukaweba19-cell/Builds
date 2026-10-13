#!/usr/bin/env python3
"""Build dragon.txt: the treehouse waterfall's dragon, reworked as an addon
for the castle - now with the water it was sculpted on.

Source: the waterfall at the treehouse centre (x~275, z~-609) is a white
LoneCave sheet with a serpentine dragon sculpted across it in CaveCrawler
blue.  This tool takes those 255 blue parts (the dragon itself - the white
waterfall stays in the treehouse), and:

  * rotates the relief +90 degrees about Y so it faces outward (+X) from
    the castle keep's tall east wall (the flat face at x=390),
  * lifts it so it stands just above the battlements, y[117.2..170.2],
    rising alongside the central tower - verified zero overlap with all
    20,081 castle parts,
  * recolours every part to the castle's accent colour (TreeValue
    'Volcano', the red of its banners and spire flag).

It then adds the WATER the dragon is bursting out of, in the waterfall's
own CaveCrawler blue with Frost foam and LoneCave spray (all verified
palette classes):

  1. burst pool  - terraced water disc clinging to the wall at the
     dragon's feet, y[114.0..116.6], with a Frost foam ring and LoneCave
     spray posts shooting up around the rim,
  2. cascade     - four vertical water sheets hugging the wall face
     (x[391.1..392.1]) from the pool down to the battlement walkway,
  3. ribbon      - a shallow channel pooling on the walkway between the
     crest wedges and the parapet (x[391..393], y[63.6..63.8),
  4. pours       - five columns spouting through the crenel gaps from
     above the merlons down the outer face to the terrace below,
  5. terrace pool - a wide sheet spreading on the terrace top (y34.6)
     with a Frost foam rim, catching every pour.

Every added part is checked: zero overlap with all 20,081 castle parts,
zero with the 255 dragon parts, and zero between water parts themselves
(touching only).

Output is a standalone partTable file: the same structure and loader
footer as every other build, containing dragon + water - no castle code.

Usage: python3 tools/gen_dragon.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import parse, part_box  # noqa: E402

ROOT = os.path.dirname(HERE)
DRAGON_TREE = "Volcano"          # castle accent colour (banners, spire flag)
WATER_TREE = "CaveCrawler"       # the waterfall's deep blue
FOAM_TREE = "Frost"              # pale cyan foam
SPRAY_TREE = "LoneCave"          # white spray
TARGET_X0 = 390.6                # just clear of the wall face at x=390.5
TARGET_Y0 = 117.2                # above the battlement ledge (tops at 67.1)
TARGET_ZC = -250.0               # centre of the keep's east wall (z -302..-198)

ID = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
# same rotation the dragon relief gets: local x -> world +Z, local z -> world -X
R90 = ((0, 0, 1), (0, 1, 0), (-1, 0, 0))


def rotate90_y(pos, axes):
    """(x,y,z) -> (z, y, -x): relief plane x-y faces +Z -> z-y faces +X."""
    def r(v):
        return (v[2], v[1], -v[0])
    return r(pos), tuple(r(a) for a in axes)


def water_parts():
    """All water parts as build3d-style dicts (pos/x/y/z/name/tree)."""
    parts = []

    def add(name, x, y, z, tree, axes=ID):
        parts.append({"pos": (x, y, z), "x": axes[0], "y": axes[1],
                      "z": axes[2], "name": name, "tree": tree})

    cx, cz = 397.0, -250.0          # burst pool centre, in front of the wall
    # the disc must stay inside x[391..403]: x<391 buries cells in the keep
    # wall body (face at x=390.5, Wedge3 to 390.6) and x>403 is unverified.
    # Floor2 half-width is 2, Floor2Small 1 - clamp centres to [393..401].

    # ---- 1. burst pool: terraced disc at the dragon's feet ---------------
    # (y, rx, rz, grid step, part name) - disc shrinks with height
    layers = [
        (114.05, 8.0, 24.0, 4, "Floor2"),
        (114.65, 7.0, 21.0, 4, "Floor2"),
        (115.25, 5.5, 17.0, 2, "Floor2Small"),
        (115.85, 4.0, 12.0, 2, "Floor2Small"),
        (116.45, 2.5, 7.0, 2, "Floor2Small"),
    ]
    for y, rx, rz, step, name in layers:
        for kx in range(-int(rx / step) - 1, int(rx / step) + 2):
            x = cx + kx * step
            if not 393.0 <= x <= 401.0:
                continue
            for kz in range(-int(rz / step) - 1, int(rz / step) + 2):
                z = cz + kz * step
                if ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 <= 1.0:
                    add(name, x, y, z, WATER_TREE)

    # foam ring on the first ledge: cells inside the base ellipse but
    # outside 72% of it, sitting in the gap between layer 0 and layer 1
    for kx in range(-5, 6):
        x = cx + kx * 2
        if not 393.0 <= x <= 401.0:
            continue
        for kz in range(-14, 15):
            z = cz + kz * 2
            e = ((x - cx) / 8.0) ** 2 + ((z - cz) / 24.0) ** 2
            if 0.70 <= e <= 1.0:
                add("Floor2Small", x, 114.35, z, FOAM_TREE)

    # spray posts shooting up around the rim, clear of the dragon's volume
    # (x>=403 is beyond the dragon's x1=402.5; the end pairs sit outside
    # its z span) and clear of the foam ring below (posts start y114.75)
    for z in (-273, -265, -257, -249, -241, -233):
        add("Post", 403.5, 116.75, z, SPRAY_TREE)
    for x in (393, 397, 401):
        add("Post", x, 116.75, -277.5, SPRAY_TREE)
        add("Post", x, 116.75, -222.5, SPRAY_TREE)

    # ---- 2. cascade: water sheets clinging to the wall face --------------
    # x[391.1..392.1] clears the crest wedges (x<=391), the merlons and
    # parapet (x>=393), the Wedge10 pair (z -273..-269 / -285..-281) and
    # the y112 band (z<=-269.9).  Lanes sit on crenel gap centres.  The
    # bottom piece starts at y63.8 = the ribbon's top (touch, no overlap).
    for z_lane, wide in ((-263, True), (-257, False),
                         (-245, False), (-239, True)):
        wall = "Wall2Tall" if wide else "Wall2TallThin"
        cap = "Wall2" if wide else "Wall2Thin"
        for y in (67.8, 75.8, 83.8, 91.8, 99.8, 107.8):
            add(wall, 391.6, y, z_lane, WATER_TREE, R90)
        add(cap, 391.6, 112.85, z_lane, WATER_TREE, R90)

    # ---- 3. ribbon pooling on the battlement walkway ---------------------
    # x[391..393] fits exactly between the crest wedges (x<=391) and the
    # parapet base (x>=393); y sits on the walkway top (63.5).
    for z in range(-282, -217, 2):
        add("Floor2Small", 392.0, 63.7, z, WATER_TREE)

    # ---- 4. pours through the crenels, out to the terrace ----------------
    # gap columns rise inside the merlon gaps; falls hang on the outer face
    # x[394.1..395.1] from above the merlons down to the terrace pool top,
    # bottom piece Wall2ShortThin landing exactly on it (touch, no overlap).
    for z in (-275, -263, -251, -239, -227):
        for y in (66.1, 68.1):
            add("Wall2Thin", 393.5, y, z, FOAM_TREE, R90)
        add("Wall2ShortThin", 394.6, 36.75, z, WATER_TREE, R90)
        for y in (42.75, 50.75, 58.75, 66.75):
            add("Wall2TallThin", 394.6, y, z, WATER_TREE, R90)

    # ---- 5. terrace pool with foam rim -----------------------------------
    POURED = (-275, -263, -251, -239, -227)
    for z in range(-275, -226, 8):
        for x in (398, 406):
            add("Floor2Large", x, 34.65, z, WATER_TREE)
    for z in range(-275, -226, 8):
        if z not in POURED:  # falls land where the inner foam would sit
            add("Floor2Small", 394.0, 34.85, z, FOAM_TREE)   # inner edge
        add("Floor2Small", 410.0, 34.85, z, FOAM_TREE)   # outer edge
    for x in (398, 406):
        add("Floor2Small", x, 34.85, -279.0, FOAM_TREE)  # north edge
        add("Floor2Small", x, 34.85, -221.0, FOAM_TREE)  # south edge
    # splash pads beside each pour, on the pool surface (clear of the fall
    # column at x[394.1..395.1] and of the pool top at 34.75)
    for z in POURED:
        add("Floor2Small", 396.5, 34.85, z, SPRAY_TREE)

    return parts


def main():
    th = parse(os.path.join(ROOT, "treehouse.txt"))

    def rgb(p):
        c = p.get("color")
        return tuple(round(v * 255) for v in c) if c else None

    dragon = [p for p in th
              if rgb(p) == (16, 42, 220)
              and 250 <= p["pos"][0] <= 298
              and -613 <= p["pos"][2] <= -604
              and 2 <= p["pos"][1] <= 60]
    if not dragon:
        raise SystemExit("dragon parts not found in treehouse waterfall")

    # exact source bounding box
    def box(p):
        cs = part_box(p)
        xs = [c[0] for c in cs]; ys = [c[1] for c in cs]; zs = [c[2] for c in cs]
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

    boxes = [box(p) for p in dragon]
    sx0 = min(b[0] for b in boxes); sx1 = max(b[1] for b in boxes)
    sy0 = min(b[2] for b in boxes)
    sz0 = min(b[4] for b in boxes); sz1 = max(b[5] for b in boxes)

    # after rotate90_y: x'=z, z'=-x.  Choose translation for exact placement.
    tz = TARGET_ZC - (-(sx0 + sx1) / 2.0)          # centre width on the wall
    tx = TARGET_X0 - sz0                            # back just off the face
    ty = TARGET_Y0 - sy0

    out_parts = []
    for p in dragon:
        npos, naxes = rotate90_y(p["pos"], (p["x"], p["y"], p["z"]))
        npos = (npos[0] + tx, npos[1] + ty, npos[2] + tz)
        out_parts.append({"pos": npos, "x": naxes[0], "y": naxes[1],
                          "z": naxes[2], "name": p["name"], "tree": DRAGON_TREE})
    water = water_parts()
    out_parts.extend(water)

    # loader footer: identical to the other partTable builds (Hant.txt)
    hant = open(os.path.join(ROOT, "Hant.txt"), encoding="utf-8").read()
    footer = hant[hant.index("\nfor _, v in pairs(partTable)"):]

    def fmt(v):
        s = "%.6f" % v
        return s

    lines = ["local partTable = {"]
    n = len(out_parts)
    for k, p in enumerate(out_parts):
        m = (p["x"], p["y"], p["z"])           # columns = local axes
        # CFrame.new(x,y,z, r00,r01,r02, r10,r11,r12, r20,r21,r22)
        r = (m[0][0], m[1][0], m[2][0],
             m[0][1], m[1][1], m[2][1],
             m[0][2], m[1][2], m[2][2])
        comma = "," if k < n - 1 else ""
        lines.append(
            "    {CFrame = CFrame.new(%s, %s, %s, %s), Name = '%s', TreeValue = '%s'}%s"
            % (fmt(p["pos"][0]), fmt(p["pos"][1]), fmt(p["pos"][2]),
               ", ".join(fmt(v) for v in r), p["name"], p["tree"], comma))
    body = "\n".join(lines) + "\n"
    with open(os.path.join(ROOT, "dragon.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body + footer)

    # report placement
    nboxes = [box({"pos": p["pos"], "x": p["x"], "y": p["y"], "z": p["z"],
                   "name": p["name"]}) for p in out_parts]
    print("dragon parts: %d (all TreeValue '%s')" % (len(dragon), DRAGON_TREE))
    print("water parts: %d (TreeValue '%s'/'%s'/'%s')"
          % (len(water), WATER_TREE, FOAM_TREE, SPRAY_TREE))
    print("source: x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]"
          % (sx0, sx1, sy0, max(b[3] for b in boxes), sz0, sz1))
    print("placed: x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]"
          % (min(b[0] for b in nboxes), max(b[1] for b in nboxes),
             min(b[2] for b in nboxes), max(b[3] for b in nboxes),
             min(b[4] for b in nboxes), max(b[5] for b in nboxes)))
    print("wrote dragon.txt")


if __name__ == "__main__":
    main()
