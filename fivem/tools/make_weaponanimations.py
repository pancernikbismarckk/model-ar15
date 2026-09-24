"""Creates weapon_ar15/meta/weaponanimations.meta from the game's own weaponanimations.meta.

Every animation-set entry of WEAPON_CARBINERIFLE is copied under the name WEAPON_AR15.

    python3 make_weaponanimations.py path/to/weaponanimations.meta [--base WEAPON_CARBINERIFLE]

Export the source file with OpenIV or CodeWalker from
update/update.rpf/common/data/ai/weaponanimations.meta.
"""
import argparse
import copy
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('vanilla')
    ap.add_argument('--base', default='WEAPON_CARBINERIFLE')
    ap.add_argument('--name', default='WEAPON_AR15')
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'weapon_ar15', 'meta', 'weaponanimations.meta'))
    a = ap.parse_args()

    src = ET.parse(a.vanilla).getroot()
    root = ET.Element('CWeaponAnimationsSets')
    sets = ET.SubElement(root, 'WeaponAnimationsSets')
    count = 0
    for s in src.findall('./WeaponAnimationsSets/Item'):
        entry = s.find(f"./WeaponAnimations/Item[@key='{a.base}']")
        if entry is None:
            continue
        ns = ET.SubElement(sets, 'Item', key=s.get('key'))
        fb = s.find('Fallback')
        if fb is not None:
            ns.append(copy.deepcopy(fb))
        anims = ET.SubElement(ns, 'WeaponAnimations')
        e = copy.deepcopy(entry)
        e.set('key', a.name)
        anims.append(e)
        count += 1
    if not count:
        raise SystemExit(f"no '{a.base}' entries in {a.vanilla}")
    ET.indent(root)
    ET.ElementTree(root).write(os.path.abspath(a.out), encoding='UTF-8', xml_declaration=True)
    print(f'wrote {count} animation sets for {a.name} to {os.path.abspath(a.out)}')


if __name__ == '__main__':
    main()
