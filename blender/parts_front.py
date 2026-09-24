"""Barrel, gas system, 15" M-LOK handguard and A2 flash hider (dimensions in mm)."""
import math

import bmesh
from mathutils import Matrix, Vector

from ar15lib import (S, bevel, boolean, box, circle, cylinder, fillet, lathe, lod, merge, mk, prism,
                     rrect, smooth, stadium)
from parts_receivers import RAIL_TOP, diff, rail_slot_cutters, rail_teeth, union

# Barrel: 16.1" (408.9 mm) from the bolt face to the crown
BOLT_FACE_X = -8.4
BARREL_LEN = 408.9
MUZZLE_X = BOLT_FACE_X + BARREL_LEN          # 400.5
GAS_PORT_X = BOLT_FACE_X + 177.8             # carbine-length gas system (7")

# Handguard: 15" (381 mm), octagonal, 44 mm across flats
HG_LEN = 381.0
HG_Z0 = 2.3          # centre of the octagon (above the bore)
HG_APO = 22.0        # outer apothem
HG_WALL = 2.8
HG_RAIL_SLOTS = [6.6 + 10.0 * k for k in range(34)]

# A2 flash hider
FH_X0 = 394.2
FH_X1 = 442.5        # muzzle end of the rifle


def octagon(apothem, z0, r, seg=4):
    R = apothem / math.cos(math.radians(22.5))
    pts = [(R * math.cos(math.radians(22.5 + 45 * k)), z0 + R * math.sin(math.radians(22.5 + 45 * k)))
           for k in range(8)]
    return fillet(pts, r, seg)


def facet_frame(angle_deg, apothem=HG_APO, z0=HG_Z0):
    """Matrix placing a local XY slot (extruded along local Z) on an octagon facet.

    angle_deg is the facet's outward normal in the YZ plane, measured from +Y
    towards +Z (0 = left side, 90 = top, 180 = right side, 270 = bottom).
    """
    a = math.radians(angle_deg)
    c = Vector((0.0, apothem * math.cos(a), z0 + apothem * math.sin(a))) * S
    return Matrix.Translation(c) @ Matrix.Rotation(a - math.pi / 2, 4, 'X')


def barrel(M):
    r_gov = 9.525        # 0.750" under the handguard
    r_muz = 8.75         # visible section in front of the handguard
    prof = [
        (BOLT_FACE_X, 2.85), (BOLT_FACE_X, 11.6), (0.0, 11.6), (0.0, 14.2), (3.2, 14.2), (3.2, 12.2),
        (14.0, 12.2), (15.5, r_gov), (GAS_PORT_X + 13.5, r_gov), (GAS_PORT_X + 14.5, r_muz),
        (FH_X0 - 1.5, r_muz), (FH_X0 - 1.0, 6.35), (MUZZLE_X - 0.6, 6.35), (MUZZLE_X, 5.6),
        (MUZZLE_X, 3.4), (MUZZLE_X - 0.5, 2.85),
    ]
    if lod():
        # game mesh: only what shows in front of and through the handguard, bore near the muzzle
        prof = [(MUZZLE_X - 12.0, 2.85), (10.0, 2.85), (10.0, r_gov), (GAS_PORT_X + 14.5, r_gov),
                (GAS_PORT_X + 14.5, r_muz), (FH_X0 - 1.0, r_muz), (FH_X0 - 1.0, 6.35), (MUZZLE_X, 6.35),
                (MUZZLE_X, 2.85)]
    bm = lathe(prof, seg=40, closed=True, lod_seg=10)
    ob = mk('ar15_barrel', bm, M['steel'])
    smooth(ob, angle=40)
    return ob


def barrel_nut(M):
    bm = lathe([(0.2, 13.0), (0.2, 17.2), (27.0, 17.2), (27.0, 13.0)], seg=40, closed=True)
    ob = mk('ar15_barrel_nut', bm, M['steel'])
    smooth(ob)
    return ob


def gas_block(M):
    x0, x1 = GAS_PORT_X - 11.5, GAS_PORT_X + 11.5
    sec = fillet([(-11.4, -11.6), (11.4, -11.6), (11.4, 8.0), (6.5, 17.8), (-6.5, 17.8), (-11.4, 8.0)],
                 [4.0, 4.0, 3.0, 2.5, 2.5, 3.0], 4)
    ob = mk('ar15_gas_block', prism(sec, 'YZ', x0, x1), M['steel'])
    cut = lathe([(x0 - 1, 9.6), (x1 + 1, 9.6)], seg=40)
    diff(ob, cut)
    # set screws on the underside
    scr = bmesh.new()
    for x in (GAS_PORT_X - 5.0, GAS_PORT_X + 5.0):
        cylinder((x, 0, -13.5), (x, 0, -10.5), 2.4, seg=6, bm=scr)
    diff(ob, scr)
    bevel(ob, 0.5, seg=2, angle=30)
    smooth(ob)
    return ob


