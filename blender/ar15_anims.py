"""Custom third-person animations for weapon_ar15 on the GTA V ped skeleton (30 fps).

    python3 blender/ar15_anims.py [--out DIR] [--weapon weapon_ar15_game.blend] [--no-export]

The ped (ped_rig.py) holds the game weapon exactly the way GTA attaches it (the weapon's Gun_GripR
on the ped's PH_R_Hand), so the right arm follows the rifle; the left hand is placed on the rifle,
on the magazine or on the bolt catch and both arms are solved with IK (ped_anim.py). Every frame
is baked. Clips:

  ped + weapon, used in game
    hold          loop: low ready across the chest, muzzle down to the left, breathing
    reload        rounds left: magazine out and into the vest pouch, fresh one in
    reload_empty  bolt locked back: empty magazine drops free, fresh one from the pouch,
                  bolt catch slapped, carrier slams home
  weapon only, used in game (the ped aims and recoils with GTA's own carbine animations)
    fire          one shot: trigger, carrier cycles, dust cover pops open
    fire_last     last round: carrier locks back on the bolt catch
  preview only (GTA-like shouldered aim, to show firing in context)
    shot, burst, burst_empty

The weapon armature of every clip is named like the clip (NLA track names match), and the
magazine rides on WAPClip, so in the game the weapon clip moves the magazine with the hand.
Events (shell ejection, magazine drop) go to <out>/ar15_anims.json.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import ped_anim as A  # noqa: E402
import ped_rig as R  # noqa: E402

FPS = 30
MM = 0.001
F, L, U = A.FWD, A.LEFT, A.UP

# weapon space (m): +X muzzle, +Y left side, +Z up
WAPCLIP = Vector((-44.0, 0.0, -16.5)) * MM
HG_Z0, HG_APO = 2.3 * MM, 22.0 * MM            # handguard octagon centre / apothem
GRIP_L_X = 136.5 * MM                           # Gun_GripL (GTA's support hand point)
HOLO_EYE = Vector((-109.0 - 80.0, 0.0, 73.1)) * MM   # eye point 8 cm behind the holo window
BUTT = Vector((-392.0, 0.0, -45.0)) * MM
MAG_TOP_Z = 9.6 * MM                            # top of the magazine above WAPClip
MAG_CLEAR = 82.0 * MM                           # pull needed to clear the magwell

# weapon part motion (same values as game_rig.py)
BOLT_TRAVEL, BOLT_LOCKED = 82.0, 78.0
TRIGGER_PULL, COVER_OPEN = 12.0, 106.0
CATCH_UP, CATCH_PRESS, MAGREL_PRESS = -7.0, 6.0, 3.0

# vest pouch (ped space): magazine standing in it, front of the magazine towards the ped's centre
POUCH = Vector((0.085, -0.122, 0.155))          # pouch centre
POUCH_SIZE = Vector((0.080, 0.040, 0.140))
# magazine frame standing in the pouch: its front (+X) towards the ped's right, its left face (+Y)
# forward, feed lips up
MAG_IN_POUCH = Matrix(((-1.0, 0.0, 0.0, 0.095), (0.0, -1.0, 0.0, -0.122), (0.0, 0.0, 1.0, 0.262), (0, 0, 0, 1)))
POUCH_LIFT = 0.155                              # draw height that clears the pouch
MAG_HIDDEN_Y = 0.055                            # pushed back into the torso until the hand takes it


# ---------------------------------------------------------------------------
# interpolation
# ---------------------------------------------------------------------------
def ease(t, mode):
    if mode == 'lin':
        return t
    if mode == 'in':
        return t * t
    if mode == 'out':
        return 1.0 - (1.0 - t) * (1.0 - t)
    if mode == 'step':
        return 1.0 if t >= 1.0 else 0.0
    return t * t * (3.0 - 2.0 * t)


def mix_matrix(a, b, t):
    la, ra, _ = a.decompose()
    lb, rb, _ = b.decompose()
    if ra.dot(rb) < 0.0:
        rb = -rb
    m = ra.slerp(rb, t).to_matrix().to_4x4()
    m.translation = la.lerp(lb, t)
    return m


def mix_value(a, b, t):
    if isinstance(a, dict):
        return {k: mix_value(a[k], b[k], t) for k in a}
    if isinstance(a, (tuple, list)):
        return tuple(mix_value(x, y, t) for x, y in zip(a, b))
    return a + (b - a) * t


class Tgt:
    """A transform given in ped space ('ped'), weapon space ('weapon') or the magazine frame ('mag')."""

    def __init__(self, space, m, palm=0.048):
        self.space, self.m, self.palm = space, m, palm

    def world(self, ctx):
        if self.space == 'ped':
            return self.m
        return ctx[self.space] @ self.m


def mix_tgt(a, b, t, ctx):
    return mix_matrix(a.world(ctx), b.world(ctx), t), a.palm + (b.palm - a.palm) * t


class Track:
    """Keys (frame, value, easing of the segment that ends at this key)."""

    def __init__(self, *keys):
        self.keys = []
        for k in keys:
            self.key(*k)

    def key(self, f, v, mode='smooth'):
        self.keys.append((f, v, mode))
        self.keys.sort(key=lambda k: k[0])
        return self

    def segment(self, f):
        ks = self.keys
        if f <= ks[0][0]:
            return ks[0][1], ks[0][1], 0.0
        for (f0, v0, _m0), (f1, v1, m1) in zip(ks, ks[1:]):
            if f <= f1:
                return v0, v1, ease((f - f0) / (f1 - f0), m1)
        return ks[-1][1], ks[-1][1], 0.0

    def value(self, f):
        a, b, t = self.segment(f)
        return mix_value(a, b, t)

    def matrix(self, f):
        a, b, t = self.segment(f)
        return mix_matrix(a, b, t)

    def target(self, f, ctx):
        a, b, t = self.segment(f)
        return mix_tgt(a, b, t, ctx)


# ---------------------------------------------------------------------------
# poses
# ---------------------------------------------------------------------------
def weapon_at(grip, barrel, left):
    """Weapon matrix with the right-hand grip point at ``grip`` (ped space)."""
    rot = A.frame(barrel, left)
    m = rot.to_4x4()
    m.translation = Vector(grip) - rot @ A.GRIP_R_POS
    return m


def ped_dir(l=0.0, f=0.0, u=0.0):
    return L * l + F * f + U * u


def contact(point, fingers, normal, palm=0.048):
    """Palm frame: origin on the palm, X along the fingers, Y to the thumb, Z out of the palm."""
    z = Vector(normal).normalized()
    x = Vector(fingers)
    x = (x - z * x.dot(z)).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = Vector(point)
    return m


def hg_grip(x):
    """Support hand around the handguard at weapon x: palm on the lower left facet."""
    s = math.sqrt(0.5)
    p = Vector((x, HG_APO * s, HG_Z0 - HG_APO * s))
    return Tgt('weapon', contact(p, (0, -s, -s), (0, -s, s)))


MAG_BODY = Tgt('mag', contact(Vector((8.0, 15.0, -95.0)) * MM, (0.6, 0.0, -0.8), (0, -1, 0)))
MAG_TOPGRIP = Tgt('mag', contact(Vector((2.0, 15.5, -14.0)) * MM, (1.0, 0.0, -0.3), (0, -1, 0)))
CATCH_SLAP = Tgt('weapon', contact(Vector((-72.0, 21.0, -16.0)) * MM, (0.45, 0.0, 0.9), (0, -1, 0)), palm=0.016)


def mag_seated(dz=0.0, tilt=0.0):
    """Magazine frame (weapon space) pulled ``dz`` metres down the magwell, front tipped ``tilt`` deg."""
    m = Matrix.Translation(WAPCLIP + Vector((0.0, 0.0, -dz))) @ Matrix.Rotation(math.radians(tilt), 4, 'Y')
    return Tgt('weapon', m)


def mag_pouch(lift=0.0, back=0.0):
    m = MAG_IN_POUCH.copy()
    m.translation.z += lift
    m.translation.y += back
    return Tgt('ped', m)


# finger presets: finger -> (base, mid, tip) curl degrees
R_GRIP = {0: (20, 30, 25), 1: (8, 4, 2), 2: (70, 75, 45), 3: (75, 78, 45), 4: (80, 80, 45)}
R_TRIGGER = {**R_GRIP, 1: (32, 42, 28)}
R_PRESS = {**R_GRIP, 1: (2, 8, 4)}
L_HG = {0: (10, 15, 10), 1: (55, 62, 40), 2: (58, 65, 40), 3: (60, 66, 40), 4: (62, 66, 40)}
L_MAG = {0: (22, 15, 10), 1: (35, 45, 30), 2: (48, 55, 35), 3: (52, 58, 35), 4: (55, 60, 35)}
L_PINCH = {0: (30, 25, 15), 1: (30, 40, 25), 2: (40, 50, 30), 3: (45, 52, 30), 4: (48, 55, 30)}
L_OPEN = {0: (8, 8, 5), 1: (12, 12, 6), 2: (14, 14, 6), 3: (16, 16, 6), 4: (18, 18, 6)}
L_FLAT = {0: (2, 2, 0), 1: (4, 4, 2), 2: (4, 4, 2), 3: (5, 5, 2), 4: (6, 6, 2)}


def posture(lean=4.0, twist=0.0, side=0.0, hpitch=4.0, hyaw=0.0, hroll=0.0,
            clp=0.0, cle=0.0, crp=0.0, cre=0.0, pole_r=(-0.35, 0.3, -1.0), pole_l=(0.4, 0.3, -1.0)):
    return dict(lean=lean, twist=twist, side=side, hpitch=hpitch, hyaw=hyaw, hroll=hroll,
                clp=clp, cle=cle, crp=crp, cre=cre, pole_r=tuple(pole_r), pole_l=tuple(pole_l))


def rot_world(rig, loc, bone, axis, deg):
    if abs(deg) < 1e-6:
        return
    w = rig.world(loc)[bone]
    ax = (w.to_3x3().inverted() @ Vector(axis)).normalized()
    loc[bone] = loc[bone] @ Matrix.Rotation(math.radians(deg), 4, ax)


def apply_posture(rig, loc, p):
    for b, k in (('SKEL_Spine1', 0.3), ('SKEL_Spine2', 0.35), ('SKEL_Spine3', 0.35)):
        rot_world(rig, loc, b, (1, 0, 0), p['lean'] * k)
        rot_world(rig, loc, b, (0, 0, 1), p['twist'] * k)
        rot_world(rig, loc, b, (0, -1, 0), p['side'] * k)
    for b, k in (('SKEL_Neck_1', 0.4), ('SKEL_Head', 0.6)):
        rot_world(rig, loc, b, (1, 0, 0), p['hpitch'] * k)
        rot_world(rig, loc, b, (0, 0, 1), p['hyaw'] * k)
        rot_world(rig, loc, b, (0, -1, 0), p['hroll'] * k)
    rot_world(rig, loc, 'SKEL_L_Clavicle', (0, 0, 1), -p['clp'])
    rot_world(rig, loc, 'SKEL_L_Clavicle', (0, 1, 0), -p['cle'])
    rot_world(rig, loc, 'SKEL_R_Clavicle', (0, 0, 1), p['crp'])
    rot_world(rig, loc, 'SKEL_R_Clavicle', (0, 1, 0), p['cre'])


def fingers(rig, loc, side, preset):
    for f, ang in preset.items():
        rig.curl(loc, side, f, ang)


# ---------------------------------------------------------------------------
# clips
# ---------------------------------------------------------------------------
class Clip:
    def __init__(self, name, frames, loop=False):
        self.name, self.frames, self.loop = name, frames, loop
        self.weapon = None           # Track of ped-space weapon matrices
        self.weapon_fx = None        # f -> weapon-space offset matrix (breathing, recoil)
        self.posture = None          # Track of posture dicts
        self.posture_fx = None       # f -> dict of posture offsets
        self.mag = Track((0, mag_seated()))
        self.lh = None               # Track of Tgt
        self.fr = Track((0, R_GRIP))
        self.fl = Track((0, L_HG))
        self.parts = {}              # part -> Track of floats
        self.events = []             # (frame, name)
        self.ped = True              # False: weapon-only clip


def solve(rig, clip, f):
    """Pose of frame ``f``: ped locals, actual weapon matrix, magazine matrix (ped space), misses."""
    p = clip.posture.value(f)
    if clip.posture_fx:
        for k, v in clip.posture_fx(f).items():
            p[k] = p[k] + v
    W = clip.weapon.matrix(f)
    if clip.weapon_fx:
        W = W @ clip.weapon_fx(f)
    loc = rig.new_pose()
    apply_posture(rig, loc, p)
    miss_r = rig.solve_arm(loc, 'R', A.right_hand_for_weapon(rig, W), Vector(p['pole_r']))
    Wact = A.weapon_from_hand(rig, loc)
    ctx = {'weapon': Wact}
    ctx['mag'] = clip.mag.target(f, ctx)[0]
    lh, palm = clip.lh.target(f, ctx)
    wrist = lh @ Matrix.Translation((-palm, -0.004, -0.017))
    miss_l = rig.solve_arm(loc, 'L', wrist, Vector(p['pole_l']))
    fingers(rig, loc, 'R', clip.fr.value(f))
    fingers(rig, loc, 'L', clip.fl.value(f))
    return loc, Wact, ctx['mag'], (miss_r, miss_l)


# poses ------------------------------------------------------------------------------------------
HOLD_W = weapon_at((-0.04, -0.17, 0.24), ped_dir(0.55, 0.30, -0.75), (0, 1, 0))
HOLD_P = posture(lean=5.0, hpitch=4.0, clp=12.0)
HOLD_LH = hg_grip(0.045)

RELOAD_W = weapon_at((-0.07, -0.20, 0.30), ped_dir(0.30, 0.85, -0.40), ped_dir(0.77, 0.0, 0.64))
RELOAD_P = posture(lean=9.0, hpitch=24.0, hyaw=8.0, clp=16.0, cle=2.0,
                   pole_r=(-0.5, 0.1, -1.0), pole_l=(0.8, 0.3, -0.6))


def aim_weapon(rig, p, pitch=0.0):
    """Shouldered aim: butt in the right shoulder pocket, bore straight ahead (``pitch`` up)."""
    loc = rig.new_pose()
    apply_posture(rig, loc, p)
    W = rig.world(loc)
    pocket = W['SKEL_R_UpperArm'] @ POCKET_LOCAL
    rot = A.frame(ped_dir(0, math.cos(math.radians(pitch)), math.sin(math.radians(pitch))), L)
    m = rot.to_4x4()
    m.translation = pocket - rot @ BUTT
    return m


AIM_P = posture(lean=10.0, hpitch=20.0, hroll=14.0, hyaw=14.0, twist=-16.0, crp=10.0, cre=8.0, clp=18.0,
                pole_r=(-0.9, 0.2, -0.6), pole_l=(0.2, -0.2, -1.0))
AIM_LH = hg_grip(0.095)
POCKET_LOCAL = None        # set in init_constants (needs the skeleton)


def init_constants(rig):
    global POCKET_LOCAL
    W = rig.world(rig.rest)
    sh = W['SKEL_R_UpperArm']
    # shoulder pocket: in front of and above the shoulder joint, a little inboard
    POCKET_LOCAL = sh.inverted() @ (sh.translation + Vector((0.05, -0.075, 0.05)))


def breathing(f, frames, amp=1.0):
    ph = 2.0 * math.pi * f / frames
    return math.sin(ph) * amp


def make_hold():
    c = Clip('hold', 120, loop=True)
    c.weapon = Track((0, HOLD_W))
    c.posture = Track((0, HOLD_P))
    c.lh = Track((0, HOLD_LH))
    c.fl = Track((0, L_HG))

    def wfx(f):
        b = breathing(f, 120)
        return Matrix.Translation((0.0, 0.0, 0.0025 * b)) @ Matrix.Rotation(math.radians(0.6 * b), 4, 'Y')

    def pfx(f):
        b = breathing(f, 120)
        scan = math.sin(2.0 * math.pi * f / 120 + 0.8)
        return {'lean': -0.6 * b, 'cle': 0.8 * b, 'cre': 0.8 * b, 'hyaw': 5.0 * scan, 'hpitch': 0.8 * b}
    c.weapon_fx, c.posture_fx = wfx, pfx
    return c


def make_reload():
    """Magazine with rounds left: out, stowed in the vest pouch, the fresh one drawn and seated."""
    c = Clip('reload', 76)
    c.weapon = Track((0, HOLD_W), (10, RELOAD_W), (60, RELOAD_W), (72, HOLD_W))
    c.posture = Track((0, HOLD_P), (10, RELOAD_P),
                      (24, posture(lean=11.0, hpitch=30.0, hyaw=14.0, twist=4.0, clp=18.0, cle=2.0,
                                   pole_r=(-0.5, 0.1, -1.0), pole_l=(0.8, 0.1, -0.7))),
                      (40, posture(lean=11.0, hpitch=30.0, hyaw=14.0, twist=4.0, clp=18.0, cle=2.0,
                                   pole_r=(-0.5, 0.1, -1.0), pole_l=(0.8, 0.1, -0.7))),
                      (52, RELOAD_P), (60, RELOAD_P), (72, HOLD_P))
    c.mag = Track((0, mag_seated()), (12, mag_seated()),
                  (18, mag_seated(MAG_CLEAR), 'in'),
                  (28, mag_pouch(POUCH_LIFT)),
                  (33, mag_pouch(0.0)),
                  (37, mag_pouch(0.0)),
                  (42, mag_pouch(POUCH_LIFT), 'in'),
                  (52, mag_seated(MAG_CLEAR, 4.0)),
                  (56, mag_seated(-0.0015), 'in'),
                  (58, mag_seated()))
    c.lh = Track((0, HOLD_LH), (10, MAG_BODY), (18, MAG_BODY), (27, MAG_TOPGRIP), (33, MAG_TOPGRIP),
                 (34, MAG_TOPGRIP), (37, MAG_TOPGRIP), (44, MAG_TOPGRIP), (50, MAG_BODY), (58, MAG_BODY),
                 (68, HOLD_LH))
    c.fl = Track((0, L_HG), (5, L_OPEN), (10, L_MAG), (18, L_MAG), (27, L_PINCH), (33, L_PINCH),
                 (35, L_OPEN), (37, L_PINCH), (44, L_PINCH), (50, L_MAG), (58, L_MAG), (62, L_OPEN), (68, L_HG))
    c.fr = Track((0, R_GRIP), (8, R_PRESS), (14, R_PRESS), (18, R_GRIP))
    c.parts['magrelease'] = Track((0, 0.0), (10, 0.0), (12, MAGREL_PRESS), (15, MAGREL_PRESS), (17, 0.0))
    c.parts['dustcover'] = Track((0, COVER_OPEN))
    return c


def make_reload_empty():
    """Bolt locked back: the empty magazine drops, a fresh one from the pouch, bolt catch slapped."""
    c = Clip('reload_empty', 86)
    look = posture(lean=11.0, hpitch=30.0, hyaw=14.0, twist=4.0, clp=18.0, cle=2.0,
                   pole_r=(-0.5, 0.1, -1.0), pole_l=(0.8, 0.1, -0.7))
    c.weapon = Track((0, HOLD_W), (10, RELOAD_W), (64, RELOAD_W), (78, HOLD_W))
    c.posture = Track((0, HOLD_P), (10, RELOAD_P), (16, look), (24, look), (36, RELOAD_P),
                      (64, RELOAD_P), (78, HOLD_P))
    drop = 8
    c.events.append((drop, 'mag_drop'))
    c.mag = Track((0, mag_seated()), (drop, mag_seated()),
                  (drop + 1, mag_pouch(-0.03, MAG_HIDDEN_Y), 'step'),   # the dropped one is a prop now
                  (13, mag_pouch(-0.03, MAG_HIDDEN_Y)),
                  (17, mag_pouch(0.0)),
                  (26, mag_pouch(POUCH_LIFT), 'in'),
                  (36, mag_seated(MAG_CLEAR, 4.0)),
                  (40, mag_seated(-0.0015), 'in'),
                  (42, mag_seated()))
    c.lh = Track((0, HOLD_LH), (17, MAG_TOPGRIP), (26, MAG_TOPGRIP),
                 (34, MAG_BODY), (42, MAG_BODY), (50, Tgt('weapon', CATCH_SLAP.m @ Matrix.Translation((0, 0, -0.05)),
                                                          palm=0.016)),
                 (53, CATCH_SLAP), (55, CATCH_SLAP), (68, HOLD_LH))
    c.fl = Track((0, L_HG), (6, L_OPEN), (14, L_OPEN), (18, L_PINCH), (26, L_PINCH), (34, L_MAG), (42, L_MAG),
                 (48, L_FLAT), (55, L_FLAT), (62, L_OPEN), (68, L_HG))
    c.fr = Track((0, R_GRIP), (4, R_PRESS), (10, R_PRESS), (14, R_GRIP))
    c.parts['magrelease'] = Track((0, 0.0), (5, 0.0), (7, MAGREL_PRESS), (10, MAGREL_PRESS), (12, 0.0))
    c.parts['bolt'] = Track((0, -BOLT_LOCKED), (53, -BOLT_LOCKED), (55, 0.0, 'in'))
    c.parts['boltcatch'] = Track((0, CATCH_UP), (51, CATCH_UP), (53, CATCH_PRESS, 'lin'), (55, CATCH_PRESS),
                                 (58, 0.0))
    c.parts['dustcover'] = Track((0, COVER_OPEN))
    return c



def weapon_fire(name, last=False):
    c = Clip(name, 6)
    c.ped = False
    c.parts['trigger'] = Track((0, 0.0), (1, TRIGGER_PULL, 'lin'), (4, TRIGGER_PULL), (5, 0.0, 'lin'))
    if last:
        c.parts['bolt'] = Track((0, 0.0), (1, -40.0, 'lin'), (2, -BOLT_TRAVEL, 'lin'), (3, -BOLT_LOCKED, 'lin'))
        c.parts['boltcatch'] = Track((0, 0.0), (2, 0.0), (3, CATCH_UP, 'lin'))
    else:
        c.parts['bolt'] = Track((0, 0.0), (1, -40.0, 'lin'), (2, -BOLT_TRAVEL, 'lin'), (3, -35.0, 'lin'),
                                (4, 0.0, 'lin'))
    c.parts['dustcover'] = Track((0, 0.0), (1, 45.0, 'lin'), (2, COVER_OPEN, 'lin'))
    c.events += [(0, 'shot'), (1, 'shell')]
    return c


# preview: shouldered aim and firing ------------------------------------------------------------
def make_fire_sequence(rig, name, shots, interval, last_empty=False):
    """Hold -> shoulder -> ``shots`` rounds -> hold (preview of the weapon clips in context)."""
    up, first = 9, 12
    end_fire = first + interval * (shots - 1) + 8
    frames = end_fire + 22 if not last_empty else end_fire + 20
    c = Clip(name, frames)
    aim = aim_weapon(rig, AIM_P)
    c.weapon = Track((0, HOLD_W), (up, aim), (end_fire + 6, aim), (frames - 2, HOLD_W))
    c.posture = Track((0, HOLD_P), (up, AIM_P), (end_fire + 6, AIM_P), (frames - 2, HOLD_P))
    c.lh = Track((0, HOLD_LH), (up, AIM_LH), (end_fire + 6, AIM_LH), (frames - 2, HOLD_LH))
    c.fl = Track((0, L_HG))
    c.fr = Track((0, R_GRIP), (up - 2, R_TRIGGER), (end_fire + 2, R_TRIGGER), (end_fire + 8, R_GRIP))
    shot_frames = [first + i * interval for i in range(shots)]

    def kick(f):
        k = 0.0
        for s in shot_frames:
            d = f - s
            if 0 <= d < 7:
                k = max(k, (d / 1.5) if d < 1.5 else math.exp(-(d - 1.5) / 1.6))
        return k

    def wfx(f):
        k = kick(f)
        return Matrix.Translation((-0.014 * k, 0.0, 0.004 * k)) @ Matrix.Rotation(math.radians(-2.2 * k), 4, 'Y')

    def pfx(f):
        k = kick(f)
        return {'lean': -1.2 * k, 'hpitch': -1.0 * k, 'crp': -2.0 * k}
    c.weapon_fx, c.posture_fx = wfx, pfx
    trig, bolt, cover, catch = [(0, 0.0)], [(0, 0.0)], [(0, 0.0)], [(0, 0.0)]
    for i, s in enumerate(shot_frames):
        final = i == len(shot_frames) - 1
        lastshot = last_empty and final
        if i == 0:
            trig += [(s - 1, 0.0)]
            cover += [(s, 0.0), (s + 1, COVER_OPEN)]
        trig += [(s, TRIGGER_PULL)]
        if final:
            trig += [(s + 3, TRIGGER_PULL), (s + 4, 0.0)]
        bolt += [(s, 0.0), (s + 1, -BOLT_TRAVEL)]
        bolt += [(s + 2, -BOLT_LOCKED)] if lastshot else [(s + 2, -30.0), (s + 3, 0.0)]
        if lastshot:
            catch += [(s + 1, 0.0), (s + 2, CATCH_UP)]
        c.events += [(s, 'shot'), (s + 1, 'shell')]
    c.parts['trigger'] = _lin_track(trig)
    c.parts['bolt'] = _lin_track(bolt)
    c.parts['dustcover'] = _lin_track(cover)
    if last_empty:
        c.parts['boltcatch'] = _lin_track(catch)
    return c


def _lin_track(keys):
    t = Track()
    seen = {}
    for f, v in keys:
        seen[f] = v
    for f in sorted(seen):
        t.key(f, seen[f], 'lin')
    return t


# ---------------------------------------------------------------------------
# baking
# ---------------------------------------------------------------------------
PART_BONES = {   # clip part -> (game-rig bone, 'T' axis | 'R' axis letter)
    'bolt': ('gun_bolt', 'T', (1, 0, 0)),
    'trigger': ('gun_trigger', 'R', 'Y'),
    'dustcover': ('gun_dustcover', 'R', 'X'),
    'boltcatch': ('gun_boltcatch', 'R', 'Y'),
    'magrelease': ('gun_magrelease', 'T', (0, 1, 0)),
}


def part_delta(arm, part, value):
    bone, kind, ax = PART_BONES[part]
    rest = arm.data.bones[bone].matrix_local
    if kind == 'T':
        return bone, Matrix.Translation(Vector(ax) * value * MM)
    head = rest.translation
    return bone, Matrix.Translation(head) @ Matrix.Rotation(math.radians(value), 4, ax) @ Matrix.Translation(-head)


def _stash(ob, act, name):
    ad = ob.animation_data
    tr = ad.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, 0, act)
    st.name = name
    tr.mute = True
    ad.action = None


def bake(rig, ped, weapon, clip, report):
    """Key every frame of ``clip`` on the ped and the weapon armatures, stash both on NLA tracks."""
    frames = range(0, clip.frames + 1)
    ped_act = None
    if clip.ped:
        ped_act = bpy.data.actions.new(clip.name)
        ped_act.use_fake_user = True
        ped.animation_data_create()
        ped.animation_data.action = ped_act
    w_act = bpy.data.actions.new('w_' + clip.name)
    w_act.use_fake_user = True
    weapon.animation_data_create()
    weapon.animation_data.action = w_act
    wap_rest = weapon.data.bones['WAPClip'].matrix_local
    mag_rest = Matrix.Translation(WAPCLIP)
    misses = [0.0, 0.0]
    prev_q = {}
    for f in frames:
        if clip.ped:
            loc, Wact, mag, miss = solve(rig, clip, f)
            misses = [max(misses[0], miss[0]), max(misses[1], miss[1])]
            pbs = ped.pose.bones
            for n, _p, *_ in rig.skel:
                pb = pbs[n]
                basis = rig.rest[n].inverted() @ loc[n]
                q = basis.to_quaternion()
                if n in prev_q and prev_q[n].dot(q) < 0.0:
                    q = -q
                prev_q[n] = q
                pb.rotation_quaternion = q
                pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
            mag_w = Wact.inverted() @ mag
        else:
            mag_w = mag_rest
        # weapon parts (armature space deltas)
        deltas = {}
        for part in PART_BONES:
            tr = clip.parts.get(part)
            bone, D = part_delta(weapon, part, tr.value(f) if tr else 0.0)
            deltas[bone] = D
        deltas['WAPClip'] = mag_w @ mag_rest.inverted()
        for bone, D in deltas.items():
            pb = weapon.pose.bones[bone]
            rest = weapon.data.bones[bone].matrix_local
            basis = rest.inverted() @ D @ rest
            loc_, q, _s = basis.decompose()
            key = 'w:' + bone
            if key in prev_q and prev_q[key].dot(q) < 0.0:
                q = -q
            prev_q[key] = q
            pb.location = loc_
            pb.rotation_quaternion = q
            pb.keyframe_insert('location', frame=f, group=bone)
            pb.keyframe_insert('rotation_quaternion', frame=f, group=bone)
    for act in (ped_act, w_act):
        if act:
            act.frame_range = (0, clip.frames)
            act['fps'] = FPS
            act.use_cyclic = clip.loop
    if clip.ped:
        _stash(ped, ped_act, clip.name)
    _stash(weapon, w_act, clip.name)
    for pb in ped.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    for pb in weapon.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    report[clip.name] = {'frames': clip.frames, 'loop': clip.loop, 'ped': clip.ped,
                         'events': [[f, e] for f, e in clip.events],
                         'miss_r_mm': round(misses[0] * 1000, 1), 'miss_l_mm': round(misses[1] * 1000, 1)}
    print(f'  {clip.name:14s} {clip.frames:3d} frames  miss R {misses[0] * 1000:5.1f} mm  L {misses[1] * 1000:5.1f} mm')


def show_pose(rig, ped, weapon, clip, f):
    """Pose both armatures at frame ``f`` of ``clip`` (no keys), for renders."""
    for pb in weapon.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    if clip.ped:
        loc, Wact, mag, miss = solve(rig, clip, f)
        rig.apply(loc)
        mag_w = Wact.inverted() @ mag
    else:
        miss = (0.0, 0.0)
        mag_w = Matrix.Translation(WAPCLIP)
    for part, tr in clip.parts.items():
        bone, D = part_delta(weapon, part, tr.value(f))
        rest = weapon.data.bones[bone].matrix_local
        weapon.pose.bones[bone].matrix_basis = rest.inverted() @ D @ rest
    rest = weapon.data.bones['WAPClip'].matrix_local
    weapon.pose.bones['WAPClip'].matrix_basis = rest.inverted() @ mag_w @ Matrix.Translation(WAPCLIP).inverted() @ rest
    bpy.context.view_layer.update()
    return miss


# ---------------------------------------------------------------------------
# scene
# ---------------------------------------------------------------------------
def build_pouch(arm):
    """Rifle magazine pouch on the vest (preview; in game the ped's own vest is used)."""
    mat = bpy.data.materials.get('ped_pouch') or bpy.data.materials.new('ped_pouch')
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.022, 0.02, 1)
    mat.diffuse_color = (0.02, 0.022, 0.02, 1)
    me = bpy.data.meshes.new('ped_pouch')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * POUCH_SIZE.x, v.co.y * POUCH_SIZE.y, v.co.z * POUCH_SIZE.z)) + POUCH
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('ped_pouch', me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    mw = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = 'BONE'
    ob.parent_bone = 'SKEL_Spine2'
    ob.matrix_world = mw
    return ob


def build_scene(weapon_blend, attachments=('holo',)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    ped = R.build_armature('ped')
    R.build_mannequin(ped)
    build_pouch(ped)
    weapon = A.load_weapon(weapon_blend)
    for o in bpy.data.objects:
        if o.name.startswith('ar15_att_'):
            keep = any(o.name.startswith('ar15_att_' + a) for a in attachments)
            o.hide_render = o.hide_viewport = not keep
    rig = A.Rig(ped)
    init_constants(rig)
    rig.apply(rig.new_pose())
    bpy.context.view_layer.update()
    A.attach_weapon(weapon, ped)
    return rig, ped, weapon


def export_preview(out_dir, name='ar15_anims'):
    """glTF for the web preview: ped + weapon (all attachments, the viewer toggles them), one
    animation per clip (the ped and weapon NLA tracks of a clip share its name and are merged)."""
    for o in bpy.data.objects:
        o.hide_render = o.hide_viewport = False
        o.hide_set(False)
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, name + '.gltf'), export_format='GLTF_SEPARATE',
                              export_image_format='JPEG', export_jpeg_quality=88, export_yup=True,
                              export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_merge_animation='NLA_TRACK', export_force_sampling=True,
                              export_frame_step=1, export_optimize_animation_size=False,
                              export_anim_single_armature=False, use_selection=False)
    print('preview exported', out_dir)


def make_clips(rig):
    return [make_hold(), make_reload(), make_reload_empty(),
            weapon_fire('fire'), weapon_fire('fire_last', last=True),
            make_fire_sequence(rig, 'shot', 1, 6),
            make_fire_sequence(rig, 'burst', 6, 3),
            make_fire_sequence(rig, 'burst_empty', 3, 3, last_empty=True)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--weapon', default=os.path.join(ROOT, 'weapon_ar15_game.blend'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'export', 'anims'))
    ap.add_argument('--no-export', action='store_true')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    rig, ped, weapon = build_scene(args.weapon)
    report = {}
    for clip in make_clips(rig):
        bake(rig, ped, weapon, clip, report)
    os.makedirs(args.out, exist_ok=True)
    json.dump({'fps': FPS, 'clips': report}, open(os.path.join(args.out, 'ar15_anims.json'), 'w'), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(args.out, 'ar15_anims.blend'))
    print('saved', args.out)
    if not args.no_export:
        export_preview(os.path.join(args.out, 'preview'))


if __name__ == '__main__':
    main()
