"""Game-ready weapon_ar15 for FiveM / GTA V: < 10k triangles, baked textures, skeleton, animations.

    python3 blender/build_game.py [--size 2048] [--att-size 1024] [--samples 4]

Input : weapon_ar15.blend (high-poly source with its baked textures: build_weapon_ar15.py,
        then texture_bake.py).
Output: weapon_ar15_game.blend, export/game/weapon_ar15_game.{fbx,glb}, textures/game/*.png

The game mesh is built by the same part builders in low-detail mode (ar15lib.set_lod): fewer
segments, no micro-bevels, small details left out. Everything the high-poly has (edge rounding,
knurling, screws, stipple, wear, the omitted small parts) is baked onto the low-poly mesh from the
high-poly (selected-to-active: base colour, ORM and tangent-space normal map).
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402  (bpy first: it provides bmesh)
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import ar15lib as L  # noqa: E402
import build_weapon_ar15 as BW  # noqa: E402
import game_rig as G  # noqa: E402
import parts_attachments as A  # noqa: E402
import parts_front as F  # noqa: E402
import parts_misc as X  # noqa: E402
import parts_rear as B  # noqa: E402
import parts_receivers as R  # noqa: E402
import texture_bake as T  # noqa: E402

GAME = 'weapon_ar15_game'
TEX_DIR = os.path.join(ROOT, 'textures', 'game')
EXP_DIR = os.path.join(ROOT, 'export', 'game')
SUFFIX = '__lod'

WEAPON_PARTS = [R.upper_receiver, R.dust_cover, R.forward_assist, R.charging_handle, R.bolt_carrier,
                R.lower_receiver, R.trigger_guard, R.trigger, R.pins, R.selector, R.mag_release, R.bolt_catch,
                F.barrel, F.handguard, F.flash_hider,
                B.buffer_tube, B.castle_nut, B.end_plate, B.stock, B.buttpad, B.stock_lever, B.pistol_grip,
                X.magazine, X.magazine_top, X.cartridge, X.rear_sight, X.front_sight]
ATTACHMENTS = [('holo', A.holo_sight), ('foregrip', A.foregrip), ('flashlight', A.flashlight),
               ('laser', A.laser)]
DROP = {'ar15_crush_washer'}          # too small for the game mesh (baked)

# relative texel density in the game atlas
UV_WEIGHT = {'ar15_barrel': 0.45, 'ar15_bolt_carrier': 0.5, 'ar15_cartridge_case': 0.5,
             'ar15_cartridge_bullet': 0.5, 'ar15_magazine_lips': 0.5, 'ar15_pistol_grip': 1.25,
             'ar15_trigger': 1.2, 'ar15_rear_sight_leaf': 1.15, 'ar15_front_sight_leaf': 1.15}


def base_name(ob):
    n = ob.name
    return n[:-len(SUFFIX)] if n.endswith(SUFFIX) else n


def is_special(ob):
    return all(s.material is not None and s.material.name in T.SPECIAL for s in ob.material_slots)


# ---------------------------------------------------------------------------
# 1. low-poly parts
# ---------------------------------------------------------------------------
def build_lod(coll):
    L.set_collection(coll)
    L.set_lod(True, SUFFIX)
    M = BW.materials()
    weapon, atts = [], {}
    for fn in WEAPON_PARTS:
        res = fn(M)
        for ob in (res if isinstance(res, (list, tuple)) else (res,)):
            if base_name(ob) in DROP:
                me = ob.data
                bpy.data.objects.remove(ob)
                bpy.data.meshes.remove(me)
                continue
            weapon.append(ob)
    for key, fn in ATTACHMENTS:
        atts[key] = list(fn(M))
    L.set_lod(False)
    # triangles only: the baked tangent space then matches what the game and the exporters use
    for ob in weapon + [o for parts in atts.values() for o in parts]:
        m = ob.modifiers.new('tri', 'TRIANGULATE')
        m.quad_method = 'BEAUTY'
        m.ngon_method = 'BEAUTY'
        m.keep_custom_normals = True
        L.apply_mods(ob)
    return weapon, atts


def report(title, objs):
    n = sum(L.tri_count(o) for o in objs)
    print(f'{title}: {len(objs)} objects, {n} triangles')
    return n


# ---------------------------------------------------------------------------
# 2. high -> low bake
# ---------------------------------------------------------------------------
def _join_copies(objs, name):
    """World-space copy of several meshes joined into one bake target (UVs and normals kept)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for o in objs:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _prefill(img, rgba):
    w, h = img.size
    img.pixels.foreach_set(np.tile(np.array(rgba, dtype=np.float32), w * h))


