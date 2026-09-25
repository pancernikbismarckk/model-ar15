"""Export the in-game animations of weapon_ar15 to a GTA V clip dictionary.

    python3 blender/build_anims_fivem.py --sollumz <Sollumz addon dir> --cwconv <cwconv executable>

The clips are the ones of ar15_anims.py (same poses, same timing), keyed on the real ped skeleton
and on the w_ar_ar15 skeleton of build_fivem.py, written as CodeWalker XML by Sollumz and turned
into a binary .ycd by cwconv (CodeWalker.Core).

Writes
    fivem/weapon_ar15/stream/anim@weapon_ar15.ycd
        ped     hold (loop), reload, reload_empty    upper body only: spine 1-3, neck, head,
                                                     clavicles, arms, hands, fingers
        weapon  w_reload, w_reload_empty,            the moving parts of w_ar_ar15 (bolt, trigger,
                w_fire, w_fire_last                  dust cover, bolt catch, magazine release, WAPClip)
    fivem/weapon_ar15/anim_data.lua
        what client.lua needs to draw the magazine during a reload: for every frame the magazine
        pose relative to the bone that carries it (R: seated in the rifle, on PH_R_Hand like the
        rifle itself, L: in the left hand,
        false: not shown), the frame it is let go and its velocity, the frame the left hand is
        back on the handguard.
"""
import argparse
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import ar15_anims as AN  # noqa: E402
import build_fivem as BF  # noqa: E402

DICT = 'anim@weapon_ar15'
FPS = AN.FPS
RESOURCE = BF.RESOURCE
XML_DIR = os.path.join(BF.BUILD, 'anims')

# ped bones written to the ped clips; everything else keeps the game's own animation
UPPER = ['SKEL_Spine1', 'SKEL_Spine2', 'SKEL_Spine3', 'SKEL_Neck_1', 'SKEL_Head'] \
    + [f'SKEL_{s}_{b}' for s in 'LR' for b in ('Clavicle', 'UpperArm', 'Forearm', 'Hand')] \
    + [f'SKEL_{s}_Finger{f}{j}' for s in 'LR' for f in range(5) for j in range(3)]
# the arm IK helpers stay on the hands, so an IK pass that reads them leaves the hands where they are
IK_HELPERS = ['IK_L_Hand', 'IK_R_Hand']

# clip part -> w_ar_ar15 bone and motion (same motion as ar15_anims.PART_BONES on the game rig)
WEAPON_PARTS = {
    'bolt': ('ar15_bolt', 'T', (1.0, 0.0, 0.0)),
    'trigger': ('ar15_trigger', 'R', 'Y'),
    'dustcover': ('ar15_dustcover', 'R', 'X'),
    'boltcatch': ('ar15_boltcatch', 'R', 'Y'),
    'magrelease': ('ar15_magrelease', 'T', (0.0, 1.0, 0.0)),
}


# ---------------------------------------------------------------------------
# sampling
# ---------------------------------------------------------------------------
def part_world(warm, part, value):
    """World (weapon space) matrix of the w_ar_ar15 bone that carries ``part`` at ``value``."""
    bone, kind, ax = WEAPON_PARTS[part]
    rest = warm.data.bones[bone].matrix_local
    if kind == 'T':
        return Matrix.Translation(Vector(ax) * value * AN.MM) @ rest
    head = rest.translation
    return Matrix.Translation(head) @ Matrix.Rotation(math.radians(value), 4, ax) @ Matrix.Translation(-head) @ rest


def sample(rig, clip, warm):
    """Per frame: ped local matrices (or None), weapon bone world matrices, magazine info."""
    frames = []
    for f in range(clip.frames + 1):
        fr = {'weapon': {}}
        if clip.ped:
            loc, wact, mag, miss = AN.solve(rig, clip, f)
            fr['loc'], fr['world'], fr['mag'] = loc, rig.world(loc), mag
            fr['miss'] = miss
            mag_w = wact.inverted() @ mag
        else:
            mag_w = Matrix.Translation(AN.WAPCLIP)
        for part in WEAPON_PARTS:
            tr = clip.parts.get(part)
            fr['weapon'][WEAPON_PARTS[part][0]] = part_world(warm, part, tr.value(f) if tr else 0.0)
        fr['weapon']['WAPClip'] = mag_w          # the magazine frame is the WAPClip bone
        frames.append(fr)
    return frames


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
def _new_action(ob, name, frames):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ob.animation_data_create()
    ob.animation_data.action = act
    return act


def _finish(ob, act, frames):
    act.frame_range = (0, frames)
    ob.animation_data.action = None
    for pb in ob.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)


