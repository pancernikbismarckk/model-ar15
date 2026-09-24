"""30-round polymer magazine and folding back-up sights (dimensions in mm)."""
import math

import bmesh
from mathutils import Matrix, Vector

from ar15lib import (S, bevel, boolean, box, cylinder, fillet, inset_outline, lathe, lod, merge, mk, prism,
                     rrect, smooth, stadium)
from parts_receivers import RAIL_TOP, diff, union

# ---------------------------------------------------------------------------
# Magazine
# ---------------------------------------------------------------------------
MAG_FRONT = [(-13.0, -66.0), (-11.0, -71.0), (-10.7, -85.0), (-9.9, -90.0), (-8.3, -100.0), (-7.5, -110.0),
             (-6.0, -120.0), (-3.6, -130.0), (-2.0, -140.0), (1.2, -150.0), (2.8, -160.0), (4.0, -165.5)]
MAG_REAR = [(-58.6, -181.0), (-61.6, -175.0), (-62.4, -170.0), (-64.0, -165.0), (-64.8, -160.0),
            (-66.3, -150.0), (-69.5, -140.0), (-70.3, -130.0), (-71.9, -120.0), (-74.3, -110.0),
            (-74.8, -100.0), (-75.9, -90.0), (-76.5, -85.0), (-75.2, -78.0)]
MAG_FLOOR = [(4.0, -165.5), (7.8, -168.0), (8.8, -176.0), (5.5, -179.8), (-56.0, -195.0), (-58.6, -191.5)]


def _edge_x(edge, z):
    """Interpolate the x of a front/rear edge polyline at height z."""
    pts = sorted(edge, key=lambda p: p[1])
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0) if z1 != z0 else 0
            return x0 + (x1 - x0) * t
    return pts[0][0] if z < pts[0][1] else pts[-1][0]


def magazine(M):
    body = [(-75.2, -16.5), (-13.0, -16.5)] + MAG_FRONT + MAG_FLOOR[1:] + MAG_REAR
    rad = [1.5, 1.5] + [2.0, 3.0] + [0] * 10 + [2.0, 2.5, 3.0, 2.5] + [2.0] + [0] * 13 + [2.0]
    rad = rad[:len(body)] + [0] * (len(body) - len(rad))
    outline = fillet(body, rad, 4)
    if lod():
        from ar15lib import simplify_outline
        outline = simplify_outline(outline, 0.45)
    # narrow upper part fits the magazine well, wider body below it
    ob = mk('ar15_magazine', prism(outline, 'XZ', -11.1, 11.1), M['polymer'])
    lower = prism(inset_outline(outline, -0.2), 'XZ', -12.9, 12.9)
    below = prism([(-120, -87.0), (40, -62.1), (40, -250), (-120, -250)], "XZ", -20, 20)
    tmpo = mk('_maglow', lower)
    boolean(tmpo, below, op='INTERSECT')
    from ar15lib import ob_to_bm
    union(ob, ob_to_bm(tmpo))
    fp = prism(inset_outline(fillet(MAG_FLOOR + [(-60.7, -183.2)], [1.5, 2.0, 2.0, 2.5, 2.5, 2.0, 1.5], 3), -0.4),
               'XZ', -14.0, 14.0)
    union(ob, fp)
    bevel(ob, 1.4, seg=3, angle=30)

    # recessed texture panels on both sides, following the curve
    cut = bmesh.new()
    rows = [] if lod() else [(-85.5, -102.5), (-106.0, -123.0), (-126.5, -143.5), (-147.0, -162.0)]
    cols = [(0.07, 0.46), (0.54, 0.93)]
    for z0, z1 in rows:
        for u0, u1 in cols:
            def P(u, z):
                xr, xf = _edge_x(MAG_REAR, z), _edge_x(MAG_FRONT, z)
                return (xr + (xf - xr) * u, z)
            quad = [P(u0, z0), P(u1, z0), P(u1, z1), P(u0, z1)]
            q = fillet(quad, 2.2, 3)
            prism(q, 'XZ', -20.0, -12.25, bm=cut)
            prism(q, 'XZ', 12.25, 20.0, bm=cut)
    # grip ribs on the front and rear of the lower body
    diff(ob, cut)
    bevel(ob, 0.3, seg=1, angle=35)
    smooth(ob, angle=35)
    return ob


