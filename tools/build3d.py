#!/usr/bin/env python3
"""Parse partTable build exports (Roblox building-game dumps) and render them.

Usage:
  python3 tools/build3d.py stats                 # infer part footprints from data
  python3 tools/build3d.py ascii <file> [name]   # top-down ASCII occupancy map
  python3 tools/build3d.py render <file> <png> [yaw_deg] [pitch_deg]
"""
import math
import os
import re
import struct
import sys
import zlib
from collections import Counter, defaultdict

ENTRY_RE = re.compile(
    r"CFrame\.new\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,"
    r"\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,"
    r"\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,"
    r"\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)\s*,"
    r"\s*Name\s*=\s*[\"']([^\"']+)[\"']"
    r"(?:\s*,\s*TreeValue\s*=\s*[\"']([^\"']*)[\"'])?"
    r"(?:\s*,\s*Color\s*=\s*Color3\.new\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\))?"
)

# TreeValue class colours, from the partTable builds' own loaders (message.txt
# and the Castle treeclass palette).
TREE_PALETTE = {
    "Generic": (204, 142, 105), "Oak": (234, 184, 146), "Cherry": (163, 75, 75),
    "Fir": (215, 197, 154), "Pine": (215, 197, 154), "Birch": (205, 205, 205),
    "Walnut": (105, 64, 40), "Koa": (143, 76, 42), "Volcano": (255, 0, 0),
    "GreenSwampy": (52, 142, 64), "GoldSwampy": (226, 155, 64),
    "Palm": (226, 220, 188), "SnowGlow": (255, 255, 0), "Frost": (159, 243, 233),
    "CaveCrawler": (16, 42, 220), "BlueSpruce": (159, 173, 192),
    "LoneCave": (248, 248, 248), "Spooky": (170, 85, 0), "SpookyNeon": (170, 85, 0),
}


def parse(path):
    """Return list of dicts: pos(x,y,z), mat(3x3 row-major as cols), name."""
    parts = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    for m in ENTRY_RE.finditer(text):
        v = [float(m.group(i)) for i in range(1, 13)]
        name = m.group(13)
        tree = m.group(14)
        color = None
        if m.group(15) is not None:
            color = tuple(float(m.group(i)) for i in (15, 16, 17))
        elif tree in TREE_PALETTE:
            color = tuple(c / 255.0 for c in TREE_PALETTE[tree])
        # Roblox CFrame.new(x,y,z, r00,r01,r02, r10,r11,r12, r20,r21,r22):
        # world = M * local, so the COLUMNS of the matrix are the part's local
        # axes expressed in world space (rows are not - using rows mirrors
        # every wedge slope the wrong way).
        xaxis = (v[3], v[6], v[9])
        yaxis = (v[4], v[7], v[10])
        zaxis = (v[5], v[8], v[11])
        parts.append({
            "pos": (v[0], v[1], v[2]),
            "x": xaxis, "y": yaxis, "z": zaxis,
            "name": name,
            "color": color,
            "tree": tree,
        })
    return parts


# ---------------------------------------------------------------- footprints
def infer_footprints(files):
    """For each part name, look at how instances sit next to each other.

    For tiling parts (floors/walls/wedges) the common nonzero coordinate
    spacing equals the part's footprint along that axis.
    """
    coords = defaultdict(lambda: (set(), set(), set()))  # name -> (xs, ys, zs)
    for f in files:
        for p in parse(f):
            xs, ys, zs = coords[p["name"]]
            xs.add(round(p["pos"][0], 2))
            ys.add(round(p["pos"][1], 2))
            zs.add(round(p["pos"][2], 2))
    out = {}
    for name, (xs, ys, zs) in coords.items():
        out[name] = (deltas(xs), deltas(ys), deltas(zs), len(xs))
    return out


def deltas(vals):
    vals = sorted(vals)
    c = Counter()
    for a, b in zip(vals, vals[1:]):
        d = round(b - a, 2)
        if 0.01 < d <= 32:
            c[d] += 1
    return c.most_common(5)