def ped_action(ped, rig, clip, frames):
    act = _new_action(ped, clip.name, clip.frames)
    prev = {}
    pbs = ped.pose.bones
    for f, fr in enumerate(frames):
        for n in UPPER:
            q = (rig.rest[n].inverted() @ fr['loc'][n]).to_quaternion()
            if n in prev and prev[n].dot(q) < 0.0:
                q = -q
            prev[n] = q
            pbs[n].rotation_quaternion = q
            pbs[n].keyframe_insert('rotation_quaternion', frame=f, group=n)
        if f in (0, clip.frames):
            for n in IK_HELPERS:
                pbs[n].location = (0.0, 0.0, 0.0)
                pbs[n].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                pbs[n].keyframe_insert('location', frame=f, group=n)
                pbs[n].keyframe_insert('rotation_quaternion', frame=f, group=n)
    _finish(ped, act, clip.frames)
    return act


def weapon_action(warm, name, clip, frames):
    act = _new_action(warm, name, clip.frames)
    prev = {}
    for f, fr in enumerate(frames):
        for bone, m in fr['weapon'].items():
            pb = warm.pose.bones[bone]
            loc, q, _s = (warm.data.bones[bone].matrix_local.inverted() @ m).decompose()
            if bone in prev and prev[bone].dot(q) < 0.0:
                q = -q
            prev[bone] = q
            pb.location = loc
            pb.rotation_quaternion = q
            pb.keyframe_insert('location', frame=f, group=bone)
            pb.keyframe_insert('rotation_quaternion', frame=f, group=bone)
    _finish(warm, act, clip.frames)
    return act


# ---------------------------------------------------------------------------
# clip dictionary
# ---------------------------------------------------------------------------
def _empty(name, stype, parent=None):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.sollum_type = stype
    ob.parent = parent
    return ob


def _quantum(values):
    """16-bit steps over the value range. Sollumz takes the smallest step between neighbouring
    frames, which snaps sparse, jumpy tracks (the bolt cycling in 2 frames) by up to a centimetre."""
    lo, hi = min(values), max(values)
    return lo, max((hi - lo) / 65535.0, 1e-9)


def write_ycd(items, xml_path):
    """``items`` = [(clip name, action, armature object, frames)] -> CodeWalker ycd XML."""
    import Sollumz.ycd.ycdexport as ycdexport
    from Sollumz.sollumz_properties import SollumType
    from Sollumz.ycd.ycdexport import export_ycd
    ycdexport.get_quantum_and_min_val = _quantum
    cd = _empty(DICT, SollumType.CLIP_DICTIONARY)
    anims = _empty(DICT + '_animations', SollumType.ANIMATIONS, cd)
    clips = _empty(DICT + '_clips', SollumType.CLIPS, cd)
    for name, act, arm, frames in items:
        a = _empty('anim_' + name, SollumType.ANIMATION, anims)
        ap = a.animation_properties
        ap.hash = name
        ap.target_id_type = 'ARMATURE'
        ap.target_id = arm.data
        ap.action = act
        c = _empty('clip_' + name, SollumType.CLIP, clips)
        cp = c.clip_properties
        cp.hash = name
        cp.name = name + '.clip'
        cp.duration = frames / FPS
        ca = cp.animations.add()
        ca.animation = a
        ca.start_frame = 0
        ca.end_frame = frames
    os.makedirs(os.path.dirname(xml_path), exist_ok=True)
    if not export_ycd(cd, xml_path):
        raise RuntimeError('ycd export failed')


# ---------------------------------------------------------------------------
# magazine track for client.lua
# ---------------------------------------------------------------------------
def mag_track(clip, frames):
    """Magazine pose per frame relative to the bone that carries it. The magazine sits in the
    rifle until the left hand has it (grab + 1), is in the left hand until it is let go (drop),
    is not shown while the hand goes to the belt, is in the left hand again from the pouch until it
    is seated (seat + 2) and then back in the rifle."""
    grab, drop, pouch, seat = 7, 13, 21, 38
    track = []
    for f, fr in enumerate(frames):
        if f <= grab or f >= seat + 2:
            hand = 'R'
        elif f <= drop or f >= pouch:
            hand = 'L'
        else:
            track.append(None)
            continue
        h = fr['world']['PH_R_Hand' if hand == 'R' else 'SKEL_L_Hand']   # PH_R_Hand carries the rifle
        loc, q, _s = (h.inverted() @ fr['mag']).decompose()
        track.append((hand, loc, q))
    # velocity of the magazine when it is let go (ped space), then entity space: GTA's ped entity
    # faces +Y with its right side +X, the rig faces -Y with its left side +X
    v = (frames[drop]['mag'].translation - frames[drop - 1]['mag'].translation) * FPS
    return track, Vector((-v.x, -v.y, v.z)), drop


def _num(x):
    return f'{x:.5f}'.rstrip('0').rstrip('.') if abs(x) >= 5e-6 else '0'


