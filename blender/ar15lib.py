"""Mesh-building helpers used by build_weapon_ar15.py.

All public helpers take dimensions in millimetres; geometry is written to
Blender in metres (1 BU = 1 m), so the model is at real-world scale.

Axes of the finished weapon:
    +X  towards the muzzle (bore axis)
    +Z  up
    +Y  the rifle's left side (the ejection-port side faces -Y)
Origin: X = 0 at the front face of the upper receiver, Z = 0 on the bore axis.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

S = 0.001  # millimetres -> metres

# Detail level. The high-poly source is built with lod=False; the game mesh (FiveM, <10k tris)
# is built by the same part builders with lod=True: fewer segments on revolved parts, corner
# rounding by chord tolerance, no micro-bevels, and micro details left to the baked normal map.
DETAIL = {'lod': False, 'suffix': ''}
LOD_TOL = 0.5           # mm, max chord deviation of rounded corners in the game mesh


def set_lod(on, suffix='__lod'):
    DETAIL['lod'] = bool(on)
    DETAIL['suffix'] = suffix if on else ''


def lod():
    return DETAIL['lod']


def rev_seg(seg, lod_seg=None):
    """Segments around a revolved part for the current detail level (hex/octagonal shapes kept)."""
    if not DETAIL['lod']:
        return seg
    if lod_seg:
        return lod_seg
    if seg <= 8:
        return seg
    return max(8, int(round(seg * 0.3 / 2.0)) * 2)


def arc_segs(r, turn, seg):
    """Segments of a rounded corner (radius r, turning angle in radians); 0 = keep it sharp."""
    if not DETAIL['lod']:
        return seg
    if r < 1.0:
        return 0
    c = 1.0 - LOD_TOL / r
    if c <= 0.0:
        return 1
    step = 2.0 * math.acos(c)
    return max(1, min(seg, int(math.ceil(turn / step - 1e-6))))


# ---------------------------------------------------------------------------
# 2D helpers
# ---------------------------------------------------------------------------
def fillet(pts, radii, seg=6):
    """Round the corners of a closed 2D polygon.

    pts   -- list of (a, b) tuples
    radii -- one radius for every corner, or a list (0 keeps the corner sharp)
    seg   -- arc segments per rounded corner
    """
    n = len(pts)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    out = []
    for i in range(n):
        p0 = Vector(pts[i - 1])
        p1 = Vector(pts[i])
        p2 = Vector(pts[(i + 1) % n])
        r = radii[i]
        e1 = p0 - p1
        e2 = p2 - p1
        if r <= 0 or e1.length < 1e-9 or e2.length < 1e-9:
            out.append((p1.x, p1.y))
            continue
        d1 = e1.normalized()
        d2 = e2.normalized()
        ang = math.acos(max(-1.0, min(1.0, d1.dot(d2))))
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
            out.append((p1.x, p1.y))
            continue
        t = r / math.tan(ang / 2)
        t = min(t, e1.length * 0.5, e2.length * 0.5)
        r_eff = t * math.tan(ang / 2)
        nseg = arc_segs(r_eff, math.pi - ang, seg)
        if nseg == 0:
            out.append((p1.x, p1.y))
            continue
        a = p1 + d1 * t
        b = p1 + d2 * t
        bis = (d1 + d2).normalized()
        c = p1 + bis * (r_eff / math.sin(ang / 2))
        a0 = math.atan2((a - c).y, (a - c).x)
        a1 = math.atan2((b - c).y, (b - c).x)
        da = a1 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        for k in range(nseg + 1):
            tt = a0 + da * k / nseg
            out.append((c.x + r_eff * math.cos(tt), c.y + r_eff * math.sin(tt)))
    return dedupe(out)


def dedupe(pts, eps=1e-4):
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps):
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def arc(cx, cy, r, a0, a1, seg):
    """Points on an arc, angles in degrees, inclusive of both ends."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / seg)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / seg))) for k in range(seg + 1)]