# ------------------------------------------------------------------ geometry
# footprint per part (sx, sy, sz) in the part's LOCAL frame.
# Ground truth: the user's real in-game exports (Musseum v1.lua.txt) place
# walls running along world X with rotation ID and along world Z with R90,
# and in-game screenshots of R90-on-X walls show 1-stud-wide fins at 4-stud
# spacing -> the wall's 4-stud length is along LOCAL X and its 1-stud
# thickness along LOCAL Z.  (An earlier guess of long-axis-local-Z turned
# every wall 90 degrees out of its line.)
PART_SIZE = {
    "Floor2Large": (8, 0.2, 8),
    "Floor2Small": (2, 0.2, 2),
    "Floor2Tiny": (1, 0.2, 1),
    "Floor2": (4, 0.2, 4),
    "Floor1Large": (8, 1.0, 8),
    "Floor1Small": (2, 1.0, 2),
    "Floor1Tiny": (1, 1.0, 1),
    "Floor1": (4, 1.0, 4),
    "Wall2Tall": (4, 8, 1),
    "Wall2TallThin": (2, 8, 1),
    "Wall2Short": (4, 4, 1),
    "Wall2ShortThin": (2, 4, 1),
    "Wall2": (4, 2, 1),
    "Wall2Thin": (2, 2, 1),
    "Wall2TallCorner": (2, 8, 2),
    "Wall2Corner": (2, 2, 2),
    "Wall2ShortCorner": (2, 4, 2),
    "Wall3TallThin": (2, 8, 1),
    "GlassPane4": (4, 8, 1),
    "GlassPane2": (2, 8, 1),
    "GlassDoor1": (4, 8, 1),
    "Door3": (6, 8, 1),
    "Post": (1, 4, 1),
    "Stair1": (4, 2, 4),
    "Stair2": (4, 2, 4),
    "Ladder1": (4, 4, 1),
    "Chair1": (2, 5, 2),
    "Wedge1": (4, 1, 4), "Wedge2": (4, 2, 4), "Wedge3": (4, 3, 4),
    "Wedge4": (4, 4, 4), "Wedge5": (4, 5, 4), "Wedge6": (4, 6, 4),
    "Wedge7": (4, 7, 4), "Wedge8": (4, 8, 4), "Wedge9": (4, 9, 4),
    "Wedge10": (4, 10, 4),
    # --- Hant.txt parts (sizes inferred from placement steps across exports) ---
    # CounterTop1 tiles a dense 4-stud grid at y=0.2 -> 4x4, h=0.4 (flush 0..0.4)
    "CounterTop1": (4, 0.4, 4),
    "CounterTop1Thin": (4, 0.4, 4),
    # _Thin wedges step at 1.0 in rows/columns -> 1-stud footprint
    "Wedge1_Thin": (1, 1, 1), "Wedge2_Thin": (1, 2, 1),
    "Wedge3_Thin": (1, 3, 1), "Wedge4_Thin": (1, 4, 1),
    "Wedge5_Thin": (1, 5, 1), "Wedge6_Thin": (1, 6, 1),
    "Wedge7_Thin": (1, 7, 1), "Wedge8_Thin": (1, 8, 1),
    "Wedge9_Thin": (1, 9, 1), "Wedge10_Thin": (1, 10, 1),
    "Door1": (4, 8, 1), "Door2": (2, 8, 1),
    "Painting6": (6, 4, 0.2), "Painting3": (3, 3, 0.2),
    "Lever0": (0.4, 1, 0.4),
    "UtilityTruck2": (6, 4, 10),
}

PART_COLOR = {
    "Floor2Large": (120, 110, 100), "Floor2Small": (120, 110, 100),
    "Floor2Tiny": (130, 120, 110), "Floor2": (120, 110, 100),
    "Floor1Large": (150, 140, 128), "Floor1Small": (150, 140, 128),
    "Floor1Tiny": (160, 150, 138), "Floor1": (150, 140, 128),
    "Wall2Tall": (168, 152, 132), "Wall2TallThin": (168, 152, 132),
    "Wall2Short": (160, 146, 128), "Wall2ShortThin": (160, 146, 128),
    "Wall2": (160, 146, 128), "Wall2Thin": (160, 146, 128),
    "Wall2TallCorner": (150, 136, 118), "Wall2Corner": (150, 136, 118),
    "Wall2ShortCorner": (150, 136, 118), "Wall3TallThin": (168, 152, 132),
    "GlassPane4": (130, 180, 210), "GlassPane2": (130, 180, 210),
    "GlassDoor1": (110, 160, 190), "Door3": (120, 90, 60),
    "Post": (90, 82, 74), "Stair1": (170, 155, 135),
    "Ladder1": (100, 92, 84), "Chair1": (110, 80, 55),
    "Wedge1": (190, 100, 80), "Wedge2": (190, 100, 80),
    "Wedge3": (190, 100, 80), "Wedge4": (190, 100, 80),
    "Wedge5": (190, 100, 80), "Wedge6": (190, 100, 80),
    "Wedge7": (190, 100, 80), "Wedge8": (190, 100, 80),
    "Wedge9": (190, 100, 80), "Wedge10": (190, 100, 80),
}

