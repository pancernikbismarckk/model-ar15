fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'weapon_ar15'
description 'AR-15 add-on weapon (semi-automatic) with its own animations: low ready, reload with a dropped magazine; holographic sight, angled foregrip, weapon light and laser'
version '1.1.1'

files {
    'meta/weaponcomponents.meta',
    'meta/weaponarchetypes.meta',
    'meta/weaponanimations.meta',
    'meta/pedpersonality.meta',
    'meta/weapons.meta',
}

data_file 'WEAPONCOMPONENTSINFO_FILE' 'meta/weaponcomponents.meta'
data_file 'WEAPON_METADATA_FILE' 'meta/weaponarchetypes.meta'
data_file 'WEAPON_ANIMATIONS_FILE' 'meta/weaponanimations.meta'
data_file 'PED_PERSONALITY_FILE' 'meta/pedpersonality.meta'
data_file 'WEAPONINFO_FILE' 'meta/weapons.meta'

-- stream/: w_ar_ar15*.ydr, w_at_ar15_*.ydr, w_ar_ar15.ytd and anim@weapon_ar15.ycd (the animations)
client_scripts {
    'config.lua',
    'anim_data.lua',
    'client.lua',
    'client_anims.lua',
}
