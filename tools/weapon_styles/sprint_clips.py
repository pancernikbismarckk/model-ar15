"""The sprint of the KTWR 'sprint:' variants as one upper-body clip each (stream/ktwr_sprint.ycd).

A variant differs from its base style only in the sprint clip, and that clip moves only the right arm:
in single player the game plays it over the unarmed sprint, so the left arm pumps. On FiveM the style
gets on the ped with SET_PED_WEAPON_MOVEMENT_CLIPSET, which the game does not use for the rifle sprint
(it keeps its own two-handed sprint, the same as the KTWR base styles' sprint). client/main.lua plays
these clips over it instead (TaskPlayAnim, upper body, tag-synced with the steps), so each clip has
both arms:

  right arm   the variant's own sprint (arm, hand, prop helpers, fingers), unchanged
  left arm    a sprint arm swing written here: forward on the right heel strike and back on the left
              one (the clips' foot tags), elbow bent, loose hand (the fingers of the base sprint grip)
"""
import copy
import json
import math
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SKELETON = os.path.join(ROOT, 'blender', 'data_ped_skeleton.json')    # mp_m_freemode_01, rot = (w, x, y, z)

DICT = 'ktwr_sprint'
ARM, FINGERS = 'hash_17BE6A07', 'hash_B440230C'    # the two animations of every KTWR rifle sprint clip
LEFT = ('SKEL_L_', 'IK_L_', 'PH_L_')

# the swing (degrees): shoulder flexion forward of hanging, elbow flexion, arm out to the side,
# forearm turned towards the body in front, hand turned so that the palm faces the body
SWING = dict(flex_mid=5.0, flex_amp=35.0, elbow_mid=86.0, elbow_amp=16.0, abduct=10.0, inward=18.0,
             hand_twist=-100.0)
# phases of the foot tags of the KTWR sprint clips: left arm forward (+1) on the right heel strike
SWING_KEYS = [(-0.027, -1.0), (0.216, 1.0), (0.459, -1.0), (0.703, 1.0), (0.973, -1.0), (1.216, 1.0)]

# FK frame of the skeleton file: the ped faces -Y, +X is its left, +Z up
FWD, UP, LEFT_AXIS = np.array([0.0, -1.0, 0.0]), np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])