WEDGE_SLOPE = {
    # wedge parts: which local direction the slope faces (heuristic)
    "Wedge1": "z", "Wedge2": "z", "Wedge3": "z", "Wedge4": "z",
    "Wedge5": "z", "Wedge6": "z", "Wedge7": "z", "Wedge8": "z",
    "Wedge9": "z", "Wedge10": "z",
}


def part_box(p):
    sx, sy, sz = PART_SIZE.get(p["name"], (2, 2, 2))
    corners = []
    for dx in (-sx / 2, sx / 2):
        for dy in (-sy / 2, sy / 2):
            for dz in (-sz / 2, sz / 2):
                ax, ay, az = p["pos"]
                bx = ax + p["x"][0] * dx + p["y"][0] * dy + p["z"][0] * dz
                by = ay + p["x"][1] * dx + p["y"][1] * dy + p["z"][1] * dz
                bz = az + p["x"][2] * dx + p["y"][2] * dy + p["z"][2] * dz
                corners.append((bx, by, bz))
    return corners


BOX_FACES = [
    ((0, 1, 3, 2), (-1, 0, 0)), ((4, 6, 7, 5), (1, 0, 0)),
    ((0, 4, 5, 1), (0, -1, 0)), ((2, 3, 7, 6), (0, 1, 0)),
    ((0, 2, 6, 4), (0, 0, -1)), ((1, 5, 7, 3), (0, 0, 1)),
]

WEDGE_FACES = [
    # prism: slope from low front (z-) to high back (z+)
    ((0, 1, 5, 4), None),          # slope quad (computed)
    ((0, 4, 6, 2), (-1, 0, 0)),
    ((3, 7, 5, 1), (1, 0, 0)),
    ((0, 2, 3, 1), (0, -1, 0)),
    ((2, 6, 7, 3), (0, 0, 1)),
]


def faces_for(p):
    """Return triangles as (pts3, worldNormal). Normal may be None for slopes."""
    corners = part_box(p)
    if p["name"] in WEDGE_SLOPE:
        # right-triangle prism, low at local -Z, high at local +Z
        # corner index: bit2=dx, bit1=dy, bit0=dz
        c = corners
        tris = [
            ([c[0], c[1], c[5]], (0, -1, 0)), ([c[0], c[5], c[4]], (0, -1, 0)),
            ([c[1], c[5], c[6]], (0, 0, 1)), ([c[1], c[6], c[2]], (0, 0, 1)),
            ([c[0], c[1], c[2]], (-1, 0, 0)),
            ([c[4], c[5], c[6]], (1, 0, 0)),
            ([c[0], c[4], c[6]], None), ([c[0], c[6], c[2]], None),
        ]
        return tris
    out = []
    for idx, nlocal in BOX_FACES:
        quad = [corners[i] for i in idx]
        n = (p["x"][0] * nlocal[0] + p["y"][0] * nlocal[1] + p["z"][0] * nlocal[2],
             p["x"][1] * nlocal[0] + p["y"][1] * nlocal[1] + p["z"][1] * nlocal[2],
             p["x"][2] * nlocal[0] + p["y"][2] * nlocal[1] + p["z"][2] * nlocal[2])
        out.append(([quad[0], quad[1], quad[2]], n))
        out.append(([quad[0], quad[2], quad[3]], n))
    return out


