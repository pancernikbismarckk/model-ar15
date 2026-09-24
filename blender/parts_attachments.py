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
HOLO_REAR_X = -110.0            # rear end of the holographic sight (clears the folded rear sight)
HOLO_LEN, HOLO_W, HOLO_H = 96.5, 58.4, 73.7   # overall L x W x H incl. mount and battery cap
HOLO_X0, HOLO_X1 = HOLO_REAR_X, HOLO_REAR_X + HOLO_LEN
HOLO_WIN_Z = 41.5               # window centre above the rail top (local)
HOLO_WINDOW_Z = RAIL_TOP + HOLO_WIN_Z
GRIP_FRONT_X = 311.5            # front end of the angled foregrip
GRIP_TNUTS = (276.5, 236.5)     # bottom M-LOK slot centres used by the grip
GRIP_X = GRIP_FRONT_X - 55.0
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
# Holographic sight (box-hood style), local coords: x from the rear of the sight,
# z from the rail top; converted to rifle coordinates with _hx / _hz.
# ---------------------------------------------------------------------------
def _hx(x):
    return HOLO_REAR_X + x


def _hz(z):
    return RAIL_TOP + z


def _hpts(pts):
    return [(_hx(x), _hz(z)) for x, z in pts]


def _screw(bm, c, axis, r, h, slot=True):
    """Small screw head (cross recess) on a face; axis is 'X' or 'Y' with direction sign."""
    x, y, z = c
    if axis in ('+Y', '-Y'):
        s_ = 1 if axis == '+Y' else -1
        lathe([(y - s_ * 0.6, 0), (y - s_ * 0.6, r), (y + s_ * h * 0.6, r), (y + s_ * h, r * 0.8), (y + s_ * h, 0)],
              seg=16, axis='Y', center=(x, z), bm=bm)
    else:
        s_ = 1 if axis == '+X' else -1
        lathe([(x - s_ * 0.6, 0), (x - s_ * 0.6, r), (x + s_ * h * 0.6, r), (x + s_ * h, r * 0.8), (x + s_ * h, 0)],
              seg=16, axis='X', center=(y, z), bm=bm)


