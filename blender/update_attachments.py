"""Rebuild only the attachments inside the textured weapon_ar15.blend.

    python3 blender/update_attachments.py && python3 blender/texture_bake.py --only ar15_attachments

The rifle keeps its baked materials; the attachment meshes are regenerated from
parts_attachments.py with their source materials, ready for an attachments-only bake.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import ar15lib as L  # noqa: E402
import build_weapon_ar15 as BW  # noqa: E402
import parts_attachments as A  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'))
    L.set_collection(bpy.data.collections[BW.WEAPON])
    M = BW.materials()
    builders = {'holo': A.holo_sight, 'foregrip': A.foregrip, 'flashlight': A.flashlight, 'laser': A.laser}
    for key, (name, sock) in BW.ATTACHMENT_ROOTS.items():
        e = bpy.data.objects[name]
        for ch in list(e.children):
            me = ch.data
            bpy.data.objects.remove(ch)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        e.location = Vector(A.SOCKETS[sock]) * L.S
    root = bpy.data.objects[BW.WEAPON]
    for name, loc in list(A.SOCKETS.items()) + list(A.EMIT_SOCKETS.items()):
        ob = bpy.data.objects.get(name)
        if ob is None:
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = 'PLAIN_AXES'
            ob.empty_display_size = 0.012
            L._COLL['c'].objects.link(ob)
            L.parent(ob, root)
        ob.location = Vector(loc) * L.S
    bpy.context.view_layer.update()
    for key, (name, sock) in BW.ATTACHMENT_ROOTS.items():
        e = bpy.data.objects[name]
        for ob in builders[key](M):
            L.set_origin(ob, tuple(v / L.S for v in e.matrix_world.translation))
            bpy.context.view_layer.update()
            L.parent(ob, e)
            print(f'  {ob.name:30s} {L.tri_count(ob):7d} tris')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'), compress=True)
    print('saved')


if __name__ == '__main__':
    main()
