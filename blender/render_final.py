"""Final presentation renders of weapon_ar15 (Cycles).

    python3 blender/render_final.py [samples] [shot,shot,...]
Writes PNGs to renders/.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import preview as P  # noqa: E402

OUT = os.path.join(ROOT, 'renders')
RES = (1920, 1080)


def mirror_lights():
    for ob in bpy.data.objects:
        if ob.type == 'LIGHT':
            ob.location.y = -ob.location.y
            e = ob.rotation_euler
            ob.rotation_euler = Euler((-e.x, e.y, math.pi - e.z))


def shot(name, loc, tgt, lens=60, res=RES, left=False):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    cam = P._camera()
    cam.data.type = 'PERSP'
    cam.data.lens = lens
    cam.data.sensor_width = 36
    P.look_at(cam, Vector(tgt) * 0.001, Vector(loc) * 0.001)
    if left:
        mirror_lights()
    P.render(os.path.join(OUT, f'weapon_ar15_{name}.png'))
    if left:
        mirror_lights()


def fit_shot(name, direction, lens=70, res=RES, margin=1.06, left=False):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    cam = P._camera()
    cam.data.type = 'PERSP'
    cam.data.lens = lens
    cam.data.sensor_width = 36
    P._fit(cam, direction, margin=margin)
    if left:
        mirror_lights()
    P.render(os.path.join(OUT, f'weapon_ar15_{name}.png'))
    if left:
        mirror_lights()


def configure(attachments=True):
    """Show or hide the attachments; iron sights fold when the optic is mounted."""
    for ob in bpy.data.objects:
        p = ob
        att = False
        while p is not None:
            if p.name.startswith('ar15_att_') and p.type == 'EMPTY':
                att = True
                break
            p = p.parent
        if att and ob.type == 'MESH':
            ob.hide_render = not attachments
    fold = math.radians(90.0) if attachments else 0.0
    bpy.data.objects['ar15_rear_sight_leaf'].rotation_euler[1] = fold
    bpy.data.objects['ar15_front_sight_leaf'].rotation_euler[1] = -fold
    bpy.context.view_layer.update()


def main():
    samples = int(sys.argv[1]) if len(sys.argv) > 1 else 128
    which = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else None
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'))
    os.makedirs(OUT, exist_ok=True)
    P.setup_cycles(RES, samples)

    def want(n):
        return which is None or n in which

    configure(True)

    if want('side'):
        P.setup_cycles((P.PHOTO_W * 2, P.PHOTO_H * 2), samples)
        P.photo_match_side(os.path.join(OUT, 'weapon_ar15_side.png'), engine='CYCLES_KEEP')
        P.setup_cycles(RES, samples)
    if want('3q_front'):
        fit_shot('3q_front', (-0.62, 0.72, -0.30))
    if want('3q_rear_left'):
        fit_shot('3q_rear_left', (0.60, -0.74, -0.30), left=True)
    if want('top'):
        fit_shot('top', (0.0, 0.02, -1.0), lens=85, res=(1920, 720))
    if want('detail_receiver'):
        shot('detail_receiver', (40.0, -360.0, 110.0), (-100.0, 0.0, -20.0), lens=55)
    if want('detail_left'):
        shot('detail_left', (-40.0, 380.0, 100.0), (-110.0, 0.0, -25.0), lens=55, left=True)
    if want('detail_stock'):
        shot('detail_stock', (-150.0, -400.0, 70.0), (-300.0, 0.0, -40.0), lens=55)
    if want('detail_muzzle'):
        shot('detail_muzzle', (530.0, -210.0, 110.0), (370.0, 0.0, 10.0), lens=55)
    if want('detail_grip_mag'):
        shot('detail_grip_mag', (-10.0, -330.0, -170.0), (-110.0, 0.0, -110.0), lens=55)
    if want('detail_holo'):
        shot('detail_holo', (60.0, -300.0, 210.0), (-80.0, 0.0, 50.0), lens=55)
    if want('detail_front'):
        shot('detail_front', (560.0, -190.0, 60.0), (345.0, 0.0, -15.0), lens=55)
    if want('plain_3q'):
        configure(False)
        fit_shot('plain_3q', (-0.62, 0.72, -0.30))
        configure(True)


if __name__ == '__main__':
    main()
