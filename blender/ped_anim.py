"""Pose and animation tools for the GTA ped rig (ped_rig.py) holding weapon_ar15.

Poses are built procedurally: the rifle is placed in ped space, the right hand follows the rifle
exactly the way the game attaches weapons (the weapon's Gun_GripR bone on the ped's PH_R_Hand),
the left hand goes to a point on the rifle (or to the magazine / a pouch during a reload), both
arms are solved with an analytic two-bone IK, and spine, head and fingers are posed on top.
"""
import math

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

import ped_rig as R

MM = 0.001
# weapon_ar15 Gun_GripR (weapon space) -> the ped's PH_R_Hand; same values as build_fivem.py
GRIP_R_ROT = Quaternion((0.7474004, 0.6578194, 0.00028754104, 0.093093015))
GRIP_R_POS = Vector((-118.0 - 91.5, -23.2, -37.8 - 55.9)) * MM
GRIP_R = Matrix.Translation(GRIP_R_POS) @ GRIP_R_ROT.to_matrix().to_4x4()

# ped space: the ped faces -Y
FWD, LEFT, UP = Vector((0, -1, 0)), Vector((1, 0, 0)), Vector((0, 0, 1))


def frame(x, y_hint):
    """Rotation matrix (3x3) with X along ``x`` and Y as close to ``y_hint`` as possible."""
    x = Vector(x).normalized()
    y = (Vector(y_hint) - x * x.dot(y_hint)).normalized()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def weapon_matrix(pos, barrel, left_side):
    """Weapon world matrix from its origin position, barrel direction and where its left side faces."""
    m = frame(barrel, left_side).to_4x4()
    m.translation = Vector(pos)
    return m


def rot_local(axis, deg):
    return Matrix.Rotation(math.radians(deg), 4, axis)


