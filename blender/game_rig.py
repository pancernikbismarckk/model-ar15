"""Skeleton, bone-parented game meshes and animations of weapon_ar15_game (30 fps).

Bones follow the GTA V weapon convention where one exists (WAPClip, WAPScop, WAPGrip,
WAPFlshLasr, gun_root, gun_muzzle); moving parts get their own gun_* bones. Rigid parts are
parented to bones (no skinning), which is how GTA weapon drawables bind models to bones.

Actions (all start and end at rest unless noted):
    fire          one shot: trigger pull, carrier cycles 82 mm, dust cover pops open (stays open)
    fire_auto     looping carrier cycle at ~600 rpm (3 frames), trigger held, cover open
    fire_last     last round: carrier locks back on the bolt catch
    reload        magazine out and a fresh one in (bolt forward)
    reload_empty  from bolt locked back: magazine swap, bolt catch pressed, carrier slams home
    charge        charging handle pulled and released
    sights_fold   iron sights fold down (used when an optic is mounted)
    stock_extend  stock from position 1 to 6 (81.2 mm)
    shell_eject   (on the ar15_shell object) ejected case: flight path with tumble
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

import ar15lib as L
import parts_attachments as A

S = L.S
FPS = 30
ROOT_NAME = 'weapon_ar15'

EJECT_DIR = Vector((-0.34, -0.87, 0.36)).normalized()   # rearward, right, up

# bone, head (mm), parent, tail direction
BONES = [
    ('gun_root', (0.0, 0.0, 0.0), None, (1, 0, 0)),
    ('gun_bolt', (-196.0, 0.0, 0.0), 'gun_root', (1, 0, 0)),
    ('gun_chargehandle', (-198.0, 0.0, 25.0), 'gun_root', (1, 0, 0)),
    ('gun_trigger', (-118.0, 0.0, -37.8), 'gun_root', (0, 0, -1)),
    ('gun_dustcover', (-52.0, -14.7, -6.9), 'gun_root', (1, 0, 0)),
    ('gun_boltcatch', (-81.5, 14.25, -17.8), 'gun_root', (1, 0, 0)),
    ('gun_magrelease', (-82.0, -14.25, -36.0), 'gun_root', (0, -1, 0)),
    ('gun_selector', (-146.5, 0.0, -36.0), 'gun_root', (0, 1, 0)),
    ('gun_stock', (-212.5, 0.0, 0.0), 'gun_root', (-1, 0, 0)),
    ('gun_sight_rear', (-151.8, 0.0, 40.2), 'gun_root', (0, 0, 1)),
    ('gun_sight_front', (347.0, 0.0, 40.2), 'gun_root', (0, 0, 1)),
    ('WAPClip', (-44.0, 0.0, -16.5), 'gun_root', (0, 0, -1)),
    ('WAPScop', A.SOCKETS['socket_att_scope'], 'gun_root', (1, 0, 0)),
    ('WAPGrip', A.SOCKETS['socket_att_grip'], 'gun_root', (0, 0, -1)),
    ('WAPFlshLasr', A.SOCKETS['socket_att_flashlight'], 'gun_root', (0, -1, 0)),
    ('WAPLasr', A.SOCKETS['socket_att_laser'], 'gun_root', (0, 1, 0)),
    ('gun_light_emit', A.EMIT_SOCKETS['socket_light_emit'], 'WAPFlshLasr', (1, 0, 0)),
    ('gun_laser_emit', A.EMIT_SOCKETS['socket_laser_emit'], 'WAPLasr', (1, 0, 0)),
    ('gun_muzzle', (442.5, 0.0, 0.0), 'gun_root', (1, 0, 0)),
    ('gun_vfx_eject', (-52.0, -16.0, 5.0), 'gun_root', tuple(EJECT_DIR)),
]

PART_BONE = {
    'ar15_bolt_carrier': 'gun_bolt',
    'ar15_charging_handle': 'gun_chargehandle',
    'ar15_trigger': 'gun_trigger',
    'ar15_dust_cover': 'gun_dustcover',
    'ar15_bolt_catch': 'gun_boltcatch',
    'ar15_mag_release': 'gun_magrelease',
    'ar15_selector': 'gun_selector',
    'ar15_stock': 'gun_stock', 'ar15_buttpad': 'gun_stock', 'ar15_stock_lever': 'gun_stock',
    'ar15_rear_sight_leaf': 'gun_sight_rear',
    'ar15_front_sight_leaf': 'gun_sight_front',
    'ar15_magazine': 'WAPClip', 'ar15_magazine_lips': 'WAPClip',
    'ar15_cartridge_case': 'WAPClip', 'ar15_cartridge_bullet': 'WAPClip',
}
ATT_BONE = {'holo': 'WAPScop', 'foregrip': 'WAPGrip', 'flashlight': 'WAPFlshLasr', 'laser': 'WAPLasr'}
BONE_OBJECT = {
    'gun_root': 'ar15_body', 'gun_bolt': 'ar15_bolt_carrier', 'gun_chargehandle': 'ar15_charging_handle',
    'gun_trigger': 'ar15_trigger', 'gun_dustcover': 'ar15_dust_cover', 'gun_boltcatch': 'ar15_bolt_catch',
    'gun_magrelease': 'ar15_mag_release', 'gun_selector': 'ar15_selector', 'gun_stock': 'ar15_stock',
    'gun_sight_rear': 'ar15_rear_sight_leaf', 'gun_sight_front': 'ar15_front_sight_leaf',
    'WAPClip': 'ar15_magazine', 'WAPScop': 'ar15_att_holo', 'WAPGrip': 'ar15_att_foregrip',
    'WAPFlshLasr': 'ar15_att_flashlight', 'WAPLasr': 'ar15_att_laser',
}

SPECIAL_SUFFIX = {'ar15_glass': 'glass', 'ar15_reticle': 'reticle', 'ar15_chrome': 'reflector', 'ar15_led': 'led',
                  'ar15_lens_laser': 'lens', 'ar15_glass_dark': 'ir_window'}

# motion constants (mm / degrees)
BOLT_TRAVEL = 82.0
BOLT_LOCKED = 78.0
CH_TRAVEL = 70.0
TRIGGER_PULL = 12.0
COVER_OPEN = 106.0
CATCH_UP = -7.0
CATCH_PRESS = 6.0
MAGREL_PRESS = 3.0


# ---------------------------------------------------------------------------
def _select(objs, active):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def _join(objs, name):
    if len(objs) > 1:
        _select(objs, objs[0])
        bpy.ops.object.join()
    ob = objs[0]
    ob.name = name
    ob.data.name = name
    return ob


def build_armature(coll):
    arm_data = bpy.data.armatures.new(ROOT_NAME)
    arm = bpy.data.objects.new(ROOT_NAME, arm_data)
    coll.objects.link(arm)
    arm.show_in_front = True
    arm_data.display_type = 'STICK'
    _select([arm], arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    for name, head, parent, d in BONES:
        b = eb.new(name)
        h = Vector(head) * S
        b.head = h
        b.tail = h + Vector(d).normalized() * 0.02
        b.roll = 0.0
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    arm['weapon_name'] = ROOT_NAME
    arm['caliber'] = '5.56x45mm NATO'
    arm['fps'] = FPS
    return arm


def _parent_to_bone(ob, arm, bone):
    mw = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = mw


def _set_origin(ob, pivot):
    """Origin of a mesh object at pivot (world, metres) without moving the geometry."""
    ob.data.transform(Matrix.Translation(-(pivot - ob.matrix_world.translation)))
    ob.matrix_world = Matrix.Translation(pivot)


def assemble(coll, atts, arm):
    """Merge parts per bone (and per material kind) and bind them to the skeleton."""
    groups = {}
    att_of = {o: key for key, parts in atts.items() for o in parts}
    for ob in list(coll.objects):
        if ob.type != 'MESH' or ob.name == 'ar15_shell':
            continue
        bone = ATT_BONE[att_of[ob]] if ob in att_of else PART_BONE.get(ob.name, 'gun_root')
        mat = ob.material_slots[0].material.name if ob.material_slots else ''
        groups.setdefault((bone, mat), []).append(ob)
    heads = {name: Vector(head) * S for name, head, _p, _d in BONES}
    result = {}
    for (bone, mat), objs in sorted(groups.items()):
        base = BONE_OBJECT[bone]
        special = mat and not mat.startswith('ar15_game_')
        name = base if not special else f'{base}_{SPECIAL_SUFFIX.get(mat, mat.replace("ar15_", ""))}'
        ob = _join(objs, name)
        _set_origin(ob, heads[bone])
        _parent_to_bone(ob, arm, bone)
        result[name] = ob
    return result


def make_shell(coll):
    """Stand-alone ejected case (copy of the chambered-round case mesh)."""
    src = bpy.data.objects.get('ar15_cartridge_case')
    me = src.data.copy()
    me.name = 'ar15_shell'
    ob = bpy.data.objects.new('ar15_shell', me)
    coll.objects.link(ob)
    # the magazine's top round lies at x -73.6..-28.9, z -11; move it into the chamber/port area
    ob.matrix_world = Matrix.Translation(Vector((11.25, -6.0, 14.0)) * S)
    bpy.context.view_layer.update()
    c = sum((ob.matrix_world @ v.co for v in me.vertices), Vector()) / len(me.vertices)
    _set_origin(ob, c)
    return ob


# ---------------------------------------------------------------------------
# keyframing
# ---------------------------------------------------------------------------
def _delta(head, loc=(0.0, 0.0, 0.0), axis=None, deg=0.0):
    D = Matrix.Translation(Vector(loc) * S)
    if axis is not None and deg:
        D = D @ Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
    return D


def _key_bone(arm, bone, frame, loc=(0.0, 0.0, 0.0), axis=None, deg=0.0):
    pb = arm.pose.bones[bone]
    rest = arm.data.bones[bone].matrix_local
    D = _delta(rest.translation, loc, axis, deg)
    pb.matrix_basis = rest.inverted() @ D @ rest
    pb.keyframe_insert('location', frame=frame, group=bone)
    pb.keyframe_insert('rotation_quaternion', frame=frame, group=bone)


# per-bone motion: (translation axis vector or rotation axis letter)
MOTION = {
    'gun_bolt': ('T', (-1, 0, 0)),
    'gun_chargehandle': ('T', (-1, 0, 0)),
    'gun_trigger': ('R', 'Y'),
    'gun_dustcover': ('R', 'X'),
    'gun_boltcatch': ('R', 'Y'),
    'gun_magrelease': ('T', (0, 1, 0)),
    'gun_stock': ('T', (-1, 0, 0)),
    'gun_sight_rear': ('R', 'Y'),
    'gun_sight_front': ('R', 'Y'),
}


def _key(arm, bone, frame, value):
    kind, ax = MOTION[bone]
    if kind == 'T':
        _key_bone(arm, bone, frame, loc=tuple(a * value for a in ax))
    else:
        _key_bone(arm, bone, frame, axis=ax, deg=value)


def _key_mag(arm, frame, dx, dz, deg):
    _key_bone(arm, 'WAPClip', frame, loc=(dx, 0.0, dz), axis='Y', deg=deg)


def _track(arm, name, frames, keys, interp='LINEAR'):
    """Create an action from {bone: [(frame, value), ...]} and stash it on an NLA track."""
    bpy.context.preferences.edit.keyframe_new_interpolation_type = interp
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = act
    for bone, seq in keys.items():
        for f, v in seq:
            if bone == 'WAPClip':
                _key_mag(arm, f, *v)
            else:
                _key(arm, bone, f, v)
    act.frame_range = (0, frames)
    act['fps'] = FPS
    tr = arm.animation_data.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, 0, act)
    st.name = name
    tr.mute = True
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    return act


MAG_OUT_IN = [
    (0, (0, 0, 0)), (8, (0, 0, 0)), (10, (0, -8, 0)), (14, (-2, -45, -2)), (20, (-8, -160, -7)),
    (26, (-14, -320, -11)), (38, (-14, -320, -11)), (46, (-6, -120, -5)), (52, (-1, -20, -1)),
    (55, (0, 1.5, 0)), (57, (0, 0, 0)),
]


def make_actions(arm):
    acts = []
    B, D, T_, C, M = 'gun_bolt', 'gun_dustcover', 'gun_trigger', 'gun_boltcatch', 'gun_magrelease'
    acts.append(_track(arm, 'fire', 6, {
        T_: [(0, 0), (1, TRIGGER_PULL), (4, TRIGGER_PULL), (5, 0)],
        B: [(0, 0), (1, 40), (2, BOLT_TRAVEL), (3, 35), (4, 0)],
        D: [(0, 0), (1, 45), (2, COVER_OPEN), (6, COVER_OPEN)],
    }))
    acts.append(_track(arm, 'fire_auto', 3, {
        T_: [(0, TRIGGER_PULL), (3, TRIGGER_PULL)],
        B: [(0, 0), (1, BOLT_TRAVEL), (2, 30), (3, 0)],
        D: [(0, COVER_OPEN), (3, COVER_OPEN)],
    }))
    acts.append(_track(arm, 'fire_last', 6, {
        T_: [(0, 0), (1, TRIGGER_PULL), (4, TRIGGER_PULL), (5, 0)],
        B: [(0, 0), (1, 40), (2, BOLT_TRAVEL), (3, BOLT_LOCKED), (6, BOLT_LOCKED)],
        C: [(0, 0), (2, 0), (3, CATCH_UP), (6, CATCH_UP)],
        D: [(0, 0), (1, 45), (2, COVER_OPEN), (6, COVER_OPEN)],
    }))
    acts.append(_track(arm, 'reload', 72, {
        M: [(0, 0), (4, 0), (6, MAGREL_PRESS), (11, MAGREL_PRESS), (13, 0)],
        'WAPClip': MAG_OUT_IN + [(72, (0, 0, 0))],
    }, interp='BEZIER'))
    acts.append(_track(arm, 'reload_empty', 80, {
        M: [(0, 0), (4, 0), (6, MAGREL_PRESS), (11, MAGREL_PRESS), (13, 0)],
        'WAPClip': MAG_OUT_IN + [(80, (0, 0, 0))],
        B: [(0, BOLT_LOCKED), (62, BOLT_LOCKED), (64, 0), (80, 0)],
        C: [(0, CATCH_UP), (59, CATCH_UP), (61, CATCH_PRESS), (63, CATCH_PRESS), (66, 0), (80, 0)],
        D: [(0, COVER_OPEN), (80, COVER_OPEN)],
    }, interp='BEZIER'))
    acts.append(_track(arm, 'charge', 30, {
        'gun_chargehandle': [(0, 0), (4, 12), (9, CH_TRAVEL), (12, CH_TRAVEL), (14, 0), (30, 0)],
        B: [(0, 0), (4, 0), (9, CH_TRAVEL), (12, CH_TRAVEL), (14, 0), (30, 0)],
        D: [(0, 0), (5, 0), (7, COVER_OPEN), (30, COVER_OPEN)],
    }, interp='BEZIER'))
    acts.append(_track(arm, 'sights_fold', 12, {
        'gun_sight_rear': [(0, 0), (12, 90)],
        'gun_sight_front': [(0, 0), (12, -90)],
    }, interp='BEZIER'))
    acts.append(_track(arm, 'stock_extend', 20, {
        'gun_stock': [(0, 0), (20, 81.2)],
    }, interp='BEZIER'))
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'BEZIER'
    return acts


def make_shell_action(shell):
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    act = bpy.data.actions.new('shell_eject')
    act.use_fake_user = True
    shell.animation_data_create()
    shell.animation_data.action = act
    shell.rotation_mode = 'QUATERNION'
    p0 = shell.location.copy()
    v = EJECT_DIR * 3.9                       # m/s
    g = Vector((0.0, 0.0, -9.81))
    spin_axis = Vector((0.25, 0.35, 1.0)).normalized()
    for f in range(0, 19):
        t = f / FPS
        shell.location = p0 + v * t + g * (0.5 * t * t)
        shell.rotation_quaternion = Quaternion(spin_axis, 26.0 * t)
        shell.keyframe_insert('location', frame=f)
        shell.keyframe_insert('rotation_quaternion', frame=f)
    act.frame_range = (0, 18)
    tr = shell.animation_data.nla_tracks.new()
    tr.name = 'shell_eject'
    tr.strips.new('shell_eject', 0, act)
    tr.mute = True
    shell.animation_data.action = None
    shell.location = p0
    shell.rotation_quaternion = Quaternion()
    return act


def rig_and_animate(coll, atts):
    shell = make_shell(coll)
    arm = build_armature(coll)
    parts = assemble(coll, atts, arm)
    make_actions(arm)
    make_shell_action(shell)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 0, 80
    tris = {n: L.tri_count(o) for n, o in parts.items()}
    arm['tris_total'] = sum(tris.values())
    for n in sorted(tris):
        print(f'  {n:34s} {tris[n]:6d}')
    return arm


# ---------------------------------------------------------------------------
def export(arm, out_dir, name):
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, name + '.glb'), export_format='GLB',
                              export_image_format='JPEG', export_jpeg_quality=92, export_tangents=True,
                              export_yup=True, export_animations=True, export_animation_mode='ACTIONS',
                              export_force_sampling=True, export_frame_range=False, export_nla_strips=True,
                              use_selection=False)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, name + '.fbx'), use_selection=False,
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                             object_types={'ARMATURE', 'MESH', 'EMPTY'}, mesh_smooth_type='OFF',
                             use_custom_props=True, add_leaf_bones=False, bake_anim=True,
                             bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
                             bake_anim_force_startend_keying=True, path_mode='RELATIVE', use_tspace=True)
    print('exported', out_dir)