def magazine_top(M):
    """Feed lips, follower region and the top round (visible when the magazine is out)."""
    bm = bmesh.new()
    for s in (-1, 1):
        lip = fillet([(-74.0, -21.0), (-40.0, -21.0), (-37.0, -15.2), (-74.0, -14.8)], [0, 2, 1.5, 0], 3)
        prism(lip, 'XZ', s * 8.2, s * 10.9, bm=bm)
    ob = mk('ar15_magazine_lips', bm, M['polymer'])
    bevel(ob, 0.5, seg=2, angle=30)
    smooth(ob)
    return ob


def cartridge(M, x_rear=-73.6, z=-11.0, y=0.0):
    """5.56x45 mm round lying in the magazine (case + bullet)."""
    L = 57.4
    case = [(0.0, 0), (0.0, 4.25), (0.6, 4.75), (1.2, 4.75), (1.2, 4.2), (2.3, 4.2), (3.0, 4.77),
            (39.5, 4.55), (41.2, 3.2), (44.7, 3.2), (44.7, 0)]
    if lod():
        case = [(0.0, 0), (0.0, 4.75), (39.5, 4.55), (41.2, 3.2), (44.7, 3.2), (44.7, 0)]
    bm = lathe(case, seg=24, lod_seg=6)
    bm.transform(Matrix.Translation(Vector((x_rear, y, z)) * S))
    co = mk('ar15_cartridge_case', bm, M['brass'])
    smooth(co, angle=40)
    bul = [(44.2, 0), (44.2, 2.85), (47.0, 2.85), (52.0, 2.4), (55.5, 1.3), (L, 0.25), (L, 0)]
    if lod():
        bul = [(44.2, 0), (44.2, 2.85), (52.0, 2.4), (L, 0.25), (L, 0)]
    bb = lathe(bul, seg=24, lod_seg=6)
    bb.transform(Matrix.Translation(Vector((x_rear, y, z)) * S))
    bo = mk('ar15_cartridge_bullet', bb, M['copper'])
    smooth(bo, angle=40)
    return co, bo


# ---------------------------------------------------------------------------
# Folding back-up sights (deployed)
# ---------------------------------------------------------------------------
def _rail_envelope(x0, x1, clr=0.12):
    t = RAIL_TOP + clr
    half = [(10.6 + clr, RAIL_TOP - 2.75), (10.6 + clr, RAIL_TOP - 3.5), (7.85 + clr, RAIL_TOP - 6.25)]
    pts = [(7.85 + clr, t)] + half + [(7.85 + clr, 20.0), (-7.85 - clr, 20.0)] + \
          [(-a, b) for a, b in reversed(half)] + [(-7.85 - clr, t)]
    return prism(pts, 'YZ', x0, x1)


def _knurled_knob(bm, cx, cz, r, y0, y1, teeth=24, depth=0.45):
    if lod():       # knurling comes from the baked normal map
        teeth, depth = 5, 0.0
    pts = []
    for k in range(teeth * 2):
        a = math.pi * k / teeth
        rr = r if k % 2 == 0 else r - depth
        pts.append((cx + rr * math.cos(a), cz + rr * math.sin(a)))
    prism(pts, 'XZ', y0, y1, bm=bm)