def gas_tube(M):
    z = 13.3
    bm = cylinder((-40.0, 0, z), (GAS_PORT_X + 6.0, 0, z), 2.38, seg=12)
    ob = mk('ar15_gas_tube', bm, M['steel'])
    smooth(ob)
    return ob


def handguard(M):
    outer = octagon(HG_APO, HG_Z0, 2.4)
    inner = octagon(HG_APO - HG_WALL, HG_Z0, 1.2)
    bm = tube_or_solid(outer, inner)
    ob = mk('ar15_handguard', bm, M['alu'])

    add = bmesh.new()
    # integral Picatinny rail on the top flat
    top_z = HG_Z0 + HG_APO
    rail = [(7.85, top_z - 0.8), (7.85, RAIL_TOP - 6.25), (10.6, RAIL_TOP - 3.5), (10.6, RAIL_TOP - 2.75),
            (7.85, RAIL_TOP), (-7.85, RAIL_TOP), (-10.6, RAIL_TOP - 2.75), (-10.6, RAIL_TOP - 3.5),
            (-7.85, RAIL_TOP - 6.25), (-7.85, top_z - 0.8)]
    if lod():   # flat bar at the dovetail line; the teeth are added as blocks after the booleans
        rail = rail[:4] + rail[6:]
        prism(rail, 'YZ', 0.0, HG_LEN - 0.8, bm=add)
    else:
        prism(fillet(rail, [0, 0.2, 0.3, 0.3, 0.5, 0.5, 0.3, 0.3, 0.2, 0], 3), 'YZ', 0.0, HG_LEN - 0.8, bm=add)
    # barrel nut clamp block under the rear of the handguard
    clamp = [(0.0, -18.2), (0.0, -21.5), (4.5, -26.8), (44.5, -26.8), (52.5, -19.0), (52.5, -18.2)]
    prism(fillet(clamp, [0, 4.5, 3.0, 5.0, 6.0, 0], 5), 'XZ', -16.5, 16.5, bm=add)
    # thicker rear ring (barrel nut section, no slots)
    union(ob, add)

    cut = bmesh.new()
    rows = []
    # side faces (row B), bottom face (row D): 8 full slots
    for a in (0, 180, 270):
        for k in range(8):
            rows.append((a, 76.5 + 40.0 * k, 32.0))
    # 45 degree facets (rows A and C): 7 full slots and short end slots
    for a in (45, 135, 225, 315):
        for k in range(7):
            rows.append((a, 96.5 + 40.0 * k, 32.0))
        rows.append((a, 366.5, 12.0))
        if a in (225, 315):
            rows.append((a, 66.5, 12.0))
    for a, xc, ln in rows:
        s = prism(stadium(xc, 0.0, ln, 7.0, seg=5), 'XY', -6.0, 6.0)
        s.transform(facet_frame(a))
        merge(cut, s)
    # side slots sit slightly high on the flat, like the reference
    diff(ob, cut)

    # QD socket bores on the upper facets
    qd = bmesh.new()
    for a in (45, 135):
        c = cylinder((63.0, 0, -4.0), (63.0, 0, 4.0), 5.2, seg=24)
        c.transform(facet_frame(a))
        merge(qd, c)
    diff(ob, qd)

    if lod():
        # teeth as blocks; screw counterbores and heads live in the baked maps
        from ar15lib import merge as _merge
        me_bm = bmesh.new()
        me_bm.from_mesh(ob.data)
        _merge(me_bm, rail_teeth(bmesh.new(), 0.0, HG_LEN - 0.8, HG_RAIL_SLOTS))
        me_bm.to_mesh(ob.data)
        me_bm.free()
        smooth(ob)
        return ob
    diff(ob, rail_slot_cutters(HG_RAIL_SLOTS, RAIL_TOP - 3.0))

    # clamp screw counterbores (right side heads, left side nuts)
    cb = bmesh.new()
    for x in (13.0, 39.0):
        cylinder((x, -20.0, -22.3), (x, -12.5, -22.3), 3.6, seg=20, bm=cb)
        cylinder((x, 12.5, -22.3), (x, 20.0, -22.3), 3.6, seg=6, bm=cb)
    diff(ob, cb)

    bevel(ob, 0.5, seg=2, angle=30)
    smooth(ob)
    return ob


def tube_or_solid(outer, inner):
    """Octagonal handguard tube, open at both ends."""
    from ar15lib import tube_prism
    return tube_prism(outer, inner, 'YZ', 0.0, HG_LEN)