def circle(cx, cy, r, seg=24, start=0.0):
    seg = rev_seg(seg)
    return [(cx + r * math.cos(start + 2 * math.pi * k / seg),
             cy + r * math.sin(start + 2 * math.pi * k / seg)) for k in range(seg)]


def stadium(cx, cy, length, width, angle=0.0, seg=8):
    """Slot outline (rounded rectangle with full-round ends), centred on (cx, cy)."""
    r = width / 2
    h = max(length / 2 - r, 0)
    if DETAIL['lod'] and width <= 10.0:
        e = h + 0.6 * r
        pts = [(e, -r), (e, r), (-e, r), (-e, -r)]
    else:
        if DETAIL['lod']:
            seg = max(2, arc_segs(r, math.pi, seg))
        pts = arc(h, 0, r, -90, 90, seg) + arc(-h, 0, r, 90, 270, seg)
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def rrect(x0, y0, x1, y1, r, seg=4):
    return fillet([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], r, seg)


def bezier(p0, p1, p2, p3, seg=12, include_start=True):
    """Cubic Bezier sampled into seg segments."""
    out = []
    for k in range(0 if include_start else 1, seg + 1):
        t = k / seg
        mt = 1 - t
        x = mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0]
        y = mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]
        out.append((x, y))
    return out


def is_ccw(pts):
    area = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        area += x0 * y1 - x1 * y0
    return area > 0


# ---------------------------------------------------------------------------
# 3D mesh builders (return bmesh.types.BMesh in metres)
# ---------------------------------------------------------------------------
def _plane_map(plane):
    """Return f(a, b, d) -> Vector(mm->m) for a 2D profile in the given plane."""
    if plane == 'XZ':      # side profile, extruded along Y
        return lambda a, b, d: Vector((a * S, d * S, b * S))
    if plane == 'YZ':      # cross-section, extruded along X
        return lambda a, b, d: Vector((d * S, a * S, b * S))
    if plane == 'XY':      # top profile, extruded along Z
        return lambda a, b, d: Vector((a * S, b * S, d * S))
    raise ValueError(plane)


def prism(pts, plane, d0, d1, bm=None):
    """Extrude a closed 2D polygon between depths d0 and d1 (mm)."""
    own = bm is None
    if own:
        bm = bmesh.new()
    f = _plane_map(plane)
    pts = dedupe(pts)
    a = [bm.verts.new(f(p[0], p[1], d0)) for p in pts]
    b = [bm.verts.new(f(p[0], p[1], d1)) for p in pts]
    n = len(pts)
    geom = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
    for i in range(n):
        j = (i + 1) % n
        geom.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    bmesh.ops.recalc_face_normals(bm, faces=geom)
    return bm


