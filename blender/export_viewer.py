"""Export a .blend as web-viewer files: glTF JSON with embedded buffers + JPEG textures next to it.

    python3 blender/export_viewer.py <file.blend> <out_dir> <name>

Writes <out_dir>/<name>.gltf.json (served as JSON by the artifact host) and the texture JPEGs.
"""
import base64
import json
import os
import shutil
import sys

import bpy


def main(blend, out_dir, name):
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and not any(m.type == 'TRIANGULATE' for m in ob.modifiers):
            m = ob.modifiers.new('export_tris', 'TRIANGULATE')
            m.keep_custom_normals = True
    tmp = os.path.join(out_dir, '_gltf_' + name)
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    bpy.ops.export_scene.gltf(filepath=os.path.join(tmp, name + '.gltf'), export_format='GLTF_SEPARATE',
                              export_image_format='JPEG', export_jpeg_quality=88, export_tangents=True,
                              export_yup=True, export_apply=True, export_animations=True,
                              export_animation_mode='ACTIONS', export_force_sampling=True, use_selection=False)
    js = json.load(open(os.path.join(tmp, name + '.gltf')))
    for buf in js['buffers']:
        data = open(os.path.join(tmp, buf['uri']), 'rb').read()
        buf['uri'] = 'data:application/octet-stream;base64,' + base64.b64encode(data).decode('ascii')
    for img in js.get('images', []):
        fn = os.path.basename(img['uri'])
        shutil.copy(os.path.join(tmp, img['uri']), os.path.join(out_dir, fn))
        img['uri'] = fn
    with open(os.path.join(out_dir, name + '.gltf.json'), 'w') as f:
        json.dump(js, f, separators=(',', ':'))
    shutil.rmtree(tmp, ignore_errors=True)
    print('viewer files:', name + '.gltf.json', [i['uri'] for i in js.get('images', [])],
          'animations:', [a['name'] for a in js.get('animations', [])])


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    main(*args)
