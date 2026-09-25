fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'weapon_styles'
description 'Weapon holding styles per player (/style): KTWR animations by Mr.KobraX, OneSync'
version '1.1.0'

ui_page 'html/index.html'

files {
    'html/index.html',
    'html/style.css',
    'html/app.js',
    'html/img/*.jpg',
    'html/img/*.png',
    'meta/clip_sets.xml',
}

-- add-on clip sets: each style dictionary (stream/ktwr_*.ycd) in front of the weapons' own clip set
-- chains; client/main.lua puts them on the ped (SET_PED_WEAPON_MOVEMENT_CLIPSET, cover override)
data_file 'CLIP_SETS_FILE' 'meta/clip_sets.xml'

shared_scripts {
    'config.lua',
    'shared/catalog.lua',
}

client_script 'client/main.lua'
server_script 'server/main.lua'
