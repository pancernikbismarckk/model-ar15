#!/usr/bin/env python3
"""Build the weapon_styles FiveM resource from Mr.KobraX's KTWR weapon holding packs.

    python3 tools/weapon_styles/build_weapon_styles.py --packs <folder with the KTWR .zip files>
        [--out fivem/weapon_styles] [--addon WEAPON_NAME=rifle|pistol:WEAPON_TWIN ...]

KTWR (GTA V single player, OpenIV) ships every holding style as a replacement of one of the game's
animation dictionaries (weapons@rifle@, weapons@pistol@, move_stealth@p_m_zero@..., cover@move@ai@
base@1h@), and its BASE routes the weapons' clip sets through them (weaponanimations.meta), so one
style per category is installed at a time. Here every style keeps its own dictionary
(stream/ktwr_*.ycd) and a player picks one per category at run time (/style):

  native   a clip set per style and weapon clip set chain: the style's dictionary in front of the
           chain KTWR BASE gives the weapon (meta/clip_sets.xml). client/main.lua puts it on the
           player's ped with SET_PED_WEAPON_MOVEMENT_CLIPSET (the game syncs it to the other
           players) and, for the cover styles, SET_PED_MOTION_IN_COVER_CLIPSET_OVERRIDE
  overlay  the dictionaries played as upper-body loops (idle / walk / run / sprint): the stealth
           styles, and every style when the game does not take the add-on clip sets

Every animation and sequence gets a new, unique signature (cwconv ycdsig): the styles are edits of the
same game animations and kept their signatures, which the game uses as cache keys, so with several
styles loaded together it mixed up their track layouts and crashed on a style change.

Weapon animation sets and movement modes of our own are not used: the game's loaders only add
weapons to the sets / modes it already has (as its DLCs do), so a new set leaves the ped without
weapon animations.

Writes (third-party content, not committed): stream/*.ycd, meta/clip_sets.xml, shared/catalog.lua,
html/img/*.jpg
"""
import argparse
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_OUT = os.path.join(ROOT, 'fivem', 'weapon_styles')