# ------------------------------------------------------------------- PNG out
def write_png(path, w, h, pixels):
    raw = b"".join(b"\x00" + bytes(pixels[y]) for y in range(h))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def render(parts, out_path, yaw_deg=35, pitch_deg=28, width=900, height=700,
           ortho_w=None, title=None):
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)

    def view(p):
        # world -> camera: yaw about Y then pitch about X
        x, y, z = p
        x1 = x * cy + z * sy
        z1 = -x * sy + z * cy
        y1 = y
        y2 = y1 * cp - z1 * sp
        z2 = y1 * sp + z1 * cp
        return (x1, y2, z2)

    tris = []
    light = (-0.45, 0.78, 0.44)
    ll = math.sqrt(sum(c * c for c in light))
    light = tuple(c / ll for c in light)
    ymin = min(min(view(c)[1] for c in part_box(p)) for p in parts)
    ymax = max(max(view(c)[1] for c in part_box(p)) for p in parts)
    for p in parts:
        if p.get("color"):
            base = tuple(max(24, min(255, int(c * 255))) for c in p["color"])
        else:
            base = PART_COLOR.get(p["name"], (140, 140, 140))
        for quad, n in faces_for(p):
            pts = [view(c) for c in quad]
            if n is not None:
                vn = (p["x"][0] * n[0] + p["y"][0] * n[1] + p["z"][0] * n[2],
                      p["x"][1] * n[0] + p["y"][1] * n[1] + p["z"][1] * n[2],
                      p["x"][2] * n[0] + p["y"][2] * n[1] + p["z"][2] * n[2])
                vl = view(vn)
            else:
                a, b, c3 = quad[0], quad[1], quad[2]
                e1 = tuple(b[i] - a[i] for i in range(3))
                e2 = tuple(c3[i] - a[i] for i in range(3))
                nrm = (e1[1] * e2[2] - e1[2] * e2[1],
                       e1[2] * e2[0] - e1[0] * e2[2],
                       e1[0] * e2[1] - e1[1] * e2[0])
                nl = math.sqrt(sum(v * v for v in nrm)) or 1
                nrm = tuple(v / nl for v in nrm)
                vl = view(nrm)
            # z-buffer handles occlusion; no backface culling needed
            lam = abs(vl[0] * light[0] + vl[1] * light[1] + vl[2] * light[2])
            shade = 0.42 + 0.58 * lam
            col = tuple(min(255, int(c * shade)) for c in base)
            tris.append((pts, col))

    xs = [v[0] for p in parts for v in (view(c) for c in part_box(p))]
    ys = [v[1] for p in parts for v in (view(c) for c in part_box(p))]
    zs = [v[2] for p in parts for v in (view(c) for c in part_box(p))]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxzs = min(zs), max(zs)
    span = ortho_w or max(maxx - minx, (maxy - miny) * width / height) * 1.08
    scale = width / span
    ox = width / 2 - (minx + maxx) / 2 * scale
    oy = height / 2 + (miny + maxy) / 2 * scale
    znear, zfar = minz - 1, maxzs + 1

    fb = [[28, 30, 36] * width for _ in range(height)]
    zb = [[-1e18] * width for _ in range(height)]

    def draw_tri(pts, col):
        scr = []
        for (x, y, z) in pts:
            sxp = x * scale + ox
            syp = -y * scale + oy
            scr.append((sxp, syp, z))
        minx_i = max(0, int(min(s[0] for s in scr)))
        maxx_i = min(width - 1, int(max(s[0] for s in scr)) + 1)
        miny_i = max(0, int(min(s[1] for s in scr)))
        maxy_i = min(height - 1, int(max(s[1] for s in scr)) + 1)
        if minx_i > maxx_i or miny_i > maxy_i:
            return
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = scr
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-9:
            return
        for py in range(miny_i, maxy_i + 1):
            rowz = zb[py]
            rowp = fb[py]
            for px in range(minx_i, maxx_i + 1):
                w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / d
                w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / d
                w2 = 1 - w0 - w1
                if w0 < -0.001 or w1 < -0.001 or w2 < -0.001:
                    continue
                z = w0 * z0 + w1 * z1 + w2 * z2
                if z > rowz[px]:
                    rowz[px] = z
                    i = px * 3
                    rowp[i] = col[0]
                    rowp[i + 1] = col[1]
                    rowp[i + 2] = col[2]

    for pts, col in tris:
        draw_tri(pts, col)
    write_png(out_path, width, height, fb)
    return out_path


