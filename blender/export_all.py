"""Export weapon_ar15 (textured) to GLB/FBX, plus a web-viewer glTF with JPEG textures.

    python3 blender/export_all.py [viewer_dir]
"""
import base64
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402


def main():
    viewer_dir = sys.argv[1] if len(sys.argv) > 1 else None
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'))
    # triangulate at export time so tangents (normal mapping) can be computed for every mesh
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            m = ob.modifiers.new('export_tris', 'TRIANGULATE')
            m.keep_custom_normals = True
            m.quad_method = 'BEAUTY'
            m.ngon_method = 'BEAUTY'
    exp = os.path.join(ROOT, 'export')
    os.makedirs(exp, exist_ok=True)
    common = dict(use_selection=False, export_apply=True, export_yup=True, export_tangents=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(exp, 'weapon_ar15.glb'), export_format='GLB',
                              export_image_format='JPEG', export_jpeg_quality=92, **common)
    bpy.ops.export_scene.fbx(filepath=os.path.join(exp, 'weapon_ar15.fbx'), use_selection=False,
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                             object_types={'EMPTY', 'MESH'}, mesh_smooth_type='OFF', use_custom_props=True,
                             add_leaf_bones=False, path_mode='RELATIVE', use_tspace=True)
    print('exported glb + fbx')
    if viewer_dir:
        tmp = os.path.join(viewer_dir, '_gltf')
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        bpy.ops.export_scene.gltf(filepath=os.path.join(tmp, 'weapon_ar15.gltf'), export_format='GLTF_SEPARATE',
                                  export_image_format='JPEG', export_jpeg_quality=88, **common)
        js = json.load(open(os.path.join(tmp, 'weapon_ar15.gltf')))
        for buf in js['buffers']:
            data = open(os.path.join(tmp, buf['uri']), 'rb').read()
            buf['uri'] = 'data:application/octet-stream;base64,' + base64.b64encode(data).decode('ascii')
        for img in js.get('images', []):
            src = os.path.join(tmp, img['uri'])
            name = os.path.basename(img['uri'])
            shutil.copy(src, os.path.join(viewer_dir, name))
            img['uri'] = name
        with open(os.path.join(viewer_dir, 'weapon_ar15.gltf.json'), 'w') as f:
            json.dump(js, f, separators=(',', ':'))
        shutil.rmtree(tmp, ignore_errors=True)
        print('viewer files:', sorted(os.listdir(viewer_dir)))


if __name__ == '__main__':
    main()