# ---------------------------------------------------------------------------------------------
# catalogue: (id, KTWR package, label, sprint / walk variant, Polish description, preview package)
# ---------------------------------------------------------------------------------------------
RIFLE = [
    ('r01', 'Rifle - M (Low Ready)', 'Low Ready', None,
     'Broń nisko przed sobą, lufa w dół, gotowa do szybkiego podniesienia.', 'Rifle - M (Low Ready)'),
    ('r02', 'Rifle - M (Low Ready + High Port Sprint)', 'Low Ready', 'sprint: High Port',
     'Low Ready; w sprincie (Shift) broń pionowo przed klatką.', 'Rifle - M (Low Ready)'),
    ('r03', 'Rifle - M (Low Ready + Sling Sprint)', 'Low Ready', 'sprint: na pasie',
     'Low Ready; w sprincie (Shift) broń puszczona na pas.', 'Rifle - M (Low Ready)'),
    ('r04', 'Rifle - M (Standard Low Ready)', 'Standard Low Ready', None,
     'Klasyczne low ready: kolba przy barku, lufa w ziemię przed sobą.', 'Rifle - M (Standard Low Ready)'),
    ('r05', 'Rifle - M (Standard Low Ready + High Port Sprint)', 'Standard Low Ready', 'sprint: High Port',
     'Standard Low Ready; w sprincie (Shift) broń pionowo przed klatką.', 'Rifle - M (Standard Low Ready)'),
    ('r06', 'Rifle - M (Standard Low Ready + Sling Sprint)', 'Standard Low Ready', 'sprint: na pasie',
     'Standard Low Ready; w sprincie (Shift) broń puszczona na pas.', 'Rifle - M (Standard Low Ready)'),
    ('r07', 'Rifle - M (High Port)', 'High Port', None,
     'Broń pionowo przed klatką, lufa w górę.', 'Rifle - M (High Port)'),
    ('r08', 'Rifle - M (Position SUL)', 'Position SUL', None,
     'Lufa w dół tuż przy ciele — bezpiecznie między ludźmi.', 'Rifle - M (Position SUL)'),
    ('r09', 'Rifle - M (Position SUL + High Port Sprint)', 'Position SUL', 'sprint: High Port',
     'Position SUL; w sprincie (Shift) broń pionowo przed klatką.', 'Rifle - M (Position SUL)'),
    ('r10', 'Rifle - M (Position SUL + Sling Sprint)', 'Position SUL', 'sprint: na pasie',
     'Position SUL; w sprincie (Shift) broń puszczona na pas.', 'Rifle - M (Position SUL)'),
    ('r11', 'Rifle - M (Relaxed Cradle)', 'Relaxed Cradle', None,
     'Broń luźno w zgięciu rąk, na spokojnie.', 'Rifle - M (Relaxed Cradle)'),
    ('r12', 'Rifle - M (Relaxed Cradle + High Port Sprint)', 'Relaxed Cradle', 'sprint: High Port',
     'Relaxed Cradle; w sprincie (Shift) broń pionowo przed klatką.', 'Rifle - M (Relaxed Cradle)'),
    ('r13', 'Rifle - M (Relaxed Cradle + Sling Sprint)', 'Relaxed Cradle', 'sprint: na pasie',
     'Relaxed Cradle; w sprincie (Shift) broń puszczona na pas.', 'Rifle - M (Relaxed Cradle)'),
    ('r14', 'Rifle - M (Sling Relaxed)', 'Sling Relaxed', None,
     'Broń na pasie, dłonie luźno na broni.', 'Rifle - M (Sling Relaxed)'),
    ('r15', 'Rifle - M (Sling Relaxed + High Port Sprint)', 'Sling Relaxed', 'sprint: High Port',
     'Sling Relaxed; w sprincie (Shift) broń pionowo przed klatką.', 'Rifle - M (Sling Relaxed)'),
    ('r16', 'Rifle - M (Sling Relaxed + Sling Sprint)', 'Sling Relaxed', 'sprint: na pasie',
     'Sling Relaxed; w sprincie (Shift) broń puszczona na pas.', 'Rifle - M (Sling Relaxed)'),
    ('r17', 'Rifle - M (Sling Down)', 'Sling Down', None,
     'Broń zwisa na pasie lufą w dół, ręce wolne.', 'Rifle - M (Sling Down)'),
    ('r18', 'Rifle - M (Sling High)', 'Sling High', None,
     'Broń na pasie wysoko przy klatce.', 'Rifle - M (Sling High)'),
]
PISTOL = [
    ('p01', 'Pistol - M (Low Ready)', 'Low Ready', None,
     'Pistolet oburącz nisko przed sobą.', 'Pistol - M (Low Ready)'),
    ('p02', 'Pistol - M (Low Ready + High Run)', 'Low Ready', 'bieg: wysoko',
     'Low Ready; w biegu pistolet wysoko przy klatce.', 'Pistol - M (Low Ready + High Run)'),
    ('p03', 'Pistol - M (Compressed Low Ready)', 'Compressed Low Ready', None,
     'Pistolet przy ciele, łokcie przy tułowiu, lufa w dół.', 'Pistol - M (Compressed Low Ready)'),
    ('p04', 'Pistol - M (Compressed Low Ready + 1 Hand Run)', 'Compressed Low Ready', 'bieg: jedną ręką',
     'Compressed Low Ready; w biegu pistolet w jednej ręce.', 'Pistol - M (Compressed Low Ready + 1 Hand Run)'),
    ('p05', 'Pistol - M (Chest Ready)', 'Chest Ready', None,
     'Pistolet przy klatce piersiowej, jedną ręką.', 'Pistol - M (Chest Ready)'),
    ('p06', 'Pistol - M (Chest Ready With 2 Hand)', 'Chest Ready', 'oburącz',
     'Pistolet przy klatce piersiowej, oburącz.', 'Pistol - M (Chest Ready With 2 Hand)'),
    ('p07', 'Pistol - M (Chest Ready With 2 Hand + Low Run)', 'Chest Ready', 'oburącz, bieg: nisko',
     'Chest Ready oburącz; w biegu pistolet nisko.', 'Pistol - M (Chest Ready With 2 Hand)'),
    ('p08', 'Pistol - M (Temple Index)', 'Temple Index', None,
     'Pistolet uniesiony przy skroni, lufa w górę.', 'Pistol - M (Temple Index)'),
    ('p09', 'Pistol - M (Temple Index + High Run)', 'Temple Index', 'bieg: wysoko',
     'Temple Index; w biegu pistolet wysoko.', 'Pistol - M (Temple Index)'),
    ('p10', 'Pistol - M (Temple Index + Low Run)', 'Temple Index', 'bieg: nisko',
     'Temple Index; w biegu pistolet nisko.', 'Pistol - M (Temple Index)'),
    ('p11', 'Pistol - M (Position SUL)', 'Position SUL', None,
     'Lufa w dół przy brzuchu, druga dłoń płasko pod bronią.', 'Pistol - M (Position SUL)'),
    ('p12', 'Pistol - M (Belt Relaxed)', 'Belt Relaxed', None,
     'Pistolet luźno przy pasie.', 'Pistol - M (Belt Relaxed)'),
]
RIFLE_STEALTH = [
    ('rs01', 'Rifle - S (Low Ready)', 'Low Ready', None,
     'Skradanie z bronią nisko, gotową do podniesienia.', 'Rifle - S (Low Ready)'),
    ('rs02', 'Rifle - S (High Ready)', 'High Ready', None,
     'Skradanie z bronią wysoko, kolba przy barku.', 'Rifle - S (High Ready)'),
]
PISTOL_STEALTH = [
    ('ps01', 'Pistol - S (Compressed Ready)', 'Compressed Ready', None,
     'Pistolet oburącz blisko ciała.', 'Pistol - S (Compressed Ready)'),
    ('ps02', 'Pistol - S (High Ready)', 'High Ready', None,
     'Pistolet oburącz wysoko, gotowy do strzału.', 'Pistol - S (High Ready)'),
    ('ps03', 'Pistol - S (Position SUL)', 'Position SUL', None,
     'Lufa w dół przy brzuchu.', 'Pistol - S (Position SUL)'),
    ('ps04', 'Pistol - S (Position SUL + Compressed Walk)', 'Position SUL', 'chód: Compressed',
     'Position SUL w miejscu, Compressed Ready w ruchu.', 'Pistol - S (Position SUL)'),
    ('ps05', 'Pistol - S (Compressed + SUL Walk)', 'Compressed Ready', 'chód: SUL',
     'Compressed Ready w miejscu, Position SUL w ruchu.', 'Pistol - S (Compressed Ready)'),
    ('ps06', 'Pistol - S (Calm Down!)', 'Calm Down!', None,
     'Pistolet nisko, wolna ręka uniesiona w geście „spokojnie”.', 'Pistol - S (Calm Down!)'),
    ('ps07', 'Unarmed - S (Holster Ready + CalmDown!)', 'Calm Down!', 'wariant z Holster Ready',
     'Calm Down! z paczki Holster Ready.', 'Unarmed - S (Holster Ready + CalmDown!)'),
]
UNARMED_STEALTH = [
    ('us01', 'Unarmed - S (Holster Ready + CalmDown!)', 'Holster Ready', None,
     'Bez broni: dłoń na kaburze.', 'Unarmed - S (Holster Ready + CalmDown!)'),
]
PISTOL_COVER = [
    ('pc01', 'Pistol - C (Temple Index)', 'Temple Index', None,
     'W osłonie pistolet przy skroni.', 'Pistol - C (Temple Index)'),
    ('pc02', 'Pistol - C (Position SUL)', 'Position SUL', None,
     'W osłonie lufa w dół przy brzuchu.', 'Pistol - C (Position SUL)'),
]


