#!/usr/bin/env python3
"""Convert a `local stolenBase = {` build file to the standard partTable
structure used by every other build in this repo:

  local partTable = {
      {CFrame = CFrame.new(...), Name = 'Wall2Tall', TreeValue = 'Walnut'},

The per-entry `Color = Color3.new(...)` of the stolenBase format is replaced
by the named TreeValue class the colour belongs to (exact palette match, see
build3d.TREE_PALETTE), and the loader footer iterates `partTable`, applying
the same colour/material palette the other builds' loaders use.

Geometry is never touched: the 12 CFrame numbers are copied verbatim.

Usage: python3 tools/to_parttable.py <file> [--out <file>]
       (in place when --out is omitted)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build3d import TREE_PALETTE  # noqa: E402

HEADER_OLD = "local stolenBase = {"
HEADER_NEW = "local partTable = {"
FOOTER_MARK = "for _, v in pairs(stolenBase) do"

NAME_RE = re.compile(r'Name = "([^"]+)"')
COLOR_RE = re.compile(r"Color = Color3\.new\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)")

# exact reverse palette: rgb tuple -> class name
REVERSE = {}
for _cls, _rgb in TREE_PALETTE.items():
    REVERSE.setdefault(_rgb, _cls)

FOOTER = '''for _, v in pairs(partTable) do
    local model = game.ReplicatedStorage.ClientItemInfo:FindFirstChild(v.Name):Clone()
    model:PivotTo(v.CFrame)
    model.Name = v.Name

    if v.TreeValue then
        local color = Color3.fromRGB(255, 255, 255)
        local material = nil
        if v.TreeValue == "Generic" then color = Color3.fromRGB(204, 142, 105)
        elseif v.TreeValue == "Oak" then color = Color3.fromRGB(234, 184, 146)
        elseif v.TreeValue == "Cherry" then color = Color3.fromRGB(163, 75, 75)
        elseif v.TreeValue == "Fir" or v.TreeValue == "Pine" then color = Color3.fromRGB(215, 197, 154)
        elseif v.TreeValue == "Birch" then color = Color3.fromRGB(205, 205, 205)
        elseif v.TreeValue == "Walnut" then color = Color3.fromRGB(105, 64, 40)
        elseif v.TreeValue == "Koa" then color = Color3.fromRGB(143, 76, 42)
        elseif v.TreeValue == "Volcano" then color = Color3.fromRGB(255, 0, 0)
        elseif v.TreeValue == "GreenSwampy" then color = Color3.fromRGB(52, 142, 64)
        elseif v.TreeValue == "GoldSwampy" then color = Color3.fromRGB(226, 155, 64)
        elseif v.TreeValue == "Palm" then color = Color3.fromRGB(226, 220, 188)
        elseif v.TreeValue == "SnowGlow" then color = Color3.fromRGB(255, 255, 0)
        elseif v.TreeValue == "Frost" then color = Color3.fromRGB(159, 243, 233)
        elseif v.TreeValue == "CaveCrawler" then color = Color3.fromRGB(16, 42, 220)
        elseif v.TreeValue == "BlueSpruce" then color = Color3.fromRGB(159, 173, 192)
        elseif v.TreeValue == "LoneCave" then color = Color3.fromRGB(248, 248, 248)
        elseif v.TreeValue == "Spooky" then color = Color3.fromRGB(170, 85, 0) material = Enum.Material.Granite
        elseif v.TreeValue == "SpookyNeon" then color = Color3.fromRGB(170, 85, 0) material = Enum.Material.Neon
        end

        for _, part in pairs(model:GetChildren()) do
            if part.Name == "BuildDependentWood" and part:IsA("BasePart") then
                part.Color = color
                if material then
                    part.Material = material
                end
            end
        end

        if model:FindFirstChild("Main") then
            model.Main.Color = color
        end

        model.Parent = workspace.Base
    else
        model.Parent = workspace.Structures
    end
end
'''


def convert(text):
    if not text.startswith(HEADER_OLD):
        raise SystemExit("not a stolenBase file (expected %r header)" % HEADER_OLD)
    body, sep, _footer = text.partition("\n" + FOOTER_MARK + "\n")
    if not sep:
        raise SystemExit("footer marker not found: %r" % FOOTER_MARK)

    out_lines = [HEADER_NEW]
    stats = {"entries": 0, "colored": 0, "unmapped": []}
    for line in body.split("\n")[1:]:
        if not line.strip():
            continue
        m = NAME_RE.search(line)
        if not m:
            raise SystemExit("entry without Name: %r" % line[:120])
        line = NAME_RE.sub("Name = '%s'" % m.group(1), line, count=1)
        c = COLOR_RE.search(line)
        if c:
            rgb = tuple(round(float(c.group(i)) * 255) for i in (1, 2, 3))
            cls = REVERSE.get(rgb)
            if cls is None:
                raise SystemExit("colour %s has no TreeValue class" % (rgb,))
            line = COLOR_RE.sub("TreeValue = '%s'" % cls, line, count=1)
            stats["colored"] += 1
        stats["entries"] += 1
        out_lines.append(line)
    return "\n".join(out_lines) + "\n\n" + FOOTER, stats


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    src = args[0]
    out = src
    if "--out" in args:
        out = args[args.index("--out") + 1]
    text = open(src, encoding="utf-8").read()
    new_text, stats = convert(text)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_text)
    print("%s -> %s: %d entries, %d recoloured to TreeValue classes"
          % (os.path.basename(src), os.path.basename(out),
             stats["entries"], stats["colored"]))


if __name__ == "__main__":
    main()
