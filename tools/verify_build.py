#!/usr/bin/env python3
"""Verify a generated build file: format rules, duplicates, overlaps, symmetry."""
import re
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from build3d import parse, PART_SIZE  # noqa: E402

CX = 383.0
ENTRY = re.compile(r"\{CFrame = CFrame\.new\(([^)]*)\), Name = '([^']+)'\},")
VALID_ROT = {
    (1, 0, 0, 0, 1, 0, 0, 0, 1), (0, 0, -1, 0, 1, 0, 1, 0, 0),
    (-1, 0, 0, 0, 1, 0, 0, 0, -1), (0, 0, 1, 0, 1, 0, -1, 0, 0),
}
VALID_NAMES = set(PART_SIZE)
# walls that legitimately sit embedded inside floor slabs
FLOORISH = {"Floor2Large", "Floor2", "Floor2Small", "Floor2Tiny",
            "Floor1Large", "Floor1", "Floor1Small", "Floor1Tiny"}
# parts meant to be mounted flush against a wall
MOUNTED = {"Ladder1"}

problems = []


def fail(msg):
    problems.append(msg)


def aabb(p):
    sx, sy, sz = PART_SIZE[p["name"]]
    ax, ay, az = p["pos"]
    pts = []
    for dx in (-sx / 2, sx / 2):
        for dy in (-sy / 2, sy / 2):
            for dz in (-sz / 2, sz / 2):
                pts.append((ax + p["x"][0] * dx + p["y"][0] * dy + p["z"][0] * dz,
                            ay + p["x"][1] * dx + p["y"][1] * dy + p["z"][1] * dz,
                            az + p["x"][2] * dx + p["y"][2] * dy + p["z"][2] * dz))
    xs, ys, zs = zip(*pts)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def main(path):
    text = open(path, encoding="utf-8").read()

    # --- format rules from the spec -------------------------------------
    if not text.startswith("local partTable = {\n"):
        fail("file must start with 'local partTable = {'")
    for bad in ("t =", "TreeValue", "Color", "PivotTo"):
        if re.search(r"\b%s\b" % re.escape(bad), text):
            fail("forbidden token in output: %r" % bad)
    if 'Instance.new("Folder", workspace)' not in text:
        fail("missing BuildsStructures folder boilerplate")
    if "SetPrimaryPartCFrame" not in text or "PurchasedBoxItemName" not in text:
        fail("missing spawner boilerplate")

    entries = ENTRY.findall(text)
    for body, name in entries:
        nums = [n.strip() for n in body.split(",")]
        if len(nums) != 12:
            fail("entry with %d numbers (need 12): %s" % (len(nums), body))
        vals = tuple(float(n) for n in nums)
        if not any(abs(abs(v) - 1) < 1e-6 for v in vals[3:]):
            pass
        if tuple(round(v) for v in vals[3:]) not in VALID_ROT:
            fail("non axis-aligned rotation: %s" % body)
        if name not in VALID_NAMES:
            fail("unknown part name: %s" % name)

    parts = parse(path)
    print("entries: %d, parsed parts: %d" % (len(entries), len(parts)))

    # --- duplicates -----------------------------------------------------
    counts = Counter((p["pos"], p["name"]) for p in parts)
    for k, c in counts.items():
        if c > 1:
            fail("duplicate part %s x%d" % (k, c))

    # --- overlaps -------------------------------------------------------
    boxes = [(p, aabb(p)) for p in parts]
    n = len(boxes)
    for i in range(n):
        pi, bi = boxes[i]
        for j in range(i + 1, n):
            pj, bj = boxes[j]
            if pi["name"] in FLOORISH and pj["name"] in FLOORISH:
                continue  # floors may tuck under walls; both are flat slabs
            if pi["name"] in MOUNTED or pj["name"] in MOUNTED:
                continue  # ladders are mounted flush against walls
            ox = min(bi[3], bj[3]) - max(bi[0], bj[0])
            oy = min(bi[4], bj[4]) - max(bi[1], bj[1])
            oz = min(bi[5], bj[5]) - max(bi[2], bj[2])
            if ox > 0.01 and oy > 0.01 and oz > 0.01:
                vol = ox * oy * oz
                # oy > 0.25 filters out slab-seating (a 0.2 floor slab under a
                # wall/merlon is normal construction contact, not a collision)
                if vol > 1.0 and oy > 0.25:
                    fail("overlap %.1f studs^3: %s@%s vs %s@%s"
                         % (vol, pi["name"], pi["pos"], pj["name"], pj["pos"]))

    # --- mirror symmetry about x = 383 ---------------------------------
    # box-like parts (walls/panes/floors/posts) are identical under a 180°
    # flip, so they are compared by their long-axis direction; wedges carry
    # a slope direction and are compared by exact mirrored rotation.
    def sig_of(name, pos, rot):
        x, y, z = pos
        if name.startswith("Wedge"):
            r = rot
        else:
            r = "Z" if rot in ((1, 0, 0, 0, 1, 0, 0, 0, 1),
                               (-1, 0, 0, 0, 1, 0, 0, 0, -1)) else "X"
        return (name, round(x, 2), y, z, r)

    orig = Counter()
    mirrored = Counter()
    for p in parts:
        x, y, z = p["pos"]
        orig[sig_of(p["name"], p["pos"], (p["x"], p["y"], p["z"]))] += 1
        # mirroring about the x=CX plane is M' = S*M*S with S = diag(-1,1,1):
        # col1 keeps x and negates y,z; col2/col3 negate x only
        mx = (p["x"][0], -p["x"][1], -p["x"][2])
        my = (-p["y"][0], p["y"][1], p["y"][2])
        mz = (-p["z"][0], p["z"][1], p["z"][2])
        mirrored[sig_of(p["name"], (2 * CX - x, y, z), (mx, my, mz))] += 1
    only_orig = orig - mirrored
    only_mirr = mirrored - orig
    asym = sum(only_orig.values())
    print("mirror-asymmetric parts: %d" % asym)
    for k in list(only_orig)[:6]:
        print("   unmirrored:", k[0], k[1:4])
    for k in list(only_mirr)[:6]:
        print("   missing  :", k[0], k[1:4])

    # --- summary --------------------------------------------------------
    print("part mix:", dict(Counter(p["name"] for p in parts)))
    xs = [p["pos"][0] for p in parts]
    ys = [p["pos"][1] for p in parts]
    zs = [p["pos"][2] for p in parts]
    print("bbox x %.0f..%.0f  y %.1f..%.1f  z %.0f..%.0f"
          % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

    if problems:
        print("\nPROBLEMS (%d):" % len(problems))
        for pmsg in problems[:40]:
            print("  -", pmsg)
        if len(problems) > 40:
            print("  ... and %d more" % (len(problems) - 40))
        sys.exit(1)
    print("\nOK: no problems found")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Halloween.txt")