# category key, menu label, hint, styles, the dictionary each package replaces, kind
CATEGORIES = [
    ('rifle', 'Karabin', 'karabiny, karabinki, pistolety maszynowe, strzelby', RIFLE, 'weapons@rifle@.ycd', 'motion'),
    ('pistol', 'Pistolet', 'pistolety, rewolwery, paralizator', PISTOL, 'weapons@pistol@.ycd', 'motion'),
    ('rifle_stealth', 'Karabin — skradanie', 'tryb skradania (kucanie w GTA)', RIFLE_STEALTH,
     'move_stealth@p_m_zero@2h@upper.ycd', 'stealth'),
    ('pistol_stealth', 'Pistolet — skradanie', 'tryb skradania (kucanie w GTA)', PISTOL_STEALTH,
     'move_stealth@p_m_zero@1h@upper.ycd', 'stealth'),
    ('unarmed_stealth', 'Bez broni — skradanie', 'tryb skradania bez broni w ręku', UNARMED_STEALTH,
     'move_stealth@p_m_zero@unarmed@core.ycd', 'stealth'),
    ('pistol_cover', 'Pistolet — osłona', 'za osłoną z pistoletem', PISTOL_COVER, 'cover@move@ai@base@1h@.ycd', 'cover'),
]

# weapon categories by the motion clip set KTWR BASE gives them
RIFLE_MOTION = re.compile(r'^(anim@)?weapons@(rifle|submg|machinegun)@')
PISTOL_MOTION = re.compile(r'^(anim@)?weapons@pistol@|^weapons@submg@micro_smg$|^weapon@w_pi_stungun$')
ONE_HANDED_SUBMG = {'weapons@submg@micro_smg'}
DEFAULT_COVER = 'cover@move@ai@base@1h'
# add-on weapons: name -> (category, the game weapon whose clip set chains it uses). Weapons that
# are not on the server cost nothing; any other add-on weapon of the groups gets the category's
# default chains (FALLBACK_TWIN).
ADDON_WEAPONS = {
    'WEAPON_AR15': ('rifle', 'WEAPON_CARBINERIFLE'),     # fivem/weapon_ar15
    'WEAPON_GLOCK17': ('pistol', 'WEAPON_PISTOL'),
}
FALLBACK_TWIN = {'rifle': 'WEAPON_CARBINERIFLE', 'pistol': 'WEAPON_PISTOL'}


