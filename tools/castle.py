#!/usr/bin/env python3
"""Parse Castle.txt - a multi-section blueprint script, unlike the partTable
builds.  Line pairs alternate data/loader:

  section A (lines 0-1): { [CFrame] = treeclass, [2] = partName }  -> part
  section B (lines 2-3): { [CFrame] = partName, ... }               -> part
  section C (lines 4-5): { [CFrame] = treeclass, [2] = Vector3 }    -> raw
                         Part with explicit size (trees/planks)

Returns build3d-style part dicts: pos, x/y/z axes, name, color, tree.
Raw sized parts (section C) get name "#SIZED" and size=(sx,sy,sz).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import TREE_PALETTE  # noqa: E402

CFRAME_RE = re.compile(
    r"\[CFrame\.new\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,"
    r"\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,"
    r"\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,"
    r"\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)\]")
VEC3_RE = re.compile(
    r"Vector3\.new\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)")
ENTRY_RE = re.compile(r"\{(.+?)\}(?=,\{|\},)")


def _axes(v):
    # columns of the rotation matrix = local axes in world space (same as build3d)
    return ((v[3], v[6], v[9]), (v[4], v[7], v[10]), (v[5], v[8], v[11]))


def _part(m, name, tree, size=None):
    v = [float(m.group(i)) for i in range(1, 13)]
    x, y, z = _axes(v)
    color = None
    if tree in TREE_PALETTE:
        color = tuple(c / 255.0 for c in TREE_PALETTE[tree])
    p = {"pos": (v[0], v[1], v[2]), "x": x, "y": y, "z": z,
         "name": name, "color": color, "tree": tree}
    if size is not None:
        p["size"] = size
    return p


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    parts = []
    # sections A and B: entries { [CFrame]=x, [2]=y }
    for li in (0, 2):
        for em in ENTRY_RE.finditer(lines[li]):
            body = em.group(1)
            cm = CFRAME_RE.search(body)
            if not cm:
                continue
            kv = re.findall(r"\[2\]\s*=\s*'([^']+)'", body)
            first = re.findall(r"\]\s*=\s*'([^']+)'", body)
            # value of the CFrame key (skipping the [CFrame...] = )
            cval = re.findall(r"\)\]\s*=\s*'([^']+)'", body)
            if li == 0:
                tree = cval[0] if cval else None
                name = kv[0] if kv else None
            else:
                name = cval[0] if cval else None
                tree = None
            if name is None:
                continue
            parts.append(_part(cm, name, tree))
    # section C: { [CFrame]=treeclass, [2]=Vector3.new(sx,sy,sz) }
    for em in ENTRY_RE.finditer(lines[4]):
        body = em.group(1)
        cm = CFRAME_RE.search(body)
        vm = VEC3_RE.search(body)
        if not cm or not vm:
            continue
        cval = re.findall(r"\)\]\s*=\s*'([^']+)'", body)
        tree = cval[0] if cval else None
        size = tuple(float(vm.group(i)) for i in (1, 2, 3))
        parts.append(_part(cm, "#SIZED", tree, size))
    return parts


def main():
    path = os.path.join(os.path.dirname(HERE), "Castle.txt")
    parts = parse(path)
    print("castle parts:", len(parts))
    from collections import Counter
    print(Counter(p["name"] for p in parts).most_common(12))
    xs = [p["pos"][0] for p in parts]
    ys = [p["pos"][1] for p in parts]
    zs = [p["pos"][2] for p in parts]
    print("x[%.1f..%.1f] y[%.1f..%.1f] z[%.1f..%.1f]"
          % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))


if __name__ == "__main__":
    main()
