"""Attachments for weapon_ar15: holographic sight, vertical foregrip, weapon light, laser (mm).

All designs are generic (no manufacturer shapes' branding, no text or logos).
Each builder returns a list of objects; the build script parents them under an
attachment root empty placed at the attachment's socket.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from ar15lib import (S, bevel, box, cylinder, fillet, lathe, merge, mk, prism, rounded_prism, rrect, smooth,
                     stadium)
from parts_front import HG_APO, HG_Z0, facet_frame
from parts_misc import _knurled_knob, _rail_envelope
from parts_receivers import RAIL_TOP, diff, union

# attachment sockets (mm): where each attachment sits on the rifle
HOLO_X0, HOLO_X1 = -106.0, -18.0
HOLO_WINDOW_Z = 64.5            # reticle centre, co-witnessed with the iron sights
GRIP_X = 276.5                  # bottom M-LOK slot centre
SIDE_SLOT_X = 356.5             # front side M-LOK slot centre
SIDE_Z = HG_Z0 + 1.0
HG_SIDE_Y = HG_APO              # side face of the handguard (|y|)
HG_BOTTOM_Z = HG_Z0 - HG_APO

SOCKETS = {
    'socket_att_scope': ((HOLO_X0 + HOLO_X1) / 2, 0.0, RAIL_TOP),
    'socket_att_grip': (GRIP_X, 0.0, HG_BOTTOM_Z),
    'socket_att_flashlight': (SIDE_SLOT_X, -HG_SIDE_Y, SIDE_Z),
    'socket_att_laser': (SIDE_SLOT_X, HG_SIDE_Y, SIDE_Z),
}


# ---------------------------------------------------------------------------
# Holographic sight
# ---------------------------------------------------------------------------
def holo_sight(M):
    x0, x1 = HOLO_X0, HOLO_X1
    zc = HOLO_WINDOW_Z
    # base / rail clamp
    base = rrect(x0, 25.4, x1, 41.0, 2.0)
    body = mk('ar15_att_holo_body', prism(base, 'XZ', -14.5, 14.5), M['alu'])
    diff(body, _rail_envelope(x0 - 5, x1 + 5))
    add = bmesh.new()
    # lower housing under the window (electronics), full width of the hood
    prism(fillet([(x0, 38.0), (-36.0, 38.0), (-30.0, 44.0), (-30.0, 50.5), (x0 + 6.0, 50.5), (x0, 46.0)],
                 [2, 3, 4, 2, 3, 2], 3), 'XZ', -19.5, 19.5, bm=add)
    # hood around the window
    outer = rrect(-20.5, 41.5, 20.5, zc + 19.5, 5.0, 4)
    inner = rrect(-16.5, zc - 13.5, 16.5, zc + 13.5, 2.5, 4)
    from ar15lib import tube_prism
    tube_prism(outer, inner, 'YZ', -99.0, -37.0, bm=add)
    # battery compartment across the front of the base
    cylinder((-27.0, -20.5, 46.0), (-27.0, 20.5, 46.0), 8.2, seg=28, bm=add)
    union(body, add)

    cut = bmesh.new()
    # two shallow grooves on the hood top
    for y in (-6.0, 6.0):
        box(-93.0, y - 1.0, zc + 18.6, -43.0, y + 1.0, zc + 21.0, bm=cut)
    # chamfered top-front and top-rear edges of the hood
    prism([(-37.0 - 7.0, zc + 22.0), (-36.0, zc + 22.0), (-36.0, zc + 12.0)], 'XZ', -30, 30, bm=cut)
    prism([(-100.0, zc + 22.0), (-99.0 + 5.0, zc + 22.0), (-100.0, zc + 15.0)], 'XZ', -30, 30, bm=cut)
    # window openings through the lower housing front (light path)
    box(-99.5, -16.5, zc - 13.5, -36.0, 16.5, zc + 13.5, bm=cut)
    diff(body, cut)

    det = bmesh.new()
    # control buttons on the left side
    for bx in (-92.0, -79.0):
        prism(rrect(bx - 4.5, 43.0, bx + 4.5, 49.5, 1.5), 'XZ', 19.2, 20.9, bm=det)
    # windage / elevation adjuster caps on the right side of the hood
    for ax, az in ((-88.0, zc + 2.0), (-74.0, zc + 2.0)):
        cylinder((ax, -20.2, az), (ax, -22.0, az), 3.0, seg=20, bm=det)
    # battery cap (knurled) on the right
    _knurled_knob(det, -27.0, 46.0, 7.6, -23.8, -20.2, teeth=26, depth=0.5)
    # throw lever on the left of the clamp, cross-bolt nut on the right
    prism(fillet([(-72.0, 27.0), (-38.0, 29.0), (-36.0, 35.5), (-70.0, 35.0)], [2, 2, 2, 2], 3), 'XZ',
          14.2, 17.4, bm=det)
    _knurled_knob(det, -52.7, 30.0, 4.2, -17.8, -14.2, teeth=18, depth=0.4)
    union(body, det)
    bevel(body, 0.5, seg=2, angle=30)
    smooth(body)

    glass = bmesh.new()
    for gx in (-40.0, -96.0):
        box(gx - 0.6, -16.9, zc - 13.9, gx + 0.6, 16.9, zc + 13.9, bm=glass)
    g = mk('ar15_att_holo_glass', glass, M['glass'])

    ret = bmesh.new()
    ring_o = [(3.6 * math.cos(2 * math.pi * k / 48), 3.6 * math.sin(2 * math.pi * k / 48)) for k in range(48)]
    ring_i = [(3.2 * math.cos(2 * math.pi * k / 48), 3.2 * math.sin(2 * math.pi * k / 48)) for k in range(48)]
    tube_prism([(y, zc + z) for y, z in ring_o], [(y, zc + z) for y, z in ring_i], 'YZ', -41.0, -40.8, bm=ret)
    cylinder((-41.0, 0.0, zc), (-40.8, 0.0, zc), 0.42, seg=12, bm=ret)
    # small tick marks at 12, 3, 6 and 9 o'clock inside the ring
    for a in (0, 90, 180, 270):
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        pts = [(c * 2.3 - s_ * 0.18, s_ * 2.3 + c * 0.18), (c * 3.1 - s_ * 0.18, s_ * 3.1 + c * 0.18),
               (c * 3.1 + s_ * 0.18, s_ * 3.1 - c * 0.18), (c * 2.3 + s_ * 0.18, s_ * 2.3 - c * 0.18)]
        prism([(y, zc + z) for y, z in pts], 'YZ', -41.0, -40.8, bm=ret)
    r = mk('ar15_att_holo_reticle', ret, M['reticle'])
    return [body, g, r]


# ---------------------------------------------------------------------------
# Vertical foregrip on the bottom M-LOK slot
# ---------------------------------------------------------------------------
def foregrip(M):
    zt = HG_BOTTOM_Z
    plate = bmesh.new()
    prism(stadium(GRIP_X, 0.0, 44.0, 20.0, seg=6), 'XY', zt - 4.6, zt + 0.3, bm=plate)
    mount = mk('ar15_att_grip_mount', plate, M['alu'])
    bevel(mount, 0.6, seg=2, angle=30)
    smooth(mount)

    prof = [(0.0, 0.0), (0.0, 14.0), (1.2, 15.8), (4.0, 16.2), (6.0, 15.2), (9.0, 14.3)]
    t = 12.0
    # grip body with shallow finger rings
    while t < 76.0:
        base = 14.6 + 0.9 * math.sin((t - 12.0) / 64.0 * math.pi)
        prof += [(t, base), (t + 3.4, base), (t + 4.0, base - 0.7), (t + 5.0, base - 0.7), (t + 5.6, base)]
        t += 8.0
    prof += [(82.0, 15.3), (88.0, 17.0), (91.0, 17.4), (93.5, 16.7), (95.0, 15.2), (95.6, 12.0), (95.6, 0.0)]
    bm = lathe(prof, seg=36, axis='Z')
    # the lathe runs along +Z; flip it to hang down from the handguard, cant the bottom forward 5 deg
    bm.transform(Matrix.Translation(Vector((GRIP_X, 0.0, zt - 4.4)) * S) @
                 Matrix.Rotation(math.radians(-5.0), 4, 'Y') @ Matrix.Scale(-1, 4, Vector((0, 0, 1))))
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    grip = mk('ar15_att_grip', bm, M['polymer'])
    smooth(grip, angle=40)
    return [mount, grip]


# ---------------------------------------------------------------------------
# Weapon light on the right side M-LOK slot
# ---------------------------------------------------------------------------
LIGHT_Y = -40.5
LIGHT_Z = SIDE_Z
LIGHT_X0 = 298.0


def flashlight(M):
    prof = [(0.0, 0.0), (0.0, 6.0), (0.8, 6.4), (0.8, 10.8), (2.6, 12.2), (8.0, 12.2), (8.6, 11.5),
            (9.6, 11.5), (10.4, 12.7)]
    x = 14.0
    while x < 52.0:     # knurl rings on the body
        prof += [(x, 12.7), (x + 0.6, 12.1), (x + 1.8, 12.1), (x + 2.4, 12.7)]
        x += 4.0
    prof += [(58.0, 12.7), (64.0, 13.2), (70.0, 14.6)]
    for hx in (74.0, 78.0, 82.0):   # cooling grooves on the head
        prof += [(hx, 14.6), (hx + 0.6, 13.8), (hx + 1.6, 13.8), (hx + 2.2, 14.6)]
    prof += [(89.0, 14.6), (90.6, 14.1), (91.2, 13.4), (91.2, 11.7), (90.0, 11.7), (90.0, 0.0)]
    bm = lathe(prof, seg=40, axis='X')
    bm.transform(Matrix.Translation(Vector((LIGHT_X0, LIGHT_Y, LIGHT_Z)) * S))
    body = mk('ar15_att_light_body', bm, M['alu'])
    smooth(body, angle=40)

    # tail switch (rubber)
    tb = lathe([(-1.4, 0.0), (-1.4, 4.4), (-0.6, 5.6), (0.8, 5.6), (0.8, 0.0)], seg=24, axis='X')
    tb.transform(Matrix.Translation(Vector((LIGHT_X0, LIGHT_Y, LIGHT_Z)) * S))
    tail = mk('ar15_att_light_switch', tb, M['rubber'])
    smooth(tail, angle=40)

    # M-LOK offset mount with a ring clamp
    mb = bmesh.new()
    prism(stadium(SIDE_SLOT_X, SIDE_Z, 34.0, 15.0, seg=6), 'XZ', -HG_SIDE_Y - 3.0, -HG_SIDE_Y + 0.3, bm=mb)
    prism(rrect(SIDE_SLOT_X - 12.0, LIGHT_Z - 6.0, SIDE_SLOT_X + 12.0, LIGHT_Z + 6.0, 2.0), 'XZ',
          LIGHT_Y + 10.0, -HG_SIDE_Y - 2.8, bm=mb)
    lathe([(SIDE_SLOT_X - 11.0, 12.8), (SIDE_SLOT_X - 11.0, 16.0), (SIDE_SLOT_X + 11.0, 16.0),
           (SIDE_SLOT_X + 11.0, 12.8)], seg=40, axis='X', center=(LIGHT_Y, LIGHT_Z), closed=True, bm=mb)
    mount = mk('ar15_att_light_mount', mb, M['alu'])
    scr = bmesh.new()
    for sx in (SIDE_SLOT_X - 6.0, SIDE_SLOT_X + 6.0):
        cylinder((sx, LIGHT_Y, LIGHT_Z - 17.5), (sx, LIGHT_Y, LIGHT_Z - 14.0), 2.4, seg=6, bm=scr)
    diff(mount, scr)
    bevel(mount, 0.5, seg=2, angle=30)
    smooth(mount)

    lens = lathe([(90.2, 0.0), (90.2, 11.8), (90.8, 11.8), (90.8, 0.0)], seg=40, axis='X')
    lens.transform(Matrix.Translation(Vector((LIGHT_X0, LIGHT_Y, LIGHT_Z)) * S))
    lo = mk('ar15_att_light_lens', lens, M['lens_light'])
    return [body, tail, mount, lo]


# ---------------------------------------------------------------------------
# Laser module on the left side M-LOK slot
# ---------------------------------------------------------------------------
LASER_X0, LASER_X1 = 332.0, 378.0
LASER_Y0, LASER_Y1 = 25.2, 47.0
LASER_Z0, LASER_Z1 = SIDE_Z - 12.0, SIDE_Z + 13.0
LASER_EMIT = (LASER_X1, 36.5, SIDE_Z + 6.0)


def laser(M):
    outline = rrect(LASER_X0, LASER_Z0, LASER_X1, LASER_Z1, 3.0, 4)
    ob = mk('ar15_att_laser_body', rounded_prism(outline, 'XZ', LASER_Y0, LASER_Y1, 2.4, seg=4, n=2.0),
            M['polymer'])
    add = bmesh.new()
    # M-LOK plate
    prism(stadium(SIDE_SLOT_X, SIDE_Z, 34.0, 15.0, seg=6), 'XZ', HG_SIDE_Y - 0.3, LASER_Y0 + 0.6, bm=add)
    # rear activation button
    prism(rrect(LASER_Y0 + 5.0, SIDE_Z - 5.0, LASER_Y1 - 5.0, SIDE_Z + 5.0, 2.5), 'YZ', LASER_X0 - 1.6,
          LASER_X0 + 0.5, bm=add)
    # adjuster caps on top and on the outer side
    cylinder((350.0, LASER_Y0 + 11.0, LASER_Z1 - 0.5), (350.0, LASER_Y0 + 11.0, LASER_Z1 + 1.6), 3.4, seg=20,
             bm=add)
    cylinder((362.0, LASER_Y1 - 0.5, SIDE_Z + 4.0), (362.0, LASER_Y1 + 1.6, SIDE_Z + 4.0), 3.4, seg=20, bm=add)
    # battery cap on the outer side
    _knurled_knob(add, 346.0, SIDE_Z - 3.0, 6.2, LASER_Y1 - 0.5, LASER_Y1 + 1.8, teeth=22, depth=0.45)
    union(ob, add)
    cut = bmesh.new()
    ex, ey, ez = LASER_EMIT
    cylinder((ex - 3.0, ey, ez), (ex + 1.0, ey, ez), 3.6, seg=24, bm=cut)
    cylinder((ex - 3.0, ey, ez - 11.0), (ex + 1.0, ey, ez - 11.0), 4.4, seg=24, bm=cut)
    diff(ob, cut)
    bevel(ob, 0.35, seg=2, angle=35)
    smooth(ob, angle=35)

    lb = bmesh.new()
    cylinder((ex - 2.2, ey, ez), (ex - 1.6, ey, ez), 3.6, seg=24, bm=lb)
    lens = mk('ar15_att_laser_lens', lb, M['lens_laser'])
    ib = bmesh.new()
    cylinder((ex - 2.2, ey, ez - 11.0), (ex - 1.6, ey, ez - 11.0), 4.4, seg=24, bm=ib)
    ir = mk('ar15_att_laser_ir_lens', ib, M['glass_dark'])
    return [ob, lens, ir]
