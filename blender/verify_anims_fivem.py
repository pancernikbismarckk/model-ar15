"""Check stream/anim@weapon_ar15.ycd against the poses of ar15_anims.py.

    python3 blender/verify_anims_fivem.py --cwconv <cwconv executable>

The binary clip dictionary is converted back to XML with CodeWalker.Core, every channel is decoded
and the ped / weapon skeletons are posed from it the way the game does (bone local = rest
translation (or the position track) and the rotation track, parents first). The hands, the fingertips,
the head, the rifle held in the right hand and the moving parts of the rifle are compared with the
poses the clips were made from.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402,F401
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import ar15_anims as AN  # noqa: E402
import build_anims_fivem as X  # noqa: E402
import build_fivem as BF  # noqa: E402
import ped_anim as A  # noqa: E402
import ped_rig as R  # noqa: E402

RT = os.path.join(BF.BUILD, 'roundtrip_anims')


def decode_channel(ch, frames):
    t = ch.find('Type').get('value')
    if t == 'StaticFloat':
        return [float(ch.find('Value').get('value'))] * frames
    if t == 'QuantizeFloat':
        vals = [float(v) for v in ch.find('Values').text.split()]
        return vals
    if t == 'IndirectQuantizeFloat':
        pal = [float(v) for v in ch.find('Values').text.split()]
        idx = [int(v) for v in ch.find('Frames').text.split()]
        return [pal[i] for i in idx]
    if t == 'RawFloat':
        return [float(v) for v in ch.find('Values').text.split()]
    raise ValueError('channel type ' + t)


def decode_ycd(path):
    """{animation hash: (frame count, {(bone tag, track): [values per frame]})}"""
    root = ET.parse(path).getroot()
    out = {}
    for an in root.find('Animations'):
        name = an.findtext('Hash')
        frames = int(an.find('FrameCount').get('value'))
        ids = [(int(i.find('BoneId').get('value')), int(i.find('Track').get('value'))) for i in an.find('BoneIds')]
        seq = an.find('Sequences')[0]
        tracks = {}
        for key, sd in zip(ids, seq.find('SequenceData')):
            chans = list(sd.find('Channels'))
            if len(chans) == 1 and chans[0].find('Type').get('value') in ('StaticVector3', 'StaticQuaternion'):
                v = chans[0].find('Value')
                comps = [float(v.get(c)) for c in ('x', 'y', 'z', 'w') if v.get(c) is not None]
                tracks[key] = [tuple(comps)] * frames
            else:
                cols = [decode_channel(c, frames) for c in chans]
                assert all(len(c) == frames for c in cols), (name, key)
                tracks[key] = list(zip(*cols))
        out[name] = (frames, tracks)
    return out


def pose_from_tracks(skel, rest, tracks, f):
    """Local matrices of every bone at frame ``f`` (tag-keyed tracks, 0 = position, 1 = rotation)."""
    local = {}
    for n, _p, tag, t, q in skel:
        tr = tracks.get((tag, 0))
        rq = tracks.get((tag, 1))
        pos = Vector(tr[f]) if tr else rest[n].translation
        rot = Quaternion((rq[f][3], rq[f][0], rq[f][1], rq[f][2])) if rq else rest[n].to_quaternion()
        m = rot.normalized().to_matrix().to_4x4()
        m.translation = pos
        local[n] = m
    return local


def compare(a, b):
    """Position error (m) and rotation error (deg) between two matrices."""
    dp = (a.translation - b.translation).length
    qa, qb = a.to_quaternion(), b.to_quaternion()
    d = min(1.0, abs(qa.dot(qb)))
    return dp, math.degrees(2.0 * math.acos(d))


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--cwconv', required=True)
    ap.add_argument('--weapon', default=os.path.join(os.path.dirname(HERE), 'weapon_ar15_game.blend'))
    a = ap.parse_args(args)

    # the skeleton subset must keep every bone's real parent, or the rest locals would be wrong
    raw = json.load(open(R.SKELETON_JSON))
    by_idx = {b[0]: b for b in raw}
    keep = set(R.BODY)
    for idx, name, parent, *_ in raw:
        if name in keep and parent >= 0:
            assert by_idx[parent][1] in keep, f'{name}: parent {by_idx[parent][1]} not in the rig'

    ycd = os.path.join(BF.STREAM, X.DICT + '.ycd')
    os.makedirs(RT, exist_ok=True)
    subprocess.run([a.cwconv, 'bin2xml', ycd, RT], check=True, stdout=subprocess.DEVNULL)
    anims = decode_ycd(os.path.join(RT, X.DICT + '.ycd.xml'))
    print('animations:', ', '.join(f'{k} ({v[0]} frames, {len(v[1])} tracks)' for k, v in sorted(anims.items())))

    rig, ped, _w = AN.build_scene(a.weapon)
    skel = rig.skel
    wbones = {n: (Vector(h) * AN.MM, p, r) for n, h, p, r in BF.BONES}
    wrest_world = {}
    for n, (h, p, r) in wbones.items():
        m = (r.to_matrix().to_4x4() if r is not None else Matrix.Identity(4))
        m.translation = h
        wrest_world[n] = m
    wtag = {n: (0 if p is None else BF.elf_tag(n)) for n, (h, p, r) in wbones.items()}

    # a stand-in armature only to sample part_world() with the same rest matrices as the export
    class _B:
        def __init__(self, m):
            self.matrix_local = m

    class _Arm:
        pass
    warm = _Arm()
    warm.data = _Arm()
    warm.data.bones = {n: _B(m) for n, m in wrest_world.items()}

    checks = {'hands': ['SKEL_L_Hand', 'SKEL_R_Hand', 'PH_R_Hand', 'SKEL_Head'],
              'tips': [f'SKEL_{s}_Finger{f}2' for s in 'LR' for f in range(5)]}
    worst = {}
    clips = [AN.make_hold(), AN.make_reload(), AN.make_reload_empty(),
             AN.weapon_fire('fire'), AN.weapon_fire('fire_last', last=True)]
    for clip in clips:
        frames = X.sample(rig, clip, warm)
        if clip.ped:
            n_frames, tracks = anims[clip.name]
            assert n_frames == clip.frames + 1, (clip.name, n_frames)
            for f, fr in enumerate(frames):
                got = rig.world(pose_from_tracks(skel, rig.rest, tracks, f))
                want = fr['world']
                for group, bones in checks.items():
                    for b in bones:
                        dp, da = compare(got[b], want[b])
                        k = (clip.name, group)
                        worst[k] = (max(worst.get(k, (0, 0))[0], dp), max(worst.get(k, (0, 0))[1], da))
                # the rifle follows the right hand exactly like the game attaches it
                dp, da = compare(got['PH_R_Hand'] @ A.GRIP_R.inverted(), want['PH_R_Hand'] @ A.GRIP_R.inverted())
                k = (clip.name, 'rifle')
                worst[k] = (max(worst.get(k, (0, 0))[0], dp), max(worst.get(k, (0, 0))[1], da))
        if clip.name == 'hold':
            continue
        wname = 'w_' + clip.name
        n_frames, tracks = anims[wname]
        assert n_frames == clip.frames + 1, (wname, n_frames)
        for f, fr in enumerate(frames):
            for bone, want in fr['weapon'].items():
                tag = wtag[bone]
                tp, tr = tracks[(tag, 0)][f], tracks[(tag, 1)][f]
                local = Quaternion((tr[3], tr[0], tr[1], tr[2])).normalized().to_matrix().to_4x4()
                local.translation = Vector(tp)
                got = wrest_world['Gun_Main_Bone'] @ local          # parent of every animated bone
                dp, da = compare(got, want)
                k = (wname, bone)
                worst[k] = (max(worst.get(k, (0, 0))[0], dp), max(worst.get(k, (0, 0))[1], da))
    bad = False
    for (clip, what), (dp, da) in sorted(worst.items()):
        ok = dp < 0.003 and da < 1.0
        bad |= not ok
        print(f'  {clip:15s} {what:16s} max {dp * 1000:6.2f} mm {da:6.2f} deg  {"ok" if ok else "MISMATCH"}')
    if bad:
        sys.exit('mismatch between the .ycd and the authored poses')
    print('all clips match the authored poses')


if __name__ == '__main__':
    main()