def holo_sight(M):
    from ar15lib import clip_outline, inset_outline, tube_prism  # noqa: F401
    wz = HOLO_WIN_Z
    ww, wh = 30.5, 21.6                      # window 1.2" x 0.85"
    # --- housing: side outline (rounded along Y) intersected with the front outline ---
    side = [(8.0, 7.0), (60.5, 7.0), (60.5, 22.0), (53.0, 65.5), (50.5, 67.7), (15.0, 67.7), (8.0, 61.0)]
    side_f = fillet(side, [1.0, 1.5, 4.0, 3.0, 3.0, 8.0, 1.5], 5)
    body = mk('ar15_att_holo_body', rounded_prism(_hpts(side_f), 'XZ', -23.0, 23.0, 3.0, seg=4, n=1.5),
              M['alu'])
    front = fillet([(-23.0, 7.0), (23.0, 7.0), (23.0, 67.7), (-23.0, 67.7)], [2.0, 2.0, 10.0, 10.0], 8)
    diff_box = prism([(y, _hz(z)) for y, z in front], 'YZ', _hx(-5.0), _hx(100.0))
    from ar15lib import boolean
    boolean(body, diff_box, op='INTERSECT')

    add = bmesh.new()
    # front battery housing ("hump") under the window
    hump = fillet([(50.0, 7.0), (84.0, 7.0), (89.0, 12.0), (89.5, 18.0), (86.5, 25.0), (80.0, 28.0),
                   (60.0, 30.0), (50.0, 30.0)], [0, 3.0, 4.0, 5.0, 5.0, 6.0, 3.0, 0], 5)
    rounded_prism(_hpts(hump), 'XZ', -21.5, 21.5, 4.0, seg=4, n=1.5, bm=add)
    # raised rear housing that carries the control buttons
    rear = fillet([(1.5, 7.0), (12.0, 7.0), (12.0, 26.0), (4.0, 26.0), (1.5, 23.0)], [1.5, 0, 0, 2.5, 1.5], 3)
    rounded_prism(_hpts(rear), 'XZ', -20.0, 22.0, 2.0, seg=3, n=1.5, bm=add)
    # window bezels (front follows the sloped face, rear on the vertical face)
    ring_o = rrect(-(ww / 2 + 3.0), wz - wh / 2 - 3.0, ww / 2 + 3.0, wz + wh / 2 + 3.0, 5.0, 4)
    ring_i = rrect(-ww / 2, wz - wh / 2, ww / 2, wz + wh / 2, 3.0, 4)
    fr = tube_prism([(y, _hz(z)) for y, z in ring_o], [(y, _hz(z)) for y, z in ring_i], 'YZ', _hx(46.0),
                    _hx(66.0))
    face = prism(_hpts(inset_outline(side_f, -1.4)), 'XZ', -30, 30)
    tmpb = mk('_bezel', fr)
    boolean(tmpb, face, op='INTERSECT')
    from ar15lib import ob_to_bm
    merge(add, ob_to_bm(tmpb))
    tube_prism([(y, _hz(z)) for y, z in ring_o], [(y, _hz(z)) for y, z in ring_i], 'YZ', _hx(6.6), _hx(9.0),
               bm=add)
    # rear cover plate below the rear window
    prism([(y, _hz(z)) for y, z in rrect(-17.5, 9.0, 17.5, 25.5, 3.0, 3)], 'YZ', _hx(0.4), _hx(2.2), bm=add)
    # button bezel on the left side
    prism(_hpts(rrect(3.0, 8.0, 30.5, 21.5, 3.0, 3)), 'XZ', 22.4, 24.6, bm=add)
    # left end boss of the battery tube
    cylinder((_hx(71.0), 21.0, _hz(17.5)), (_hx(71.0), 22.6, _hz(17.5)), 9.2, seg=32, bm=add)
    union(body, add)

    cut = bmesh.new()
    # window tunnel
    prism([(y, _hz(z)) for y, z in ring_i], 'YZ', _hx(-5.0), _hx(100.0), bm=cut)
    # recesses of the elevation (rear, upper) and windage (front, lower) dials on the right side
    for dx, dz in ((24.5, 33.0), (46.5, 20.5)):
        cylinder((_hx(dx), -24.5, _hz(dz)), (_hx(dx), -21.9, _hz(dz)), 10.6, seg=40, bm=cut)
    # recesses for the two push buttons
    for bx in (9.5, 23.5):
        prism(_hpts(rrect(bx - 5.4, 9.3, bx + 5.4, 20.2, 2.2, 3)), 'XZ', 23.6, 26.0, bm=cut)
    diff(body, cut)

    det = bmesh.new()
    # dial turrets with coin slots
    for dx, dz in ((24.5, 33.0), (46.5, 20.5)):
        lathe([(-22.0, 0), (-22.0, 8.9), (-22.9, 8.9), (-23.3, 8.3), (-23.3, 0)], seg=36, axis='Y',
              center=(_hx(dx), _hz(dz)), bm=det)
        # click-detent ring around the turret
        for k in range(24):
            a = 2 * math.pi * k / 24
            cx, cz = _hx(dx) + 9.9 * math.cos(a), _hz(dz) + 9.9 * math.sin(a)
            cylinder((cx, -22.4, cz), (cx, -22.9, cz), 0.35, seg=6, bm=det)
    # battery cap on the right end of the hump (knurled, with a raised "+")
    _knurled_knob(det, _hx(71.0), _hz(17.5), 11.4, -27.0, -21.2, teeth=40, depth=0.55)
    cylinder((_hx(71.0), -27.0, _hz(17.5)), (_hx(71.0), -28.4, _hz(17.5)), 9.6, seg=36, bm=det)
    box(_hx(71.0) - 3.6, -28.9, _hz(17.5) - 0.8, _hx(71.0) + 3.6, -28.2, _hz(17.5) + 0.8, bm=det)
    box(_hx(71.0) - 0.8, -28.9, _hz(17.5) - 3.6, _hx(71.0) + 0.8, -28.2, _hz(17.5) + 3.6, bm=det)
    # --- mount: rail clamp with throw lever (left) and cross-bolt nut (right) ---
    base = fillet(_hpts([(1.0, -6.2), (93.0, -6.2), (93.0, 7.5), (1.0, 7.5)]), [1.5, 1.5, 3.0, 3.0], 3)
    prism(base, 'XZ', -17.5, 17.5, bm=det)
    lever = fillet(_hpts([(44.0, -4.0), (71.0, -2.4), (74.0, 1.8), (71.0, 5.2), (46.0, 5.0)]), [2, 2, 2, 2, 2], 3)
    prism(lever, 'XZ', 17.2, 20.2, bm=det)
    _knurled_knob(det, _hx(49.0), _hz(0.5), 4.6, -20.0, -17.2, teeth=18, depth=0.4)
    union(body, det)
    cut2 = _rail_envelope(_hx(-5.0), _hx(100.0))
    # coin slots across the dial turrets
    for dx, dz, a in ((24.5, 33.0, 20.0), (46.5, 20.5, -15.0)):
        b = box(-6.8, -1.2, -1.2, 6.8, 1.2, 1.2)
        b.transform(Matrix.Translation(Vector((_hx(dx), -23.3, _hz(dz))) * S) @ Matrix.Rotation(math.radians(a), 4, 'Y'))
        merge(cut2, b)
    diff(body, cut2)
    bevel(body, 0.4, seg=2, angle=35)
    smooth(body, angle=35)

    # push buttons (rubber) with arrow reliefs
    bb = bmesh.new()
    for bx, up in ((9.5, False), (23.5, True)):
        prism(_hpts(rrect(bx - 4.8, 9.9, bx + 4.8, 19.6, 1.8, 3)), 'XZ', 23.4, 25.6, bm=bb)
        tip, bot = (17.4, 12.1) if up else (12.1, 17.4)
        prism(_hpts([(bx - 2.6, bot), (bx + 2.6, bot), (bx, tip)]), 'XZ', 25.5, 26.0, bm=bb)
    btn = mk('ar15_att_holo_buttons', bb, M['rubber'])
    bevel(btn, 0.3, seg=1, angle=40)
    smooth(btn)

    # screws: rear cover (4), left side (2), right rear (1)
    sb = bmesh.new()
    for y in (-14.5, 14.5):
        for z in (11.5, 23.0):
            _screw(sb, (_hx(0.4), y, _hz(z)), '-X', 1.7, 0.9)
    for x in (38.6, 62.7):
        _screw(sb, (_hx(x), 21.3 if x > 50 else 22.8, _hz(10.5)), '+Y', 2.1, 0.8)
    _screw(sb, (_hx(6.5), -19.8, _hz(13.0)), '-Y', 2.0, 0.8)
    scr = mk('ar15_att_holo_screws', sb, M['steel'])
    smooth(scr, angle=40)

    # glass and reticle
    glass = bmesh.new()
    for gx in (54.0, 10.8):
        box(_hx(gx) - 0.6, -ww / 2 - 0.3, _hz(wz - wh / 2 - 0.3), _hx(gx) + 0.6, ww / 2 + 0.3,
            _hz(wz + wh / 2 + 0.3), bm=glass)
    g = mk('ar15_att_holo_glass', glass, M['glass'])
    zc = _hz(wz)
    xr = _hx(54.0) - 0.8
    ret = bmesh.new()
    ring_o2 = [(3.6 * math.cos(2 * math.pi * k / 48), 3.6 * math.sin(2 * math.pi * k / 48)) for k in range(48)]
    ring_i2 = [(3.2 * math.cos(2 * math.pi * k / 48), 3.2 * math.sin(2 * math.pi * k / 48)) for k in range(48)]
    tube_prism([(y, zc + z) for y, z in ring_o2], [(y, zc + z) for y, z in ring_i2], 'YZ', xr - 0.2, xr, bm=ret)
    cylinder((xr - 0.2, 0.0, zc), (xr, 0.0, zc), 0.42, seg=12, bm=ret)
    for a in (0, 90, 180, 270):
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        pts = [(c * 2.3 - s_ * 0.18, s_ * 2.3 + c * 0.18), (c * 3.1 - s_ * 0.18, s_ * 3.1 + c * 0.18),
               (c * 3.1 + s_ * 0.18, s_ * 3.1 - c * 0.18), (c * 2.3 + s_ * 0.18, s_ * 2.3 - c * 0.18)]
        prism([(y, zc + z) for y, z in pts], 'YZ', xr - 0.2, xr, bm=ret)
    r = mk('ar15_att_holo_reticle', ret, M['reticle'])
    return [body, btn, scr, g, r]


