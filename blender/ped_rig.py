"""GTA V freemode ped skeleton (from Sollumz' vanilla bone data) and a preview mannequin.

The skeleton keeps the game's exact rest transforms and bone tags, so poses made on it can be
exported as .ycd clips for real peds. Bones follow the GTA convention (length along local +X);
Blender tails only exist for display. The ped faces -Y, its left side is +X, up is +Z, and the
pelvis sits at the origin (feet at about z = -0.95).
"""
import json
import math
import os

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SKELETON_JSON = os.path.join(HERE, 'data_ped_skeleton.json')

# body bones used for animation (everything else of the 549-bone ped rig stays at rest)
BODY = [
    'SKEL_ROOT', 'SKEL_Pelvis',
    'SKEL_L_Thigh', 'SKEL_L_Calf', 'SKEL_L_Foot', 'SKEL_L_Toe0',
    'SKEL_R_Thigh', 'SKEL_R_Calf', 'SKEL_R_Foot', 'SKEL_R_Toe0',
    'SKEL_Spine_Root', 'SKEL_Spine0', 'SKEL_Spine1', 'SKEL_Spine2', 'SKEL_Spine3',
    'SKEL_Neck_1', 'SKEL_Head',
] + [f'SKEL_{s}_{b}' for s in 'LR' for b in ('Clavicle', 'UpperArm', 'Forearm', 'Hand')] \
  + [f'SKEL_{s}_Finger{f}{j}' for s in 'LR' for f in range(5) for j in range(3)] \
  + ['PH_L_Hand', 'PH_R_Hand', 'IK_L_Hand', 'IK_R_Hand']


def load_skeleton(names=BODY):
    """[(name, parent name, tag, T Vector, R Quaternion)] in hierarchy order, parents kept inside ``names``."""
    raw = json.load(open(SKELETON_JSON))
    by_idx = {b[0]: b for b in raw}
    keep = set(names)
    out = []
    for idx, name, parent, tag, t, q in raw:
        if name not in keep:
            continue
        p = parent
        while p >= 0 and by_idx[p][1] not in keep:   # skip over dropped helper bones
            p = by_idx[p][2]
        pname = by_idx[p][1] if p >= 0 else None
        out.append((name, pname, tag, Vector(t), Quaternion(q)))   # stored as w, x, y, z
    return out


def rest_locals(skel):
    return {n: Matrix.Translation(t) @ q.to_matrix().to_4x4() for n, _p, _tag, t, q in skel}


def fk(skel, local):
    """World matrices from local matrices (dict name -> 4x4)."""
    world = {}
    for n, p, *_ in skel:
        world[n] = world[p] @ local[n] if p else local[n].copy()
    return world


def build_armature(name='ped', skel=None):
    skel = skel or load_skeleton()
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    world = fk(skel, rest_locals(skel))
    for n, p, tag, t, q in skel:
        eb = arm.edit_bones.new(n)
        eb.head, eb.tail = (0, 0, 0), (0, 0.03, 0)
        eb.matrix = world[n]
        if p:
            eb.parent = arm.edit_bones[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    for n, p, tag, t, q in skel:
        arm.bones[n]['gta_tag'] = tag
    for pb in ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return ob


# ---------------------------------------------------------------------------
# mannequin
# ---------------------------------------------------------------------------
def _mat(name, rgb, rough=0.6, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (*rgb, 1.0)
    return m


def _capsule(bm, a, b, ra, rb, seg=10, rings=3):
    """Tapered capsule between points a and b."""
    a, b = Vector(a), Vector(b)
    axis = b - a
    L = axis.length
    z = axis.normalized()
    x = z.orthogonal().normalized()
    y = z.cross(x)
    rows = []
    # bottom hemisphere, body, top hemisphere
    profile = []
    for i in range(rings, 0, -1):
        ang = math.pi / 2 * i / rings
        profile.append((-ra * math.sin(ang), ra * math.cos(ang)))
    profile.append((0.0, ra))
    profile.append((L, rb))
    for i in range(1, rings + 1):
        ang = math.pi / 2 * i / rings
        profile.append((L + rb * math.sin(ang), rb * math.cos(ang)))
    bottom = bm.verts.new(a - z * ra)
    top = bm.verts.new(b + z * rb)
    for h, r in profile:
        ring = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            ring.append(bm.verts.new(a + z * h + (x * math.cos(t) + y * math.sin(t)) * r))
        rows.append(ring)
    for k in range(seg):
        k2 = (k + 1) % seg
        bm.faces.new((bottom, rows[0][k2], rows[0][k]))
        bm.faces.new((top, rows[-1][k], rows[-1][k2]))
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(seg):
            k2 = (k + 1) % seg
            bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))


