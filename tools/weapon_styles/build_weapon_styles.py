#!/usr/bin/env python3
"""Build the weapon_styles FiveM resource from Mr.KobraX's KTWR weapon holding packs.

    python3 tools/weapon_styles/build_weapon_styles.py --packs <folder with the KTWR .zip files>
        [--vanilla <fivem-addon-weapon-tool-kit/templates/weapons>] [--out fivem/weapon_styles]
        [--addon WEAPON_NAME=rifle|pistol:WEAPON_TWIN ...]

KTWR (GTA V single player, OpenIV) ships every holding style as a replacement of one of the game's
animation dictionaries (weapons@rifle@, weapons@pistol@, move_stealth@p_m_zero@..., cover@move@
ai@base@1h@), so one style per category is installed at a time. Here every style keeps its own
dictionary (stream/ktwr_*.ycd) and a player picks one per category at run time (/style):

  native   a clip set per style put in front of the weapon's own clip set (meta/clip_sets.xml),
           weapon animation sets that only swap the motion / cover clip set (sparse entries: every
           other field falls back to the game's own set, meta/weaponanimations.meta) and movement
           modes for the stealth styles (meta/pedpersonality.meta); client/main.lua switches them
           per ped with SET_WEAPON_ANIMATION_OVERRIDE / SET_MOVEMENT_MODE_OVERRIDE
  overlay  the same dictionaries played as upper-body loops (idle / walk / run / sprint), used when
           the game does not take the add-on clip sets and for add-on weapons without set entries

Writes (third-party content, not committed): stream/*.ycd, meta/*, shared/catalog.lua, html/img/*.jpg
"""
import argparse
import copy
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
AR15_META = os.path.join(ROOT, 'fivem', 'weapon_ar15', 'meta', 'weaponanimations.meta')

