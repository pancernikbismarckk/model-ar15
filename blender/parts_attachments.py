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
GRIP_FRONT_X = 311.5            # front end of the angled foregrip (outline is drawn toe-first, then mirrored)
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
    # mounted with the tall toe to the rear (toward the magazine), ribbed slope rising to the muzzle
    from ar15lib import mirror_x
    mirror_x(grip, GRIP_X)
    smooth(grip, angle=35)

    tn = bmesh.new()
    for x in GRIP_TNUTS:
        cylinder((x, 0, zt - 0.5), (x, 0, zt + 2.2), 3.1, seg=18, bm=tn)
        prism(rrect(x - 7.0, -3.5, x + 7.0, 3.5, 1.2), 'XY', zt + 2.2, zt + 3.6, bm=tn)
    nuts = mk('ar15_att_grip_tnuts', tn, M['steel'])
    smooth(nuts)
    return [grip, nuts]


# ---------------------------------------------------------------------------
# Weapon light on the right side: short Picatinny rail on an M-LOK slot + rail-clamp light
# Profile measured from reference photos: 117.9 mm long, head D32.2, fins D34.2, body D26.5,
# clamp ring D29.4, knurled grip D25.0, tail cap D23.8.
# ---------------------------------------------------------------------------
FL_SLOT_X = 316.5               # right-side M-LOK slot carrying the rail section
FL_LEN = 117.9
FL_RAIL_H = 8.4                 # height of the rail section above the handguard face
FL_SADDLE = 17.0                # light axis to rail top
LIGHT_Z = HG_Z0
LIGHT_Y = -(HG_SIDE_Y + FL_RAIL_H + FL_SADDLE)
FL_MOUNT_A = 69.7               # clamp centre, measured back from the bezel face
LIGHT_FRONT_X = FL_SLOT_X + FL_MOUNT_A
LIGHT_X0 = LIGHT_FRONT_X - FL_LEN
FL_BOLT_Y = -(HG_SIDE_Y + FL_RAIL_H - 2.0)   # cross bolt runs through a rail groove

SOCKETS['socket_att_flashlight'] = (FL_SLOT_X, -HG_SIDE_Y, HG_Z0)


def _ax(a):
    """World X of a point a mm behind the bezel face."""
    return LIGHT_FRONT_X - a


def _light_lathe(prof, seg=48, closed=True, bm=None):
    """Lathe around the light axis; prof holds (a, r) pairs, a measured back from the bezel."""
    return lathe([(_ax(a), r) for a, r in prof], seg=seg, axis='X', center=(LIGHT_Y, LIGHT_Z), closed=closed,
                 bm=bm)