def _ellipsoid(bm, c, rx, ry, rz, frame=Matrix.Identity(3), seg=16, rings=10):
    c = Vector(c)
    rows = []
    for i in range(1, rings):
        v = math.pi * i / rings
        ring = []
        for k in range(seg):
            u = 2 * math.pi * k / seg
            p = Vector((rx * math.sin(v) * math.cos(u), ry * math.sin(v) * math.sin(u), rz * math.cos(v)))
            ring.append(bm.verts.new(c + frame @ p))
        rows.append(ring)
    top = bm.verts.new(c + frame @ Vector((0, 0, rz)))
    bot = bm.verts.new(c + frame @ Vector((0, 0, -rz)))
    for k in range(seg):
        k2 = (k + 1) % seg
        bm.faces.new((top, rows[0][k], rows[0][k2]))
        bm.faces.new((bot, rows[-1][k2], rows[-1][k]))
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(seg):
            k2 = (k + 1) % seg
            bm.faces.new((r0[k], r1[k], r1[k2], r0[k2]))


def _loft(bm, sections, seg=20):
    """Closed loft through horizontal super-ellipse sections [(z, width, depth, y_offset)]."""
    rows = []
    for z, w, d, yo in sections:
        ring = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            cx, cy = math.cos(t), math.sin(t)
            ex = math.copysign(abs(cx) ** 0.7, cx)
            ey = math.copysign(abs(cy) ** 0.7, cy)
            ring.append(bm.verts.new((w / 2 * ex, yo + d / 2 * ey, z)))
        rows.append(ring)
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(seg):
            k2 = (k + 1) % seg
            bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
    bm.faces.new(list(reversed(rows[0])))
    bm.faces.new(rows[-1])


def _part(name, build, material, arm, bone):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build(bm)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(material)
    mw = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    ob.matrix_world = mw
    return ob


