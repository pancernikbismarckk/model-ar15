"""ox_inventory item images (transparent PNG) rendered from weapon_ar15.blend.

    python3 blender/render_icons.py [samples] [item,item,...]

Writes fivem/ox_inventory/web/images/{WEAPON_AR15,at_ar15_holo,at_ar15_grip,at_ar15_flashlight,at_ar15_laser}.png
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image  # noqa: E402

import preview as P  # noqa: E402
import render_final as R  # noqa: E402

OUT = os.path.join(ROOT, 'fivem', 'ox_inventory', 'web', 'images')

# item: (attachment empty or None for the rifle, view direction, render size, final canvas, left side)
ICONS = {
    'WEAPON_AR15': (None, (-0.12, 1.0, -0.10), (1600, 800), (512, 256), False),
    'at_ar15_holo': ('ar15_att_holo', (-0.55, 1.0, -0.38), (800, 800), (256, 256), False),
    'at_ar15_grip': ('ar15_att_foregrip', (-0.40, 1.0, -0.12), (800, 800), (256, 256), False),
    'at_ar15_flashlight': ('ar15_att_flashlight', (-0.50, 1.0, -0.28), (800, 800), (256, 256), False),
    'at_ar15_laser': ('ar15_att_laser', (-1.0, -0.62, -0.32), (800, 800), (256, 256), True),
}


def isolate(empty_name):
    """Show only the meshes under ``empty_name`` (or the plain rifle when None)."""
    R.configure(attachments=False)
    if empty_name is None:
        return
    keep = set(bpy.data.objects[empty_name].children_recursive)
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            ob.hide_render = ob not in keep
    bpy.context.view_layer.update()


def crop_to_canvas(path, canvas, pad=0.06):
    img = Image.open(path).convert('RGBA')
    box = img.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox()
    img = img.crop(box)
    cw, ch = canvas
    scale = min(cw * (1 - 2 * pad) / img.width, ch * (1 - 2 * pad) / img.height)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    out = Image.new('RGBA', canvas, (0, 0, 0, 0))
    out.paste(img, ((cw - img.width) // 2, (ch - img.height) // 2), img)
    out.save(path, optimize=True)


def main():
    samples = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    only = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else None
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'))
    os.makedirs(OUT, exist_ok=True)
    for item, (empty, direction, res, canvas, left) in ICONS.items():
        if only and item not in only:
            continue
        P.setup_cycles(res, samples)
        isolate(empty)
        cam = P._camera()
        cam.data.type = 'PERSP'
        cam.data.lens = 85
        cam.data.sensor_width = 36
        P._fit(cam, Vector(direction), margin=1.05)
        if left:
            R.mirror_lights()
        path = os.path.join(OUT, item + '.png')
        P.render(path)
        if left:
            R.mirror_lights()
        crop_to_canvas(path, canvas)
        print('icon', path)


if __name__ == '__main__':
    main()
