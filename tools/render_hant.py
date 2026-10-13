#!/usr/bin/env python3
"""Multi-angle PNG renders of Hant.txt, before and after the gap fills.

Views produced in renders/:
  hant_before_*.png      the build as exported
  hant_after_*.png       build + missing.txt fills
  hant_fills_only.png    build in grey with the 1281 fills in bright colour

Angles: two opposite overviews, a porch close-up, a ground-floor cutaway
(parts above y=14 removed -> look inside the house) and a bedroom-level
cutaway (parts above y=51 removed).

Usage: python3 tools/render_hant.py [out_dir] [job1,job2,...]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import parse, render, part_box  # noqa: E402

W, H = 760, 560


def cut(parts, ymax):
    """Keep only parts whose box bottom sits at or below ymax."""
    out = []
    for p in parts:
        if min(c[1] for c in part_box(p)) <= ymax:
            out.append(p)
    return out


def window(parts, x0, x1, z0, z1):
    """Keep parts whose centre lies inside the x/z window (close-ups)."""
    out = []
    for p in parts:
        cs = part_box(p)
        cx = sum(c[0] for c in cs) / 8.0
        cz = sum(c[2] for c in cs) / 8.0
        if x0 <= cx <= x1 and z0 <= cz <= z1:
            out.append(p)
    return out


def grey(parts):
    out = []
    for p in parts:
        q = dict(p)
        q["color"] = (0.42, 0.44, 0.48)
        out.append(q)
    return out


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "renders"
    os.makedirs(out_dir, exist_ok=True)
    root = os.path.dirname(HERE)
    base = parse(os.path.join(root, "Hant.txt"))
    fills = parse(os.path.join(root, "missing.txt"))
    after = base + fills
    print("before: %d parts   fills: %d   after: %d"
          % (len(base), len(fills), len(after)))

    jobs = [
        ("hant_before_SE",    base, 35, 26),
        ("hant_after_SE",     after, 35, 26),
        ("hant_before_NW",    base, 215, 26),
        ("hant_after_NW",     after, 215, 26),
        ("hant_before_ground_cut", cut(base, 6), 35, 30),
        ("hant_after_ground_cut",  cut(after, 6), 35, 30),
        ("hant_before_upstairs_cut", cut(base, 51), 35, 24),
        ("hant_after_upstairs_cut",  cut(after, 51), 35, 24),
        ("hant_before_porch", window(base, 0, 76, -258, -170), 60, 22),
        ("hant_after_porch",  window(after, 0, 76, -258, -170), 60, 22),
        ("hant_fills_only",   grey(base) + fills, 35, 26),
    ]
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    for name, parts, yaw, pitch in jobs:
        if only and name not in only:
            continue
        out = os.path.join(out_dir, name + ".png")
        render(parts, out, yaw_deg=yaw, pitch_deg=pitch, width=W, height=H)
        print("wrote %s (%d parts)" % (out, len(parts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