def _emit_route(mat, source):
    """Make an atlas material emit one of its textures (for EMIT bakes); source=None restores it."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial')
    bsdf = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    emi = nt.nodes.get('__bake_emit') or nt.nodes.new('ShaderNodeEmission')
    emi.name = '__bake_emit'
    for l in list(out.inputs['Surface'].links):
        nt.links.remove(l)
    if source is None:
        nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
        return
    tex = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeTexImage' and n.image is not None
               and n.image.name.endswith('_' + source))
    for l in list(emi.inputs['Color'].links):
        nt.links.remove(l)
    nt.links.new(tex.outputs['Color'], emi.inputs['Color'])
    nt.links.new(emi.outputs[0], out.inputs['Surface'])


def bake_group(group, lod_objs, hp_objs, size, samples):
    t0 = time.time()
    print(f'== bake {group}: {len(lod_objs)} low-poly <- {len(hp_objs)} high-poly, {size}px')
    saved = dict(T.UV_WEIGHT)
    T.UV_WEIGHT.clear()
    T.UV_WEIGHT.update({o.name: UV_WEIGHT.get(base_name(o), 1.0) for o in lod_objs})
    T.atlas_unwrap(lod_objs, margin=0.004)
    T.UV_WEIGHT.clear()
    T.UV_WEIGHT.update(saved)

    target = _join_copies(lod_objs, '_bake_target')
    imgs = {
        'basecolor': T.new_image(f'{group}_basecolor', size, False),
        'orm': T.new_image(f'{group}_orm', size, True),
        'normal': T.new_image(f'{group}_normal', size, True),
    }
    _prefill(imgs['basecolor'], (0.02, 0.02, 0.021, 1.0))
    _prefill(imgs['orm'], (1.0, 0.6, 0.2, 1.0))
    _prefill(imgs['normal'], (0.5, 0.5, 1.0, 1.0))

    bake_mat = bpy.data.materials.new('_bake_target_mat')
    bake_mat.use_nodes = True
    img_node = bake_mat.node_tree.nodes.new('ShaderNodeTexImage')
    bake_mat.node_tree.nodes.active = img_node
    target.data.materials.clear()
    target.data.materials.append(bake_mat)

    hp_mats = {s.material for o in hp_objs for s in o.material_slots if s.material}
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.cage_extrusion = 0.0025
    bk.max_ray_distance = 0.006
    bk.margin = max(8, size // 128)
    bk.margin_type = 'EXTEND'
    bk.use_clear = False

    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in hp_objs:
        o.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target

    for key in ('basecolor', 'orm', 'normal'):
        img_node.image = imgs[key]
        t = time.time()
        if key == 'normal':
            for m in hp_mats:
                _emit_route(m, None)
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
        else:
            for m in hp_mats:
                _emit_route(m, key)
            bpy.ops.object.bake(type='EMIT')
        print(f'   {key}: {time.time() - t:.1f}s')
    for m in hp_mats:
        _emit_route(m, None)

    os.makedirs(TEX_DIR, exist_ok=True)
    for key, img in imgs.items():
        img.filepath_raw = os.path.join(TEX_DIR, f'{group}_{key}.png')
        img.file_format = 'PNG'
        img.save()
        img.filepath = f'//textures/game/{group}_{key}.png'

    # game material
    mat = bpy.data.materials.new(group)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    tb = nt.nodes.new('ShaderNodeTexImage')
    tb.image = imgs['basecolor']
    to = nt.nodes.new('ShaderNodeTexImage')
    to.image = imgs['orm']
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = imgs['normal']
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tb.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(to.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
    nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    for o in lod_objs:
        o.data.materials.clear()
        o.data.materials.append(mat)

    me = target.data
    bpy.data.objects.remove(target)
    bpy.data.meshes.remove(me)
    bpy.data.materials.remove(bake_mat)
    print(f'   done in {time.time() - t0:.1f}s')
    return mat


# ---------------------------------------------------------------------------
# 3. clean-up: drop the high-poly, keep the game mesh
# ---------------------------------------------------------------------------
def drop_high_poly(game_coll):
    keep = set(game_coll.all_objects)
    for ob in list(bpy.data.objects):
        if ob not in keep:
            bpy.data.objects.remove(ob)
    for coll in list(bpy.data.collections):
        if coll is not game_coll:
            bpy.data.collections.remove(coll)
    for m in bpy.data.materials:
        m.use_fake_user = False
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    for ob in game_coll.all_objects:
        if ob.name.endswith(SUFFIX):
            ob.name = ob.name[:-len(SUFFIX)]
            if ob.data is not None:
                ob.data.name = ob.name


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, default=2048)
    ap.add_argument('--att-size', type=int, default=1024)
    ap.add_argument('--samples', type=int, default=4)
    ap.add_argument('--skip-bake', action='store_true')
    args = ap.parse_args(argv)

    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'))
    hp_all = [o for o in bpy.data.objects if o.type == 'MESH']

    def hp_is_att(o):
        p = o.parent
        return p is not None and p.name.startswith('ar15_att_')

    hp_weapon = [o for o in hp_all if not hp_is_att(o) and not is_special(o)]
    hp_atts = [o for o in hp_all if hp_is_att(o) and not is_special(o)]

    coll = bpy.data.collections.new(GAME)
    bpy.context.scene.collection.children.link(coll)
    weapon, atts = build_lod(coll)
    att_objs = [o for parts in atts.values() for o in parts]
    n_w = report('rifle (incl. magazine)', weapon)
    n_a = report('attachments', att_objs)
    print(f'TOTAL {n_w + n_a} triangles')

    if not args.skip_bake:
        bake_group('ar15_game_weapon', [o for o in weapon if not is_special(o)], hp_weapon, args.size,
                   args.samples)
        bake_group('ar15_game_attachments', [o for o in att_objs if not is_special(o)], hp_atts,
                   args.att_size, args.samples)
    drop_high_poly(coll)

    rig = G.rig_and_animate(coll, atts)
    out = os.path.join(ROOT, f'{GAME}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('saved', out)
    G.export(rig, EXP_DIR, GAME)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