def build_mannequin(arm, skel=None):
    """Simple uniformed figure (dark uniform, vest, cap, bare hands) bone-parented to ``arm``."""
    skel = skel or load_skeleton()
    W = fk(skel, rest_locals(skel))
    P = {n: W[n].translation.copy() for n in W}
    uniform = _mat('ped_uniform', (0.05, 0.065, 0.11), 0.85)
    vest = _mat('ped_vest', (0.05, 0.05, 0.053), 0.8)
    skin = _mat('ped_skin', (0.62, 0.45, 0.36), 0.55)
    boots = _mat('ped_boots', (0.01, 0.01, 0.01), 0.45)
    cap = _mat('ped_cap', (0.02, 0.02, 0.025), 0.6)
    parts = []
    yb = P['SKEL_Spine3'].y   # body centre line (front is -Y)

    parts.append(_part('ped_hips', lambda bm: _loft(bm, [
        (-0.13, 0.30, 0.20, yb + 0.01), (-0.04, 0.35, 0.23, yb), (0.06, 0.32, 0.21, yb)]), uniform, arm, 'SKEL_Pelvis'))
    parts.append(_part('ped_belly', lambda bm: _loft(bm, [
        (0.05, 0.315, 0.205, yb), (0.16, 0.30, 0.20, yb - 0.005), (0.24, 0.34, 0.215, yb - 0.01)]), uniform, arm, 'SKEL_Spine1'))
    parts.append(_part('ped_chest', lambda bm: _loft(bm, [
        (0.23, 0.345, 0.22, yb - 0.01), (0.36, 0.39, 0.235, yb - 0.01), (0.46, 0.40, 0.20, yb + 0.005),
        (0.52, 0.22, 0.14, yb + 0.01)]), uniform, arm, 'SKEL_Spine3'))
    parts.append(_part('ped_vest', lambda bm: _loft(bm, [
        (0.06, 0.345, 0.245, yb - 0.005), (0.30, 0.37, 0.26, yb - 0.012), (0.44, 0.39, 0.245, yb - 0.005)]),
        vest, arm, 'SKEL_Spine2'))
    neck, head = P['SKEL_Neck_1'], P['SKEL_Head']
    parts.append(_part('ped_neck', lambda bm: _capsule(bm, neck, head + Vector((0, -0.004, 0.03)), 0.064, 0.058, 12, 2),
                       skin, arm, 'SKEL_Neck_1'))
    for s in (1, -1):   # trapezius: neck into the shoulders
        parts.append(_part(f'ped_trap_{"L" if s > 0 else "R"}', lambda bm, s=s: _ellipsoid(
            bm, Vector((0.075 * s, yb + 0.012, 0.505)), 0.085, 0.062, 0.045, seg=12, rings=6), uniform, arm, 'SKEL_Spine3'))
    hc = head + Vector((0, -0.014, 0.088))
    parts.append(_part('ped_head', lambda bm: _ellipsoid(bm, hc, 0.083, 0.102, 0.122), skin, arm, 'SKEL_Head'))
    parts.append(_part('ped_nose', lambda bm: _ellipsoid(bm, hc + Vector((0, -0.099, -0.008)), 0.014, 0.022, 0.026,
                                                         seg=10, rings=6), skin, arm, 'SKEL_Head'))
    for s in (1, -1):
        parts.append(_part(f'ped_ear_{"L" if s > 0 else "R"}', lambda bm, s=s: _ellipsoid(
            bm, hc + Vector((0.083 * s, 0.004, -0.004)), 0.012, 0.022, 0.03, seg=8, rings=5), skin, arm, 'SKEL_Head'))
    cap_c = hc + Vector((0, 0.004, 0.058))

    def build_cap(bm):
        _ellipsoid(bm, cap_c, 0.084, 0.102, 0.072, seg=16, rings=8)
        brim = [bm.verts.new(cap_c + Vector((0.07 * math.cos(t), -0.07 + 0.075 * math.sin(t) - 0.035, -0.012)))
                for t in [math.pi + math.pi * i / 10 for i in range(11)]]
        c0 = bm.verts.new(cap_c + Vector((0, -0.07, -0.01)))
        for a, b in zip(brim, brim[1:]):
            bm.faces.new((c0, a, b))
    parts.append(_part('ped_cap', build_cap, cap, arm, 'SKEL_Head'))

    for s in 'LR':
        sh, el, wr = P[f'SKEL_{s}_UpperArm'], P[f'SKEL_{s}_Forearm'], P[f'SKEL_{s}_Hand']
        cl = P[f'SKEL_{s}_Clavicle']
        parts.append(_part(f'ped_{s}_shoulder', lambda bm, a=cl, b=sh: _capsule(bm, a.lerp(b, 0.35), b, 0.055, 0.058, 10, 2),
                           uniform, arm, f'SKEL_{s}_Clavicle'))
        parts.append(_part(f'ped_{s}_upperarm', lambda bm, a=sh, b=el: _capsule(bm, a, b, 0.056, 0.045, 12, 3),
                           uniform, arm, f'SKEL_{s}_UpperArm'))
        parts.append(_part(f'ped_{s}_forearm', lambda bm, a=el, b=wr: _capsule(bm, a, b, 0.043, 0.030, 12, 3),
                           uniform, arm, f'SKEL_{s}_Forearm'))
        hw = W[f'SKEL_{s}_Hand']
        hx, hy, hz = (hw.col[i].to_3d().normalized() for i in range(3))

        def build_palm(bm, hw=hw, hx=hx, hy=hy, hz=hz):
            c = hw.translation + hx * 0.048 + hy * 0.004
            frame = Matrix((hx, hy, hz)).transposed()
            _ellipsoid(bm, c, 0.046, 0.042, 0.017, frame=frame, seg=12, rings=6)
        parts.append(_part(f'ped_{s}_palm', build_palm, skin, arm, f'SKEL_{s}_Hand'))
        for f in range(5):
            chain = [f'SKEL_{s}_Finger{f}{j}' for j in range(3)]
            r = 0.0105 if f else 0.012
            for j, bn in enumerate(chain):
                a = P[bn]
                if j < 2:
                    b = P[chain[j + 1]]
                else:
                    b = a + W[bn].col[0].to_3d().normalized() * (0.022 if f else 0.026)
                parts.append(_part(f'ped_{bn}', lambda bm, a=a, b=b, r=r: _capsule(bm, a, b, r, r * 0.92, 8, 2),
                                   skin, arm, bn))

    for s in 'LR':
        hip, knee, ank, toe = (P[f'SKEL_{s}_{b}'] for b in ('Thigh', 'Calf', 'Foot', 'Toe0'))
        parts.append(_part(f'ped_{s}_thigh', lambda bm, a=hip, b=knee: _capsule(bm, a, b, 0.085, 0.060, 12, 3),
                           uniform, arm, f'SKEL_{s}_Thigh'))
        parts.append(_part(f'ped_{s}_calf', lambda bm, a=knee, b=ank: _capsule(bm, a, b, 0.058, 0.042, 12, 3),
                           uniform, arm, f'SKEL_{s}_Calf'))

        def build_boot(bm, ank=ank, toe=toe):
            fwd = (toe - ank)
            fwd.z = 0
            fwd.normalize()
            c = ank.lerp(toe, 0.45) + Vector((0, 0, -0.035))
            side = fwd.cross(Vector((0, 0, 1)))
            frame = Matrix((side, fwd, Vector((0, 0, 1)))).transposed()
            _ellipsoid(bm, c, 0.048, 0.135, 0.05, frame=frame, seg=12, rings=6)
        parts.append(_part(f'ped_{s}_boot', build_boot, boots, arm, f'SKEL_{s}_Foot'))
    return parts