class Rig:
    def __init__(self, arm_obj):
        self.arm = arm_obj
        self.skel = R.load_skeleton()
        self.rest = R.rest_locals(self.skel)
        self.parent = {n: p for n, p, *_ in self.skel}
        # elbow hinge sign per side, from the rest pose: hinge = sign * (upper x forearm)
        W = R.fk(self.skel, self.rest)
        self.hinge_sign = {}
        for s in 'LR':
            su = W[f'SKEL_{s}_UpperArm']
            u = W[f'SKEL_{s}_Forearm'].translation - su.translation
            f = W[f'SKEL_{s}_Hand'].translation - W[f'SKEL_{s}_Forearm'].translation
            n = u.cross(f)
            self.hinge_sign[s] = 1.0 if n.dot(su.col[2].to_3d()) >= 0 else -1.0
        self.len_upper = {s: self.rest[f'SKEL_{s}_Forearm'].translation.length for s in 'LR'}
        self.len_fore = {s: self.rest[f'SKEL_{s}_Hand'].translation.length for s in 'LR'}

    def new_pose(self):
        return {n: m.copy() for n, m in self.rest.items()}

    def world(self, local):
        return R.fk(self.skel, local)

    def set_world_rot(self, local, name, rot3, world=None):
        """Give bone ``name`` the world rotation ``rot3``, keeping its rest offset from the parent."""
        world = world or self.world(local)
        p = self.parent[name]
        pw = world[p] if p else Matrix.Identity(4)
        m = rot3.to_4x4()
        m.translation = (pw @ self.rest[name]).translation if p else self.rest[name].translation
        loc = pw.inverted() @ m
        loc.translation = self.rest[name].translation
        local[name] = loc
        return loc

    def rotate(self, local, name, axis, deg):
        """Extra local rotation on top of the current local pose of ``name``."""
        local[name] = local[name] @ rot_local(axis, deg)

    def solve_arm(self, local, side, hand_world, pole):
        """Two-bone IK: wrist to ``hand_world``'s origin, hand rotation exact, elbow bent towards the
        direction ``pole`` (relative to the shoulder)."""
        W = self.world(local)
        S = W[f'SKEL_{side}_UpperArm'].translation
        a, b = self.len_upper[side], self.len_fore[side]
        T = hand_world.translation
        d = T - S
        dist = min(max(d.length, abs(a - b) + 1e-4), a + b - 1e-4)
        dirv = d.normalized()
        cos_a = (a * a + dist * dist - b * b) / (2 * a * dist)
        sin_a = math.sqrt(max(0.0, 1 - cos_a * cos_a))
        pv = Vector(pole)
        perp = (pv - dirv * dirv.dot(pv)).normalized()
        E = S + dirv * (a * cos_a) + perp * (a * sin_a)
        Tr = S + dirv * dist
        hinge = (E - S).cross(Tr - E).normalized() * self.hinge_sign[side]
        up = frame(E - S, hinge.cross(E - S))
        fore = frame(Tr - E, hinge.cross(Tr - E))
        self.set_world_rot(local, f'SKEL_{side}_UpperArm', up)
        self.set_world_rot(local, f'SKEL_{side}_Forearm', fore)
        self.set_world_rot(local, f'SKEL_{side}_Hand', hand_world.to_3x3())
        return (T - Tr).length   # 0 when the target was reached

    # --- fingers ---------------------------------------------------------------------------
    def curl(self, local, side, finger, angles, spread=0.0):
        """Curl a finger (0 = thumb .. 4 = pinky) by per-joint angles in degrees, on top of rest."""
        sgn = 1.0 if side == 'R' else -1.0
        for j, ang in enumerate(angles):
            n = f'SKEL_{side}_Finger{finger}{j}'
            m = self.rest[n] @ rot_local('Z', sgn * ang)
            if j == 0 and spread:
                m = m @ rot_local('Y', sgn * spread)
            local[n] = m

    def apply(self, local, frame_no=None):
        """Write the pose to the armature (and keyframe it)."""
        pbs = self.arm.pose.bones
        for n, _p, *_ in self.skel:
            pb = pbs[n]
            pb.matrix_basis = self.rest[n].inverted() @ local[n]
            if frame_no is not None:
                pb.keyframe_insert('rotation_quaternion', frame=frame_no)
                if n in ('SKEL_ROOT',):
                    pb.keyframe_insert('location', frame=frame_no)


# ---------------------------------------------------------------------------
# weapon in hand
# ---------------------------------------------------------------------------
def load_weapon(blend, actions=False):
    """Append the rigged game weapon (armature 'weapon_ar15' + meshes, optionally its own actions)."""
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(('weapon_ar15', 'ar15_'))]
        if actions:
            dst.actions = list(src.actions)
    for ob in dst.objects:
        if ob is not None and ob.name != 'ar15_shell':
            bpy.context.scene.collection.objects.link(ob)
    arm = bpy.data.objects['weapon_ar15']
    arm.animation_data_clear()
    return arm


def attach_weapon(weapon, ped, local_hand=True):
    """Parent the weapon to PH_R_Hand so that Gun_GripR sits on it (as the game does)."""
    weapon.parent = ped
    weapon.parent_type = 'BONE'
    weapon.parent_bone = 'PH_R_Hand'
    bpy.context.view_layer.update()
    ph = ped.matrix_world @ ped.pose.bones['PH_R_Hand'].matrix
    weapon.matrix_world = ph @ GRIP_R.inverted()


def weapon_from_hand(rig, local):
    """World matrix of the weapon for the current pose (right hand holds the grip)."""
    W = rig.world(local)
    return W['PH_R_Hand'] @ GRIP_R.inverted()


def right_hand_for_weapon(rig, weapon_world):
    """SKEL_R_Hand world matrix that puts the weapon at ``weapon_world``."""
    ph_local = rig.rest['PH_R_Hand']
    return weapon_world @ GRIP_R @ ph_local.inverted()
