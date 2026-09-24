"""Buffer tube, castle nut, end plate, MOE SL-style stock and A2 pistol grip (mm)."""
import math

import bmesh
from mathutils import Matrix, Vector

from ar15lib import (S, bevel, boolean, box, clip_outline, cylinder, fillet, inset_outline, lathe, lod, merge,
                     mk, prism, rounded_prism, rrect, smooth, stadium)
from parts_receivers import diff, union

TUBE_R = 14.6            # mil-spec receiver extension, 1.148"
TUBE_X0 = -199.0         # threaded into the lower receiver
TUBE_X1 = -384.0         # rear end of the tube
STOCK_TRAVEL = 81.2      # 33.0" collapsed -> 36.2" extended (6 positions)
STOCK_FRONT_X = -212.5


def buffer_tube(M):
    bm = lathe([(TUBE_X0, 0), (TUBE_X0, 13.2), (TUBE_X0 + 1, TUBE_R), (TUBE_X1 + 1.5, TUBE_R),
                (TUBE_X1, TUBE_R - 1.5), (TUBE_X1, 0)], seg=40)
    # indexing rail on the bottom with the six adjustment holes
    box(-214.0, -4.9, -18.6, TUBE_X1 + 2.0, 4.9, -12.0, bm=bm)
    ob = mk('ar15_buffer_tube', bm, M['alu'])
    holes = bmesh.new()
    for k in range(0 if lod() else 6):
        x = -230.0 - 16.24 * k
        cylinder((x, 0, -22.0), (x, 0, -15.0), 2.6, seg=16, bm=holes)
    diff(ob, holes)
    bevel(ob, 0.5, seg=2, angle=30)
    smooth(ob)
    return ob


def castle_nut(M):
    ob = mk('ar15_castle_nut', lathe([(-212.0, TUBE_R + 0.05), (-212.0, 16.3), (-211.2, 17.0),
                                      (-204.0, 17.0), (-204.0, TUBE_R + 0.05)], seg=48, closed=True, lod_seg=12),
            M['steel'])
    cut = bmesh.new()
    for k in range(3):
        b = box(-213.0, -2.6, 13.5, -209.0, 2.6, 18.5)
        b.transform(Matrix.Rotation(math.radians(30 + 120 * k), 4, 'X'))
        merge(cut, b)
    # knurl ring
    for k in range(0 if lod() else 40):
        b = box(-207.5, -0.35, 16.6, -204.6, 0.35, 17.6)
        b.transform(Matrix.Rotation(math.radians(9 * k), 4, 'X'))
        merge(cut, b)
    diff(ob, cut)
    bevel(ob, 0.25, seg=1, angle=35)
    smooth(ob)
    return ob


def end_plate(M):
    outline = [(math.cos(math.radians(a)) * 17.6, math.sin(math.radians(a)) * 17.6)
               for a in range(-60, 241, 30 if lod() else 10)]
    outline += [(-5.5, -21.5), (5.5, -21.5)]
    pts = fillet(outline, [0] * (len(outline) - 2) + [1.5, 1.5], 3)
    ob = mk('ar15_end_plate', prism(pts, 'YZ', -204.0, -198.0), M['steel'])
    if not lod():
        cut = lathe([(-205.0, TUBE_R + 0.05), (-197.0, TUBE_R + 0.05)], seg=48)
        diff(ob, cut)
    bevel(ob, 0.5, seg=2, angle=30)
    smooth(ob)
    return ob


# ---------------------------------------------------------------------------
# Stock (collapsed position; slides STOCK_TRAVEL mm rearwards on the tube)
# ---------------------------------------------------------------------------
PAD_T = 9.0  # buttpad thickness

# rear (butt) surface of the stock, top to bottom
REAR_LINE = [(-393.0, 16.0), (-395.7, 2.0), (-394.9, -14.0), (-393.3, -32.0), (-390.9, -52.0),
             (-389.7, -74.0), (-388.3, -90.0), (-386.0, -100.5)]
# joint between the stock body and the rubber buttpad
JOINT_LINE = [(-383.0, 30.0), (-383.0, 18.0), (-387.2, 2.0), (-386.4, -14.0), (-384.8, -32.0),
              (-382.4, -52.0), (-381.2, -74.0), (-379.8, -90.0), (-377.6, -100.5), (-378.5, -106.0),
              (-380.5, -130.0)]


