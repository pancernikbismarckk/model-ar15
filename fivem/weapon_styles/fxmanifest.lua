fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'weapon_styles'
description 'Weapon holding styles per player (/style): KTWR animations by Mr.KobraX, OneSync'
version '1.0.0'

ui_page 'html/index.html'

files {
    'html/index.html',
    'html/style.css',
    'html/app.js',
    'html/img/*.jpg',
    'html/img/*.png',
    'meta/clip_sets.xml',
    'meta/weaponanimations.meta',
    'meta/pedpersonality.meta',
}

-- add-on clip sets: one per style dictionary (stream/ktwr_*.ycd)
data_file 'CLIP_SETS_FILE' 'meta/clip_sets.xml'
-- one weapon animation set and one movement mode per style, switched per player by client/main.lua
data_file 'WEAPON_ANIMATIONS_FILE' 'meta/weaponanimations.meta'
data_file 'PED_PERSONALITY_FILE' 'meta/pedpersonality.meta'

shared_scripts {
    'config.lua',
    'shared/catalog.lua',
}

client_script 'client/main.lua'
server_script 'server/main.lua'