# ---------------------------------------------------------------------------------------------
# packages
# ---------------------------------------------------------------------------------------------
def read_packages(packs_dir):
    """{package name: {dictionary file name: bytes}}, {package name: preview image bytes}, base oiv"""
    dicts, previews, base = {}, {}, None
    for zpath in sorted(glob.glob(os.path.join(packs_dir, '*.zip'))):
        with zipfile.ZipFile(zpath) as z:
            for n in z.namelist():
                name = os.path.basename(n)
                if name.lower().endswith('.oiv'):
                    oiv = zipfile.ZipFile(io.BytesIO(z.read(n)))
                    pkg = name[:-4]
                    if 'BASE (Required)' in pkg:
                        base = oiv
                        continue
                    if 'BASE' in pkg:
                        continue
                    dicts[pkg] = {os.path.basename(m): oiv.read(m) for m in oiv.namelist() if m.endswith('.ycd')}
                elif name.startswith('[Preview] '):
                    previews[os.path.splitext(name[len('[Preview] '):])[0]] = z.read(n)
    if base is None:
        sys.exit('KTWR BASE package not found in ' + packs_dir)
    return dicts, previews, base


# ---------------------------------------------------------------------------------------------
# weapon animations (KTWR BASE: the game's files with KTWR's routing, all DLC weapons)
# ---------------------------------------------------------------------------------------------
def load_sets(paths):
    """{set key: {'fallback': str, 'weapons': {weapon: element}}} merged over the given files"""
    sets = {}
    for p in paths:
        root = ET.parse(p).getroot()
        for s in root.find('WeaponAnimationsSets'):
            d = sets.setdefault(s.get('key'), {'fallback': (s.findtext('Fallback') or '').strip(), 'weapons': {}})
            for w in s.find('WeaponAnimations'):
                d['weapons'][w.get('key')] = w
    return sets


def field(sets, set_key, weapon, name):
    """A field the way the game reads it: the set's entry, then its fallback sets."""
    seen = set()
    while set_key and set_key not in seen:
        seen.add(set_key)
        s = sets.get(set_key)
        if s is None:
            break
        w = s['weapons'].get(weapon)
        if w is not None:
            e = w.find(name)
            if e is not None and (e.text or '').strip():
                return e.text.strip()
        set_key = s['fallback']
    return ''


# ---------------------------------------------------------------------------------------------
# clip sets
# ---------------------------------------------------------------------------------------------
class ClipSets:
    def __init__(self):
        self.items = {}

    def get(self, dict_name, fallback):
        name = f'{dict_name}@{fallback}' if fallback else dict_name
        self.items[name] = (dict_name, fallback)
        return name

    def xml(self):
        root = ET.Element('fwClipSetManager')
        cs = ET.SubElement(root, 'clipSets')
        for name, (d, fb) in sorted(self.items.items()):
            it = ET.SubElement(cs, 'Item', key=name, type='fwClipSet')
            f = ET.SubElement(it, 'fallbackId')
            if fb:
                f.text = fb
            ET.SubElement(it, 'clipDictionaryName').text = d
            ET.SubElement(it, 'clipItems')
            ET.SubElement(it, 'moveNetworkFlags')
        for tag in ('clipDictionaryMetadatas', 'memoryGroupMetadatas'):
            ET.SubElement(root, tag)
        return root


# ---------------------------------------------------------------------------------------------
def write_xml(root, path, comment=None):
    ET.indent(root, space='  ')
    body = ET.tostring(root, encoding='unicode')
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    if comment:
        head += '<!--\n  ' + comment.replace('\n', '\n  ') + '\n-->\n'
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(head + body + '\n')


