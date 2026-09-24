"""Procedural build of weapon_ar15 in Blender.

Usage (Blender as a Python module, `pip install bpy`):
    python3 blender/build_weapon_ar15.py --save --export [--preview quick|beauty|match]

or with a Blender install:
    blender -b -P blender/build_weapon_ar15.py -- --save --export
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import ar15lib as L  # noqa: E402
import parts_front as F  # noqa: E402
import parts_misc as X  # noqa: E402
import parts_rear as B  # noqa: E402
import parts_receivers as R  # noqa: E402

WEAPON = 'weapon_ar15'


def materials():
    return {
        'alu': L.material('ar15_aluminum_anodized', (0.030, 0.030, 0.032), metallic=0.55, roughness=0.42),
        'steel': L.material('ar15_steel_phosphate', (0.038, 0.038, 0.038), metallic=0.75, roughness=0.48),
        'polymer': L.material('ar15_polymer', (0.040, 0.040, 0.041), metallic=0.0, roughness=0.62),
        'checker': L.checkered_material('ar15_polymer_checkered', (0.040, 0.040, 0.041), roughness=0.7),
        'rubber': L.material('ar15_rubber', (0.030, 0.030, 0.030), metallic=0.0, roughness=0.85),
        'brass': L.material('ar15_brass', (0.80, 0.56, 0.26), metallic=1.0, roughness=0.3),
        'copper': L.material('ar15_copper', (0.78, 0.40, 0.24), metallic=1.0, roughness=0.32),
    }


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = 'MILLIMETERS'
    coll = bpy.data.collections.new(WEAPON)
    sc.collection.children.link(coll)
    L.set_collection(coll)
    return coll


def build():
    M = materials()
    obs = {}
    t0 = time.time()

    def add(fn, *a):
        t = time.time()
        res = fn(M, *a)
        for ob in (res if isinstance(res, tuple) else (res,)):
            obs[ob.name] = ob
            print(f'  {ob.name:30s} {L.tri_count(ob):7d} tris')
        print(f'    ({fn.__name__}: {time.time() - t:.1f}s)')

    # receivers
    for fn in (R.upper_receiver, R.dust_cover, R.forward_assist, R.charging_handle, R.bolt_carrier,
               R.lower_receiver, R.trigger_guard, R.trigger, R.pins, R.selector, R.mag_release, R.bolt_catch):
        add(fn)
    # barrel, gas system, handguard, muzzle
    for fn in (F.barrel, F.barrel_nut, F.gas_block, F.gas_tube, F.handguard, F.handguard_hardware,
               F.flash_hider):
        add(fn)
    # buttstock group and grip
    for fn in (B.buffer_tube, B.castle_nut, B.end_plate, B.stock, B.buttpad, B.stock_lever, B.stock_qd,
               B.pistol_grip):
        add(fn)
    # magazine and sights
    for fn in (X.magazine, X.magazine_top, X.cartridge, X.rear_sight, X.front_sight):
        add(fn)
    print(f'built {len(obs)} objects in {time.time() - t0:.1f}s, '
          f'{sum(L.tri_count(o) for o in obs.values())} tris')
    return obs


# pivot (origin) of every part, in mm; parts that move in animations get their real pivot
PIVOTS = {
    'ar15_upper_receiver': (-4.2, 0.0, -19.5),          # front pivot pin
    'ar15_lower_receiver': (0.0, 0.0, 0.0),
    'ar15_dust_cover': (-52.0, -14.7, -6.9),            # hinge rod
    'ar15_forward_assist': (-189.0, -19.6, 6.0),
    'ar15_charging_handle': (-198.0, 0.0, 25.0),        # slides along -X
    'ar15_bolt_carrier': (-196.0, 0.0, 0.0),            # slides along -X when cycling
    'ar15_trigger': (-118.0, 0.0, -37.8),               # trigger pin
    'ar15_trigger_guard': (-131.0, 0.0, -76.2),         # rear roll pin
    'ar15_selector': (-146.5, 0.0, -36.0),
    'ar15_mag_release': (-82.0, 0.0, -36.0),
    'ar15_bolt_catch': (-81.5, 0.0, -17.8),
    'ar15_pins': (0.0, 0.0, 0.0),
    'ar15_barrel': (0.0, 0.0, 0.0),
    'ar15_barrel_nut': (0.0, 0.0, 0.0),
    'ar15_gas_block': (F.GAS_PORT_X, 0.0, 0.0),
    'ar15_gas_tube': (0.0, 0.0, 13.3),
    'ar15_handguard': (0.0, 0.0, 0.0),
    'ar15_handguard_hardware': (0.0, 0.0, 0.0),
    'ar15_flash_hider': (F.FH_X0, 0.0, 0.0),
    'ar15_crush_washer': (F.FH_X0, 0.0, 0.0),
    'ar15_buffer_tube': (B.TUBE_X0, 0.0, 0.0),
    'ar15_castle_nut': (-204.0, 0.0, 0.0),
    'ar15_end_plate': (-198.0, 0.0, 0.0),
    'ar15_stock': (B.STOCK_FRONT_X, 0.0, 0.0),          # slides 81.2 mm along -X
    'ar15_buttpad': (B.STOCK_FRONT_X, 0.0, 0.0),
    'ar15_stock_lever': (-291.0, 0.0, -24.8),
    'ar15_stock_qd': (-356.5, 0.0, -40.0),
    'ar15_pistol_grip': (-172.0, 0.0, -49.0),
    'ar15_magazine': (-44.0, 0.0, -16.5),
    'ar15_magazine_lips': (-44.0, 0.0, -16.5),
    'ar15_cartridge_case': (-73.6, 0.0, -11.0),
    'ar15_cartridge_bullet': (-73.6, 0.0, -11.0),
    'ar15_rear_sight_base': (-152.5, 0.0, 31.6),
    'ar15_rear_sight_leaf': (-151.8, 0.0, 39.5),        # folding axis (Y)
    'ar15_front_sight_base': (357.0, 0.0, 31.6),
    'ar15_front_sight_leaf': (347.0, 0.0, 39.5),        # folding axis (Y)
}

HIERARCHY = {
    'ar15_lower_receiver': None,
    'ar15_upper_receiver': 'ar15_lower_receiver',
    'ar15_trigger': 'ar15_lower_receiver',
    'ar15_trigger_guard': 'ar15_lower_receiver',
    'ar15_selector': 'ar15_lower_receiver',
    'ar15_mag_release': 'ar15_lower_receiver',
    'ar15_bolt_catch': 'ar15_lower_receiver',
    'ar15_pins': 'ar15_lower_receiver',
    'ar15_pistol_grip': 'ar15_lower_receiver',
    'ar15_buffer_tube': 'ar15_lower_receiver',
    'ar15_castle_nut': 'ar15_buffer_tube',
    'ar15_end_plate': 'ar15_buffer_tube',
    'ar15_stock': 'ar15_buffer_tube',
    'ar15_buttpad': 'ar15_stock',
    'ar15_stock_lever': 'ar15_stock',
    'ar15_stock_qd': 'ar15_stock',
    'ar15_magazine': 'ar15_lower_receiver',
    'ar15_magazine_lips': 'ar15_magazine',
    'ar15_cartridge_case': 'ar15_magazine',
    'ar15_cartridge_bullet': 'ar15_magazine',
    'ar15_dust_cover': 'ar15_upper_receiver',
    'ar15_forward_assist': 'ar15_upper_receiver',
    'ar15_charging_handle': 'ar15_upper_receiver',
    'ar15_bolt_carrier': 'ar15_upper_receiver',
    'ar15_rear_sight_base': 'ar15_upper_receiver',
    'ar15_rear_sight_leaf': 'ar15_rear_sight_base',
    'ar15_barrel': 'ar15_upper_receiver',
    'ar15_barrel_nut': 'ar15_barrel',
    'ar15_gas_block': 'ar15_barrel',
    'ar15_gas_tube': 'ar15_barrel',
    'ar15_flash_hider': 'ar15_barrel',
    'ar15_crush_washer': 'ar15_barrel',
    'ar15_handguard': 'ar15_upper_receiver',
    'ar15_handguard_hardware': 'ar15_handguard',
    'ar15_front_sight_base': 'ar15_handguard',
    'ar15_front_sight_leaf': 'ar15_front_sight_base',
}

# attachment points for the game side (mm)
SOCKETS = {
    'socket_muzzle': (F.FH_X1, 0.0, 0.0),
    'socket_shell_eject': (-52.0, -16.0, 5.0),
    'socket_grip': (-188.0, 0.0, -92.0),
    'socket_sight_rear': (-150.6, 0.0, 64.5),
    'socket_sight_front': (347.0, 0.0, 67.4),
    'socket_magazine': (-44.0, 0.0, -70.0),
}


def assemble(obs):
    coll = L._COLL['c']
    root = bpy.data.objects.new(WEAPON, None)
    root.empty_display_type = 'ARROWS'
    root.empty_display_size = 0.1
    coll.objects.link(root)
    for name, piv in PIVOTS.items():
        if name in obs:
            L.set_origin(obs[name], piv)
    bpy.context.view_layer.update()
    for name, par in HIERARCHY.items():
        if name not in obs:
            continue
        L.parent(obs[name], obs[par] if par else root)
        bpy.context.view_layer.update()
    missing = [n for n in obs if n not in HIERARCHY]
    for n in missing:
        L.parent(obs[n], root)
    for name, loc in SOCKETS.items():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'PLAIN_AXES'
        e.empty_display_size = 0.015
        e.location = Vector(loc) * L.S
        coll.objects.link(e)
        L.parent(e, root)
    # metadata for the pipeline
    root['weapon_name'] = WEAPON
    root['caliber'] = '5.56x45mm NATO'
    root['length_collapsed_mm'] = 838.2
    root['length_extended_mm'] = 919.4
    root['barrel_length_mm'] = F.BARREL_LEN
    root['handguard_length_mm'] = F.HG_LEN
    root['stock_travel_mm'] = B.STOCK_TRAVEL
    root['stock_positions'] = 6
    root['mass_kg'] = 3.0
    root['twist'] = '1:7 RH, 6 grooves'
    return root


def uv_unwrap(obs):
    """Automatic UVs (Smart UV Project) so the exports are ready for texture baking."""
    import math
    for ob in obs.values():
        bpy.context.view_layer.objects.active = ob
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        ob.select_set(False)


def report(obs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in obs.values():
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    d = (hi - lo) * 1000
    print(f'bounds mm: X {lo.x * 1000:.1f} .. {hi.x * 1000:.1f}  Y {lo.y * 1000:.1f} .. {hi.y * 1000:.1f}  '
          f'Z {lo.z * 1000:.1f} .. {hi.z * 1000:.1f}')
    print(f'overall length {d.x:.1f} mm (target 838.2), width {d.y:.1f} mm, height {d.z:.1f} mm')
    print(f'total tris: {sum(L.tri_count(o) for o in obs.values())}')
    return d


def export(path_glb, path_fbx):
    os.makedirs(os.path.dirname(path_glb), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path_glb, export_format='GLB', use_selection=False,
                              export_apply=True, export_yup=True)
    bpy.ops.export_scene.fbx(filepath=path_fbx, use_selection=False, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_UNITS', object_types={'EMPTY', 'MESH'},
                             mesh_smooth_type='OFF', use_custom_props=True, add_leaf_bones=False)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--export', action='store_true')
    ap.add_argument('--preview', default='')
    ap.add_argument('--out', default=os.path.join(ROOT, 'renders', 'wip'))
    args = ap.parse_args(argv)

    reset_scene()
    obs = build()
    assemble(obs)
    uv_unwrap(obs)
    report(obs)

    if args.save:
        p = os.path.join(ROOT, f'{WEAPON}.blend')
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
        print('saved', p)
    if args.export:
        export(os.path.join(ROOT, 'export', f'{WEAPON}.glb'), os.path.join(ROOT, 'export', f'{WEAPON}.fbx'))
        print('exported glb + fbx')
    if args.preview:
        import preview as P
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        if 'match' in args.preview:
            P.photo_match_side(args.out + '_match.png')
        if 'quick' in args.preview:
            P.views(args.out, 'WORKBENCH')
        if 'beauty' in args.preview:
            P.views(args.out, 'CYCLES')


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    main(argv)
