"""Check the FiveM binaries the way the game will use them.

    python3 blender/verify_fivem.py --sollumz <Sollumz addon dir> --cwconv <cwconv executable> [--samples 48]

Every .ydr/.ytd in fivem/weapon_ar15/stream is converted back to CodeWalker XML with CodeWalker.Core,
imported with Sollumz, and each component is placed like the game places it: the component origin
(its AAP bone) on the weapon's attach bone. Renders go to renders/fivem_*.png; the hand bones are
marked (Gun_GripR red, Gun_GripL green) in the 'hands' shot.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import build_fivem as B  # noqa: E402
import preview as P  # noqa: E402

RT = os.path.join(B.BUILD, 'roundtrip')
OUT = os.path.join(ROOT, 'renders')

ATTACH = {   # component drawable -> weapon attach bone
    'w_ar_ar15_mag1': 'WAPClip', 'w_ar_ar15_sights': 'WAPScop', 'w_at_ar15_holo': 'WAPScop',
    'w_at_ar15_afgrip': 'WAPGrip', 'w_at_ar15_flsh': 'WAPFlshLasr', 'w_at_ar15_laser': 'WAPSupp_2',
}
LOADOUTS = {
    'default': ['w_ar_ar15_mag1', 'w_ar_ar15_sights'],
    'full': ['w_ar_ar15_mag1', 'w_at_ar15_holo', 'w_at_ar15_afgrip', 'w_at_ar15_flsh', 'w_at_ar15_laser'],
}


def roundtrip(cwconv):
    os.makedirs(RT, exist_ok=True)
    for fn in sorted(os.listdir(B.STREAM)):
        subprocess.run([cwconv, 'bin2xml', os.path.join(B.STREAM, fn), RT], check=True, stdout=subprocess.DEVNULL)


def import_all():
    files = [{'name': f} for f in sorted(os.listdir(RT)) if f.endswith('.ydr.xml')]
    bpy.ops.sollumz.import_assets(directory=RT + os.sep, files=files)
    # textures live in the shared dictionary, not next to each drawable
    txd = os.path.join(RT, B.TXD)
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image is not None:
                name = os.path.splitext(os.path.basename(node.image.filepath or node.image.name))[0].lower()
                path = os.path.join(txd, name + '.dds')
                if os.path.exists(path) and not node.image.has_data:
                    img = bpy.data.images.load(path, check_existing=True)
                    img.colorspace_settings.name = node.image.colorspace_settings.name
                    node.image = img


def drawables():
    return {o.name.split('.')[0]: o for o in bpy.data.objects if o.sollum_type == 'sollumz_drawable'}


def show(loadout):
    d = drawables()
    weapon = d['w_ar_ar15']
    for name, ob in d.items():
        if name == 'w_ar_ar15':
            continue
        visible = name in LOADOUTS[loadout]
        for o in [ob] + list(ob.children_recursive):
            o.hide_render = not visible
        if visible:
            ob.matrix_world = weapon.matrix_world @ weapon.pose.bones[ATTACH[name]].matrix
    bpy.context.view_layer.update()


def markers(on):
    weapon = drawables()['w_ar_ar15']
    for bone, col in (('Gun_GripR', (1, 0.1, 0.1, 1)), ('Gun_GripL', (0.1, 0.9, 0.2, 1))):
        name = 'marker_' + bone
        ob = bpy.data.objects.get(name)
        if ob is None:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012)
            ob = bpy.context.active_object
            ob.name = name
            m = bpy.data.materials.new(name)
            m.diffuse_color = col
            m.use_nodes = True
            m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = col
            m.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = col
            m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
            ob.data.materials.append(m)
            ob.location = weapon.matrix_world @ weapon.pose.bones[bone].head
        ob.hide_render = not on


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--sollumz', required=True)
    ap.add_argument('--cwconv', required=True)
    ap.add_argument('--samples', type=int, default=48)
    a = ap.parse_args(args)

    roundtrip(a.cwconv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    B.enable_sollumz(a.sollumz)
    import_all()
    print('imported:', sorted(drawables()))
    P.setup_cycles(res=(1600, 800), samples=a.samples)
    cam = P._camera()
    cam.data.lens = 70
    for loadout, direction in (('default', (-0.55, 1.0, -0.30)), ('full', (-0.55, 1.0, -0.30))):
        show(loadout)
        markers(False)
        P._fit(cam, Vector(direction), margin=1.06)
        P.render(os.path.join(OUT, f'fivem_{loadout}.png'))
    show('full')
    markers(True)
    P._fit(cam, Vector((0.0, 1.0, 0.0)), margin=1.04)
    P.render(os.path.join(OUT, 'fivem_hands.png'))


if __name__ == '__main__':
    main()