def _stock_outline():
    top_f, top_r = 17.8, 18.8
    pts = [(STOCK_FRONT_X, top_f), (-300.0, 18.3), (-383.0, top_r)] + REAR_LINE + [
        (-381.0, -110.5), (-374.0, -112.3), (-365.5, -112.3),
        # leg front edge up to the body
        (-358.2, -110.4), (-320.5, -54.2), (-315.0, -51.8),
        (-285.0, -48.3), (-255.0, -44.3), (-235.0, -41.9), (-224.0, -40.2),
        (-218.0, -35.0), (-214.2, -27.0), (-212.6, -18.0),
    ]
    radii = [2.0, 0, 3.0,
             4.0, 6.0, 0, 0, 0, 0, 0, 4.0,
             5.0, 3.0, 3.0,
             3.0, 12.0, 6.0,
             0, 0, 0, 6.0,
             6.0, 5.0, 2.0]
    return fillet(pts, radii, 5)


def _stock_section(x0, x1):
    """Cross-section (YZ) of the stock: round top over the tube, flat sides, narrower toe."""
    step = 30 if lod() else 10
    pts = [(math.cos(math.radians(a)) * 18.5, math.sin(math.radians(a)) * 18.5) for a in range(0, 181, step)]
    pts += [(-18.5, -60.0), (-16.2, -116.0), (16.2, -116.0), (18.5, -60.0)]
    return prism(pts, 'YZ', x0, x1)


def _behind_joint(y=30.0):
    return prism([(-440.0, 30.0)] + JOINT_LINE + [(-440.0, -130.0)], 'XZ', -y, y)


def stock(M):
    ob = mk('ar15_stock', rounded_prism(_stock_outline(), 'XZ', -18.5, 18.5, 4.5, seg=5, n=2.5), M['polymer'])
    boolean(ob, _stock_section(-420, -200), op='INTERSECT')
    diff(ob, _behind_joint())

    # side pockets (both sides) leaving a 12 mm centre web
    pocket = fillet([(-377.5, -16.0), (-238.0, -16.0), (-247.0, -38.2), (-318.5, -44.6),
                     (-322.0, -49.5), (-356.8, -101.8), (-363.5, -106.8), (-377.5, -106.8)],
                    [2.5, 2.5, 3.0, 2.0, 3.0, 2.5, 2.5, 2.5], 4)
    cut = prism(pocket, 'XZ', -25.0, -6.0)
    prism(pocket, 'XZ', 6.0, 25.0, bm=cut)
    diff(ob, cut)

    # ribs and QD boss inside the pockets
    add = bmesh.new()
    cylinder((-356.5, -18.4, -40.0), (-356.5, 18.4, -40.0), 7.6, seg=28, bm=add)
    rib = fillet([(-356.5, -43.0), (-354.5, -36.8), (-322.5, -45.2), (-321.0, -50.5)], 1.0, 3)
    prism(rib, 'XZ', -18.3, 18.3, bm=add)
    union(ob, add)

    thru = bmesh.new()
    prism(stadium(-350.0, -26.4, 32.0, 4.2, seg=6), 'XZ', -30, 30, bm=thru)
    prism(stadium(-354.5, -89.5, 33.5, 3.9, angle=math.radians(59.6), seg=6), 'XZ', -30, 30, bm=thru)
    cylinder((-356.5, -30, -40.0), (-356.5, 30, -40.0), 5.0, seg=24, bm=thru)
    # bore and indexing-rail channel for the buffer tube (the game mesh keeps the stock solid)
    if not lod():
        lathe([(STOCK_FRONT_X - 5, 14.95), (-386.0, 14.95)], seg=40, bm=thru)
        box(-386.0, -5.1, -19.2, STOCK_FRONT_X + 5, 5.1, -10.0, bm=thru)
    diff(ob, thru)

    bevel(ob, 0.6, seg=2, angle=35)
    smooth(ob, angle=35)
    return ob


def buttpad(M):
    ob = mk('ar15_buttpad', rounded_prism(_stock_outline(), 'XZ', -19.2, 19.2, 4.8, seg=5, n=2.5), M['rubber'])
    sec = [(math.cos(math.radians(a)) * 19.2, math.sin(math.radians(a)) * 19.2)
           for a in range(0, 181, 30 if lod() else 10)]
    sec += [(-19.2, -60.0), (-16.9, -116.0), (16.9, -116.0), (19.2, -60.0)]
    boolean(ob, prism(sec, 'YZ', -420, -300), op='INTERSECT')
    boolean(ob, _behind_joint(), op='INTERSECT')
    # serrations across the rear face
    cut = bmesh.new()
    for i in range(0 if lod() else len(REAR_LINE) - 1):
        (x0, z0), (x1, z1) = REAR_LINE[i], REAR_LINE[i + 1]
        L = math.hypot(x1 - x0, z1 - z0)
        n = max(1, round(L / 3.4))
        ang = math.degrees(math.atan2(z1 - z0, x1 - x0))
        for k in range(n):
            t = (k + 0.5) / n
            cx, cz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            b = box(-0.8, -30.0, -0.9, 0.8, 30.0, 0.9)
            b.transform(Matrix.Translation(Vector((cx, 0.0, cz)) * S) @
                        Matrix.Rotation(math.radians(-ang + 90.0), 4, 'Y') @
                        Matrix.Rotation(math.radians(45.0), 4, 'Y'))
            merge(cut, b)
    diff(ob, cut)
    smooth(ob, angle=40)
    return ob


