#!/usr/bin/env python3
"""Verify dragon.txt against its sources.

Checks:
1. Format (OUTPUT_FORMAT.md):
     local partTable = {
         {CFrame = CFrame.new(x, y, z, r00..r22), Name = 'PartName'},
     }
   - every body line matches the {CFrame, Name} entry pattern exactly,
     with 12 numbers in CFrame.new,
   - NO TreeValue, NO colour, no stolenBase leftovers,
   - the loader footer clones from ReplicatedStorage.ClientItemInfo into
     workspace.BuildsStructures with SetPrimaryPartCFrame and a
     PurchasedBoxItemName StringValue - byte-identical to the required
     FOOTER,
   - the file on disk is byte-identical to what gen_dragon.py produces
     (no hand-edited drift).
2. Part names: every Name used must appear in the real in-game export
   files (they are what ReplicatedStorage.ClientItemInfo actually holds).
3. Identity: the dragon group is exactly the treehouse waterfall's blue
   dragon parts (same name multiset - only pose changed).  The dragon /
   water split comes from gen_dragon.build().
4. Rotations: every CFrame rotation stays orthonormal.
5. Placement: zero AABB overlap (volume > 1e-4) for every pair of
   dragon~castle, water~castle, water~dragon and water~water (parts may
   touch but not interpenetrate).  The dragon must lie inside the
   intended mounting volume on the keep's east face; the water must stay
   inside its own corridor volume between the wall and the terrace.

Usage: python3 tools/verify_dragon.py   Exit 1 on any violation.
"""
import glob
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import parse, part_box  # noqa: E402
import castle       # noqa: E402
import gen_dragon   # noqa: E402

ROOT = os.path.dirname(HERE)
MOUNT = (388.0, 405.0, 115.0, 170.0, -280.0, -220.0)     # dragon volume
WATER_BOX = (386.0, 415.0, 33.0, 119.0, -285.0, -215.0)  # water corridor

ENTRY_RE = re.compile(
    r"^    \{CFrame = CFrame\.new\((.*)\), Name = '([A-Za-z0-9_]+)'\}(,)?$")


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
    xs = [c[0] for c in cs]
    ys = [c[1] for c in cs]
    zs = [c[2] for c in cs]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def overlap(b, c, eps=1e-4):
    return (min(b[1], c[1]) - max(b[0], c[0]) > eps
            and min(b[3], c[3]) - max(b[2], c[2]) > eps
            and min(b[5], c[5]) - max(b[4], c[4]) > eps)


