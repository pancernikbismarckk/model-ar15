"""Upper and lower receiver groups of weapon_ar15 (all dimensions in mm)."""
import math

import bmesh
from mathutils import Matrix, Vector

from ar15lib import (S, arc, bevel, bm_intersect, boolean, box, circle, cylinder, fillet, hexahedron,
                     lathe, merge, mk, prism, rrect, smooth, sphere, stadium)

# Key reference lines (see README for the coordinate system)
UPPER_REAR = -190.0
PARTING_Z = -12.5
RAIL_TOP = 31.6
UPPER_W2 = 14.5     # half width of the upper receiver walls
LOWER_W2 = 14.25    # half width of the lower receiver walls

# Picatinny slot centres on the receiver rail (in phase with the handguard rail)
UPPER_RAIL_SLOTS = [-12.7 - 10.0 * k for k in range(17)]


def union(ob, bm):
    return boolean(ob, bm, op='UNION')


def diff(ob, bm):
    return boolean(ob, bm, op='DIFFERENCE')


def intersect(ob, bm):
    return boolean(ob, bm, op='INTERSECT')


def picatinny_section(top=RAIL_TOP, neck=7.85, wide=10.6, base_w=None, base_z=None):
    """Half of a MIL-STD-1913 profile (y >= 0), top-down, as (y, z) points."""
    return [(wide, top - 2.75), (wide, top - 3.5), (neck, top - 6.25)]


def rail_slot_cutters(centres, z_bottom, half_w=13.0, width=5.23):
    bm = bmesh.new()
    for c in centres:
        box(c - width / 2, -half_w, z_bottom, c + width / 2, half_w, z_bottom + 10, bm=bm)
    return bm


# ---------------------------------------------------------------------------
# Upper receiver
# ---------------------------------------------------------------------------
def upper_receiver(M):
    W2 = UPPER_W2
    top = RAIL_TOP
    sec = [(W2, PARTING_Z), (W2, 17.5), (7.85, 24.2), (7.85, top - 6.25), (10.6, top - 3.5),
           (10.6, top - 2.75), (7.85, top), (-7.85, top), (-10.6, top - 2.75), (-10.6, top - 3.5),
           (-7.85, top - 6.25), (-7.85, 24.2), (-W2, 17.5), (-W2, PARTING_Z)]
    rad = [0.8, 3.0, 1.2, 0.2, 0.3, 0.3, 0.5, 0.5, 0.3, 0.3, 0.2, 1.2, 3.0, 0.8]
    ob = mk('ar15_upper_receiver', prism(fillet(sec, rad, 4), 'YZ', UPPER_REAR, 0.0), M['alu'])

    # --- forward assist housing (right side, axis toes in towards the front) ---
    fa = lathe([(0, 0), (0, 7.3), (36, 7.3), (40.5, 7.0), (44.0, 6.2), (46.8, 5.0), (48.8, 3.4),
                (49.9, 1.7), (50.2, 0)], seg=32)
    fa.transform(Matrix.Translation(Vector((-189.0, -19.6, 6.0)) * S) @
                 Matrix.Rotation(math.radians(6.0), 4, 'Z'))
    # web blending the housing into the receiver wall
    web = fillet([(-189.0, -14.0), (-189.0, -21.0), (-160.0, -18.2), (-142.0, -14.0)], [0, 2, 8, 0], 5)
    prism(web, 'XY', 0.5, 11.5, bm=fa)
    union(ob, fa)

    # --- brass deflector: top-view wedge intersected with its side outline ---
    tri = [(-115.5, -13.5), (-115.5, -21.6), (-112.5, -22.4), (-97.0, -13.5)]
    defl = prism(fillet(tri, [0, 1.2, 1.5, 0], 3), 'XY', 0.0, 24.0)
    side = prism(fillet([(-117, 3.5), (-96, 0.5), (-96, 21.0), (-100, 23.0), (-117, 23.0)],
                        [0, 0, 2.5, 2, 0], 3), 'XZ', -30, 0)
    union(ob, bm_intersect(defl, side))

    # --- dust cover hinge lugs under the ejection port ---
    lugs = bmesh.new()
    for x0, x1 in ((-97.0, -92.0), (-12.0, -7.5)):
        box(x0, -16.4, -9.0, x1, -13.0, -4.8, bm=lugs)
    union(ob, lugs)

    cut = bmesh.new()
    # rear top notch for the charging handle and its channel
    box(UPPER_REAR - 5, -20, 20.5, -178.0, 20, 40, bm=cut)
    box(UPPER_REAR - 5, -5.6, 11.0, -150.0, 5.6, 21.5, bm=cut)
    # bolt carrier bore (opens at the bottom of the upper)
    lathe([(UPPER_REAR - 5, 12.6), (1.0, 12.6)], seg=40, bm=cut)
    box(-186.0, -11.2, PARTING_Z - 3, -6.0, 11.2, -4.0, bm=cut)
    # ejection port
    prism(rrect(-92.0, -4.5, -12.0, 15.0, 2.0), 'XZ', -22.0, -6.0, bm=cut)
    diff(ob, cut)

    diff(ob, rail_slot_cutters(UPPER_RAIL_SLOTS, RAIL_TOP - 3.0))

    bevel(ob, 0.45, seg=2, angle=30)
    smooth(ob)
    return ob