def _arc_params(loop):
    d = [0.0]
    for i in range(1, len(loop) + 1):
        a, b = loop[i - 1], loop[i % len(loop)]
        d.append(d[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = d[-1] or 1.0
    return [x / total for x in d[:-1]], d, total


def _point_at(loop, t, d, total):
    s = t * total
    for i in range(len(loop)):
        if d[i + 1] >= s - 1e-9:
            a, b = loop[i], loop[(i + 1) % len(loop)]
            seg = d[i + 1] - d[i]
            u = 0.0 if seg < 1e-12 else (s - d[i]) / seg
            return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
    return loop[-1]


def match_loops(a, b):
    """Give two similar closed loops the same point count, pairing points by arc length."""
    if len(a) == len(b):
        return a, b
    ta, da, la = _arc_params(a)
    tb, db, lb = _arc_params(b)
    ts = sorted(set(round(t, 6) for t in ta + tb))
    return ([_point_at(a, t, da, la) for t in ts], [_point_at(b, t, db, lb) for t in ts])


def tube_prism(outer, inner, plane, d0, d1, bm=None):
    """Extrude a 2D ring given by an outer and an inner loop (paired by arc length)."""
    own = bm is None
    if own:
        bm = bmesh.new()
    f = _plane_map(plane)
    outer, inner = match_loops(dedupe(outer), dedupe(inner))
    n = len(outer)
    oa = [bm.verts.new(f(p[0], p[1], d0)) for p in outer]
    ob = [bm.verts.new(f(p[0], p[1], d1)) for p in outer]
    ia = [bm.verts.new(f(p[0], p[1], d0)) for p in inner]
    ib = [bm.verts.new(f(p[0], p[1], d1)) for p in inner]
    geom = []
    for i in range(n):
        j = (i + 1) % n
        geom.append(bm.faces.new((oa[i], oa[j], ob[j], ob[i])))
        geom.append(bm.faces.new((ib[i], ib[j], ia[j], ia[i])))
        geom.append(bm.faces.new((oa[j], oa[i], ia[i], ia[j])))
        geom.append(bm.faces.new((ob[i], ob[j], ib[j], ib[i])))
    bmesh.ops.recalc_face_normals(bm, faces=geom)
    return bm


def lathe(profile, seg=32, bm=None, axis='X', center=(0.0, 0.0), phase=0.0, closed=False, lod_seg=None,
          caps=True):
    """Revolve a profile of (axial, radius) points (mm) around an axis.

    The profile is an open polyline from one end of the part to the other;
    points with radius 0 become poles, otherwise the ends are capped.
    closed=True treats the profile as a loop (hollow parts such as rings).
    axis 'X' revolves around the X axis through (Y, Z) = center.
    axis 'Y' revolves around a Y-parallel axis through (X, Z) = center.
    axis 'Z' revolves around a Z-parallel axis through (X, Y) = center.
    """
    own = bm is None
    if own:
        bm = bmesh.new()
    seg = rev_seg(seg, lod_seg)

    def P(ax, r, t):
        c, s = math.cos(t), math.sin(t)
        if axis == 'X':
            return Vector((ax * S, (center[0] + r * c) * S, (center[1] + r * s) * S))
        if axis == 'Y':
            return Vector(((center[0] + r * c) * S, ax * S, (center[1] + r * s) * S))
        return Vector(((center[0] + r * c) * S, (center[1] + r * s) * S, ax * S))

    rings = []
    for ax, r in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new(P(ax, 0, 0))])
        else:
            rings.append([bm.verts.new(P(ax, r, phase + 2 * math.pi * k / seg)) for k in range(seg)])
    geom = []
    pairs = list(range(len(rings) - 1))
    if closed:
        rings.append(rings[0])
        pairs.append(len(rings) - 2)
    for i in pairs:
        r0, r1 = rings[i], rings[i + 1]
        if len(r0) == 1 and len(r1) == 1:
            continue
        for k in range(seg):
            k2 = (k + 1) % seg
            if len(r0) == 1:
                geom.append(bm.faces.new((r0[0], r1[k2], r1[k])))
            elif len(r1) == 1:
                geom.append(bm.faces.new((r0[k], r0[k2], r1[0])))
            else:
                geom.append(bm.faces.new((r0[k], r0[k2], r1[k2], r1[k])))
    if caps and not closed and len(rings[0]) > 1:
        geom.append(bm.faces.new(list(reversed(rings[0]))))
    if caps and not closed and len(rings[-1]) > 1:
        geom.append(bm.faces.new(rings[-1]))
    if caps:
        bmesh.ops.recalc_face_normals(bm, faces=geom)
    return bm


def cylinder(p0, p1, r, seg=24, bm=None, r1=None, lod_seg=None):
    """Closed cylinder (or cone when r1 is given) between two points (mm)."""
    own = bm is None
    if own:
        bm = bmesh.new()
    p0 = Vector(p0)
    p1 = Vector(p1)
    L = (p1 - p0).length
    tmp = lathe([(0, r), (L, r if r1 is None else r1)], seg=seg, axis='Z', lod_seg=lod_seg)
    rot = Vector((0, 0, 1)).rotation_difference((p1 - p0).normalized()).to_matrix().to_4x4()
    tmp.transform(Matrix.Translation(p0 * S) @ rot)
    merge(bm, tmp)
    return bm