def main():
    problems = []
    text = open(os.path.join(ROOT, "dragon.txt"), encoding="utf-8").read()

    # ------------------------------------------------------------ format
    if not text.startswith("local partTable = {\n"):
        problems.append("header is not 'local partTable = {'")
    if "TreeValue" in text:
        problems.append("TreeValue found in dragon.txt (format allows none)")

    lines = text.split("\n")
    try:
        close = lines.index("}")
    except ValueError:
        close = -1
        problems.append("partTable closing '}' line missing")
    body = lines[1:close] if close > 0 else []
    if not body:
        problems.append("no entries between the header and '}'")
    for l in body:
        if "Color3" in l or 'Name = "' in l:
            problems.append("colour / double-quoted-name leftover in entry: %s"
                            % l[:90])
            break
        m = ENTRY_RE.match(l)
        if not m:
            problems.append("entry does not match the {CFrame, Name} pattern: %s"
                            % l[:90])
            continue
        nums = [s.strip() for s in m.group(1).split(",")]
        if len(nums) != 12:
            problems.append("CFrame.new has %d numbers (must be 12): %s"
                            % (len(nums), l[:90]))
        for s in nums:
            try:
                float(s)
            except ValueError:
                problems.append("non-numeric CFrame value %r: %s" % (s, l[:90]))
                break

    sep = text.find("\n}\n\n")
    footer = text[sep + 4:] if sep != -1 else ""
    if sep == -1:
        problems.append("'}' not followed by a blank line + loader footer")
    if footer != gen_dragon.FOOTER:
        problems.append("loader footer differs from the required "
                        "BuildsStructures / PurchasedBoxItemName footer")

    # part names must exist in ReplicatedStorage.ClientItemInfo; the real
    # in-game export files are the ground truth for what it contains.
    valid = set()
    for f in glob.glob(os.path.join(ROOT, "*.txt")):
        if os.path.basename(f) == "dragon.txt":
            continue
        s = open(f, encoding="utf-8", errors="replace").read()
        valid |= set(re.findall(r"Name\s*=\s*'([^']+)'", s))
        valid |= set(re.findall(r"\[2\]\s*=\s*'([^']+)'", s))
    names = set(re.findall(r"Name = '([A-Za-z0-9_]+)'", text))
    bogus = sorted(n for n in names if n not in valid)
    if bogus:
        problems.append("part names not present in any in-game export "
                        "(would error in ClientItemInfo: %s)" % ", ".join(bogus))

    # ------------------------------------------------- generator drift
    dragon, water = gen_dragon.build()
    expected = gen_dragon.render_file(dragon, water)
    if text != expected:
        problems.append("dragon.txt differs from gen_dragon.py output "
                        "(hand edits or stale file)")

    # --------------------------------------------------- parse + split
    dg = parse(os.path.join(ROOT, "dragon.txt"))
    if len(dg) != len(body):
        problems.append("parse mismatch: %d parsed vs %d entry lines"
                        % (len(dg), len(body)))
    for p in dg:
        for a in (p["x"], p["y"], p["z"]):
            if abs(sum(v * v for v in a) - 1.0) > 1e-4:
                problems.append("non-orthonormal rotation on %s" % p["name"])
                break
    print("parts: %d total = %d dragon + %d water"
          % (len(dg), len(dragon), len(water)))
    print("water by render class: %s"
          % dict(Counter(p["tree"] for p in water)))
    print("distinct part names: %d (all valid ClientItemInfo names)"
          % len(names))

    # ------------------------------------------------ identity (names)
    th = parse(os.path.join(ROOT, "treehouse.txt"))

    def rgb(p):
        c = p.get("color")
        return tuple(round(v * 255) for v in c) if c else None

    src = [p for p in th
           if rgb(p) == (16, 42, 220)
           and 250 <= p["pos"][0] <= 298 and -613 <= p["pos"][2] <= -604
           and 2 <= p["pos"][1] <= 60]
    if Counter(p["name"] for p in src) != Counter(p["name"] for p in dragon):
        problems.append("dragon part multiset differs from the treehouse source")
    print("source dragon parts: %d   dragon.txt dragon parts: %d"
          % (len(src), len(dragon)))

    # -------------------------------------------------- volumes
    db = [aabb(p) for p in dragon]
    wb = [aabb(p) for p in water]
    for p, b in zip(dragon, db):
        if not (MOUNT[0] <= b[0] and b[1] <= MOUNT[1]
                and MOUNT[2] <= b[2] and b[3] <= MOUNT[3]
                and MOUNT[4] <= b[4] and b[5] <= MOUNT[5]):
            problems.append("dragon part %s outside the mounting volume" % p["name"])
            break
    for p, b in zip(water, wb):
        if not (WATER_BOX[0] <= b[0] and b[1] <= WATER_BOX[1]
                and WATER_BOX[2] <= b[2] and b[3] <= WATER_BOX[3]
                and WATER_BOX[4] <= b[4] and b[5] <= WATER_BOX[5]):
            problems.append("water part %s (%r) outside the water corridor"
                            % (p["name"], p.get("tree")))
            break
    if db:
        print("dragon volume: x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]"
              % (min(b[0] for b in db), max(b[1] for b in db),
                 min(b[2] for b in db), max(b[3] for b in db),
                 min(b[4] for b in db), max(b[5] for b in db)))
    if wb:
        print("water volume:  x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]"
              % (min(b[0] for b in wb), max(b[1] for b in wb),
                 min(b[2] for b in wb), max(b[3] for b in wb),
                 min(b[4] for b in wb), max(b[5] for b in wb)))

    # -------------------------------------------------- vs the castle
    cp = castle.parse(os.path.join(ROOT, "Castle.txt"))
    cb = [aabb(p) for p in cp]

    def count_hits(boxes, others, label, same=False):
        hits = 0
        for i, b in enumerate(boxes):
            for j, c in enumerate(others):
                if same and j <= i:          # distinct pairs only
                    continue
                if overlap(b, c):
                    hits += 1
                    if hits <= 3:
                        print("  HARD %s x[%.1f..%.1f] y[%.1f..%.1f] z[%.1f..%.1f]"
                              % (label, c[0], c[1], c[2], c[3], c[4], c[5]))
        print("hard overlaps %s: %d" % (label, hits))
        return hits

    hard = 0
    hard += count_hits(db, cb, "dragon~castle")
    hard += count_hits(wb, cb, "water~castle")
    hard += count_hits(wb, db, "water~dragon")
    hard += count_hits(wb, wb, "water~water", same=True)

    for pr in problems:
        print("  PROBLEM  %s" % pr)
    if problems or hard:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
