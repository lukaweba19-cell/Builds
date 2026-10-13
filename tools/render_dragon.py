#!/usr/bin/env python3
"""Render dragon.txt (dragon + water) to PNGs for visual checks.

dragon.txt itself carries no colours (the format allows none), so the
preview colours come from the render-only wood classes in
gen_dragon.build(): dragon = Volcano red, water = CaveCrawler blue with
Frost foam and LoneCave spray.

Jobs:
  dragon_only.png              dragon + water on their own
  dragon_on_castle_closeup.png east wing + dragon + water
  castle_with_dragon.png       the whole castle with the addon in place

Usage: python3 tools/render_dragon.py [out_dir]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import TREE_PALETTE, render, part_box  # noqa: E402
import castle      # noqa: E402
import gen_dragon  # noqa: E402

ROOT = os.path.dirname(HERE)


def colored(parts):
    """Attach the render-only wood colours (never written to disk)."""
    out = []
    for p in parts:
        q = dict(p)
        rgb = TREE_PALETTE.get(p.get("tree"))
        q["color"] = tuple(c / 255.0 for c in rgb) if rgb else (0.6, 0.6, 0.6)
        out.append(q)
    return out


def center_x(p):
    cs = part_box(p)
    return sum(c[0] for c in cs) / 8.0


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "renders"
    os.makedirs(out_dir, exist_ok=True)

    dragon, water = gen_dragon.build()
    addon = colored(dragon + water)
    cp = castle.parse(os.path.join(ROOT, "Castle.txt"))

    jobs = [
        ("dragon_only", addon, 30, 15),
        ("dragon_on_castle_closeup",
         [p for p in cp if center_x(p) >= 330] + addon, 55, 20),
        ("castle_with_dragon", cp + addon, 35, 26),
    ]
    for name, parts, yaw, pitch in jobs:
        out = os.path.join(out_dir, name + ".png")
        render(parts, out, yaw_deg=yaw, pitch_deg=pitch,
               width=900, height=700)
        print("wrote %s (%d parts)" % (out, len(parts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
