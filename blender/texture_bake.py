"""Bake PBR texture atlases for weapon_ar15.

    python3 blender/texture_bake.py [size]

Opens weapon_ar15.blend, lays out one shared UV atlas per group (the rifle and
the attachments), bakes procedural surface detail (anodize/phosphate grain,
edge wear, polymer stipple, grip checkering, ambient occlusion) into
basecolor / ORM (R=AO, G=roughness, B=metallic) / normal maps, switches the
parts to texture-based materials and saves the .blend.  Textures go to textures/.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

TEX_DIR = os.path.join(ROOT, 'textures')

# materials that stay as they are (transparent / emissive)
SPECIAL = {'ar15_glass', 'ar15_glass_dark', 'ar15_reticle', 'ar15_lens_light', 'ar15_lens_laser', 'ar15_chrome',
           'ar15_led'}

# surface recipes: base colour, colour variation, roughness, roughness variation, metallic,
# edge wear (colour, roughness, metallic, amount), bump (grain strength, stipple strength)
RECIPES = {
    'ar15_aluminum_anodized': dict(col=(0.024, 0.024, 0.026), var=0.20, rough=0.44, rvar=0.12, metal=0.45,
                                   wear=((0.30, 0.30, 0.31), 0.32, 1.0, 0.50), grain=0.55, gscale=800.0,
                                   stipple=0.0, streaks=0.08),
    'ar15_steel_phosphate': dict(col=(0.030, 0.030, 0.029), var=0.26, rough=0.56, rvar=0.15, metal=0.55,
                                 wear=((0.30, 0.30, 0.30), 0.34, 1.0, 0.55), grain=0.85, gscale=1000.0,
                                 stipple=0.0, streaks=0.0),
    'ar15_polymer': dict(col=(0.035, 0.035, 0.036), var=0.15, rough=0.62, rvar=0.10, metal=0.0,
                         wear=((0.070, 0.070, 0.072), 0.48, 0.0, 0.35), grain=0.25, gscale=1100.0,
                         stipple=0.75, streaks=0.0),
    'ar15_polymer_checkered': dict(col=(0.035, 0.035, 0.036), var=0.12, rough=0.68, rvar=0.08, metal=0.0,
                                   wear=((0.080, 0.080, 0.082), 0.46, 0.0, 0.35), grain=0.2, gscale=1100.0,
                                   stipple=0.2, streaks=0.0, checker=True),
    'ar15_rubber': dict(col=(0.028, 0.028, 0.028), var=0.10, rough=0.86, rvar=0.05, metal=0.0,
                        wear=((0.05, 0.05, 0.05), 0.8, 0.0, 0.0), grain=0.7, gscale=900.0, stipple=0.35,
                        streaks=0.0),
    'ar15_brass': dict(col=(0.78, 0.56, 0.26), var=0.10, rough=0.30, rvar=0.08, metal=1.0,
                       wear=((0.85, 0.65, 0.35), 0.2, 1.0, 0.3), grain=0.1, gscale=900.0, stipple=0.0,
                       streaks=0.0),
    'ar15_copper': dict(col=(0.72, 0.38, 0.22), var=0.10, rough=0.32, rvar=0.08, metal=1.0,
                        wear=((0.8, 0.5, 0.3), 0.2, 1.0, 0.3), grain=0.1, gscale=900.0, stipple=0.0,
                        streaks=0.0),
}

# relative texel density in the atlas (hidden internals get less space, the grip more)
UV_WEIGHT = {
    'ar15_barrel': 0.35, 'ar15_barrel_nut': 0.25, 'ar15_bolt_carrier': 0.45, 'ar15_gas_tube': 0.4,
    'ar15_gas_block': 0.6, 'ar15_buffer_tube': 0.6, 'ar15_magazine_lips': 0.35, 'ar15_cartridge_case': 0.4,
    'ar15_cartridge_bullet': 0.4, 'ar15_pistol_grip': 1.6, 'ar15_trigger': 1.3,
}


# ---------------------------------------------------------------------------
# node helpers
# ---------------------------------------------------------------------------
class NB:
    def __init__(self, mat):
        self.nt = mat.node_tree
        self.N = self.nt.nodes
        self.L = self.nt.links

    def node(self, kind, **inputs):
        n = self.N.new(kind)
        for k, v in inputs.items():
            if isinstance(k, str) and k in n.inputs:
                if hasattr(v, 'bl_idname') or isinstance(v, bpy.types.NodeSocket):
                    self.L.new(v, n.inputs[k])
                else:
                    n.inputs[k].default_value = v
        return n

    def link(self, a, b):
        self.L.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        n = self.N.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.L.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    def mix_rgb(self, fac, a, b, blend='MIX'):
        n = self.N.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.L.new(v, sock)
            elif isinstance(v, (tuple, list)):
                sock.default_value = (*v[:3], 1.0)
            else:
                sock.default_value = v
        return n.outputs[2]

    def mix_f(self, fac, a, b):
        n = self.N.new('ShaderNodeMix')
        n.data_type = 'FLOAT'
        for sock, v in ((n.inputs[0], fac), (n.inputs[2], a), (n.inputs[3], b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.L.new(v, sock)
            else:
                sock.default_value = v
        return n.outputs[0]

    def noise(self, vec, scale, detail=2.0, rough=0.5, dims='3D'):
        n = self.N.new('ShaderNodeTexNoise')
        n.noise_dimensions = dims
        self.L.new(vec, n.inputs['Vector'])
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        return n.outputs['Fac']

    def maprange(self, v, a0, a1, b0=0.0, b1=1.0, clamp=True):
        n = self.N.new('ShaderNodeMapRange')
        n.clamp = clamp
        self.L.new(v, n.inputs['Value'])
        n.inputs['From Min'].default_value = a0
        n.inputs['From Max'].default_value = a1
        n.inputs['To Min'].default_value = b0
        n.inputs['To Max'].default_value = b1
        return n.outputs['Result']


def build_detail(mat_name, r):
    """Procedural surface of one source material. Returns (material, sockets)."""
    m = bpy.data.materials.new(mat_name + '__detail')
    m.use_nodes = True
    b = NB(m)
    for n in list(b.N):
        b.N.remove(n)
    out = b.node('ShaderNodeOutputMaterial')
    bsdf = b.node('ShaderNodeBsdfPrincipled')
    b.link(bsdf.outputs[0], out.inputs['Surface'])
    tc = b.node('ShaderNodeTexCoord')
    obj = tc.outputs['Object']

    big = b.noise(obj, 45.0, 3.0, 0.55)             # ~2 cm blotches
    mid = b.noise(obj, 260.0, 2.0, 0.5)             # ~4 mm
    fine = b.noise(obj, r['gscale'], 2.0, 0.55)     # ~1 mm grain (resolvable at ~2 px/mm)
    # streaks: noise squashed along one axis (machining / handling marks)
    mp = b.node('ShaderNodeMapping')
    b.link(obj, mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (1.0, 1.0, 22.0)
    streak = b.noise(mp.outputs['Vector'], 90.0, 4.0, 0.6)

    # edge mask from the bevel normal
    bev = b.node('ShaderNodeBevel')
    bev.samples = 8
    bev.inputs['Radius'].default_value = 0.0011
    geo = b.node('ShaderNodeNewGeometry')
    dot = b.node('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    b.link(bev.outputs['Normal'], dot.inputs[0])
    b.link(geo.outputs['Normal'], dot.inputs[1])
    edge = b.maprange(dot.outputs['Value'], 0.985, 0.90)
    patch = b.noise(obj, 70.0, 3.0, 0.6)           # ~1.5 cm patches of handling wear
    breakup = b.math('MULTIPLY', b.maprange(patch, 0.48, 0.62), b.maprange(mid, 0.35, 0.6))
    wear = b.math('MULTIPLY', edge, breakup)
    wear = b.math('MULTIPLY', wear, r['wear'][3], clamp=True)

    ao = b.node('ShaderNodeAmbientOcclusion')
    ao.samples = 16
    ao.only_local = True
    ao.inputs['Distance'].default_value = 0.004
    cav = b.maprange(ao.outputs['AO'], 0.0, 1.0, 0.42, 1.0)

    # base colour with variation, cavity and wear
    v = b.maprange(big, 0.3, 0.7, 1.0 - r['var'], 1.0 + r['var'], clamp=True)
    v = b.math('MULTIPLY', v, b.maprange(fine, 0.3, 0.7, 0.88, 1.12))
    if r['streaks']:
        v = b.math('MULTIPLY', v, b.maprange(streak, 0.35, 0.65, 1.0 - r['streaks'], 1.0 + r['streaks']))
    base = b.mix_rgb(1.0, r['col'], (1, 1, 1), 'MULTIPLY')
    colv = b.node('ShaderNodeCombineColor')
    for i in range(3):
        b.link(v, colv.inputs[i])
    base = b.mix_rgb(1.0, base, colv.outputs[0], 'MULTIPLY')
    col = b.mix_rgb(wear, base, r['wear'][0])
    cavc = b.node('ShaderNodeCombineColor')
    for i in range(3):
        b.link(cav, cavc.inputs[i])
    col = b.mix_rgb(1.0, col, cavc.outputs[0], 'MULTIPLY')

    rough = b.maprange(big, 0.3, 0.7, r['rough'] - r['rvar'], r['rough'] + r['rvar'])
    rough = b.math('ADD', rough, b.maprange(fine, 0.3, 0.7, -0.07, 0.07))
    rough = b.mix_f(wear, rough, r['wear'][1])
    metal = b.mix_f(wear, r['metal'], r['wear'][2])

    # height for the normal map
    h = b.math('MULTIPLY', fine, r['grain'])
    if r['stipple']:
        vor = b.node('ShaderNodeTexVoronoi')
        b.link(obj, vor.inputs['Vector'])
        vor.inputs['Scale'].default_value = 650.0
        st = b.maprange(vor.outputs['Distance'], 0.0, 0.6, 1.0, 0.0)
        h = b.math('ADD', h, b.math('MULTIPLY', st, r['stipple']))
    if r['streaks']:
        h = b.math('ADD', h, b.math('MULTIPLY', streak, 0.05))
    bump = b.node('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.6
    bump.inputs['Distance'].default_value = 0.0005
    b.link(h, bump.inputs['Height'])
    nrm = bump.outputs['Normal']
    if r.get('checker'):
        mp2 = b.node('ShaderNodeMapping')
        mp2.inputs['Rotation'].default_value = (0.0, math.radians(45.0), 0.0)
        mp2.inputs['Scale'].default_value = (1 / 0.0016,) * 3
        b.link(obj, mp2.inputs['Vector'])
        sep = b.node('ShaderNodeSeparateXYZ')
        b.link(mp2.outputs['Vector'], sep.inputs['Vector'])

        def tri(sock):
            f = b.math('FRACT', sock)
            return b.math('ABSOLUTE', b.math('SUBTRACT', f, 0.5))

        ch = b.math('MINIMUM', tri(sep.outputs['X']), tri(sep.outputs['Z']))
        bump2 = b.node('ShaderNodeBump')
        bump2.inputs['Strength'].default_value = 1.0
        bump2.inputs['Distance'].default_value = 0.0007
        b.link(ch, bump2.inputs['Height'])
        b.link(nrm, bump2.inputs['Normal'])
        nrm = bump2.outputs['Normal']

    b.link(col, bsdf.inputs['Base Color'])
    b.link(rough, bsdf.inputs['Roughness'])
    b.link(metal, bsdf.inputs['Metallic'])
    b.link(nrm, bsdf.inputs['Normal'])
    emi = b.node('ShaderNodeEmission')
    img = b.node('ShaderNodeTexImage')
    img.name = 'BAKE_TARGET'
    b.N.active = img
    return m, dict(out=out, bsdf=bsdf, emi=emi, img=img, color=col, rough=rough, metal=metal, ao=ao.outputs['AO'])


# ---------------------------------------------------------------------------
# UV atlas
# ---------------------------------------------------------------------------
def select_only(objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def atlas_unwrap(objs, margin=0.0022):
    select_only(objs)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in objs:
        k = UV_WEIGHT.get(o.name, 1.0)
        if k != 1.0:
            uv = o.data.uv_layers.active.data
            for d in uv:
                d.uv = d.uv * k
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin, shape_method='CONCAVE')
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')


def uv_coverage(objs, size=512):
    """Fraction of the atlas covered by UV triangles (rough raster)."""
    from PIL import Image, ImageDraw
    im = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(im)
    area3d = 0.0
    for o in objs:
        me = o.data
        uv = me.uv_layers.active.data
        for p in me.polygons:
            pts = [(uv[li].uv.x * size, (1 - uv[li].uv.y) * size) for li in p.loop_indices]
            d.polygon(pts, fill=255)
            area3d += p.area
    cov = np.asarray(im).astype(bool).mean()
    return cov, area3d


# ---------------------------------------------------------------------------
# baking
# ---------------------------------------------------------------------------
def new_image(name, size, non_color):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    return img


def bake(kind, samples, margin):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    t = time.time()
    if kind == 'NORMAL':
        bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=margin, use_clear=True)
    else:
        bpy.ops.object.bake(type='EMIT', margin=margin, use_clear=True)
    print(f'    baked {kind} in {time.time() - t:.1f}s')


def bake_group(group, objs, size):
    print(f'== {group}: {len(objs)} objects')
    atlas_unwrap(objs)
    cov, a3 = uv_coverage(objs)
    px_per_mm = math.sqrt(cov * size * size / (a3 * 1e6)) if a3 else 0
    print(f'   atlas coverage {cov * 100:.0f}%, surface {a3 * 1e4:.0f} cm2, ~{px_per_mm:.1f} px/mm')

    # detail materials replace the source materials during the bake
    details = {}
    orig = {}
    for o in objs:
        if 'src_materials' in o:           # re-bake: restore the source materials first
            o.data.materials.clear()
            for name in o['src_materials']:
                o.data.materials.append(bpy.data.materials[name])
        o['src_materials'] = [s.material.name for s in o.material_slots]
        orig[o.name] = [s.material for s in o.material_slots]
        for i, s in enumerate(o.material_slots):
            src = s.material
            src.use_fake_user = True
            if src.name not in details:
                r = RECIPES.get(src.name, RECIPES['ar15_polymer'])
                details[src.name] = build_detail(src.name, r)
            s.material = details[src.name][0]

    imgs = {k: new_image(f'{group}_{k}', size, k != 'basecolor')
            for k in ('basecolor', 'rough', 'metal', 'ao', 'normal')}
    select_only(objs)

    def route(key):
        for m, so in details.values():
            nt = m.node_tree
            for l in list(so['out'].inputs['Surface'].links):
                nt.links.remove(l)
            if key == 'normal':
                nt.links.new(so['bsdf'].outputs[0], so['out'].inputs['Surface'])
            else:
                src = {'basecolor': so['color'], 'rough': so['rough'], 'metal': so['metal'], 'ao': so['ao']}[key]
                for l in list(so['emi'].inputs['Color'].links):
                    nt.links.remove(l)
                nt.links.new(src, so['emi'].inputs['Color'])
                nt.links.new(so['emi'].outputs[0], so['out'].inputs['Surface'])
            so['img'].image = imgs[key]
            nt.nodes.active = so['img']

    margin = max(4, size // 256)
    for key, spp in (('basecolor', 24), ('rough', 16), ('metal', 8), ('ao', 16), ('normal', 4)):
        route(key)
        bake('NORMAL' if key == 'normal' else 'EMIT', spp, margin)

    os.makedirs(TEX_DIR, exist_ok=True)
    w = size
    rough = np.array(imgs['rough'].pixels[:]).reshape(w, w, 4)[..., 0]
    metal = np.array(imgs['metal'].pixels[:]).reshape(w, w, 4)[..., 0]
    ao = np.array(imgs['ao'].pixels[:]).reshape(w, w, 4)[..., 0]
    orm = np.stack([ao, np.clip(rough, 0.04, 1.0), metal, np.ones_like(ao)], axis=-1)
    img_orm = new_image(f'{group}_orm', size, True)
    img_orm.pixels[:] = orm.ravel()
    paths = {}
    for key, img in (('basecolor', imgs['basecolor']), ('normal', imgs['normal']), ('orm', img_orm)):
        img.filepath_raw = os.path.join(TEX_DIR, f'{group}_{key}.png')
        img.file_format = 'PNG'
        img.save()
        img.filepath = f'//textures/{group}_{key}.png'
        paths[key] = img
    for k in ('rough', 'metal', 'ao'):
        bpy.data.images.remove(imgs[k])

    # final texture material for the whole group
    mat = bpy.data.materials.get(group) or bpy.data.materials.new(group)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    tb = nt.nodes.new('ShaderNodeTexImage')
    tb.image = paths['basecolor']
    to = nt.nodes.new('ShaderNodeTexImage')
    to.image = paths['orm']
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = paths['normal']
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tb.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(to.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
    nt.links.new(tn.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(mat)
    for m, _ in details.values():
        m.use_fake_user = True
    return mat


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('size', nargs='?', type=int, default=2048)
    ap.add_argument('--att-size', type=int, default=2048)
    ap.add_argument('--only', default='', help='bake only this group (ar15_weapon or ar15_attachments)')
    args = ap.parse_args(sys.argv[1:])
    size = args.size
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'))
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.render.bake.use_selected_to_active = False
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']

    def is_special(o):
        return all(s.material and s.material.name in SPECIAL for s in o.material_slots)

    def is_att(o):
        p = o.parent
        return p is not None and p.name.startswith('ar15_att_')

    weapon = [o for o in meshes if not is_att(o) and not is_special(o)]
    atts = [o for o in meshes if is_att(o) and not is_special(o)]
    if args.only in ('', 'ar15_weapon'):
        bake_group('ar15_weapon', weapon, size)
    if args.only in ('', 'ar15_attachments'):
        bake_group('ar15_attachments', atts, args.att_size)
    for m in list(bpy.data.materials):
        if m.users == 0 and not m.use_fake_user:
            bpy.data.materials.remove(m)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'weapon_ar15.blend'), compress=True)
    print('saved')


if __name__ == '__main__':
    main()
