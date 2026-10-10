#!/usr/bin/env python3
"""Generate the new Halloween base build (Lumber Tycoon 2 partTable export).

Design rules (ground truth: Musseum v1.lua.txt = the user's real in-game
export, which places world-X wall lines with ID and world-Z lines with R90;
the previous R90-on-X file rendered in game as 1-stud-wide fins because the
wall's 4-stud length runs along LOCAL X, not local Z):
  * walls/panes/doors: 4 long (local X) x 8 tall x 1 thick (local Z)
      -> X-running lines use ID  (local X -> world +X)
      -> Z-running lines use R90 (local X -> world +Z)
  * Wedge4 = 4x4x4, slope rises toward local +Z (assumed - LT2 docs silent)
      -> rises toward +Z: ID,  -Z: R180,  +X: R270,  -X: R90
      (note: axes are the matrix COLUMNS, Roblox convention)
  * Floor2Large 8x8x0.2, Floor2 4x4x0.2, Floor1 4x4x1, Floor1Small 2x2x1, Post 1x1x4
  * everything symmetric about x = 383, no doubled parts, no pane/wall overlaps.
"""
import os

ID = (1, 0, 0, 0, 1, 0, 0, 0, 1)
R90 = (0, 0, -1, 0, 1, 0, 1, 0, 0)
R180 = (-1, 0, 0, 0, 1, 0, 0, 0, -1)
R270 = (0, 0, 1, 0, 1, 0, -1, 0, 0)

CX = 383
PLOT_X0, PLOT_X1 = 303, 463
PLOT_Z0, PLOT_Z1 = -330, -170
CRY_X0, CRY_X1 = 371, 395        # crypt, back of the plot
CRY_Z0, CRY_Z1 = -330, -314

parts = []


def add(name, x, y, z, rot=ID):
    parts.append((name, (round(float(x), 2), round(float(y), 2), round(float(z), 2)), rot))


def frange(a, b, step=4):
    out, v = [], float(a)
    while v <= b + 1e-9:
        out.append(round(v, 2))
        v += step
    return out


# --------------------------------------------------------------- the plot
for x in frange(PLOT_X0, PLOT_X1, 8):
    for z in frange(PLOT_Z0, PLOT_Z1, 8):
        add("Floor2Large", x, 0.2, z)


def wall_line(axis, fixed, a, b, courses, openings=None):
    """Complete wall run on the 4-grid. openings: {(coord, course): name|None}."""
    openings = openings or {}
    rot = ID if axis == "x" else R90
    for c in courses:
        for t in frange(a, b, 4):
            name = openings.get((t, c), "Wall2Tall")
            if name is None:
                continue
            if axis == "x":
                add(name, t, c, fixed, rot)
            else:
                add(name, fixed, c, t, rot)