def dust_cover(M):
    """Closed ejection-port cover; origin on the hinge rod."""
    bm = prism(rrect(-93.0, -5.2, -11.0, 15.8, 2.2), 'XZ', -15.9, -14.6)
    # stiffening rib and latch
    prism(rrect(-63.5, -2.6, -42.5, -0.6, 0.8), 'XZ', -16.7, -15.5, bm=bm)
    prism(rrect(-60.5, 2.2, -47.5, 9.2, 1.8), 'XZ', -17.4, -15.5, bm=bm)
    # rolled top edge
    cylinder((-92.5, -15.3, 15.0), (-11.5, -15.3, 15.0), 0.9, seg=10, bm=bm)
    # hinge rod (part of the same object: the cover rotates about it)
    cylinder((-97.5, -14.7, -6.9), (-7.0, -14.7, -6.9), 1.2, seg=12, bm=bm)
    ob = mk('ar15_dust_cover', bm, M['steel'])
    smooth(ob)
    return ob


def forward_assist(M):
    bm = lathe([(-8.2, 0), (-8.2, 4.2), (-7.6, 5.6), (-5.0, 5.9), (-4.4, 5.3), (-3.6, 5.3),
                (-3.0, 5.9), (0.5, 5.9), (0.5, 0)], seg=28)
    bm.transform(Matrix.Translation(Vector((-189.0, -19.6, 6.0)) * S) @
                 Matrix.Rotation(math.radians(6.0), 4, 'Z'))
    ob = mk('ar15_forward_assist', bm, M['steel'])
    smooth(ob)
    return ob


def charging_handle(M):
    """Mil-spec charging handle: T-handle with the latch on the left side."""
    bm = bmesh.new()
    # stem running forward inside the upper's top channel (U-section around the gas key)
    box(-192.0, -5.3, 17.2, -30.0, 5.3, 20.3, bm=bm)
    for s in (-1, 1):
        box(-192.0, s * 5.3, 12.0, -30.0, s * 4.9, 17.4, bm=bm)
    # tongue that fills the rear notch of the upper
    prism(fillet([(-192.0, 20.3), (-178.3, 20.3), (-178.3, 27.5), (-181.0, 30.4), (-192.0, 30.4)],
                 [0, 0.6, 1.5, 1.2, 0], 3), 'XZ', -7.5, 7.5, bm=bm)
    # T wings
    wing = [(-24.0, -198.0), (24.0, -198.0), (24.0, -189.0), (-24.0, -189.0)]
    wing = fillet(wing, [4.5, 4.5, 3.0, 3.0], 5)
    prism([(b, a) for a, b in wing], 'XY', 21.0, 29.6, bm=bm)
    # latch on the left wing
    latch = fillet([(-190.0, 14.5), (-178.5, 15.8), (-176.8, 19.0), (-178.0, 23.5),
                    (-189.0, 24.0)], [0, 1.5, 1.5, 1.5, 0], 4)
    prism(latch, 'XY', 21.8, 29.0, bm=bm)
    ob = mk('ar15_charging_handle', bm, M['alu'])
    bevel(ob, 0.7, seg=2, angle=30)
    smooth(ob)
    return ob