def write_lua(path, info):
    lines = ['-- generated by blender/build_anims_fivem.py from blender/ar15_anims.py; do not edit',
             '-- mag[frame] = { hand, x, y, z, qx, qy, qz, qw }: magazine prop (w_ar_ar15_mag_prop, origin =',
             '-- the rifle\'s WAPClip) relative to PH_R_Hand (R, seated in the rifle) or SKEL_L_Hand (L),',
             '-- false = not shown. Frames are 30 per second, frame 0 = start of the clip.',
             'AR15_ANIM = {',
             f"    dict = '{DICT}',",
             f'    fps = {FPS},',
             f"    hold = {{ clip = 'hold', frames = {info['hold']['frames']} }},"]
    for name in ('reload', 'reload_empty'):
        d = info[name]
        v = d['drop_velocity']
        lines += [f'    {name} = {{',
                  f"        clip = '{name}', weapon_clip = 'w_{name}', frames = {d['frames']},",
                  f"        drop = {d['drop']}, release = {d['release']},",
                  f'        drop_velocity = {{ {_num(v.x)}, {_num(v.y)}, {_num(v.z)} }},',
                  '        mag = {']
        for f, m in enumerate(d['mag']):
            if m is None:
                lines.append(f'            [{f}] = false,')
                continue
            hand, loc, q = m
            vals = ', '.join(_num(x) for x in (loc.x, loc.y, loc.z, q.x, q.y, q.z, q.w))
            lines.append(f"            [{f}] = {{ '{hand}', {vals} }},")
        lines += ['        },', '    },']
    lines += ["    fire = { clip = 'w_fire', frames = 6 },",
              "    fire_last = { clip = 'w_fire_last', frames = 6 },",
              '}', '']
    with open(path, 'w', newline='\n') as fh:
        fh.write('\n'.join(lines))


# ---------------------------------------------------------------------------
def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--sollumz', required=True, help='Sollumz addon directory (git clone of Sollumz/Sollumz)')
    ap.add_argument('--cwconv', required=True, help='cwconv executable (tools/cwconv)')
    ap.add_argument('--weapon', default=os.path.join(ROOT, 'weapon_ar15_game.blend'))
    a = ap.parse_args(args)

    rig, ped, _game_weapon = AN.build_scene(a.weapon)       # also fits the fingers to the rifle
    bpy.context.scene.render.fps = FPS
    BF.enable_sollumz(a.sollumz)
    for b in ped.data.bones:
        b.bone_properties.tag = b['gta_tag']
    warm = BF.armature_drawable('w_ar_ar15', BF.BONES)       # the in-game weapon skeleton

    hold, reload, reload_empty = AN.make_hold(), AN.make_reload(), AN.make_reload_empty()
    fire, fire_last = AN.weapon_fire('fire'), AN.weapon_fire('fire_last', last=True)
    items, info = [], {}
    for clip in (hold, reload, reload_empty):
        frames = sample(rig, clip, warm)
        miss = max(max(fr['miss']) for fr in frames)
        print(f'  {clip.name:14s} {clip.frames:3d} frames  worst IK miss {miss * 1000:.1f} mm')
        items.append((clip.name, ped_action(ped, rig, clip, frames), ped, clip.frames))
        info[clip.name] = {'frames': clip.frames}
        if clip is not hold:
            items.append(('w_' + clip.name, weapon_action(warm, 'w_' + clip.name, clip, frames), warm, clip.frames))
            track, vel, drop = mag_track(clip, frames)
            back = 44 if clip is reload else 56          # ar15_anims._reload: hand leaves the magazine
            info[clip.name].update(mag=track, drop_velocity=vel, drop=drop, release=back + 6)
    for clip in (fire, fire_last):
        frames = sample(rig, clip, warm)
        items.append(('w_' + clip.name, weapon_action(warm, 'w_' + clip.name, clip, frames), warm, clip.frames))

    xml_path = os.path.join(XML_DIR, DICT + '.ycd.xml')
    write_ycd(items, xml_path)
    print('ycd xml', xml_path)
    subprocess.run([a.cwconv, 'xml2bin', xml_path, BF.STREAM], check=True)
    ycd = os.path.join(BF.STREAM, DICT + '.ycd')
    # unique animation signatures: the game caches animation data per signature, and Sollumz derives it
    # from the animation name (hold, reload...), which other resources' dictionaries use as well
    subprocess.run([a.cwconv, 'ycdsig', ycd, ycd, 'weapon_ar15/' + DICT], check=True)
    subprocess.run([a.cwconv, 'check', ycd], check=True)
    write_lua(os.path.join(RESOURCE, 'anim_data.lua'), info)
    print('wrote', os.path.join(RESOURCE, 'anim_data.lua'))


if __name__ == '__main__':
    main()