def deck(x0, x1, z0, z1, y, kind="Floor2Large", skip=None):
    step = {"Floor2Large": 8, "Floor2": 4, "Floor1": 4}[kind]
    for x in frange(x0 + step // 2, x1 - step // 2, step):
        for z in frange(z0 + step // 2, z1 - step // 2, step):
            if skip and (x, z) in skip:
                continue
            add(kind, x, y, z)


def ring(y, cx, cz, span):
    """Square ring of Wedge4 centred on (cx,cz), each side rising to the centre.
    Slope rises toward local +Z; under column axes R90 points local Z at -X
    and R270 at +X, so the west edge needs R270 and the east edge R90."""
    n = span // 4
    xs = [cx - span / 2 + 2 + 4 * i for i in range(n)]
    zs = [cz - span / 2 + 2 + 4 * i for i in range(n)]
    for i, x in enumerate(xs):
        for j, z in enumerate(zs):
            if i not in (0, n - 1) and j not in (0, n - 1):
                continue
            if j == 0:
                rot = ID
            elif j == n - 1:
                rot = R180
            elif i == 0:
                rot = R270
            else:
                rot = R90
            add("Wedge4", x, y, z, rot)


def seam_fill(x, z, top_y):
    """Fill the 1.5-stud vertical seam left where a 1-thick X-run wall meets
    the end of a 4-long Z-run wall (a 4-grid corner with 1-thick walls can
    never butt flush). A 1x1 Post stack closes it without overlapping."""
    for y in frange(2.4, top_y - 2, 4):
        add("Post", x, y, z)


# ----------------------------------------------------------------- manor
MAN_X0, MAN_X1 = 351, 415
MAN_Z0, MAN_Z1 = -306, -266          # front faces +Z (toward the yard/gate)
C3 = (0.4, 8.4, 16.4)                # 3 wall courses -> top at 20.4

front_open = {
    (383, 0.4): "GlassDoor1",
    (379, 8.4): "GlassPane4", (387, 8.4): "GlassPane4",
    (375, 16.4): "GlassPane4", (383, 16.4): "GlassPane4", (391, 16.4): "GlassPane4",
    (351, 8.4): "GlassPane4", (355, 8.4): "GlassPane4",
    (411, 8.4): "GlassPane4", (415, 8.4): "GlassPane4",
    (351, 16.4): "GlassPane4", (355, 16.4): "GlassPane4",
    (411, 16.4): "GlassPane4", (415, 16.4): "GlassPane4",
}
wall_line("x", MAN_Z1, 351, 355, C3, front_open)
wall_line("x", MAN_Z1, 375, 391, C3, front_open)
wall_line("x", MAN_Z1, 411, 415, C3, front_open)

back_open = {(383, 0.4): "GlassDoor1"}
for t in (355, 363, 371, 379, 387, 395, 403, 411):
    back_open[(t, 8.4)] = "GlassPane4"
for t in (351, 359, 367, 375, 383, 391, 399, 407, 415):
    back_open[(t, 16.4)] = "GlassPane4"
wall_line("x", MAN_Z0, MAN_X0, MAN_X1, C3, back_open)

side_open = {}
for t in (-298, -290, -282, -274):
    side_open[(t, 8.4)] = "GlassPane4"
for t in (-294, -286, -278):
    side_open[(t, 16.4)] = "GlassPane4"
wall_line("z", MAN_X0, MAN_Z0 + 4, MAN_Z1 - 4, C3, side_open)
wall_line("z", MAN_X1, MAN_Z0 + 4, MAN_Z1 - 4, C3, side_open)

deck(MAN_X0, MAN_X1, MAN_Z0, MAN_Z1, 12.4,       # second floor on course 2
     skip={(363, -302), (371, -302), (395, -302), (403, -302)})  # ladder hatch
deck(MAN_X0, MAN_X1, MAN_Z0, MAN_Z1, 20.5)   # roof deck on the wall top

for lx in (367, 399):                        # ladders, between the back windows
    for y in (2.4, 6.4, 10.4):               # (top at 12.4, through the hatch)
        add("Ladder1", lx, y, -305)

for sx, sz in ((MAN_X0, -304.75), (MAN_X1, -304.75),
               (MAN_X0, -267.25), (MAN_X1, -267.25)):
    seam_fill(sx, sz, 20.4)

merl = {(x, MAN_Z0) for x in frange(MAN_X0, MAN_X1, 8)}
merl |= {(x, MAN_Z1) for x in (351, 383, 415)}
for z in frange(MAN_Z0 + 8, MAN_Z1 - 8, 8):
    merl.add((MAN_X0, z))
    merl.add((MAN_X1, z))
for (x, z) in sorted(merl):
    add("Wall2Short", x, 22.4, z, ID if z in (MAN_Z0, MAN_Z1) else R90)

# ----------------------------------------------------------- front towers
TC = (0.4, 8.4, 16.4, 24.4)                   # 4 courses -> top at 28.4
for tx0 in (359, 391):
    west = tx0 == 359
    x0, x1 = tx0, tx0 + 16
    z0, z1 = -266, -250
    if west:                                    # two slits, the middle columns
        open_s = {(x0 + 4, 8.4): "GlassPane4", (x0 + 8, 8.4): "GlassPane4"}
        wall_line("x", z0, x0, x0 + 12, TC, open_s)
    else:
        open_s = {(x0 + 8, 8.4): "GlassPane4", (x0 + 12, 8.4): "GlassPane4"}
        wall_line("x", z0, x0 + 4, x1, TC, open_s)
    wall_line("x", z1, x0, x1, TC,
              {(x0 + 8, 8.4): "GlassPane4", (x0 + 8, 16.4): "GlassPane4"})
    side = {(z0 + 8, 8.4): "GlassPane4", (z0 + 8, 16.4): "GlassPane4"}
    wall_line("z", x0, z0 + 4, z1 - 4, TC, side)
    wall_line("z", x1, z0 + 4, z1 - 4, TC, side)
    deck(x0, x1, z0, z1, 28.5)
    seam_fill(x0, -264.75, 28.4)
    seam_fill(x1, -264.75, 28.4)
    seam_fill(x0, -251.25, 28.4)
    seam_fill(x1, -251.25, 28.4)
    # course 4 above the facade: close the 1.5-stud notch where the tower
    # front wall stops short of the projecting side wall (mirrored pair)
    add("Wall2Tall", x1 if west else x0, 24.4, -266)
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    for y, span in ((30.4, 16), (34.4, 12), (38.4, 8), (42.4, 4)):
        ring(y, cx, cz, span)
    add("Post", cx, 46.4, cz)

# ----------------------------------------------------------------- porch
# balcony deck between the towers, crenellated parapet on the yard side
deck(375, 391, -266, -250, 12.4, "Floor2")
for px in (377, 389):
    for y in (0.4, 8.4):
        add("Wall2TallCorner", px, y, -252)
for px in (379, 383, 387):
    add("Wall2Short", px, 14.4, -252, ID)

# --------------------------------------------------------------- fencing
for x in frange(PLOT_X0, PLOT_X1, 8):
    for z in (PLOT_Z0, PLOT_Z1):
        if z == PLOT_Z1 and x in (375, 383, 391):
            continue                                # gate opening
        if z == PLOT_Z0 and CRY_X0 <= x <= CRY_X1:
            continue                                # crypt wall replaces fence
        add("Post", x, 2.4, z)
for z in frange(PLOT_Z0 + 8, PLOT_Z1 - 8, 8):
    add("Post", PLOT_X0, 2.4, z)
    add("Post", PLOT_X1, 2.4, z)
for gx in (375, 391):                               # gate pillars
    for y in (0.4, 8.4):
        add("Wall2TallCorner", gx, y, -170)
    add("Post", gx, 14.4, -170)

# ------------------------------------------------------------------ path
for z in frange(-246, -178, 4):                    # stone path, gate -> porch
    for x in (381, 385):
        add("Floor2", x, 0.4, z)

# ------------------------------------------------------------- graveyard
for gx in (337, 349, 417, 429):
    for gz in (-198, -210, -222):
        add("Floor1", gx, 0.8, gz)
        add("Floor1Small", gx, 1.8, gz - 1)
        add("Floor1Small", gx, 2.8, gz - 1)

# ------------------------------------------------------------ dead trees
for tx, tz in ((323, -182), (443, -182), (323, -238), (443, -238),
               (315, -270), (451, -270), (315, -318), (451, -318),
               (339, -318), (427, -318)):
    for y in (2.4, 6.4, 10.4):
        add("Post", tx, y, tz)
    add("Wedge4", tx - 2, 12.4, tz, R270)   # branches rise toward the trunk
    add("Wedge4", tx + 2, 12.4, tz, R90)

# ----------------------------------------------------------------- crypt
CC = (0.4, 8.4)
wall_line("x", CRY_Z0, CRY_X0, CRY_X1, CC)
wall_line("z", CRY_X0, CRY_Z0 + 4, CRY_Z1 - 4, CC)
wall_line("z", CRY_X1, CRY_Z0 + 4, CRY_Z1 - 4, CC)
wall_line("x", CRY_Z1, CRY_X0, CRY_X0 + 4, CC)
wall_line("x", CRY_Z1, CRY_X1 - 4, CRY_X1, CC)
wall_line("x", CRY_Z1, CRY_X0 + 8, CRY_X1 - 8, CC, {(383, 0.4): "GlassDoor1"})
deck(CRY_X0, CRY_X1, CRY_Z0, CRY_Z1, 12.5, "Floor2")
cry_ring = {(x, CRY_Z0) for x in frange(CRY_X0, CRY_X1, 4)}
cry_ring |= {(x, CRY_Z1) for x in frange(CRY_X0, CRY_X1, 4)}
cry_ring |= {(CRY_X0, z) for z in frange(CRY_Z0 + 4, CRY_Z1 - 4, 4)}
cry_ring |= {(CRY_X1, z) for z in frange(CRY_Z0 + 4, CRY_Z1 - 4, 4)}
for (x, z) in sorted(cry_ring):
    add("Wall2Short", x, 14.4, z, ID if z in (CRY_Z0, CRY_Z1) else R90)
for px in (379, 383, 387):                     # gable ridge: sits ON the deck
    add("Wedge4", px, 14.6, -324, ID)         # (was 16.4/-325: floating + gap)
    add("Wedge4", px, 14.6, -320, R180)
for sx in (CRY_X0, CRY_X1):
    seam_fill(sx, -328.75, 12.4)
    seam_fill(sx, -315.25, 12.4)

# ------------------------------------------------- pumpkins and porch seats
for px, pz in ((371, -248), (395, -248), (367, -222), (399, -222),
               (375, -186), (391, -186), (363, -194), (403, -194)):
    add("Floor1Small", px, 0.8, pz)
add("Chair1", 379, 0.4, -256, R180)     # y=0.4 = chernobyl's ground-chair height
add("Chair1", 387, 0.4, -256, R180)

# ------------------------------------------------------------- emit file
def fmt(v):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.2f" % v).rstrip("0").rstrip(".")


lines = ["local partTable = {"]
for name, (x, y, z), rot in parts:
    lines.append("    {CFrame = CFrame.new(%s, %s, %s, %s), Name = '%s'},"
                 % (fmt(x), fmt(y), fmt(z), ", ".join(fmt(v) for v in rot), name))
lines += ["}",
          "",
          'local previewFolder = workspace:FindFirstChild("BuildsStructures") or Instance.new("Folder", workspace)',
          'previewFolder.Name = "BuildsStructures"',
          "",
          "for _, v in pairs(partTable) do",
          "    local part = game.ReplicatedStorage.ClientItemInfo:FindFirstChild(v.Name):FindFirstChildOfClass('Model'):Clone()",
          "    part.Parent = previewFolder",
          "    part:SetPrimaryPartCFrame(v.CFrame)",
          "    part.Name = v.Name",
          '    local treeValue = Instance.new("StringValue", part)',
          '    treeValue.Name = "PurchasedBoxItemName"',
          "    treeValue.Value = v.Name",
          "end", ""]

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Halloween.txt")
with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("wrote %s with %d parts" % (out, len(parts)))