def box(x0, y0, z0, x1, y1, z1, bm=None):
    return prism([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], 'XZ', y0, y1, bm=bm)


def sphere(c, r, seg=16, rings=8, bm=None):
    own = bm is None
    if own:
        bm = bmesh.new()
    tmp = bmesh.new()
    if DETAIL['lod']:
        seg, rings = rev_seg(seg), max(4, rings // 2)
    bmesh.ops.create_uvsphere(tmp, u_segments=seg, v_segments=rings, radius=r * S)
    tmp.transform(Matrix.Translation(Vector(c) * S))
    merge(bm, tmp)
    return bm


def merge(dst, src):
    """Append the geometry of bmesh src into dst (src is freed)."""
    me = bpy.data.meshes.new('_tmp_merge')
    src.to_mesh(me)
    src.free()
    dst.from_mesh(me)
    bpy.data.meshes.remove(me)
    return dst


def xform(bm, mat):
    bm.transform(mat)
    return bm


def rot_about(axis, deg, pivot_mm):
    """4x4 rotation about a world axis passing through pivot (mm)."""
    p = Vector(pivot_mm) * S
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-p)


def mirror_y(bm):
    """Mirror geometry across the XZ plane (Y -> -Y), keeping normals valid."""
    bm.transform(Matrix.Scale(-1, 4, Vector((0, 1, 0))))
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return bm


def copy_bm(bm):
    return bm.copy()


# ---------------------------------------------------------------------------
# Objects, modifiers and materials
# ---------------------------------------------------------------------------
_COLL = {'c': None}


def set_collection(coll):
    _COLL['c'] = coll


def mk(name, bm, mat=None, clean=True):
    if clean:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    if not name.startswith('_'):
        name = name + DETAIL['suffix']
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (_COLL['c'] or bpy.context.scene.collection).objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    return ob


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ob_eval = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = ob.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def boolean(ob, cutter, op='DIFFERENCE', solver='EXACT', keep=False, use_self=True, mat=None):
    """Apply a boolean with another object or with a raw bmesh."""
    tmp_created = False
    if isinstance(cutter, bmesh.types.BMesh):
        cutter = mk('_cutter', cutter, mat)
        tmp_created = True
    cutter.hide_render = True
    m = ob.modifiers.new('bool', 'BOOLEAN')
    m.operation = op
    m.object = cutter
    m.solver = solver
    if solver == 'EXACT':
        m.use_hole_tolerant = False
        m.use_self = use_self
    if mat is not None:
        m.material_mode = 'TRANSFER'
    apply_mods(ob)
    if tmp_created or not keep:
        me = cutter.data
        bpy.data.objects.remove(cutter)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return ob


def bevel(ob, width, seg=2, angle=30.0, profile=0.5, harden=False, clamp=True, apply=True):
    if DETAIL['lod']:
        return ob       # edge rounding comes from the baked normal map
    m = ob.modifiers.new('bevel', 'BEVEL')
    m.width = width * S
    m.segments = seg
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.use_clamp_overlap = clamp
    m.harden_normals = harden
    m.miter_outer = 'MITER_ARC'
    if apply:
        apply_mods(ob)
    return ob


