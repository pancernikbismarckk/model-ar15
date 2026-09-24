"""Render preview images from the saved weapon_ar15.blend.

    python3 blender/render_blend.py OUT_PREFIX [workbench|cycles] [shot,shot,...] [samples]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import preview as P  # noqa: E402

if __name__ == '__main__':
    out = sys.argv[1]
    engine = (sys.argv[2] if len(sys.argv) > 2 else 'workbench').upper()
    which = sys.argv[3].split(',') if len(sys.argv) > 3 and sys.argv[3] != 'all' else None
    samples = int(sys.argv[4]) if len(sys.argv) > 4 else 64
    bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(HERE), 'weapon_ar15.blend'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if which and which == ['match']:
        P.photo_match_side(out + '_match.png', 'CYCLES' if engine == 'CYCLES' else 'WORKBENCH')
    else:
        P.views(out, 'CYCLES' if engine == 'CYCLES' else 'WORKBENCH', which=which, samples=samples)