# --------------------------------------------------------------- ascii views
def ascii_top(parts, step=2.0, only=None):
    parts = [p for p in parts if only is None or p["name"] == only]
    if not parts:
        return "(no parts)"
    xs = [p["pos"][0] for p in parts]
    zs = [p["pos"][2] for p in parts]
    minx, maxx = min(xs), max(xs)
    minz, maxz = min(zs), max(zs)
    w = int((maxx - minx) / step) + 1
    h = int((maxz - minz) / step) + 1
    grid = [[" "] * w for _ in range(h)]
    sym = {
        "Floor2Large": "#", "Floor2Small": "+", "Floor2Tiny": ".", "Floor2": "#",
        "Floor1Large": "#", "Floor1Small": "o", "Floor1Tiny": "'", "Floor1": "+",
        "Wall2Tall": "W", "Wall2TallThin": "w", "Wall2Short": "S", "Wall2ShortThin": "w",
        "Wall2": "M", "Wall2Thin": "m", "Wall2TallCorner": "C",
        "Wall2Corner": "C", "Wall2ShortCorner": "c", "Wall3TallThin": "w",
        "GlassPane4": "G", "GlassPane2": "g", "GlassDoor1": "D", "Door3": "D",
        "Post": "P", "Stair1": "H", "Ladder1": "h", "Chair1": "c",
        "Wedge1": "/", "Wedge2": "/", "Wedge3": "/", "Wedge4": "/",
        "Wedge5": "/", "Wedge6": "/", "Wedge7": "/", "Wedge8": "/",
        "Wedge9": "/", "Wedge10": "/",
        "CounterTop1": "=", "CounterTop1Thin": "-",
        "Stair2": "H", "Door1": "D", "Door2": "D",
        "Painting6": "p", "Painting3": "p", "Lever0": "l",
        "UtilityTruck2": "T",
    }
    for p in parts:
        sx, sy, sz = PART_SIZE.get(p["name"], (2, 2, 2))
        # footprint under rotation: extents of local axes in world
        ex = abs(p["x"][0]) * sx + abs(p["z"][0]) * sz
        ez = abs(p["x"][2]) * sx + abs(p["z"][2]) * sz
        cx, cz = p["pos"][0], p["pos"][2]
        i0 = int(round((cx - ex / 2 - minx) / step))
        i1 = int(round((cx + ex / 2 - minx) / step))
        k0 = int(round((cz - ez / 2 - minz) / step))
        k1 = int(round((cz + ez / 2 - minz) / step))
        ch = sym.get(p["name"], "?")
        for k in range(max(0, k0), min(h, max(k1, k0 + 1))):
            for i in range(max(0, i0), min(w, max(i1, i0 + 1))):
                grid[k][i] = ch
    lines = ["x from %g to %g, z from %g to %g, cell %g" % (minx, maxx, minz, maxz, step)]
    header = "      " + "".join(str(int((minx + i * step) // 10) % 10) if i % 5 == 0 else " "
                                for i in range(w))
    lines.append(header)
    for k, row in enumerate(grid):
        lines.append("%6d" % int(minz + k * step) + "".join(row))
    return "\n".join(lines)


RAMP = " .:-=+*#%@"


def preview(parts, yaw_deg=35, pitch_deg=25, width=150, height=56):
    """Offscreen render printed as ASCII so the shape can be inspected."""
    import io
    tmp = io.BytesIO()
    path = "/tmp/_prev.png"
    render(parts, path, yaw_deg, pitch_deg, width=width, height=height)
    data = open(path, "rb").read()
    # decode our own PNG (8-bit RGB, no interlace)
    pos = 8
    w = h = None
    idat = b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
        elif tag == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    stride = w * 3 + 1
    lines = []
    for y in range(0, h, 2):          # sample every 2nd row for aspect
        row = raw[y * stride + 1:(y + 1) * stride]
        out = []
        for x in range(0, w, 1):
            i = x * 3
            lum = (row[i] * 3 + row[i + 1] * 6 + row[i + 2]) // 10
            lum = min(9, max(0, (lum * 10) // 256))
            out.append(RAMP[lum])
        lines.append("".join(out))
    return "\n".join(lines)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    all_files = sorted(
        os.path.join(root, f) for f in os.listdir(root) if f.endswith(".txt")
    )
    if cmd == "stats":
        data = infer_footprints(all_files)
        for name in sorted(data):
            dx, dy, dz, n = data[name]
            print("%-18s n=%-5d  dx=%s  dy=%s  dz=%s" % (name, n, dx, dy, dz))
    elif cmd == "ascii":
        path = sys.argv[2]
        only = sys.argv[3] if len(sys.argv) > 3 else None
        print(ascii_top(parse(path), only=only))
    elif cmd == "preview":
        path = sys.argv[2]
        yaw = float(sys.argv[3]) if len(sys.argv) > 3 else 35
        pitch = float(sys.argv[4]) if len(sys.argv) > 4 else 25
        parts = parse(path)
        if len(sys.argv) > 8:
            x0, x1, z0, z1 = (float(v) for v in sys.argv[5:9])
            parts = [p for p in parts if x0 <= p["pos"][0] <= x1 and z0 <= p["pos"][2] <= z1]
        print("parts in view: %d" % len(parts))
        print(preview(parts, yaw, pitch))
    elif cmd == "render":
        path = sys.argv[2]
        out = sys.argv[3]
        yaw = float(sys.argv[4]) if len(sys.argv) > 4 else 35
        pitch = float(sys.argv[5]) if len(sys.argv) > 5 else 28
        parts = parse(path)
        render(parts, out, yaw, pitch)
        print("wrote", out, "parts:", len(parts))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