def _knurl_sleeve(a0, a1, r_peak, depth, r_in, n=96):
    """Diamond-knurled tube: checkerboard of peaks/valleys, split along the valley diagonals."""
    bm = bmesh.new()
    pitch = 2 * math.pi * r_peak / n
    K = max(2, int(round((a1 - a0) / pitch)))
    rings = []
    for k in range(K + 1):
        a = a0 + (a1 - a0) * k / K
        ring = []
        for i in range(n):
            t = 2 * math.pi * i / n
            r = r_peak if (i + k) % 2 == 0 else r_peak - depth
            ring.append(bm.verts.new(Vector((_ax(a), LIGHT_Y + r * math.cos(t), LIGHT_Z + r * math.sin(t))) * S))
        rings.append(ring)
    for k in range(K):
        for i in range(n):
            j = (i + 1) % n
            v00, v01, v11, v10 = rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]
            if (i + k) % 2 == 0:
                bm.faces.new((v00, v01, v10))
                bm.faces.new((v01, v11, v10))
            else:
                bm.faces.new((v00, v01, v11))
                bm.faces.new((v00, v11, v10))
    inner = []
    for a in (a0, a1):
        inner.append([bm.verts.new(Vector((_ax(a), LIGHT_Y + r_in * math.cos(2 * math.pi * i / n),
                                           LIGHT_Z + r_in * math.sin(2 * math.pi * i / n))) * S) for i in range(n)])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((rings[0][j], rings[0][i], inner[0][i], inner[0][j]))
        bm.faces.new((rings[K][i], rings[K][j], inner[1][j], inner[1][i]))
        bm.faces.new((inner[0][i], inner[1][i], inner[1][j], inner[0][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _rail_section(x0, x1):
    """Short Picatinny rail on the right handguard facet (local u = height above the facet)."""
    h = FL_RAIL_H
    sec = [(7.85, -0.6), (7.85, h - 6.25), (10.6, h - 3.5), (10.6, h - 2.75), (7.85, h), (-7.85, h),
           (-10.6, h - 2.75), (-10.6, h - 3.5), (-7.85, h - 6.25), (-7.85, -0.6)]
    bm = prism(fillet(sec, [0, 0.2, 0.3, 0.3, 0.5, 0.5, 0.3, 0.3, 0.2, 0], 3), 'YZ', x0, x1)
    cut = bmesh.new()
    for k in range(-2, 3):
        xc = FL_SLOT_X + 10.0 * k
        box(xc - 2.62, -13.0, h - 3.0, xc + 2.62, 13.0, h + 2.0, bm=cut)
    # chamfered rail ends
    for xe, sgn in ((x0, 1), (x1, -1)):
        pts = [(xe - sgn * 1.0, h + 1.0), (xe + sgn * 2.2, h + 1.0), (xe - sgn * 1.0, h - 2.2)]
        prism(pts, 'XZ', -13.0, 13.0, bm=cut)
    fr = facet_frame(180)
    bm.transform(fr)
    cut.transform(fr)
    return bm, cut


def _knob_z(bm, cx, cy, z0, z1, r, teeth=30, depth=0.45):
    """Knurled thumbscrew knob with its axis along Z (chamfered top)."""
    pts = []
    for k in range(teeth * 2):
        t = math.pi * k / teeth
        rr = r if k % 2 == 0 else r - depth
        pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
    prism(pts, 'XY', z0, z1 - 0.9, bm=bm)
    lathe([(z1 - 1.0, 0.0), (z1 - 1.0, r - 0.3), (z1, r - 1.2), (z1, 0.0)], seg=32, axis='Z', center=(cx, cy),
          bm=bm)


def flashlight(M):
    parts = []
    # --- housing: bezel, head with four cooling fins, taper, body tube (under ring and knurl) ---
    # starts at the bottom of the reflector cavity so the lens opening stays hollow
    prof = [(10.5, 0.0), (10.5, 12.9), (1.2, 12.9), (0.0, 13.35), (0.0, 14.6), (0.25, 15.35), (0.7, 15.9),
            (1.4, 16.1), (20.5, 16.1)]
    for c in (21.85, 25.05, 28.25, 31.45):
        prof += [(c - 1.1, 16.1), (c - 0.85, 16.8), (c - 0.55, 17.1), (c + 0.55, 17.1), (c + 0.85, 16.8),
                 (c + 1.1, 16.1)]
    prof += [(39.7, 16.1), (40.4, 15.85), (42.0, 14.85), (43.8, 13.75), (44.8, 13.35), (45.6, 13.25),
             (53.4, 13.25), (53.7, 12.45), (54.9, 12.45), (55.4, 12.9), (84.6, 12.9), (84.8, 11.85),
             (108.9, 11.85), (108.9, 0.0)]
    body = mk('ar15_att_light_body', _light_lathe(prof, seg=56), M['alu'])
    smooth(body, angle=35)
    parts.append(body)

    # --- clamp ring with the rail saddle and the cross-bolt jaws ---
    mb = _light_lathe([(55.4, 12.7), (55.4, 13.5), (56.0, 14.2), (56.8, 14.7), (82.2, 14.7), (83.2, 13.9),
                       (84.2, 12.7)], seg=56)
    rail_top_y = -(HG_SIDE_Y + FL_RAIL_H)
    xa, xb = FL_SLOT_X - 11.0, FL_SLOT_X + 11.0
    box(xa, LIGHT_Y + 9.0, LIGHT_Z - 13.6, xb, rail_top_y, LIGHT_Z + 13.6, bm=mb)
    for sgn in (-1, 1):
        z0, z1 = sorted((LIGHT_Z + sgn * 10.85, LIGHT_Z + sgn * 13.6))
        box(xa, rail_top_y - 0.5, z0, xb, rail_top_y + 5.4, z1, bm=mb)
    mount = mk('ar15_att_light_mount', mb, M['alu'])
    rail, rail_cut = _rail_section(FL_SLOT_X - 22.5, FL_SLOT_X + 22.5)
    # clearance for the rail inside the clamp
    tmp = mk('_rail_env', rail.copy())
    from ar15lib import ob_to_bm
    env = ob_to_bm(tmp)
    diff(mount, env)
    bevel(mount, 0.5, seg=2, angle=30)
    smooth(mount)
    parts.append(mount)

    rail_ob = mk('ar15_att_light_rail', rail, M['alu'])
    diff(rail_ob, rail_cut)
    bevel(rail_ob, 0.3, seg=1, angle=35)
    smooth(rail_ob)
    parts.append(rail_ob)

    # --- thumbscrew knob (top) and nut (bottom) on the cross bolt ---
    kb = bmesh.new()
    cylinder((FL_SLOT_X, FL_BOLT_Y, LIGHT_Z + 13.4), (FL_SLOT_X, FL_BOLT_Y, LIGHT_Z + 17.6), 4.4, seg=24, bm=kb)
    _knob_z(kb, FL_SLOT_X, FL_BOLT_Y, LIGHT_Z + 17.5, LIGHT_Z + 24.0, 7.25)
    knob = mk('ar15_att_light_knob', kb, M['alu'])
    smooth(knob, angle=35)
    parts.append(knob)
    nb = bmesh.new()
    lathe([(LIGHT_Z - 13.4, 0.0), (LIGHT_Z - 13.4, 4.3), (LIGHT_Z - 16.4, 4.3), (LIGHT_Z - 16.4, 0.0)], seg=6,
          axis='Z', center=(FL_SLOT_X, FL_BOLT_Y), phase=math.pi / 6, bm=nb)
    cylinder((FL_SLOT_X, FL_BOLT_Y, LIGHT_Z - 16.3), (FL_SLOT_X, FL_BOLT_Y, LIGHT_Z - 17.3), 2.1, seg=14, bm=nb)
    nut = mk('ar15_att_light_nut', nb, M['steel'])
    bevel(nut, 0.25, seg=1, angle=35)
    smooth(nut)
    parts.append(nut)

    # --- diamond-knurled grip section ---
    kn = mk('ar15_att_light_knurl', _knurl_sleeve(85.0, 107.6, 12.55, 0.38, 11.7), M['alu'])
    smooth(kn, angle=12, weighted=False)
    parts.append(kn)

    # --- tail cap with crenellated rim ---
    tc = _light_lathe([(108.6, 11.2), (108.6, 11.45), (109.0, 11.9), (114.9, 11.9), (115.7, 11.55),
                       (117.1, 11.0), (117.3, 10.3), (117.3, 8.7), (115.6, 8.4), (115.6, 0.0), (108.6, 0.0)],
                      seg=48)
    tail = mk('ar15_att_light_tailcap', tc, M['alu'])
    notches = bmesh.new()
    for k in range(6):
        t = math.radians(30 + 60 * k)
        b = box(_ax(118.5), -1.6, 7.5, _ax(115.9), 1.6, 13.5)
        b.transform(Matrix.Translation(Vector((0.0, LIGHT_Y, LIGHT_Z)) * S) @ Matrix.Rotation(t, 4, 'X'))
        merge(notches, b)
    diff(tail, notches)
    bevel(tail, 0.35, seg=2, angle=30)
    smooth(tail)
    parts.append(tail)

    sw = mk('ar15_att_light_switch', _light_lathe([(115.3, 0.0), (115.3, 7.6), (116.9, 7.6), (117.5, 6.7),
                                                   (117.85, 4.5), (117.9, 0.0)], seg=40, closed=False),
            M['rubber'])
    smooth(sw, angle=40)
    parts.append(sw)

    # --- optics: glass, chrome reflector, LED ---
    gl = mk('ar15_att_light_glass', _light_lathe([(0.75, 0.0), (0.75, 13.1), (1.05, 13.1), (1.05, 0.0)], seg=48,
                                                 closed=False), M['glass'])
    parts.append(gl)
    rf = _light_lathe([(1.15, 12.95), (3.0, 10.6), (5.5, 7.3), (7.8, 4.5), (9.0, 3.0), (9.6, 3.0), (9.6, 0.0),
                       (9.9, 0.0), (9.9, 3.3), (8.2, 4.8), (5.9, 7.7), (3.4, 11.0), (1.5, 13.2)], seg=48)
    ref = mk('ar15_att_light_reflector', rf, M['chrome'])
    smooth(ref, angle=40)
    parts.append(ref)
    led = box(_ax(9.6), LIGHT_Y - 1.6, LIGHT_Z - 1.6, _ax(9.0), LIGHT_Y + 1.6, LIGHT_Z + 1.6)
    lo = mk('ar15_att_light_led', led, M['led'])
    parts.append(lo)
    return parts


EMIT_SOCKETS = {
    'socket_light_emit': (LIGHT_FRONT_X, LIGHT_Y, LIGHT_Z),
}


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


EMIT_SOCKETS['socket_laser_emit'] = LASER_EMIT