# ---------------------------------------------------------------------------
# Lower receiver
# ---------------------------------------------------------------------------
LOWER_PROFILE = [
    (-190.0, PARTING_Z), (-2.0, PARTING_Z),
    (0.6, -15.5), (1.0, -20.0), (-0.8, -24.8), (-5.5, -28.0), (-9.8, -30.5),
    (-8.8, -61.0), (-8.0, -64.0),
    (-78.0, -75.6), (-83.5, -76.5), (-84.5, -48.0),
    (-127.5, -48.0), (-127.5, -79.5), (-138.5, -79.5), (-138.5, -49.0),
    (-171.0, -49.0), (-180.0, -46.8), (-189.5, -41.5), (-196.0, -33.0), (-198.0, -24.0),
    (-198.0, PARTING_Z),
]
LOWER_RADII = [0, 0, 2.5, 3.0, 3.0, 3.0, 2.0,
               3.0, 1.0,
               2.0, 3.0, 7.0,
               5.5, 3.0, 3.0, 3.0,
               4.0, 8.0, 8.0, 6.0, 4.0,
               0]


def lower_receiver(M):
    W2 = LOWER_W2
    ob = mk('ar15_lower_receiver', prism(fillet(LOWER_PROFILE, LOWER_RADII, 5), 'XZ', -W2, W2), M['alu'])

    add = bmesh.new()
    # receiver extension tower
    lathe([(-198.0, 17.6), (-190.0, 17.6)], seg=48, bm=add)
    # flared lip at the bottom of the magazine well
    lip = [(-6.2, -63.2), (-6.4, -67.8), (-80.8, -79.4), (-81.0, -74.6)]
    prism(fillet(lip, [1.2, 1.5, 1.5, 1.2], 3), 'XZ', -15.9, 15.9, bm=add)
    # magazine release fence (right side)
    fence = [(-75.0, -20.5), (-70.4, -20.5), (-69.4, -24.0), (-70.2, -57.5), (-72.8, -57.5), (-75.4, -24.0)]
    prism(fillet(fence, [1.2, 1.2, 1.0, 1.0, 1.0, 1.0], 3), 'XZ', -W2 - 1.7, -W2 + 0.5, bm=add)
    # bolt catch bosses (left side)
    for z0, z1 in ((-15.0, -20.5), (-33.5, -39.0)):
        prism(rrect(-86.5, z1, -76.5, z0, 1.5), 'XZ', W2 - 0.5, W2 + 2.2, bm=add)
    # selector detent/pin boss is flush; rear takedown pin boss
    union(ob, add)

    cut = bmesh.new()
    # magazine well
    box(-75.8, -11.4, -95.0, -12.4, 11.4, PARTING_Z + 2, bm=cut)
    # flare chamfer following the slanted bottom of the well
    hexahedron([(-9.9, -13.9, -69.4), (-78.3, -13.9, -80.0), (-78.3, 13.9, -80.0), (-9.9, 13.9, -69.4)],
               [(-12.4, -11.4, -65.2), (-75.8, -11.4, -75.1), (-75.8, 11.4, -75.1), (-12.4, 11.4, -65.2)],
               bm=cut)
    # trigger guard slots in the front and rear ears
    box(-86.0, -7.7, -86.0, -79.5, 7.7, -71.0, bm=cut)
    box(-140.0, -7.7, -86.0, -130.0, 7.7, -73.5, bm=cut)
    # trigger slot
    box(-124.5, -3.6, -56.0, -103.0, 3.6, -40.0, bm=cut)
    # hollow fire-control pocket (seen through the trigger slot)
    box(-140.0, -9.5, -46.0, -86.0, 9.5, PARTING_Z + 2, bm=cut)
    # buffer tube thread bore
    lathe([(-205.0, 14.3), (-192.0, 14.3)], seg=48, bm=cut)
    diff(ob, cut)

    bevel(ob, 0.55, seg=2, angle=30)
    smooth(ob)
    return ob