def smooth(ob, angle=32.0, weighted=True):
    """Smooth shading with sharp edges by angle (+ optional weighted normals)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    if DETAIL['lod']:
        angle = 60.0    # hard edges only where the UV unwrap also splits (smart project 60 deg)
    lim = math.radians(angle)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < lim
        else:
            e.smooth = False
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    if weighted:
        m = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
        m.keep_sharp = True
        m.weight = 50
        m.mode = 'FACE_AREA'
        apply_mods(ob)
    return ob


def material(name, color, metallic=0.0, roughness=0.5, coat=0.0, spec=0.5):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = coat
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = spec
    m.diffuse_color = (*color, 1.0)
    m.metallic = metallic
    m.roughness = roughness
    return m


def set_origin(ob, pivot_mm):
    """Move the object origin to pivot (mm, world space) without moving the mesh."""
    p = Vector(pivot_mm) * S
    ob.data.transform(Matrix.Translation(-p))
    ob.location = ob.location + p
    return ob


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = par.matrix_world.inverted()
    return child


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def hexahedron(bottom, top, bm=None):
    """Closed 6-sided solid from two quads of (x, y, z) mm points (same winding)."""
    own = bm is None
    if own:
        bm = bmesh.new()
    vb = [bm.verts.new(Vector(p) * S) for p in bottom]
    vt = [bm.verts.new(Vector(p) * S) for p in top]
    geom = [bm.faces.new(vb), bm.faces.new(list(reversed(vt)))]
    for i in range(4):
        j = (i + 1) % 4
        geom.append(bm.faces.new((vb[i], vb[j], vt[j], vt[i])))
    bmesh.ops.recalc_face_normals(bm, faces=geom)
    return bm


def ob_to_bm(ob, delete=True):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    if delete:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return bm


def bm_intersect(a, b):
    """Boolean intersection of two bmeshes, returned as a new bmesh."""
    tmp = mk('_isect', a)
    boolean(tmp, b, op='INTERSECT')
    return ob_to_bm(tmp)


def checkered_material(name, color, roughness=0.6, pitch_mm=1.25, strength=0.8):
    """Polymer with procedural pyramid checkering (bump), used on grip panels."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = material(name, color, 0.0, roughness)
    nt = m.node_tree
    N = nt.nodes
    Lk = nt.links
    bsdf = N.get('Principled BSDF')
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0.0, math.radians(45.0), 0.0)
    mp.inputs['Scale'].default_value = (1.0 / (pitch_mm * S),) * 3
    Lk.new(tc.outputs['Object'], mp.inputs['Vector'])
    sep = N.new('ShaderNodeSeparateXYZ')
    Lk.new(mp.outputs['Vector'], sep.inputs['Vector'])

    def tri(sock):
        fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'
        Lk.new(sock, fr.inputs[0])
        sub = N.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'
        sub.inputs[1].default_value = 0.5
        Lk.new(fr.outputs[0], sub.inputs[0])
        ab = N.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'
        Lk.new(sub.outputs[0], ab.inputs[0])
        return ab.outputs[0]

    mn = N.new('ShaderNodeMath'); mn.operation = 'MINIMUM'
    Lk.new(tri(sep.outputs['X']), mn.inputs[0])
    Lk.new(tri(sep.outputs['Z']), mn.inputs[1])
    bump = N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = 0.0006
    Lk.new(mn.outputs[0], bump.inputs['Height'])
    Lk.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def _offset_rings(outline, offsets, n):
    """Resample an outline to n points and project it onto inward offset curves."""
    from shapely.geometry import Point, Polygon
    poly = Polygon(outline)
    if not poly.exterior.is_ccw:
        poly = Polygon(list(reversed(outline)))
    base = poly.exterior
    if isinstance(n, int):
        L0 = base.length
        samples = [base.interpolate(L0 * j / n) for j in range(n)]
    else:
        # adaptive: keep the outline's own vertices, split edges longer than n (mm)
        coords = list(base.coords)[:-1]
        samples = []
        for i, (a0, b0) in enumerate(coords):
            a1, b1 = coords[(i + 1) % len(coords)]
            seglen = math.hypot(a1 - a0, b1 - b0)
            k = max(1, int(math.ceil(seglen / n)))
            for j in range(k):
                samples.append(Point(a0 + (a1 - a0) * j / k, b0 + (b1 - b0) * j / k))
    rings = []
    for d in offsets:
        if d <= 1e-6:
            rings.append([(p.x, p.y) for p in samples])
            continue
        g = poly.buffer(-d, join_style='round', quad_segs=12)
        if g.geom_type == 'MultiPolygon':
            g = max(g.geoms, key=lambda q: q.area)
        ext = g.exterior
        pts = []
        for p in samples:
            q = ext.interpolate(ext.project(Point(p.x, p.y)))
            pts.append((q.x, q.y))
        rings.append(pts)
    return rings