# ---------------------------------------------------------------------------------------------
# catalogue: (id, KTWR package, label, sprint / walk variant, Polish description, preview package)
# ---------------------------------------------------------------------------------------------
RIFLE = [
    ('r01', 'Rifle - M (Low Ready)', 'Low Ready', None,
     'Broń nisko przed sobą, lufa w dół, gotowa do szybkiego podniesienia.', 'Rifle - M (Low Ready)'),
    ('r02', 'Rifle - M (Low Ready + High Port Sprint)', 'Low Ready', 'sprint: High Port',
     'Low Ready; w sprincie broń pionowo przed klatką.', 'Rifle - M (Low Ready)'),
    ('r03', 'Rifle - M (Low Ready + Sling Sprint)', 'Low Ready', 'sprint: na pasie',
     'Low Ready; w sprincie broń puszczona na pas.', 'Rifle - M (Low Ready)'),
    ('r04', 'Rifle - M (Standard Low Ready)', 'Standard Low Ready', None,
     'Klasyczne low ready: kolba przy barku, lufa w ziemię przed sobą.', 'Rifle - M (Standard Low Ready)'),
    ('r05', 'Rifle - M (Standard Low Ready + High Port Sprint)', 'Standard Low Ready', 'sprint: High Port',
     'Standard Low Ready; w sprincie broń pionowo przed klatką.', 'Rifle - M (Standard Low Ready)'),
    ('r06', 'Rifle - M (Standard Low Ready + Sling Sprint)', 'Standard Low Ready', 'sprint: na pasie',
     'Standard Low Ready; w sprincie broń puszczona na pas.', 'Rifle - M (Standard Low Ready)'),
    ('r07', 'Rifle - M (High Port)', 'High Port', None,
     'Broń pionowo przed klatką, lufa w górę.', 'Rifle - M (High Port)'),
    ('r08', 'Rifle - M (Position SUL)', 'Position SUL', None,
     'Lufa w dół tuż przy ciele — bezpiecznie między ludźmi.', 'Rifle - M (Position SUL)'),
    ('r09', 'Rifle - M (Position SUL + High Port Sprint)', 'Position SUL', 'sprint: High Port',
     'Position SUL; w sprincie broń pionowo przed klatką.', 'Rifle - M (Position SUL)'),
    ('r10', 'Rifle - M (Position SUL + Sling Sprint)', 'Position SUL', 'sprint: na pasie',
     'Position SUL; w sprincie broń puszczona na pas.', 'Rifle - M (Position SUL)'),
    ('r11', 'Rifle - M (Relaxed Cradle)', 'Relaxed Cradle', None,
     'Broń luźno w zgięciu rąk, na spokojnie.', 'Rifle - M (Relaxed Cradle)'),
    ('r12', 'Rifle - M (Relaxed Cradle + High Port Sprint)', 'Relaxed Cradle', 'sprint: High Port',
     'Relaxed Cradle; w sprincie broń pionowo przed klatką.', 'Rifle - M (Relaxed Cradle)'),
    ('r13', 'Rifle - M (Relaxed Cradle + Sling Sprint)', 'Relaxed Cradle', 'sprint: na pasie',
     'Relaxed Cradle; w sprincie broń puszczona na pas.', 'Rifle - M (Relaxed Cradle)'),
    ('r14', 'Rifle - M (Sling Relaxed)', 'Sling Relaxed', None,
     'Broń na pasie, dłonie luźno na broni.', 'Rifle - M (Sling Relaxed)'),
    ('r15', 'Rifle - M (Sling Relaxed + High Port Sprint)', 'Sling Relaxed', 'sprint: High Port',
     'Sling Relaxed; w sprincie broń pionowo przed klatką.', 'Rifle - M (Sling Relaxed)'),
    ('r16', 'Rifle - M (Sling Relaxed + Sling Sprint)', 'Sling Relaxed', 'sprint: na pasie',
     'Sling Relaxed; w sprincie broń puszczona na pas.', 'Rifle - M (Sling Relaxed)'),
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
STEALTH_CORE = 'move_stealth@p_m_zero@unarmed@core.ycd'
VANILLA_STEALTH_CORE = 'move_stealth@p_m_zero@unarmed@core'

# weapon categories by the motion clip set of the game's Default weapon animations
RIFLE_MOTION = re.compile(r'^(anim@)?weapons@(rifle|submg|machinegun)@')
PISTOL_MOTION = re.compile(r'^(anim@)?weapons@pistol@|^weapons@submg@micro_smg$|^weapon@w_pi_stungun$')
ONE_HANDED_SUBMG = {'weapons@submg@micro_smg'}
# add-on weapons: name -> (category, vanilla twin). A twin stands in for the add-on's own metas: its
# weaponanimations entries (value fields, fallback clip sets) and its place in the movement modes.
# Entries of a weapon that is not on the server are never looked up, so extra names cost nothing.
ADDON_WEAPONS = {
    'WEAPON_AR15': ('rifle', 'WEAPON_CARBINERIFLE'),     # fivem/weapon_ar15 (its own metas are read)
    'WEAPON_GLOCK17': ('pistol', 'WEAPON_PISTOL'),
}


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
# weapon animations
# ---------------------------------------------------------------------------------------------
def load_sets(paths):
    """{set key: {'fallback': str, 'weapons': {weapon: element}}} merged over the given files"""
    sets = {}
    for p in paths:
        try:
            root = ET.parse(p).getroot()
        except ET.ParseError as e:            # a few community templates are not well-formed
            print(f'skipping {p}: {e}')
            continue
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


def default_entry(sets, weapon):
    for key in ('Default',):
        w = sets.get(key, {}).get('weapons', {}).get(weapon)
        if w is not None:
            return w
    return None


def sparse_entry(weapon, template, overrides):
    """A weapon entry that only sets ``overrides`` (clip set hashes). The other clip set fields are
    left out (empty), so the game takes them from the set's fallback; value fields have no 'empty'
    state and are copied from ``template``."""
    e = ET.Element('Item', key=weapon)
    for tag, v in overrides.items():
        ET.SubElement(e, tag).text = v
    for c in template:
        if c.get('value') is not None:
            ET.SubElement(e, c.tag, value=c.get('value'))
        elif c.get('ref') is not None:
            ET.SubElement(e, c.tag, ref='NULL')
    return e


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
# ped personality (stealth movement modes)
# ---------------------------------------------------------------------------------------------
def strip_item_types(e):
    for x in e.iter():
        x.attrib.pop('itemType', None)


def movement_mode(src, name, cat, style_dicts, clipsets, extra_weapons, addons):
    """Copy of a vanilla movement mode (DEFAULT_ACTION / MP_FEMALE_ACTION) whose stealth part uses the
    style for its weapon kind. Add-on weapons are listed wherever their twin is (action and stealth,
    as their own pedpersonality.meta does for the vanilla modes); weapons of the category still
    missing from the stealth lists are added to the style's items."""
    mm = copy.deepcopy(src)
    strip_item_types(mm)
    mm.find('Name').text = name
    for part in mm.find('MovementModes'):
        for it in part:
            wl = it.find('Weapons')
            names = {w.text.lower() for w in wl}
            for w, twin in addons.items():
                if twin.lower() in names and w.lower() not in names:
                    ET.SubElement(wl, 'Item').text = w.lower()
                    names.add(w.lower())
    stealth = list(mm.find('MovementModes'))[1]
    listed = {w.text.lower() for it in stealth for w in it.find('Weapons')}
    for it in stealth:
        weapons = [w.text.lower() for w in it.find('Weapons')]
        for cs in it.find('ClipSets'):
            core, upper = cs.find('MovementClipSetId'), cs.find('WeaponClipSetId')
            up = (upper.text or '').strip()
            if cat == 'rifle_stealth' and up == 'move_stealth@p_m_zero@2h@upper':
                upper.text = clipsets.get(style_dicts['upper'], up)
                target = True
            elif cat == 'pistol_stealth' and up == 'move_stealth@p_m_zero@1h@upper':
                upper.text = clipsets.get(style_dicts['upper'], up)
                core.text = clipsets.get(style_dicts['core'], (core.text or '').strip())
                target = True
            elif cat == 'unarmed_stealth' and 'weapon_unarmed' in weapons:
                core.text = clipsets.get(style_dicts['core'], (core.text or '').strip())
                if up == VANILLA_STEALTH_CORE:
                    upper.text = core.text
                target = False
            else:
                target = False
            if target:
                wl = it.find('Weapons')
                for w in extra_weapons:
                    if w.lower() not in listed:
                        ET.SubElement(wl, 'Item').text = w.lower()
                        listed.add(w.lower())
    return mm


# ---------------------------------------------------------------------------------------------
def write_xml(root, path, comment=None):
    ET.indent(root, space='  ')
    body = ET.tostring(root, encoding='unicode')
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    if comment:
        head += '<!--\n  ' + comment.replace('\n', '\n  ') + '\n-->\n'
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(head + body + '\n')


def lua_str(s):
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--packs', required=True, help='folder with the KTWR .zip files')
    ap.add_argument('--vanilla', default=os.path.join(ROOT, 'build', 'fivem-addon-weapon-tool-kit', 'templates', 'weapons'),
                    help='weapon templates with the game\'s own weaponanimations.meta entries '
                         '(git clone https://github.com/Hxrv3y/fivem-addon-weapon-tool-kit build/fivem-addon-weapon-tool-kit)')
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
    for sub in ('stream', os.path.join('html', 'img')):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
    for sub in ('stream', 'meta', 'shared', os.path.join('html', 'img')):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    # the game's weapon animations: KTWR's full files (all DLC weapons) under the vanilla templates
    tmp = tempfile.mkdtemp()
    ktwr_files = []
    for n in base.namelist():
        if n.endswith('weaponanimations.meta'):
            p = os.path.join(tmp, n.replace('/', '_'))
            open(p, 'wb').write(base.read(n))
            ktwr_files.append(p)
    ktwr = load_sets(sorted(ktwr_files))
    vanilla = load_sets(sorted(glob.glob(os.path.join(a.vanilla, '*', 'weaponanimations.meta'))))
    ar15 = load_sets([AR15_META]) if os.path.exists(AR15_META) else {}

    def game(key):
        """vanilla template set if it has the weapon, else KTWR's (all DLC weapons)"""
        return vanilla if key in vanilla.get('Default', {}).get('weapons', {}) else ktwr

    # weapon lists per category, from the Default motion clip set
    cats = {'rifle': [], 'pistol': []}
    for w in ktwr['Default']['weapons']:
        motion = field(ktwr, 'Default', w, 'MotionClipSetHash')
        if motion in ONE_HANDED_SUBMG or PISTOL_MOTION.match(motion):
            cats['pistol'].append(w)
        elif RIFLE_MOTION.match(motion):
            cats['rifle'].append(w)
    for w, (cat, _twin) in ADDON_WEAPONS.items():
        if w not in cats[cat]:
            cats[cat].append(w)
    twins = {w: twin for w, (_cat, twin) in ADDON_WEAPONS.items()}

    def entry_source(w):
        """(sets, weapon) whose game entries stand for weapon w"""
        if w == 'WEAPON_AR15' and ar15:
            return ar15, w
        w = twins.get(w, w)
        return game(w), w

    clipsets = ClipSets()
    renamed = {}                              # (package, dictionary file) -> new dictionary name
    shared_core = {}                          # bytes -> name (the pistol packages share one core)

    def stream_dict(pkg, fname, new):
        data = dicts[pkg][fname]
        if fname == STEALTH_CORE:
            if data in shared_core:
                return shared_core[data]
            shared_core[data] = new
        open(os.path.join(out, 'stream', new + '.ycd'), 'wb').write(data)
        return new

    sets_root = ET.Element('CWeaponAnimationsSets')
    sets_list = ET.SubElement(sets_root, 'WeaponAnimationsSets')

    def add_set(key, fallback, entries):
        s = ET.SubElement(sets_list, 'Item', key=key)
        ET.SubElement(s, 'Fallback').text = fallback
        wa = ET.SubElement(s, 'WeaponAnimations')
        for e in entries:
            wa.append(e)

    # personality movement modes
    ped_x = tempfile.mktemp(suffix='.xml')
    ymt = os.path.join(tmp, 'pedpersonality.ymt')
    open(ymt, 'wb').write(base.read('content/ped/pedpersonality.ymt'))
    cw = os.environ.get('CWCONV', os.path.join(ROOT, 'build', 'cwconv', 'cwconv'))
    subprocess.run([cw, 'ymt2xml', ymt, ped_x], check=True, stdout=subprocess.DEVNULL)
    ped_root = ET.parse(ped_x).getroot()
    modes_src = {m.findtext('Name').lower(): m for m in ped_root.find('MovementModes')}
    ped_out = ET.Element('CPedModelInfo__PersonalityDataList')
    ped_modes = ET.SubElement(ped_out, 'MovementModes')

    catalog = []
    test_clipset = None
    for cat, label, hint, styles, dict_file, kind in CATEGORIES:
        entries = []
        for sid, pkg, name, variant, desc, preview in styles:
            files = dicts[pkg]
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
            if kind == 'motion':
                d = stream_dict(pkg, dict_file, f'ktwr_{sid}')
                st['dict'] = d
                st['clips'] = {'idle': 'idle', 'walk': 'walk', 'run': 'run',
                               'sprint': 'sprint' if cat == 'rifle' else 'run'}
                male, female = [], []
                for w in cats[cat]:
                    src, sw = entry_source(w)
                    tmpl = default_entry(src, sw) if default_entry(src, sw) is not None else default_entry(ktwr, sw)
                    m = field(src, 'Default', sw, 'MotionClipSetHash')
                    male.append(sparse_entry(w, tmpl, {'MotionClipSetHash': clipsets.get(d, m)}))
                    fm = field(src, 'MP_F_Freemode', sw, 'MotionClipSetHash') or m
                    female.append(sparse_entry(w, tmpl, {'MotionClipSetHash': clipsets.get(d, fm)}))
                st['set'], st['setF'] = f'KTWR_{sid.upper()}', f'KTWR_{sid.upper()}_F'
                add_set(st['set'], 'Default', male)
                add_set(st['setF'], 'MP_F_Freemode', female)
                if test_clipset is None:
                    test_clipset = clipsets.get(d, field(game('WEAPON_CARBINERIFLE'), 'Default',
                                                         'WEAPON_CARBINERIFLE', 'MotionClipSetHash'))
            elif kind == 'cover':
                d = stream_dict(pkg, dict_file, f'ktwr_{sid}')
                st['dict'] = d
                male, female = [], []
                for w in cats['pistol']:
                    src, sw = entry_source(w)
                    tmpl = default_entry(src, sw) if default_entry(src, sw) is not None else default_entry(ktwr, sw)
                    fb = field(src, 'Default', sw, 'CoverMovementClipSetHash') or 'cover@move@base@1h'
                    c = clipsets.get(d, fb)
                    e = sparse_entry(w, tmpl, {'CoverMovementClipSetHash': c, 'CoverAlternateMovementClipSetHash': c})
                    male.append(e)
                    female.append(copy.deepcopy(e))
                st['set'], st['setF'] = f'KTWR_{sid.upper()}', f'KTWR_{sid.upper()}_F'
                add_set(st['set'], 'Default', male)
                add_set(st['setF'], 'MP_F_Freemode', female)
            else:   # stealth: movement modes
                sd = {}
                if cat in ('rifle_stealth', 'pistol_stealth'):
                    sd['upper'] = stream_dict(pkg, dict_file, f'ktwr_{sid}')
                    st['dict'] = sd['upper']
                if cat in ('pistol_stealth', 'unarmed_stealth'):
                    sd['core'] = stream_dict(pkg, STEALTH_CORE, f'ktwr_{sid}_core')
                    if cat == 'unarmed_stealth':
                        st['dict'] = sd['core']
                st['clips'] = {'idle': 'idle', 'walk': 'walk', 'run': 'run', 'sprint': 'run'}
                extra = cats['rifle'] if cat == 'rifle_stealth' else cats['pistol'] if cat == 'pistol_stealth' else []
                st['mode'], st['modeF'] = f'KTWR_{sid.upper()}', f'KTWR_{sid.upper()}_F'
                ped_modes.append(movement_mode(modes_src['default_action'], st['mode'], cat, sd, clipsets, extra, twins))
                ped_modes.append(movement_mode(modes_src['mp_female_action'], st['modeF'], cat, sd, clipsets, extra,
                                               twins))
            entries.append(st)
        catalog.append((cat, label, hint, kind, entries))

    write_xml(clipsets.xml(), os.path.join(out, 'meta', 'clip_sets.xml'),
              'weapon_styles: one clip set per KTWR style dictionary (stream/ktwr_*.ycd) in front of\n'
              'the game clip set it replaces; generated by tools/weapon_styles/build_weapon_styles.py')
    write_xml(sets_root, os.path.join(out, 'meta', 'weaponanimations.meta'),
              'weapon_styles: one weapon animation set per style (male + _F female). Entries only set\n'
              'the motion / cover clip set; every other field falls back to the game\'s own set.')
    write_xml(ped_out, os.path.join(out, 'meta', 'pedpersonality.meta'),
              'weapon_styles: movement modes for the stealth styles (copies of DEFAULT_ACTION /\n'
              'MP_FEMALE_ACTION with the style in the stealth part).')

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
            for k in ('img', 'dict', 'set', 'setF', 'mode', 'modeF'):
                if st.get(k):
                    parts.append(f'{k} = {lua_str(st[k])}')
            if st.get('clips'):
                c = st['clips']
                parts.append('clips = { ' + ', '.join(f'{k} = {lua_str(c[k])}' for k in ('idle', 'walk', 'run', 'sprint')) + ' }')
            L.append('            { ' + ', '.join(parts) + ' },')
        L.append('        } },')
    L.append('    },')
    L.append('    -- weapons with entries in the native sets / movement modes (others use the overlay)')
    L.append('    native = {')
    for cat in ('rifle', 'pistol'):
        L.append(f'        {cat} = {{')
        for w in cats[cat]:
            L.append(f'            [`{w}`] = true,')
        L.append('        },')
    L.append('    },')
    L.append('}')
    with open(os.path.join(out, 'shared', 'catalog.lua'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')

    icon = os.path.join(ROOT, 'fivem', 'ox_inventory', 'web', 'images', 'WEAPON_AR15.png')
    if os.path.exists(icon):                  # menu card of the AR-15's own low ready
        shutil.copy(icon, os.path.join(out, 'html', 'img', 'ar15.png'))

    n_dicts = len(os.listdir(os.path.join(out, 'stream')))
    print(f'styles: {sum(len(e) for *_x, e in catalog)}, dictionaries: {n_dicts}, clip sets: {len(clipsets.items)}, '
          f'weapon sets: {len(sets_list)}, movement modes: {len(ped_modes)}, '
          f'rifle weapons: {len(cats["rifle"])}, pistol weapons: {len(cats["pistol"])}')


if __name__ == '__main__':
    main()