def handguard_hardware(M):
    """Steel QD sockets and clamp screws of the handguard."""
    bm = bmesh.new()
    if lod():
        for a in (45, 135):
            c = lathe([(-3.8, 3.0), (-3.8, 4.95), (0.55, 4.95), (0.55, 3.0)], seg=8, axis='Z', center=(63.0, 0.0),
                      closed=True)
            c.transform(facet_frame(a))
            merge(bm, c)
        for x in (13.0, 39.0):
            merge(bm, lathe([(-12.8, 0), (-12.8, 3.35), (-16.75, 3.0), (-16.75, 0)], seg=8, axis='Y',
                            center=(x, -22.3)))
            merge(bm, lathe([(12.8, 0), (12.8, 3.4), (16.6, 3.4), (16.6, 0.0)], seg=6, axis='Y',
                            center=(x, -22.3), phase=math.pi / 6))
        ob = mk('ar15_handguard_hardware', bm, M['steel'])
        smooth(ob)
        return ob
    for a in (45, 135):
        c = lathe([(-3.8, 3.0), (-3.8, 4.95), (0.35, 4.95), (0.55, 4.6), (0.55, 3.0)], seg=24,
                  axis='Z', center=(63.0, 0.0), closed=True)
        c.transform(facet_frame(a))
        merge(bm, c)
    # socket head cap screws, M4
    for x in (13.0, 39.0):
        head = lathe([(-12.8, 0), (-12.8, 3.35), (-16.4, 3.35), (-16.75, 3.0), (-16.75, 0)], seg=20,
                     axis='Y', center=(x, -22.3))
        merge(bm, head)
        merge(bm, lathe([(12.8, 0), (12.8, 3.4), (16.6, 3.4), (16.6, 0.0)], seg=6, axis='Y',
                        center=(x, -22.3), phase=math.pi / 6))
    # rear sling/anti-rotation tab between the screws
    tab = fillet([(20.5, -25.0), (31.5, -25.0), (28.5, -18.0), (26.0, -16.8), (23.5, -18.0)],
                 [1.5, 1.5, 1.5, 2.0, 1.5], 3)
    prism(tab, 'XZ', -17.4, -16.0, bm=bm)
    ob = mk('ar15_handguard_hardware', bm, M['steel'])
    if lod():
        smooth(ob)
        return ob
    hexes = bmesh.new()
    for x in (13.0, 39.0):
        cylinder((x, -17.5, -22.3), (x, -14.6, -22.3), 1.6, seg=6, bm=hexes)
    cylinder((26.0, -18.5, -21.2), (26.0, -15.0, -21.2), 1.9, seg=16, bm=hexes)
    for a in (45, 135):
        c = cylinder((63.0, 0, -5.0), (63.0, 0, 1.0), 3.0, seg=20)
        c.transform(facet_frame(a))
        merge(hexes, c)
    diff(ob, hexes)
    bevel(ob, 0.25, seg=1, angle=35)
    smooth(ob)
    return ob


def flash_hider(M):
    r = 10.8
    outer = [(FH_X0, 9.6), (FH_X0 + 0.7, r), (399.0, r), (399.8, 9.9), (400.6, r), (404.6, r), (405.4, 9.9),
             (406.2, r), (FH_X1 - 1.0, r), (FH_X1, r - 1.0)]
    inner = [(FH_X1, 5.3), (FH_X1 - 3.2, 5.3), (FH_X1 - 3.2, 7.7), (409.5, 7.7), (408.6, 6.35),
             (FH_X0, 6.35)]
    if lod():
        outer = [(FH_X0, 9.6), (FH_X0 + 0.7, r), (FH_X1 - 1.0, r), (FH_X1, r - 1.0)]
        inner = [(FH_X1, 5.3), (FH_X1 - 3.2, 5.3), (FH_X1 - 3.2, 7.7), (FH_X0, 7.7)]
    ob = mk('ar15_flash_hider', lathe(outer + inner, seg=36, closed=True, lod_seg=12), M['steel'])
    # five slots, the 6 o'clock port stays closed (A2 pattern)
    cut = bmesh.new()
    for a in (90, 30, 150, -30, 210):
        b = box(411.5, -1.35, 5.0, 437.5, 1.35, 13.0)
        b.transform(Matrix.Rotation(math.radians(a - 90), 4, 'X'))
        merge(cut, b)
    diff(ob, cut)
    bevel(ob, 0.35, seg=2, angle=30)
    smooth(ob)
    washer = lathe([(FH_X0 - 1.7, 6.4), (FH_X0 - 1.7, 9.9), (FH_X0, 9.9), (FH_X0, 6.4)], seg=36, closed=True)
    wo = mk('ar15_crush_washer', washer, M['steel'])
    smooth(wo)
    return ob, wo