def rear_sight(M):
    """Folding rear sight; the base has a channel the leaf folds forward into."""
    base = [(-178.0, 25.4), (-112.0, 25.4), (-112.0, 33.2), (-114.0, 36.6), (-127.0, 38.0), (-134.0, 43.6),
            (-141.5, 45.4), (-149.0, 44.2), (-155.5, 40.5), (-158.0, 34.0), (-178.0, 34.0)]
    ob = mk('ar15_rear_sight_base',
            prism(fillet(base, [1, 1, 1.5, 2, 3, 3, 3, 3, 2, 2, 1.5], 4), 'XZ', -12.8, 12.8), M['polymer'])
    if not lod():   # hidden where the base sits on the rail
        diff(ob, _rail_envelope(-190, -100))
    cut = bmesh.new()
    # channel for the leaf between the base cheeks (deployed and folded)
    box(-159.5, -10.3, 33.0, -108.0, 10.3, 50.0, bm=cut)
    # relief in the right cheek for the windage drum when folded
    if not lod():
        cylinder((-128.8, -16.5, 39.0), (-128.8, -9.0, 39.0), 6.9, seg=24, bm=cut)
    diff(ob, cut)
    add = bmesh.new()
    _knurled_knob(add, -140.5, 37.0, 4.3, -16.2, -12.3)
    cylinder((-140.5, 12.3, 37.0), (-140.5, 14.6, 37.0), 4.0, seg=20, bm=add)
    # leaf hinge pin
    if not lod():
        cylinder((-151.8, -13.3, 40.2), (-151.8, 13.3, 40.2), 1.8, seg=14, bm=add)
    union(ob, add)
    bevel(ob, 0.45, seg=2, angle=30)
    smooth(ob)

    # leaf (pivots at the base)
    leaf = bmesh.new()
    for s in (-1, 1):
        ear = fillet([(-157.4, 36.5), (-146.4, 36.5), (-144.9, 70.0), (-146.6, 76.3), (-155.2, 76.6),
                      (-157.3, 72.0)], [1.5, 1.5, 2.0, 2.0, 2.0, 2.0], 3)
        prism(ear, 'XZ', s * 5.6, s * 9.9, bm=leaf)
    prism(fillet([(-156.8, 36.5), (-147.0, 36.5), (-146.2, 49.0), (-156.4, 49.0)], 1.0, 2), 'XZ', -9.9, 9.9,
          bm=leaf)
    prism(fillet([(-155.0, 55.0), (-147.2, 55.0), (-146.8, 70.5), (-155.2, 70.5)], 1.2, 2), 'XZ', -5.8, 5.8,
          bm=leaf)
    lo = mk('ar15_rear_sight_leaf', leaf, M['polymer'])
    if not lod():
        ap = bmesh.new()
        cylinder((-160.0, 0, 64.5), (-142.0, 0, 64.5), 1.1, seg=16, bm=ap)
        diff(lo, ap)
    kn = bmesh.new()
    _knurled_knob(kn, -150.6, 63.2, 6.2, -14.4, -9.7, teeth=28)
    if not lod():
        cylinder((-150.6, -9.9, 63.2), (-150.6, -5.5, 63.2), 3.0, seg=16, bm=kn)
    union(lo, kn)
    bevel(lo, 0.35, seg=2, angle=30)
    smooth(lo)
    return ob, lo


def front_sight(M):
    """Folding front sight; the leaf folds rearwards into the channel of its base."""
    base = [(318.0, 25.4), (373.0, 25.4), (373.0, 33.5), (371.5, 40.5), (367.0, 45.0), (360.0, 45.8),
            (354.5, 43.4), (349.0, 42.8), (336.0, 41.5), (322.0, 38.5), (318.0, 34.0)]
    ob = mk('ar15_front_sight_base',
            prism(fillet(base, [1, 1, 2, 3, 3, 3, 3, 2, 3, 3, 1.5], 4), 'XZ', -12.8, 12.8), M['polymer'])
    if not lod():
        diff(ob, _rail_envelope(305, 385))
    diff(ob, box(314.0, -10.3, 33.0, 353.8, 10.3, 50.0))
    add = bmesh.new()
    _knurled_knob(add, 363.5, 37.8, 5.2, -16.4, -12.3)
    cylinder((363.5, 12.3, 37.8), (363.5, 14.6, 37.8), 4.2, seg=20, bm=add)
    if not lod():
        cylinder((347.0, -13.3, 40.2), (347.0, 13.3, 40.2), 1.8, seg=14, bm=add)
    union(ob, add)
    bevel(ob, 0.45, seg=2, angle=30)
    smooth(ob)

    leaf = bmesh.new()
    for s in (-1, 1):
        ear = fillet([(341.8, 36.5), (352.2, 36.5), (351.2, 68.5), (349.8, 70.6), (344.2, 70.8),
                      (342.9, 68.0)], [1.5, 1.5, 2.0, 2.0, 2.0, 2.0], 3)
        prism(ear, 'XZ', s * 4.6, s * 9.8, bm=leaf)
    prism(fillet([(342.0, 36.5), (352.0, 36.5), (351.6, 48.5), (342.4, 48.5)], 1.0, 2), 'XZ', -9.8, 9.8, bm=leaf)
    # sight post with its threaded base
    cylinder((347.0, 0, 44.0), (347.0, 0, 55.0), 2.6, seg=16, bm=leaf)
    prism(fillet([(345.9, 54.0), (348.1, 54.0), (347.9, 67.4), (346.1, 67.4)], [0.3, 0.3, 0.4, 0.4], 2),
          'XZ', -1.15, 1.15, bm=leaf)
    lo = mk('ar15_front_sight_leaf', leaf, M['polymer'])
    bevel(lo, 0.3, seg=2, angle=30)
    smooth(lo)
    return ob, lo