def check_signatures(stream_dir, cw):
    """Every animation and sequence signature of the streamed dictionaries must be unique."""
    tmpx = tempfile.mkdtemp()
    seen = {}
    for f in sorted(os.listdir(stream_dir)):
        subprocess.run([cw, 'bin2xml', os.path.join(stream_dir, f), tmpx], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(os.path.join(tmpx, f + '.xml')).getroot()
        for anim in root.find('Animations'):
            keys = [anim.findtext('Unknown1C')] + [s.findtext('Hash') for s in anim.find('Sequences')]
            for key in keys:
                if not key or key in seen:
                    sys.exit(f'signature {key!r} of {f} is not unique ({seen.get(key)})')
                seen[key] = f
    shutil.rmtree(tmpx, ignore_errors=True)
    return len(seen)


def lua_str(s):
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--packs', required=True, help='folder with the KTWR .zip files')
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--addon', action='append', default=[], metavar='WEAPON_NAME=rifle|pistol:WEAPON_TWIN',
                    help='another add-on weapon, e.g. WEAPON_M4A1=rifle:WEAPON_CARBINERIFLE (repeatable)')
    a = ap.parse_args()
    for spec in a.addon:
        m = re.fullmatch(r'(\w+)=(rifle|pistol):(\w+)', spec.strip())
        if not m:
            sys.exit('bad --addon ' + spec)
        ADDON_WEAPONS[m.group(1).upper()] = (m.group(2), m.group(3).upper())

    dicts, previews, base = read_packages(a.packs)
    out = a.out
    for sub in ('stream', 'meta', os.path.join('html', 'img')):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
    for sub in ('stream', 'meta', 'shared', os.path.join('html', 'img')):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    tmp = tempfile.mkdtemp()
    ktwr_files = []
    for n in base.namelist():
        if n.endswith('weaponanimations.meta'):
            p = os.path.join(tmp, n.replace('/', '_'))
            open(p, 'wb').write(base.read(n))
            ktwr_files.append(p)
    ktwr = load_sets(sorted(ktwr_files))

    def chains(w):
        """(male, female freemode) movement clip set chains and the cover chain of weapon w"""
        m = field(ktwr, 'Default', w, 'MotionClipSetHash')
        f = field(ktwr, 'MP_F_Freemode', w, 'MotionClipSetHash') or m
        c = field(ktwr, 'Default', w, 'CoverMovementClipSetHash') or DEFAULT_COVER
        return m, f, c

    # weapons per category, from their movement clip set
    weapons = {}                              # name -> (category, male, female, cover)
    for w in ktwr['Default']['weapons']:
        m, f, c = chains(w)
        if m in ONE_HANDED_SUBMG or PISTOL_MOTION.match(m):
            weapons[w] = ('pistol', m, f, c)
        elif RIFLE_MOTION.match(m):
            weapons[w] = ('rifle', m, f, c)
    for w, (cat, twin) in ADDON_WEAPONS.items():
        weapons[w] = (cat,) + chains(twin)
    fallback = {cat: (cat,) + chains(twin) for cat, twin in FALLBACK_TWIN.items()}

    def chain_set(cat, idx):
        """distinct chains of a category (idx 1 male, 2 female, 3 cover), the default included"""
        out_ = {fallback[cat][idx]}
        out_.update(v[idx] for v in weapons.values() if v[0] == cat)
        return sorted(out_)

    clipsets = ClipSets()
    shared_core = {}                          # bytes -> name (identical dictionaries are streamed once)
    cw = os.environ.get('CWCONV', os.path.join(ROOT, 'build', 'cwconv', 'cwconv'))

    def stream_dict(pkg, fname, new):
        data = dicts[pkg][fname]
        if data in shared_core:
            return shared_core[data]
        shared_core[data] = new
        src = os.path.join(tmp, new + '.ycd')
        open(src, 'wb').write(data)
        # unique animation / sequence signatures (see the module docstring)
        subprocess.run([cw, 'ycdsig', src, os.path.join(out, 'stream', new + '.ycd'), 'weapon_styles/' + new],
                       check=True, stdout=subprocess.DEVNULL)
        return new

    catalog = []
    for cat, label, hint, styles, dict_file, kind in CATEGORIES:
        entries = []
        for sid, pkg, name, variant, desc, preview in styles:
            st = {'id': sid, 'label': name, 'variant': variant, 'desc': desc}
            img = previews.get(preview)
            if img:
                slug = re.sub(r'[^a-z0-9]+', '_', preview.lower()).strip('_')
                path = os.path.join(out, 'html', 'img', slug + '.jpg')
                if not os.path.exists(path):
                    im = Image.open(io.BytesIO(img)).convert('RGB')
                    im.thumbnail((640, 360), Image.LANCZOS)
                    im.save(path, quality=82, optimize=True)
                st['img'] = 'img/' + slug + '.jpg'
            d = stream_dict(pkg, dict_file, f'ktwr_{sid}')
            st['dict'] = d
            if kind == 'motion':
                for ch in chain_set(cat, 1) + chain_set(cat, 2):
                    clipsets.get(d, ch)
                st['clips'] = {'idle': 'idle', 'walk': 'walk', 'run': 'run',
                               'sprint': 'sprint' if cat == 'rifle' else 'run'}
            elif kind == 'cover':
                for ch in chain_set('pistol', 3):
                    clipsets.get(d, ch)
            else:                             # stealth: upper-body loops (overlay)
                st['clips'] = {'idle': 'idle', 'walk': 'walk', 'run': 'run', 'sprint': 'run'}
            entries.append(st)
        catalog.append((cat, label, hint, kind, entries))

    test_clipset = clipsets.get('ktwr_r01', weapons['WEAPON_CARBINERIFLE'][1])
    write_xml(clipsets.xml(), os.path.join(out, 'meta', 'clip_sets.xml'),
              'weapon_styles: a clip set per KTWR style dictionary (stream/ktwr_*.ycd) and weapon clip set\n'
              'chain, the style in front of the chain; generated by tools/weapon_styles/build_weapon_styles.py')

    # catalogue for the scripts and the menu
    L = ['-- generated by tools/weapon_styles/build_weapon_styles.py; do not edit',
         'Catalog = {',
         f'    testClipSet = {lua_str(test_clipset)},',
         '    categories = {']
    for cat, label, hint, kind, entries in catalog:
        L.append(f'        {{ key = {lua_str(cat)}, label = {lua_str(label)}, hint = {lua_str(hint)}, kind = {lua_str(kind)}, styles = {{')
        for st in entries:
            parts = [f'id = {lua_str(st["id"])}', f'label = {lua_str(st["label"])}']
            if st.get('variant'):
                parts.append(f'variant = {lua_str(st["variant"])}')
            parts.append(f'desc = {lua_str(st["desc"])}')
            for k in ('img', 'dict'):
                if st.get(k):
                    parts.append(f'{k} = {lua_str(st[k])}')
            if st.get('clips'):
                c = st['clips']
                parts.append('clips = { ' + ', '.join(f'{k} = {lua_str(c[k])}' for k in ('idle', 'walk', 'run', 'sprint')) + ' }')
            L.append('            { ' + ', '.join(parts) + ' },')
        L.append('        } },')
    L.append('    },')
    L.append("    -- weapon -> { category, movement clip set chain (male, female freemode), cover chain };")
    L.append("    -- a style's clip set is '<style dict>@<chain>'")
    L.append('    weapons = {')
    for w in sorted(weapons):
        L.append(f'        [`{w}`] = {{ ' + ', '.join(lua_str(x) for x in weapons[w]) + ' },')
    L.append('    },')
    L.append('    -- any other (add-on) weapon of the pistol / rifle groups')
    L.append('    fallback = {')
    for cat in ('rifle', 'pistol'):
        L.append(f'        {cat} = {{ ' + ', '.join(lua_str(x) for x in fallback[cat]) + ' },')
    L.append('    },')
    L.append('}')
    with open(os.path.join(out, 'shared', 'catalog.lua'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')

    icon = os.path.join(ROOT, 'fivem', 'ox_inventory', 'web', 'images', 'WEAPON_AR15.png')
    if os.path.exists(icon):                  # menu card of the AR-15's own low ready
        shutil.copy(icon, os.path.join(out, 'html', 'img', 'ar15.png'))

    n_sigs = check_signatures(os.path.join(out, 'stream'), cw)
    n_dicts = len(os.listdir(os.path.join(out, 'stream')))
    n_w = {cat: sum(1 for v in weapons.values() if v[0] == cat) for cat in ('rifle', 'pistol')}
    print(f'styles: {sum(len(e) for *_x, e in catalog)}, dictionaries: {n_dicts}, clip sets: {len(clipsets.items)}, '
          f'unique signatures: {n_sigs}, rifle weapons: {n_w["rifle"]}, pistol weapons: {n_w["pistol"]}')


if __name__ == '__main__':
    main()