# ------------------------------------------------------------------------------------------------
# rotations
# ------------------------------------------------------------------------------------------------
def qmat(w, x, y, z):
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def mat2q(R):
    """rotation matrix -> animation quaternion (x, y, z, w), w >= 0"""
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = [0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s]
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = [(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s]
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = [(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s]
    q = np.array(q)
    q /= np.linalg.norm(q)
    return q if q[3] >= 0 else -q


class Skeleton:
    def __init__(self, path=SKELETON):
        self.bones = json.load(open(path))                # [idx, name, parent, tag, trans, rot(w,x,y,z)]
        self.by_name = {b[1]: b for b in self.bones}
        self.name = {b[3]: b[1] for b in self.bones}

    def tag(self, name):
        return self.by_name[name][3]

    def bind_q(self, name):
        w, x, y, z = self.by_name[name][5]
        return mat2q(qmat(w, x, y, z))

    def fk(self, tracks):
        """world matrices; tracks: (tag, 0 | 1) -> translation / (x, y, z, w) rotation"""
        world = {}
        for idx, name, parent, tag, trans, rot in self.bones:
            R = qmat(*rot)
            T = np.array(trans, float)
            if (tag, 1) in tracks:
                x, y, z, w = tracks[(tag, 1)][:4]
                R = qmat(w, x, y, z)
            if (tag, 0) in tracks:
                T = np.array(tracks[(tag, 0)][:3], float)
            M = np.eye(4)
            M[:3, :3] = R
            M[:3, 3] = T
            world[name] = world[self.bones[parent][1]] @ M if parent >= 0 else M
        return world


# ------------------------------------------------------------------------------------------------
# the left arm swing
# ------------------------------------------------------------------------------------------------
def swing(phase):
    """-1 (arm back) .. +1 (arm forward) at a phase of the clip, eased between the foot tags"""
    for (p0, v0), (p1, v1) in zip(SWING_KEYS, SWING_KEYS[1:]):
        if p0 <= phase <= p1:
            u = 0.5 - 0.5 * math.cos(math.pi * (phase - p0) / (p1 - p0))
            return v0 + (v1 - v0) * u
    raise ValueError(phase)


def left_arm(skel, phase, p=SWING):
    """(upper arm, forearm) local rotations (x, y, z, w) at a phase; the clavicle keeps its bind pose"""
    s = swing(phase)
    th = math.radians(p['flex_mid'] + p['flex_amp'] * s)
    el = math.radians(p['elbow_mid'] + p['elbow_amp'] * s)
    ab = math.radians(p['abduct'])
    tw = math.radians(p['inward'] * (0.5 + 0.5 * s))
    D = -UP * math.cos(th) + FWD * math.sin(th)           # upper arm (the bone's X axis)
    P = FWD * math.cos(th) + UP * math.sin(th)            # the way the elbow bends (the bone's Y axis)
    D = D * math.cos(ab) + LEFT_AXIS * math.sin(ab)
    D /= np.linalg.norm(D)
    P -= np.dot(P, D) * D
    P /= np.linalg.norm(P)
    Z = np.cross(D, P)
    P, Z = P * math.cos(tw) + Z * math.sin(tw), Z * math.cos(tw) - P * math.sin(tw)
    clav = skel.fk({})['SKEL_L_Clavicle'][:3, :3]
    upper = mat2q(clav.T @ np.column_stack([D, P, Z]))
    forearm = np.array([0.0, 0.0, math.sin(el / 2), math.cos(el / 2)])   # the elbow turns about the local Z
    return upper, forearm


# ------------------------------------------------------------------------------------------------
# CodeWalker XML
# ------------------------------------------------------------------------------------------------
def _val(parent, tag, value):
    ET.SubElement(parent, tag, value=value)


def _fmt(v):
    return repr(float(np.float32(v)))


def _channels_quantized(cols):
    """one QuantizeFloat channel per column (list of floats)"""
    out = []
    for col in cols:
        lo, hi = min(col), max(col)
        c = ET.Element('Item')
        _val(c, 'Type', 'QuantizeFloat')
        q = max((hi - lo) / 65535.0, 1e-7)
        _val(c, 'Quantum', _fmt(q))
        _val(c, 'Offset', _fmt(lo))
        ET.SubElement(c, 'Values').text = ' '.join(_fmt(lo + round((v - lo) / q) * q) for v in col)
        out.append(c)
    return out


def _channel_static_quat(q):
    c = ET.Element('Item')
    _val(c, 'Type', 'StaticQuaternion')
    ET.SubElement(c, 'Value', x=_fmt(q[0]), y=_fmt(q[1]), z=_fmt(q[2]), w=_fmt(q[3]))
    return c


def _animation(name, frames, duration, limit, flags, tracks):
    """tracks: [(bone tag, track, unk0, [channel elements])]"""
    a = ET.Element('Item')
    ET.SubElement(a, 'Hash').text = name
    _val(a, 'Unknown10', str(flags))
    _val(a, 'FrameCount', str(frames))
    _val(a, 'SequenceFrameLimit', str(limit))
    _val(a, 'Duration', _fmt(duration))
    ET.SubElement(a, 'Unknown1C').text = name + '_sig'
    seqs = ET.SubElement(a, 'Sequences')
    seq = ET.SubElement(seqs, 'Item')
    ET.SubElement(seq, 'Hash').text = name + '_seq'
    _val(seq, 'FrameCount', str(frames))
    data = ET.SubElement(seq, 'SequenceData')
    ids = ET.SubElement(a, 'BoneIds')
    for bone, track, unk0, chans in sorted(tracks, key=lambda t: (t[1], t[0])):
        sd = ET.SubElement(data, 'Item')
        ET.SubElement(sd, 'Channels').extend(chans)
        b = ET.SubElement(ids, 'Item')
        _val(b, 'BoneId', str(bone))
        _val(b, 'Track', str(track))
        _val(b, 'Unk0', str(unk0))
    return a


def _filtered(anim, name, keep):
    """a copy of an animation with only the tracks keep(bone tag, track) accepts"""
    a = copy.deepcopy(anim)
    a.find('Hash').text = name
    a.find('Unknown1C').text = name + '_sig'
    ids = a.find('BoneIds')
    items = list(ids)
    mask = [keep(int(i.find('BoneId').get('value')), int(i.find('Track').get('value'))) for i in items]
    for i, k in zip(items, mask):
        if not k:
            ids.remove(i)
    for n, seq in enumerate(a.find('Sequences')):
        seq.find('Hash').text = f'{name}_seq{n}'
        data = seq.find('SequenceData')
        for sd, k in zip(list(data), mask):
            if not k:
                data.remove(sd)
    return a


def _chan_values(ch, frames):
    t = ch.find('Type').get('value')
    if t == 'StaticFloat':
        return [float(ch.find('Value').get('value'))] * frames
    if t in ('QuantizeFloat', 'RawFloat', 'LinearFloat'):
        return [float(x) for x in ch.find('Values').text.split()]
    if t == 'IndirectQuantizeFloat':
        pal = [float(x) for x in ch.find('Values').text.split()]
        return [pal[int(i)] for i in ch.find('Frames').text.split()]
    raise ValueError('channel type ' + t)


def track_values(anim, bone, track):
    """per-frame values of one track of a CodeWalker XML animation (rotations as (x, y, z, w))"""
    frames = int(anim.find('FrameCount').get('value'))
    for i, sd in zip(anim.find('BoneIds'), anim.find('Sequences')[0].find('SequenceData')):
        if (int(i.find('BoneId').get('value')), int(i.find('Track').get('value'))) != (bone, track):
            continue
        chans = list(sd.find('Channels'))
        t0 = chans[0].find('Type').get('value')
        if t0 in ('StaticQuaternion', 'StaticVector3'):
            v = chans[0].find('Value')
            return [tuple(float(v.get(c)) for c in 'xyzw' if v.get(c) is not None)] * frames
        if chans[-1].find('Type').get('value').startswith('CachedQuaternion'):
            cols = [_chan_values(c, frames) for c in chans[:3]]
            cols.append([math.sqrt(max(0.0, 1 - a * a - b * b - c * c)) for a, b, c in zip(*cols)])
        else:
            cols = [_chan_values(c, frames) for c in chans]
        return list(zip(*cols))
    return None


def _clip(src_clip, name, parts):
    """the variant's sprint clip (foot tags, properties, duration) playing parts [(anim, start, end, rate)]"""
    c = copy.deepcopy(src_clip)
    c.find('Hash').text = name
    c.find('Name').text = f'pack:/{name}.clip'
    anims = c.find('Animations')
    for it in list(anims):
        anims.remove(it)
    for anim, start, end, rate in parts:
        it = ET.SubElement(anims, 'Item')
        ET.SubElement(it, 'AnimationHash').text = anim
        _val(it, 'StartTime', _fmt(start))
        _val(it, 'EndTime', _fmt(end))
        _val(it, 'Rate', _fmt(rate))
    return c


# ------------------------------------------------------------------------------------------------
def build(cw, variants, base, out_ycd, salt):
    """variants: {style id: KTWR rifle dictionary bytes}; base: a base style's dictionary (fingers of
    the left hand); writes out_ycd with a clip per style id. Returns {style id: clip name}."""
    skel = Skeleton()
    tmp = tempfile.mkdtemp()

    def to_xml(data, name):
        p = os.path.join(tmp, name + '.ycd')
        open(p, 'wb').write(data)
        subprocess.run([cw, 'bin2xml', p, tmp], check=True, stdout=subprocess.DEVNULL)
        return ET.parse(p + '.xml').getroot()

    def anims_clips(root):
        return ({a.findtext('Hash'): a for a in root.find('Animations')},
                {c.findtext('Hash'): c for c in root.find('Clips')})

    # the left hand: the base sprint's finger pose (a loose grip), the first frame
    b_anims, _ = anims_clips(to_xml(base, 'base'))
    fingers_left = []
    for b in skel.bones:
        if b[1].startswith('SKEL_L_Finger'):
            v = track_values(b_anims[FINGERS], b[3], 1)
            if v is None:
                raise SystemExit(f'{b[1]}: no rotation in the base sprint')
            fingers_left.append((b[3], np.array(v[0]) / np.linalg.norm(v[0])))

    root = ET.Element('ClipDictionary')
    clips_el, anims_el = ET.SubElement(root, 'Clips'), ET.SubElement(root, 'Animations')
    pump_added = False
    out, src_arms = {}, {}
    for sid in sorted(variants):
        v_anims, v_clips = anims_clips(to_xml(variants[sid], sid))
        sprint = v_clips['sprint']
        parts = {x.findtext('AnimationHash'): (float(x.find('StartTime').get('value')),
                                                float(x.find('EndTime').get('value')),
                                                float(x.find('Rate').get('value')))
                 for x in sprint.find('Animations')}
        if set(parts) != {ARM, FINGERS}:
            raise SystemExit(f'{sid}: unexpected sprint clip {sorted(parts)}')
        arm = v_anims[ARM]
        if not pump_added:
            frames = int(arm.find('FrameCount').get('value'))
            dur = float(arm.find('Duration').get('value'))
            loop = parts[ARM][1] - parts[ARM][0]                 # the part of the animation the clip plays
            ua, fa = [], []
            for f in range(frames):                              # frame f at clip phase (f / 30) / loop
                u, a = left_arm(skel, f / 30.0 / loop)
                ua.append(u)
                fa.append(a)
            ht = math.radians(SWING['hand_twist'])
            hand = np.array([math.sin(ht / 2), 0.0, 0.0, math.cos(ht / 2)])   # about the forearm (local X)
            tracks = [(skel.tag('SKEL_L_Clavicle'), 1, 1, [_channel_static_quat(skel.bind_q('SKEL_L_Clavicle'))]),
                      (skel.tag('SKEL_L_UpperArm'), 1, 1, _channels_quantized(list(zip(*ua)))),
                      (skel.tag('SKEL_L_Forearm'), 1, 1, _channels_quantized(list(zip(*fa)))),
                      (skel.tag('SKEL_L_Hand'), 1, 1, [_channel_static_quat(hand)])]
            tracks += [(t, 1, 1, [_channel_static_quat(q)]) for t, q in fingers_left]
            anims_el.append(_animation('ws_left_swing', frames, dur, int(arm.find('SequenceFrameLimit').get('value')),
                                       int(arm.find('Unknown10').get('value')), tracks))
            pump_added = True
            pump_part = (0.0, loop, 1.0)

        def right_side(bone, track):
            return not skel.name.get(bone, '').startswith(LEFT) and bone != 0

        src_arms[sid] = (arm, right_side)
        anims_el.append(_filtered(arm, f'ws_{sid}_arm', right_side))
        anims_el.append(_filtered(v_anims[FINGERS], f'ws_{sid}_fingers',
                                  lambda bone, track: skel.name.get(bone, '').startswith('SKEL_R_Finger')))
        clips_el.append(_clip(sprint, sid, [(f'ws_{sid}_arm',) + parts[ARM],
                                            (f'ws_{sid}_fingers',) + parts[FINGERS],
                                            ('ws_left_swing',) + pump_part]))
        out[sid] = sid

    ET.indent(root, space=' ')
    xml_path = os.path.join(tmp, DICT + '.ycd.xml')
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n')
    subprocess.run([cw, 'xml2bin', xml_path, tmp], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([cw, 'ycdsig', os.path.join(tmp, DICT + '.ycd'), out_ycd, salt], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([cw, 'check', out_ycd], check=True, stdout=subprocess.DEVNULL)
    verify(cw, out_ycd, src_arms, skel, tmp)
    return out


def verify(cw, ycd, src_arms, skel, tmp):
    """the right arm is the variant's (to the quantisation), the left arm swings through the foot tags"""
    subprocess.run([cw, 'bin2xml', ycd, tmp], check=True, stdout=subprocess.DEVNULL)
    root = ET.parse(os.path.join(tmp, os.path.basename(ycd) + '.xml')).getroot()
    anims = {a.findtext('Hash'): a for a in root.find('Animations')}
    clips = {c.findtext('Hash'): c for c in root.find('Clips')}

    def anim(name):
        a = anims.get(name) or anims.get(f'hash_{_joaat(name):08X}')
        if a is None:
            raise SystemExit(f'{DICT}: no animation {name}')
        return a

    for sid, (src, keep) in src_arms.items():
        if sid not in clips:
            raise SystemExit(f'{DICT}: no clip {sid}')
        built = anim(f'ws_{sid}_arm')
        n = 0
        for i in src.find('BoneIds'):
            bone, track = int(i.find('BoneId').get('value')), int(i.find('Track').get('value'))
            if not keep(bone, track):
                continue
            a, b = track_values(src, bone, track), track_values(built, bone, track)
            if b is None or max(abs(x - y) for fa, fb in zip(a, b) for x, y in zip(fa, fb)) > 2e-3:
                raise SystemExit(f'{DICT}/{sid}: track {skel.name.get(bone, bone)}:{track} differs from the variant')
            n += 1
        if n < 8:
            raise SystemExit(f'{DICT}/{sid}: only {n} right arm tracks')
    swing_anim = anim('ws_left_swing')
    ua = track_values(swing_anim, skel.tag('SKEL_L_UpperArm'), 1)
    frames = len(ua)
    hand_y = []
    for f in range(frames):
        tr = {(skel.tag('SKEL_L_UpperArm'), 1): ua[f],
              (skel.tag('SKEL_L_Forearm'), 1): track_values(swing_anim, skel.tag('SKEL_L_Forearm'), 1)[f]}
        w = skel.fk(tr)
        hand_y.append(-(w['SKEL_L_Hand'][1, 3] - w['SKEL_L_UpperArm'][1, 3]))     # forward of the shoulder
    front, back = max(hand_y), min(hand_y)
    if not (front > 0.25 and back < 0.08):
        raise SystemExit(f'{DICT}: the left hand swings {back:.2f}..{front:.2f} m, expected forward and back')


def _joaat(s):
    h = 0
    for ch in s.lower().encode():
        h = (h + ch) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF
