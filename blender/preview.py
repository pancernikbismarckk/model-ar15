"""Preview renders of weapon_ar15 (Workbench for quick checks, Cycles for beauty shots)."""
import math
import os

import bpy
from mathutils import Euler, Vector

# Reference photo mapping (see README): 1 px = 838.2/1055 mm, photo 1200 x 496 px,
# X = 0 at photo px 576, bore axis at photo py 182.75.
PHOTO_MM_PER_PX = 838.2 / 1055.0
PHOTO_W, PHOTO_H = 1200, 496
PHOTO_CX_MM = (600.0 - 576.0) * PHOTO_MM_PER_PX
PHOTO_CZ_MM = (182.75 - 248.0) * PHOTO_MM_PER_PX


def _camera(name='PreviewCam'):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cd = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cd)
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def setup_workbench(res=(1600, 900)):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_specular_highlight = True
    sh.show_object_outline = False
    sc.render.film_transparent = False
    sc.display.render_aa = '8'
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass


def setup_cycles(res=(1600, 900), samples=64, light_scale=1.0):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    world = sc.world or bpy.data.worlds.new('World')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        if n.bl_idname not in ('ShaderNodeOutputWorld',):
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputWorld'][0]
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -0.3
    mr.inputs['From Max'].default_value = 0.9
    mr.inputs['To Min'].default_value = 0.02
    mr.inputs['To Max'].default_value = 0.9
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.92, 0.94, 1.0, 1.0)
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], bg.inputs['Strength'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    _studio_lights(light_scale)


def _studio_lights(scale=1.0):
    for n in ('Key', 'Fill', 'Rim', 'Top'):
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob)

    def area(name, loc, rot, size, energy, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.size = size
        ld.energy = energy * scale
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_euler = Euler([math.radians(a) for a in rot])
        bpy.context.scene.collection.objects.link(ob)
        return ob

    area('Key', (0.4, -1.3, 1.3), (42, 0, 17), 1.4, 45)
    area('Fill', (-1.1, -1.3, 0.1), (84, 0, -40), 1.8, 14, (0.93, 0.96, 1.0))
    area('Rim', (0.3, 1.4, 0.9), (-52, 0, 180), 1.2, 38)
    area('Top', (0.0, 0.0, 1.7), (0, 0, 0), 2.6, 22)


def look_at(cam, target, loc):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def photo_match_side(path, engine='WORKBENCH'):
    """Orthographic right-side render framed exactly like the reference photo."""
    sc = bpy.context.scene
    if engine == 'WORKBENCH':
        setup_workbench((PHOTO_W * 2, PHOTO_H * 2))
    elif engine == 'CYCLES':
        setup_cycles((PHOTO_W * 2, PHOTO_H * 2), 48)
    sc.render.resolution_x, sc.render.resolution_y = PHOTO_W * 2, PHOTO_H * 2
    cam = _camera()
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = PHOTO_W * PHOTO_MM_PER_PX * 0.001
    cam.data.clip_start = 0.01
    cam.data.clip_end = 10
    cam.location = (PHOTO_CX_MM * 0.001, -2.0, PHOTO_CZ_MM * 0.001)
    cam.rotation_euler = (math.radians(90), 0, 0)
    render(path)


def _fit(cam, direction, margin=1.08, bbox_objs=None):
    """Aim the camera along direction and pull back until the objects fit in frame."""
    objs = bbox_objs or [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render]
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    d = Vector(direction).normalized()
    cam.rotation_euler = (-d).to_track_quat('Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    flat = [v for p in pts for v in p]
    co, _scale = cam.camera_fit_coords(dg, flat)
    c = Vector(co)
    # pull back along the view direction for some margin
    center = sum(pts, Vector()) / len(pts)
    depth = (center - c).dot(d)
    cam.location = c - d * depth * (margin - 1.0)
    return cam


SHOTS = {
    'side_r': dict(dir=(0, 1, 0)),
    'persp_fr': dict(dir=(-0.62, 0.72, -0.30)),
    'persp_rl': dict(dir=(0.62, -0.72, -0.32)),
    'top': dict(dir=(0, 0.02, -1)),
    'side_l': dict(dir=(0, -1, 0)),
    'front': dict(dir=(-1, 0.25, -0.12), objs=None),
}

CLOSEUPS = {
    # name: (camera location, target) in mm
    'cu_receiver_r': ((60.0, -420.0, 90.0), (-95.0, 0.0, -25.0)),
    'cu_receiver_l': ((-40.0, 430.0, 110.0), (-110.0, 0.0, -25.0)),
    'cu_stock': ((-160.0, -420.0, 60.0), (-300.0, 0.0, -40.0)),
    'cu_muzzle': ((520.0, -170.0, 80.0), (380.0, 0.0, 10.0)),
    'cu_handguard_top': ((250.0, -260.0, 260.0), (150.0, 0.0, 10.0)),
    'cu_grip_mag': ((-20.0, -330.0, -210.0), (-100.0, 0.0, -100.0)),
}


def views(prefix, engine='WORKBENCH', res=(1600, 800), samples=64, which=None, closeups=True):
    if engine == 'WORKBENCH':
        setup_workbench(res)
        w = bpy.context.scene.world or bpy.data.worlds.new('World')
        bpy.context.scene.world = w
        w.color = (0.75, 0.76, 0.78)
    else:
        setup_cycles(res, samples)
    cam = _camera()
    cam.data.type = 'PERSP'
    cam.data.lens = 70
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.01
    cam.data.clip_end = 20
    out = []
    for name, cfg in SHOTS.items():
        if which and name not in which:
            continue
        _fit(cam, cfg['dir'])
        p = f'{prefix}_{name}.png'
        render(p)
        out.append(p)
    if closeups:
        cam.data.lens = 60
        for name, (loc, tgt) in CLOSEUPS.items():
            if which and name not in which:
                continue
            look_at(cam, Vector(tgt) * 0.001, Vector(loc) * 0.001)
            p = f'{prefix}_{name}.png'
            render(p)
            out.append(p)
    return out