# ---------------------------------------------------------------------------
# Angled foregrip with hand stop on the bottom M-LOK slots
# ---------------------------------------------------------------------------
GRIP_OUTLINE = [
    (0.0, 0.4), (-110.0, 0.4),
    (-110.0, -5.0), (-106.5, -23.5), (-100.0, -27.5), (-93.5, -26.0),
    (-88.0, -19.5), (-72.0, -14.0), (-54.0, -14.5), (-40.0, -20.5),
    (-31.0, -33.0), (-27.0, -41.5), (-18.5, -43.0), (-14.5, -40.0), (1.0, -6.0),
]
GRIP_RADII = [1.0, 1.0, 3.0, 4.0, 3.0, 3.0, 6.0, 30.0, 30.0, 8.0, 5.0, 3.0, 3.0, 3.0, 3.0]


def foregrip(M):
    zt = HG_BOTTOM_Z
    xf = GRIP_FRONT_X
    outline = [(xf + x, zt + z) for x, z in fillet(GRIP_OUTLINE, GRIP_RADII, 6)]
    grip = mk('ar15_att_grip', rounded_prism(outline, 'XZ', -10.5, 10.5, 2.6, seg=4, n=1.4), M['polymer'])
    cut = bmesh.new()
    # triangular window through the front fin
    tri = fillet([(xf - 6.5, zt - 7.5), (xf - 25.0, zt - 7.5), (xf - 16.0, zt - 29.0)], 2.2, 4)
    prism(tri, 'XZ', -20.0, 20.0, bm=cut)
    # long lightening slot through the body
    prism(stadium(xf - 60.0, zt - 6.2, 34.0, 4.2, seg=6), 'XZ', -20.0, 20.0, bm=cut)
    # grip grooves across the sloped front face and the rear stop
    ang = math.atan2(-34.0, -15.5)
    for k in range(6):
        t = 0.2 + k * 0.13
        px, pz = xf + 1.0 - 15.5 * t, zt - 6.0 - 34.0 * t
        b = box(-0.8, -20.0, -1.4, 0.8, 20.0, 1.4)
        b.transform(Matrix.Translation(Vector((px, 0.0, pz)) * S) @ Matrix.Rotation(-ang, 4, 'Y'))
        merge(cut, b)
    for k in range(3):
        pz = zt - 9.0 - k * 5.0
        box(xf - 111.5, -20.0, pz - 0.8, xf - 109.2, 20.0, pz + 0.8, bm=cut)
    # serrations along the curved underside (finger rest), 0.9 mm deep
    arc = [(-40.0, -20.5), (-54.0, -14.5), (-72.0, -14.0), (-88.0, -19.5)]

    def bottom(x):
        for (x0, z0), (x1, z1) in zip(arc, arc[1:]):
            if x1 <= x <= x0:
                return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
        return arc[-1][1]

    for k in range(10):
        x = -45.0 - k * 4.4
        zb = bottom(x)
        box(xf + x - 0.7, -20.0, zt + zb - 6.0, xf + x + 0.7, 20.0, zt + zb + 0.9, bm=cut)
    diff(grip, cut)
    bevel(grip, 0.35, seg=2, angle=35)
    smooth(grip, angle=35)

    tn = bmesh.new()
    for x in GRIP_TNUTS:
        cylinder((x, 0, zt - 0.5), (x, 0, zt + 2.2), 3.1, seg=18, bm=tn)
        prism(rrect(x - 7.0, -3.5, x + 7.0, 3.5, 1.2), 'XY', zt + 2.2, zt + 3.6, bm=tn)
    nuts = mk('ar15_att_grip_tnuts', tn, M['steel'])
    smooth(nuts)
    return [grip, nuts]


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