def trigger_guard(M):
    outer = ([(-79.0, -73.5)] +
             [(-82.0, -80.5), (-92.0, -84.2), (-109.0, -85.4), (-126.0, -84.2), (-133.5, -81.5),
              (-138.0, -78.5)])
    inner = [(-136.0, -74.5), (-130.0, -77.4), (-120.0, -79.4), (-109.0, -80.0), (-96.0, -79.3),
             (-87.0, -77.0), (-82.5, -72.8)]
    pts = fillet(outer + inner, [1.5, 3, 8, 12, 8, 3, 1.5, 1.5, 3, 8, 12, 8, 3, 1.5], 4)
    ob = mk('ar15_trigger_guard', prism(pts, 'XZ', -7.4, 7.4), M['alu'])
    bevel(ob, 1.6, seg=3, angle=30)
    smooth(ob)
    return ob


def trigger(M):
    """Curved mil-spec trigger; origin on the trigger pin."""
    front = [(-113.0, -44.0), (-116.4, -51.0), (-118.2, -58.0), (-117.9, -65.0), (-115.6, -70.5),
             (-112.2, -74.6)]
    back = [(-110.6, -74.9), (-111.0, -73.2), (-113.8, -69.0), (-115.4, -63.5), (-115.4, -57.5),
            (-113.6, -51.0), (-110.5, -44.0)]
    body = [(-104.0, -40.0), (-104.0, -33.0), (-121.5, -33.0), (-121.5, -40.0)]
    pts = fillet(front + back, [0, 2, 4, 5, 4, 1.2, 0.8, 1.0, 4, 5, 4, 2, 0], 4)
    bm = prism(pts, 'XZ', -3.1, 3.1)
    prism(body, 'XZ', -3.1, 3.1, bm=bm)
    ob = mk('ar15_trigger', bm, M['steel'])
    bevel(ob, 0.9, seg=3, angle=30)
    smooth(ob)
    return ob


def pins(M):
    """Visible ends/heads of the receiver pins (right and left side)."""
    bm = bmesh.new()
    W = LOWER_W2
    # pivot pin and takedown pin: detent ends on the right, heads on the left
    for x, z in ((-4.2, -19.5), (-165.6, -20.3)):
        lathe([(-W - 0.8, 0), (-W - 0.8, 2.6), (-W - 0.5, 3.15), (-W + 1, 3.15), (-W + 1, 0)],
              seg=20, bm=bm, axis='Y', center=(x, z))
        lathe([(W - 1, 0), (W - 1, 3.15), (W + 0.4, 3.15), (W + 0.4, 4.3), (W + 1.4, 4.1),
               (W + 1.9, 3.2), (W + 1.9, 0)], seg=20, bm=bm, axis='Y', center=(x, z))
    # trigger guard roll pin
    cylinder((-131.0, -7.9, -76.2), (-131.0, 7.9, -76.2), 1.25, seg=12, bm=bm)
    # hammer and trigger pins (flush ends)
    for x, z in ((-96.8, -29.9), (-118.0, -37.8)):
        for s in (-1, 1):
            y0 = s * (W - 0.6)
            y1 = s * (W + 0.25)
            cylinder((x, y0, z), (x, y1, z), 2.0, seg=14, bm=bm)
    ob = mk('ar15_pins', bm, M['steel'])
    smooth(ob)
    return ob


def selector(M):
    """Ambidextrous safety selector; origin on its axis. Shown on SAFE."""
    ax, az = -146.5, -36.0
    W = LOWER_W2
    bm = bmesh.new()
    # drum through the receiver
    cylinder((ax, -W - 1.2, az), (ax, W + 1.2, az), 4.6, seg=24, bm=bm)
    # right lever: short, points rearwards
    rl = fillet([(ax + 4.0, az - 3.6), (ax - 17.0, az + 2.4), (ax - 17.6, az + 6.4), (ax + 4.0, az + 4.0)],
                [4.0, 2.5, 2.5, 4.0], 4)
    prism(rl, 'XZ', -W - 3.4, -W - 1.2, bm=bm)
    # left lever: long paddle pointing forwards
    ll = fillet([(ax - 4.5, az - 4.0), (ax + 24.0, az - 3.4), (ax + 25.5, az + 3.0), (ax - 4.5, az + 4.5)],
                [4.5, 2.5, 2.5, 4.5], 4)
    prism(ll, 'XZ', W + 1.2, W + 3.6, bm=bm)
    ob = mk('ar15_selector', bm, M['steel'])
    bevel(ob, 0.6, seg=2, angle=30)
    smooth(ob)
    return ob


