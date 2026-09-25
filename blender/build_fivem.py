"""Build the GTA V / FiveM assets of weapon_ar15 from weapon_ar15_game.blend.

    python3 blender/build_fivem.py --sollumz <Sollumz addon dir> --cwconv <cwconv executable>

Needs bpy 5.0 (pip), Sollumz 2.9 with szio (PyPI), ImageMagick (DDS writer) and cwconv
(tools/cwconv: a small CodeWalker.Core console app that turns CodeWalker XML into .ydr/.ytd).

Writes
    fivem/weapon_ar15/stream/w_ar_ar15.ydr         weapon (skeleton, moving parts on their own bones)
    fivem/weapon_ar15/stream/w_ar_ar15_mag1.ydr    COMPONENT_AR15_CLIP_01 (default)
    fivem/weapon_ar15/stream/w_ar_ar15_sights.ydr  COMPONENT_AR15_SIGHTS (default, iron sights up)
    fivem/weapon_ar15/stream/w_at_ar15_holo.ydr    COMPONENT_AT_AR15_SCOPE_HOLO (holo + iron sights folded)
    fivem/weapon_ar15/stream/w_at_ar15_afgrip.ydr  COMPONENT_AT_AR15_AFGRIP
    fivem/weapon_ar15/stream/w_at_ar15_flsh.ydr    COMPONENT_AT_AR15_FLSH
    fivem/weapon_ar15/stream/w_at_ar15_laser.ydr   COMPONENT_AT_AR15_LASER
    fivem/weapon_ar15/stream/w_ar_ar15.ytd         shared texture dictionary
    fivem/weapon_ar15_sollumz.blend                the Sollumz scene, for editing in Blender

GTA conventions used (checked against the vanilla weapon bones shipped with Sollumz): the barrel
points +X, Z up, right side is -Y; weapon bone tags are ElfHash(NAME) % 0xFE8F + 0x170; the hand
holds the weapon at Gun_GripR, whose rotation is copied from a vanilla rifle so the barrel lines up
with the aim; attach bones (WAP*) and everything under Gun_Main_Bone are axis aligned. The iron
sights are a default component on WAPScop: fitting the holo replaces it, and the holo model carries
the folded sights, which is how the sights fold in game.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

import bpy  # noqa: F401  (bpy must be imported before bmesh/mathutils users)
import addon_utils
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_BLEND = os.path.join(ROOT, 'weapon_ar15_game.blend')
TEX_IN = os.path.join(ROOT, 'textures', 'game')
TEX_OUT = os.path.join(ROOT, 'textures', 'fivem')
BUILD = os.path.join(ROOT, 'build', 'fivem')
RESOURCE = os.path.join(ROOT, 'fivem', 'weapon_ar15')
STREAM = os.path.join(RESOURCE, 'stream')
SCENE_OUT = os.path.join(ROOT, 'fivem', 'weapon_ar15_sollumz.blend')

TXD = 'w_ar_ar15'
MM = 0.001

# ---------------------------------------------------------------------------
# skeleton (millimetres, weapon space)
# ---------------------------------------------------------------------------
# vanilla rifle: Gun_GripR sits at trigger pivot + (-91.5, -23.2, -55.9) mm, with this rotation
GRIP_R_ROT = Quaternion((0.7474004, 0.6578194, 0.00028754104, 0.093093015))   # (w, x, y, z)
TRIGGER_PIVOT = Vector((-118.0, 0.0, -37.8))
GRIP_R_POS = TRIGGER_PIVOT + Vector((-91.5, -23.2, -55.9))

LIGHT_EMIT = Vector((386.2, -47.4, 2.3))      # flashlight lens centre
LASER_EMIT = Vector((378.0, 36.5, 9.3))       # laser aperture

# (name, head mm, parent, rotation in weapon space or None for identity)
BONES = [
    ('gun_root', (0.0, 0.0, 0.0), None, None),
    ('Gun_GripR', tuple(GRIP_R_POS), 'gun_root', GRIP_R_ROT),
    ('Gun_Main_Bone', (0.0, 0.0, 0.0), 'Gun_GripR', None),
    ('Gun_Muzzle', (442.5, 0.0, 0.0), 'Gun_Main_Bone', Quaternion((0.0, 1.0, 0.0, 0.0))),       # 180 deg about X
    ('Gun_VFX_Eject', (-52.0, -16.0, 5.0), 'Gun_Main_Bone', Quaternion((0.7071068, 0.0, 0.0, -0.7071068))),  # X -> right
    ('Gun_GripL', (136.5, 0.0, -45.0), 'Gun_Main_Bone', None),     # support hand on the foregrip
    ('WAPClip', (-44.0, 0.0, -16.5), 'Gun_Main_Bone', None),
    ('WAPScop', (-61.8, 0.0, 31.6), 'Gun_Main_Bone', None),
    ('WAPGrip', (136.5, 0.0, -19.7), 'Gun_Main_Bone', None),
    ('WAPFlshLasr', tuple(LIGHT_EMIT), 'Gun_Main_Bone', None),
    ('WAPSupp_2', tuple(LASER_EMIT), 'Gun_Main_Bone', None),
    ('ar15_bolt', (-196.0, 0.0, 0.0), 'Gun_Main_Bone', None),
    ('ar15_chargehandle', (-198.0, 0.0, 25.0), 'Gun_Main_Bone', None),
    ('ar15_trigger', tuple(TRIGGER_PIVOT), 'Gun_Main_Bone', None),
    ('ar15_dustcover', (-52.0, -14.7, -6.9), 'Gun_Main_Bone', None),
    ('ar15_boltcatch', (-81.5, 14.25, -17.8), 'Gun_Main_Bone', None),
    ('ar15_magrelease', (-82.0, -14.25, -36.0), 'Gun_Main_Bone', None),
    ('ar15_selector', (-146.5, 0.0, -36.0), 'Gun_Main_Bone', None),
    ('ar15_stock', (-212.5, 0.0, 0.0), 'Gun_Main_Bone', None),
]
UNK0_BONES = {'gun_root', 'Gun_GripR', 'Gun_Main_Bone'}

# game mesh -> GTA bone of w_ar_ar15
WEAPON_PARTS = {
    'ar15_body': 'Gun_Main_Bone',
    'ar15_bolt_carrier': 'ar15_bolt',
    'ar15_charging_handle': 'ar15_chargehandle',
    'ar15_trigger': 'ar15_trigger',
    'ar15_dust_cover': 'ar15_dustcover',
    'ar15_bolt_catch': 'ar15_boltcatch',
    'ar15_mag_release': 'ar15_magrelease',
    'ar15_selector': 'ar15_selector',
    'ar15_stock': 'ar15_stock',
}

SIGHT_HINGES = {   # leaf: (hinge mm, fold angle about Y)
    'ar15_rear_sight_leaf': (Vector((-151.8, 0.0, 40.2)), 90.0),
    'ar15_front_sight_leaf': (Vector((347.0, 0.0, 40.2)), -90.0),
}

# component drawable: (weapon attach bone, component attach bone, [(mesh, folded)])
COMPONENTS = {
    'w_ar_ar15_mag1': ('WAPClip', 'AAPClip', [('ar15_magazine', False)]),
    'w_ar_ar15_sights': ('WAPScop', 'AAPScop', [('ar15_rear_sight_leaf', False), ('ar15_front_sight_leaf', False)]),
    'w_at_ar15_holo': ('WAPScop', 'AAPScop', [('ar15_att_holo', False), ('ar15_att_holo_glass', False),
                                               ('ar15_att_holo_reticle', False),
                                               ('ar15_rear_sight_leaf', True), ('ar15_front_sight_leaf', True)]),
    'w_at_ar15_afgrip': ('WAPGrip', 'AAPGrip', [('ar15_att_foregrip', False)]),
    'w_at_ar15_flsh': ('WAPFlshLasr', 'AAPFlsh', [('ar15_att_flashlight', False), ('ar15_att_flashlight_glass', False),
                                                  ('ar15_att_flashlight_reflector', False),
                                                  ('ar15_att_flashlight_led', False)]),
    'w_at_ar15_laser': ('WAPSupp_2', 'AAPFlsh', [('ar15_att_laser', False), ('ar15_att_laser_lens', False),
                                                  ('ar15_att_laser_ir_window', False)]),
}

# small parts share a 64 px palette texture: material -> (cell, GTA material)
MISC_CELLS = {
    'ar15_chrome': (0, 'misc'),
    'ar15_led': (1, 'misc'),
    'ar15_lens_laser': (2, 'misc'),
    'ar15_glass_dark': (3, 'misc'),
    'ar15_glass': (4, 'glass'),
    'ar15_reticle': (6, 'emissive'),
}
# cell: (sRGB colour, alpha, spec intensity, gloss)
PALETTE = {
    0: ((196, 198, 204), 255, 0.95, 0.92),   # reflector
    1: ((246, 242, 222), 255, 0.50, 0.80),   # LED
    2: ((150, 16, 12), 255, 0.85, 0.95),     # laser lens
    3: ((22, 22, 26), 255, 0.60, 0.90),      # IR window
    4: ((150, 186, 206), 64, 1.00, 0.97),    # glass (holo window, flashlight lens)
    6: ((255, 36, 24), 255, 0.00, 0.20),     # holo reticle (emissive)
}


# ---------------------------------------------------------------------------
# textures: PBR atlases -> GTA diffuse / normal / specular
# ---------------------------------------------------------------------------
def _load(path):
    return np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255.0


def _srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def _save(arr, path, size=None):
    mode = 'RGBA' if arr.shape[2] == 4 else 'RGB'
    img = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), mode)
    if size and img.size[0] != size:
        img = img.resize((size, size), Image.LANCZOS)
    img.save(path)
    return path


def _dds(png, fmt):
    dds = os.path.splitext(png)[0] + '.dds'
    # one thread: cluster fit is only deterministic single-threaded (reproducible .ytd)
    subprocess.run(['convert', '-limit', 'thread', '1', png, '-define', f'dds:compression={fmt}',
                    '-define', 'dds:cluster-fit=true', dds], check=True)
    return dds


def gta_textures(tex_dir):
    """Convert the baked PBR atlases. The base colour already carries the cavity AO; diffuse gets a
    touch more AO and slightly darker metal (GTA adds the metal's shine through the spec map), spec
    is grey intensity with gloss in alpha (specMapIntMask = R), normal maps get DirectX green."""
    os.makedirs(tex_dir, exist_ok=True)
    out = {}
    for group, key, sizes in (('weapon', 'ar15_weapon', (2048, 2048, 1024)),
                              ('attachments', 'ar15_att', (1024, 1024, 512))):
        base = _load(os.path.join(TEX_IN, f'ar15_game_{group}_basecolor.png'))
        orm = _load(os.path.join(TEX_IN, f'ar15_game_{group}_orm.png'))
        nrm = _load(os.path.join(TEX_IN, f'ar15_game_{group}_normal.png'))
        ao, rough, metal = orm[..., 0], orm[..., 1], orm[..., 2]
        lin = _srgb_to_lin(base) * ((1.0 - 0.22 * metal) * (0.75 + 0.25 * ao))[..., None]
        diffuse = _lin_to_srgb(lin)
        spec = np.clip((0.12 + 0.6 * metal) * (1.0 - rough) ** 0.7 * (0.6 + 0.4 * ao), 0.0, 1.0)
        gloss = np.clip(1.0 - rough, 0.0, 1.0)
        specmap = np.stack([spec, spec, spec, gloss], -1)
        nrm[..., 1] = 1.0 - nrm[..., 1]
        out[key + '_d'] = _save(diffuse, os.path.join(tex_dir, key + '_d.png'), sizes[0])
        out[key + '_n'] = _save(nrm, os.path.join(tex_dir, key + '_n.png'), sizes[1])
        out[key + '_s'] = _save(specmap, os.path.join(tex_dir, key + '_s.png'), sizes[2])
    d = np.full((64, 64, 4), 0.5, np.float32)
    s = np.zeros((64, 64, 4), np.float32)
    for cell, (rgb, a, si, gl) in PALETTE.items():
        cy, cx = divmod(cell, 4)
        d[cy * 16:(cy + 1) * 16, cx * 16:(cx + 1) * 16] = [c / 255 for c in rgb] + [a / 255]
        s[cy * 16:(cy + 1) * 16, cx * 16:(cx + 1) * 16] = [si, si, si, gl]
    n = np.zeros((64, 64, 3), np.float32) + [0.5, 0.5, 1.0]
    out['ar15_misc_d'] = _save(d, os.path.join(tex_dir, 'ar15_misc_d.png'))
    out['ar15_misc_n'] = _save(n, os.path.join(tex_dir, 'ar15_misc_n.png'))
    out['ar15_misc_s'] = _save(s, os.path.join(tex_dir, 'ar15_misc_s.png'))
    return out


def write_ytd(pngs, xml_dir):
    """Compress to DDS and write the CodeWalker texture dictionary XML."""
    folder = os.path.join(xml_dir, TXD)
    os.makedirs(folder, exist_ok=True)
    root = ET.Element('TextureDictionary')
    for name, png in sorted(pngs.items()):
        alpha = name.endswith('_s') or name == 'ar15_misc_d'
        dds = _dds(png, 'dxt5' if alpha else 'dxt1')
        shutil.move(dds, os.path.join(folder, name + '.dds'))
        with open(os.path.join(folder, name + '.dds'), 'rb') as f:
            hdr = f.read(128)
        h, w, _pitch, _depth, mips = struct.unpack('<5I', hdr[12:32])
        it = ET.SubElement(root, 'Item')
        ET.SubElement(it, 'Name').text = name
        ET.SubElement(it, 'Unk32', value='0')
        ET.SubElement(it, 'Usage').text = {'d': 'DIFFUSE', 'n': 'NORMAL', 's': 'SPECULAR'}[name[-1]]
        ET.SubElement(it, 'UsageFlags').text = '0'
        ET.SubElement(it, 'ExtraFlags', value='0')
        ET.SubElement(it, 'Width', value=str(w))
        ET.SubElement(it, 'Height', value=str(h))
        ET.SubElement(it, 'MipLevels', value=str(max(1, mips)))
        ET.SubElement(it, 'Format').text = 'D3DFMT_DXT5' if alpha else 'D3DFMT_DXT1'
        ET.SubElement(it, 'FileName').text = name + '.dds'
    ET.indent(root)
    path = os.path.join(xml_dir, TXD + '.ytd.xml')
    ET.ElementTree(root).write(path, encoding='UTF-8', xml_declaration=True)
    return path


# ---------------------------------------------------------------------------
# Sollumz scene
# ---------------------------------------------------------------------------
def elf_tag(name):
    h = 0
    for c in name.upper().encode():
        h = ((h << 4) + c) & 0xFFFFFFFF
        x = h & 0xF0000000
        if x:
            h ^= x >> 24
        h &= ~x & 0xFFFFFFFF
    return h % 0xFE8F + 0x170


def enable_sollumz(path):
    addons = bpy.utils.user_resource('SCRIPTS', path='addons', create=True)
    link = os.path.join(addons, 'Sollumz')
    if not os.path.exists(link):
        os.symlink(os.path.abspath(path), link)
    addon_utils.enable('Sollumz', default_set=True, handle_error=None)


def sz_material(name, shader, textures, params):
    from Sollumz.ydr.shader_materials import create_shader
    mat = create_shader(shader)
    mat.name = name
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.name in textures:
            img = bpy.data.images.load(textures[node.name], check_existing=True)
            if node.name != 'DiffuseSampler':
                img.colorspace_settings.name = 'Non-Color'
            node.image = img
        elif node.name in params:
            v = params[node.name]
            v = v if isinstance(v, (tuple, list)) else (v,)
            for i, x in enumerate(v):
                node.set(i, x)
    return mat


def make_materials(pngs):
    tex = lambda k: {'DiffuseSampler': pngs[k + '_d'], 'BumpSampler': pngs[k + '_n'], 'SpecSampler': pngs[k + '_s']}
    spec = {'bumpiness': 1.0, 'specularIntensityMult': 1.0, 'specularFalloffMult': 100.0,
            'specularFresnel': 0.97, 'specMapIntMask': (1.0, 0.0, 0.0)}
    return {
        'weapon': sz_material('ar15_weapon', 'normal_spec.sps', tex('ar15_weapon'), spec),
        'att': sz_material('ar15_att', 'normal_spec.sps', tex('ar15_att'), spec),
        'misc': sz_material('ar15_misc', 'normal_spec.sps', tex('ar15_misc'), spec),
        'glass': sz_material('ar15_glass', 'weapon_normal_spec_alpha.sps', tex('ar15_misc'),
                             dict(spec, specularFalloffMult=200.0)),
        'emissive': sz_material('ar15_reticle', 'weapon_emissivestrong_alpha.sps',
                                {'DiffuseSampler': pngs['ar15_misc_d']}, {'emissiveMultiplier': 6.0}),
    }


def world_mesh(src, matrix):
    """Evaluated copy of ``src`` with ``matrix`` applied, with Sollumz attribute names."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(matrix)
    if me.uv_layers:
        me.uv_layers[0].name = 'UVMap 0'
    else:
        me.uv_layers.new(name='UVMap 0')
    col = me.color_attributes.new('Color 1', 'BYTE_COLOR', 'CORNER')
    col.data.foreach_set('color_srgb', [1.0] * (4 * len(me.loops)))
    return me


def assign(me, mats, src_mat_name):
    """Swap the game material for its Sollumz material; palette parts get UVs on their colour cell."""
    me.materials.clear()
    if src_mat_name == 'ar15_game_weapon':
        me.materials.append(mats['weapon'])
    elif src_mat_name == 'ar15_game_attachments':
        me.materials.append(mats['att'])
    else:
        cell, kind = MISC_CELLS[src_mat_name]
        me.materials.append(mats[kind])
        cy, cx = divmod(cell, 4)
        u, v = (cx * 16 + 8) / 64.0, 1.0 - (cy * 16 + 8) / 64.0
        me.uv_layers['UVMap 0'].data.foreach_set('uv', [u, v] * len(me.loops))


def model_obj(name, me, parent):
    from Sollumz.sollumz_properties import LODLevel, SollumType
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.sollum_type = SollumType.DRAWABLE_MODEL
    ob.sz_lods.get_lod(LODLevel.HIGH).mesh = me
    ob.sz_lods.active_lod_level = LODLevel.HIGH
    return ob


def armature_drawable(name, bones, origin=Vector()):
    """Armature object flagged as a Sollumz drawable. ``bones`` = [(name, head mm, parent, rot)]."""
    from Sollumz.sollumz_properties import SollumType
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = origin
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    ebs = {}
    for bname, head, parent, rot in bones:
        eb = arm.edit_bones.new(bname)
        eb.head, eb.tail = (0.0, 0.0, 0.0), (0.0, 0.02, 0.0)   # needs a length before the matrix is set
        m = (rot.to_matrix().to_4x4() if rot is not None else Matrix.Identity(4))
        m.translation = Vector(head) * MM - origin
        eb.matrix = m
        if parent:
            eb.parent = ebs[parent]
        ebs[bname] = eb
    bpy.ops.object.mode_set(mode='OBJECT')
    for b in arm.bones:
        b.bone_properties.tag = 0 if b.parent is None else elf_tag(b.name)
        b.bone_properties.flags.clear()
        for f in ('RotX', 'RotY', 'RotZ', 'TransX', 'TransY', 'TransZ') + (('Unk0',) if b.name in UNK0_BONES else ()):
            b.bone_properties.flags.add().name = f
    ob.sollum_type = SollumType.DRAWABLE
    return ob


def bind(ob, arm, bone):
    """Rigid model on ``bone`` (Sollumz uses a copy-transforms constraint). The mesh is in armature
    space; the inverse rest matrix makes the evaluated object sit exactly on the armature, which is
    what Sollumz expects when it moves the vertices into bone space on export."""
    from Sollumz.tools.blenderhelper import add_child_of_bone_constraint
    add_child_of_bone_constraint(ob, arm, bone)
    ob.matrix_basis = arm.data.bones[bone].matrix_local.inverted()


def add_bound(drawable, lo, hi):
    """Single box collision (used when the weapon lies on the ground as a pickup)."""
    from Sollumz.sollumz_properties import SollumType
    from Sollumz.tools.blenderhelper import create_blender_object, create_empty_object
    from Sollumz.tools.meshhelper import create_box_from_extents
    comp = create_empty_object(SollumType.BOUND_COMPOSITE)
    comp.name = drawable.name + '_col'
    comp.parent = drawable
    box = create_blender_object(SollumType.BOUND_BOX)
    box.name = drawable.name + '_col_box'
    box.parent = comp
    create_box_from_extents(box.data, Vector(lo) * MM, Vector(hi) * MM)
    from Sollumz.ybn.collision_materials import collisionmats, create_collision_material_from_index
    box.data.materials.append(create_collision_material_from_index(
        next(i for i, m in enumerate(collisionmats) if m.name == 'METAL_HOLLOW_SMALL')))
    for flag in ('object',):
        setattr(box.composite_flags1, flag, True)
    for flag in ('map_weapon', 'map_dynamic', 'map_animal', 'map_cover', 'map_vehicle', 'vehicle_not_bvh',
                 'vehicle_bvh', 'ped', 'ragdoll', 'animal', 'animal_ragdoll', 'object', 'plant', 'projectile',
                 'explosion', 'forklift_forks', 'test_weapon', 'test_camera', 'test_ai', 'test_script',
                 'test_vehicle_wheel', 'glass'):
        setattr(box.composite_flags2, flag, True)
    return comp


def build_scene(pngs):
    bpy.ops.wm.open_mainfile(filepath=GAME_BLEND)
    game_arm = bpy.data.objects['weapon_ar15']
    game_arm.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    src = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
    rest = {n: o.matrix_world.copy() for n, o in src.items()}
    mats = make_materials(pngs)

    new_objs = []
    # weapon
    arm = armature_drawable('w_ar_ar15', BONES)
    for part, bone in WEAPON_PARTS.items():
        me = world_mesh(src[part], arm.matrix_world.inverted() @ rest[part])
        assign(me, mats, src[part].data.materials[0].name)
        ob = model_obj(part, me, arm)
        bind(ob, arm, bone)
        new_objs.append(ob)
    add_bound(arm, (-384.0, -27.0, -146.0), (442.5, 27.0, 46.0))

    # components: gun_root -> AAPxxx at the weapon attach bone, meshes rigid on gun_root
    heads = {b[0]: Vector(b[1]) for b in BONES}
    for comp, (wap, aap, parts) in COMPONENTS.items():
        origin = heads[wap] * MM
        carm = armature_drawable(comp, [('gun_root', tuple(heads[wap]), None, None),
                                        (aap, tuple(heads[wap]), 'gun_root', None)], origin=origin)
        for part, folded in parts:
            m = rest[part]
            if folded:
                hinge, deg = SIGHT_HINGES[part]
                h = hinge * MM
                m = Matrix.Translation(h) @ Matrix.Rotation(np.radians(deg), 4, 'Y') @ Matrix.Translation(-h) @ m
            me = world_mesh(src[part], carm.matrix_world.inverted() @ m)
            assign(me, mats, src[part].data.materials[0].name)
            ob = model_obj(f'{comp}__{part}', me, carm)
            bind(ob, carm, 'gun_root')

    # drop the game rig, keep only the Sollumz drawables
    keep = {o for o in bpy.data.objects if o.sollum_type != 'sollumz_none'}
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    bpy.data.orphans_purge(do_recursive=True)
    return [o for o in bpy.data.objects if o.sollum_type == 'sollumz_drawable']


def export_xml(xml_dir):
    os.makedirs(xml_dir, exist_ok=True)
    res = bpy.ops.sollumz.export_assets(directory=xml_dir + os.sep, direct_export=True, use_custom_settings=True,
                                        target_formats={'CWXML'}, target_versions={'GEN8'},
                                        limit_to_selected=False, apply_transforms=False)
    print('sollumz export:', res)


def to_binary(cwconv, xml_dir):
    os.makedirs(STREAM, exist_ok=True)
    for fn in sorted(os.listdir(xml_dir)):
        if fn.endswith(('.ydr.xml', '.ytd.xml')):
            subprocess.run([cwconv, 'xml2bin', os.path.join(xml_dir, fn), STREAM], check=True)
    for fn in sorted(os.listdir(STREAM)):
        subprocess.run([cwconv, 'check', os.path.join(STREAM, fn)], check=True)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--sollumz', required=True, help='Sollumz addon directory (git clone of Sollumz/Sollumz)')
    ap.add_argument('--cwconv', required=True, help='cwconv executable (tools/cwconv)')
    a = ap.parse_args(args)

    tex_dir = TEX_OUT
    xml_dir = os.path.join(BUILD, 'xml')
    shutil.rmtree(xml_dir, ignore_errors=True)
    pngs = gta_textures(tex_dir)
    write_ytd(pngs, xml_dir)

    enable_sollumz(a.sollumz)
    drawables = build_scene(pngs)
    print('drawables:', [d.name for d in drawables])
    export_xml(xml_dir)
    os.makedirs(os.path.dirname(SCENE_OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT, compress=True)   # texture paths are absolute here
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    to_binary(a.cwconv, xml_dir)


if __name__ == '__main__':
    main()
