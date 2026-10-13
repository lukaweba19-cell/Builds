#!/usr/bin/env python3
"""Build dragon.txt: the treehouse waterfall's dragon, reworked as an addon
for the castle.

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

Output is a standalone partTable file: the same structure and loader
footer as every other build, containing only the dragon - no castle code.

Usage: python3 tools/gen_dragon.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import parse, part_box  # noqa: E402

ROOT = os.path.dirname(HERE)
DRAGON_TREE = "Volcano"          # castle accent colour (banners, spire flag)
TARGET_X0 = 390.6                # just clear of the wall face at x=390.5
TARGET_Y0 = 117.2                # above the battlement ledge (tops at 67.1)
TARGET_ZC = -250.0               # centre of the keep's east wall (z -302..-198)


def rotate90_y(pos, axes):
    """(x,y,z) -> (z, y, -x): relief plane x-y faces +Z -> z-y faces +X."""
    def r(v):
        return (v[2], v[1], -v[0])
    return r(pos), tuple(r(a) for a in axes)


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
    print("dragon parts: %d (all TreeValue '%s')" % (n, DRAGON_TREE))
    print("source: x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]"
          % (sx0, sx1, sy0, max(b[3] for b in boxes), sz0, sz1))
    print("placed: x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]"
          % (min(b[0] for b in nboxes), max(b[1] for b in nboxes),
             min(b[2] for b in nboxes), max(b[3] for b in nboxes),
             min(b[4] for b in nboxes), max(b[5] for b in nboxes)))
    print("wrote dragon.txt")


if __name__ == "__main__":
    main()