def mag_release(M):
    """Magazine release button (right) and magazine catch (left)."""
    W = LOWER_W2
    x, z = -82.0, -36.0
    bm = lathe([(-W + 1, 0), (-W + 1, 4.7), (-W - 2.6, 4.7), (-W - 3.3, 4.2), (-W - 3.6, 2.5),
                (-W - 3.6, 0)], seg=28, axis='Y', center=(x, z))
    # left side catch plate, sitting flush in its pocket
    prism(rrect(-88.5, -42.5, -75.5, -28.5, 2.5), 'XZ', W - 0.8, W + 0.35, bm=bm)
    ob = mk('ar15_mag_release', bm, M['steel'])
    bevel(ob, 0.3, seg=2, angle=40)
    smooth(ob)
    return ob


def bolt_catch(M):
    """Bolt catch paddle on the left side; origin on its roll pin."""
    W = LOWER_W2
    pts = fillet([(-84.5, -20.6), (-76.8, -20.6), (-62.5, -27.0), (-61.0, -33.0), (-69.0, -33.8),
                  (-84.5, -33.4)], [2.0, 3.0, 3.5, 2.0, 3.0, 2.0], 4)
    bm = prism(pts, 'XZ', W + 0.4, W + 2.6)
    # ribbed lower paddle
    for i in range(3):
        xx = -70.5 + i * 3.2
        box(xx - 0.6, W + 2.4, -33.2, xx + 0.6, W + 3.2, -27.0 + i * 0.8, bm=bm)
    cylinder((-81.5, W - 0.6, -17.8), (-81.5, W + 2.5, -17.8), 1.6, seg=12, bm=bm)
    ob = mk('ar15_bolt_catch', bm, M['steel'])
    bevel(ob, 0.45, seg=2, angle=30)
    smooth(ob)
    return ob


def bolt_carrier(M):
    """Bolt carrier group in battery (hidden by the closed dust cover); origin at its rear."""
    bm = lathe([(-196.0, 0), (-196.0, 9.8), (-195.2, 10.6), (-186.0, 10.6), (-185.0, 12.25),
                (-37.2, 12.25), (-36.2, 11.4), (-36.2, 0)], seg=40)
    # gas key with its nozzle
    prism(fillet([(-84.0, 9.5), (-47.0, 9.5), (-47.0, 18.2), (-84.0, 18.2)], 1.0, 2), 'XZ', -4.6, 4.6, bm=bm)
    cylinder((-48.0, 0, 13.3), (-38.5, 0, 13.3), 2.9, seg=16, bm=bm)
    for x in (-78.0, -55.0):
        cylinder((x, 0, 17.0), (x, 0, 19.2), 2.2, seg=6, bm=bm)
    # bolt with cam pin and locking lugs
    lathe([(-40.0, 0), (-40.0, 6.6), (-14.5, 6.6), (-14.5, 8.9), (-8.4, 8.9), (-8.4, 0)], seg=28, bm=bm)
    cylinder((-44.0, 0, 5.0), (-44.0, 0, 14.0), 3.1, seg=14, bm=bm)
    ob = mk('ar15_bolt_carrier', bm, M['steel'])
    cut = bmesh.new()
    # ejection-port side flat and forward-assist serrations on the right
    box(-120.0, -20.0, -6.0, -36.0, -11.0, 7.0, bm=cut)
    for k in range(9):
        x = -150.0 + k * 3.0
        box(x - 0.8, -20.0, 1.0, x + 0.8, -11.2, 11.0, bm=cut)
    # lug gaps
    for k in range(7):
        b = box(-15.0, -1.2, 6.0, -8.0, 1.2, 10.0)
        b.transform(Matrix.Rotation(math.radians(360.0 / 7 * k + 12), 4, 'X'))
        merge(cut, b)
    diff(ob, cut)
    bevel(ob, 0.35, seg=1, angle=35)
    smooth(ob)
    return ob
