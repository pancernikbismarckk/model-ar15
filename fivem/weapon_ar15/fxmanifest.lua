fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'weapon_ar15'
description 'AR-15 add-on weapon: holographic sight, angled foregrip, weapon light and laser (ox_inventory ready)'
version '1.0.0'

files {
    'meta/weaponcomponents.meta',
    'meta/weaponarchetypes.meta',
    'meta/weaponanimations.meta',
    'meta/weapons.meta',
}

data_file 'WEAPONCOMPONENTSINFO_FILE' 'meta/weaponcomponents.meta'
data_file 'WEAPON_METADATA_FILE' 'meta/weaponarchetypes.meta'
data_file 'WEAPON_ANIMATIONS_FILE' 'meta/weaponanimations.meta'
data_file 'WEAPONINFO_FILE' 'meta/weapons.meta'

client_script 'client.lua'