def stock_lever(M):
    pts = fillet([(-346.5, -29.0), (-346.5, -34.2), (-300.0, -31.8), (-286.0, -31.2), (-280.5, -27.5),
                  (-282.0, -20.8), (-292.0, -18.6), (-300.5, -22.0), (-322.0, -26.6)],
                 [1.5, 1.5, 3.0, 3.0, 2.0, 3.0, 4.0, 3.0, 3.0], 4)
    bm = prism(pts, 'XZ', -13.2, 13.2)
    for k in range(0 if lod() else 7):
        x = -344.0 + k * 3.1
        box(x - 0.7, -13.8, -33.8, x + 0.7, 13.8, -28.2 + k * 0.25, bm=bm)
    cylinder((-291.0, -14.2, -24.8), (-291.0, 14.2, -24.8), 4.3, seg=20, bm=bm)
    cylinder((-276.5, -9.0, -35.0), (-276.5, -9.0, -21.0), 2.0, seg=12, bm=bm)
    ob = mk('ar15_stock_lever', bm, M['polymer'])
    bevel(ob, 0.5, seg=2, angle=35)
    smooth(ob)
    return ob


def stock_qd(M):
    bm = bmesh.new()
    for s in (-1, 1):
        prof = [(s * 17.6, 4.2), (s * 17.6, 6.9), (s * 19.0, 6.9), (s * 19.4, 6.4), (s * 19.4, 4.2)]
        if s < 0:
            prof = list(reversed(prof))
        merge(bm, lathe(prof, seg=24, axis='Y', center=(-356.5, -40.0), closed=True))
    ob = mk('ar15_stock_qd', bm, M['steel'])
    smooth(ob)
    return ob


# ---------------------------------------------------------------------------
# A2 pistol grip
# ---------------------------------------------------------------------------
GRIP_OUTLINE = [
    (-138.2, -49.0), (-139.4, -62.0), (-141.8, -82.0), (-146.6, -90.0), (-148.4, -94.0),
    (-147.0, -98.0), (-144.6, -101.4), (-146.2, -103.6), (-151.0, -105.0), (-154.5, -106.2),
    (-157.7, -110.0), (-162.5, -118.0), (-167.2, -126.0), (-171.2, -134.0), (-172.6, -140.0),
    (-173.6, -145.8), (-179.0, -146.4), (-199.0, -142.0), (-213.3, -138.0), (-224.6, -134.8),
    (-224.2, -130.0), (-220.5, -126.0), (-214.9, -118.0), (-209.4, -110.0), (-203.8, -102.0),
    (-198.2, -94.0), (-192.7, -86.0), (-187.1, -78.0), (-181.5, -70.0), (-178.4, -66.0),
    (-175.2, -62.0), (-173.4, -57.0), (-172.6, -49.0),
]
GRIP_RADII = [1.0, 10.0, 8.0, 6.0, 4.0,
              3.5, 2.0, 2.0, 5.0, 3.0,
              6.0, 0, 0, 6.0, 5.0,
              3.0, 4.0, 0, 0, 5.0,
              4.0, 0, 0, 0, 0,
              0, 0, 0, 0, 6.0,
              5.0, 4.0, 1.0]


def pistol_grip(M):
    outline = fillet(GRIP_OUTLINE, GRIP_RADII, 6)
    ob = mk('ar15_pistol_grip', rounded_prism(outline, 'XZ', -14.4, 14.4, 6.5, seg=7, n=1.6, lod_seg=2),
            M['polymer'])
    if lod():
        smooth(ob)
        return ob
    # checkered side panels on the flat part of the grip
    panel = clip_outline(inset_outline(outline, 8.0), (-240.0, -129.0, -120.0, -63.0))
    panel = fillet(panel, 2.0, 2) if len(panel) < 40 else panel
    cut = prism(panel, 'XZ', -20.0, -13.95)
    prism(panel, 'XZ', 13.95, 20.0, bm=cut)
    boolean(ob, cut, mat=M['checker'])
    bevel(ob, 0.35, seg=1, angle=40)
    smooth(ob, angle=38)
    return ob