def rounded_prism(outline, plane, d0, d1, r0, r1=None, seg=6, n=2.0, bm=None, lod_seg=1):
    """Extrude a 2D outline between depths d0 < d1 with rounded (quarter-round) cap edges.

    r0 / r1 are the rounding radii at the d0 / d1 caps.  The outline is offset
    robustly (shapely), so tight convex corners simply sharpen instead of
    self-intersecting the way a large bevel would.  n is either a fixed ring
    resolution (int) or the maximum edge length in mm (float, adaptive).
    """
    r1 = r0 if r1 is None else r1
    own = bm is None
    if own:
        bm = bmesh.new()
    if DETAIL['lod']:
        seg = lod_seg
        n = 1000.0          # straight edges stay single segments
        outline = simplify_outline(outline, 0.3)
    f = _plane_map(plane)
    prof = []   # (offset, depth) from the d0 cap to the d1 cap
    for k in range(seg + 1):
        t = math.radians(90.0 * (seg - k) / seg)
        prof.append((r0 * (1 - math.cos(t)), d0 + r0 * (1 - math.sin(t))))
    for k in range(seg + 1):
        t = math.radians(90.0 * k / seg)
        prof.append((r1 * (1 - math.cos(t)), d1 - r1 * (1 - math.sin(t))))
    rings2d = _offset_rings(outline, [o for o, _ in prof], n)
    rings = []
    for (o, d), r2 in zip(prof, rings2d):
        rings.append([bm.verts.new(f(a, b, d)) for a, b in r2])
    geom = []
    cnt = len(rings[0])
    for i in range(len(rings) - 1):
        ra, rb = rings[i], rings[i + 1]
        for j in range(cnt):
            k = (j + 1) % cnt
            try:
                geom.append(bm.faces.new((ra[j], ra[k], rb[k], rb[j])))
            except ValueError:
                pass
    geom.append(bm.faces.new(list(reversed(rings[0]))))
    geom.append(bm.faces.new(rings[-1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def inset_outline(outline, d):
    """Inward offset of a 2D outline (list of points), largest piece only."""
    from shapely.geometry import Polygon
    g = Polygon(outline).buffer(-d, join_style='round', quad_segs=8)
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda q: q.area)
    return list(g.exterior.coords)[:-1]


def clip_outline(outline, box2d):
    """Intersection of a 2D outline with an axis-aligned box (a0, b0, a1, b1)."""
    from shapely.geometry import Polygon, box as sbox
    g = Polygon(outline).intersection(sbox(*box2d))
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda q: q.area)
    return list(g.exterior.coords)[:-1]


def emissive_material(name, color, strength, base=None, roughness=0.2, metallic=0.0):
    m = material(name, base or color, metallic, roughness)
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Emission Color'].default_value = (*color, 1.0)
    b.inputs['Emission Strength'].default_value = strength
    return m


def glass_material(name, color=(0.86, 0.93, 0.92), alpha=0.16, roughness=0.04):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = material(name, color, 0.0, roughness)
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Alpha'].default_value = alpha
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        m.blend_method = 'BLEND'
    m.use_backface_culling = False
    return m


def mirror_x(ob, xc_mm):
    """Mirror an object's mesh front-to-back about the plane x = xc (mm), keeping normals outward."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    xc = xc_mm * S
    bm.transform(Matrix.Translation((xc, 0, 0)) @ Matrix.Scale(-1, 4, Vector((1, 0, 0))) @
                 Matrix.Translation((-xc, 0, 0)))
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def simplify_outline(pts, tol):
    """Douglas-Peucker simplification of a closed 2D outline (keeps its topology)."""
    from shapely.geometry import Polygon
    g = Polygon(pts)
    if not g.is_valid:
        return pts
    h = g.simplify(tol, preserve_topology=True)
    if h.is_empty or h.geom_type != 'Polygon':
        return pts
    return list(h.exterior.coords)[:-1]
