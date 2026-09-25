Config = {}

-- the menu command
Config.Command = 'style'

-- 'auto'    native styles (the game plays them itself, walking and turning included) when the game
--           takes the add-on clip sets, otherwise the script plays them on the upper body
-- 'native'  always native     'overlay'  always the script (upper body: idle, walk, run, sprint)
Config.Mode = 'auto'

-- a player's choice before they open the menu for the first time
-- (rifle 'ar15' = the AR-15's own low ready from weapon_ar15; other rifles keep the GTA look)
Config.Defaults = {
    rifle = 'ar15',
    pistol = 'default',
    rifle_stealth = 'default',
    pistol_stealth = 'default',
    unarmed_stealth = 'default',
    pistol_cover = 'default',
}

-- other players' styles are applied within this distance (native mode; the script mode is synced
-- by the game itself)
Config.SyncDistance = 150.0

-- weapons that keep their own animations, e.g. an add-on weapon with its own holding script:
-- Config.ExcludedWeapons = { 'WEAPON_GLOCK17' }
Config.ExcludedWeapons = {}

-- style ids to hide from the menu, e.g. { 'r17', 'p12' }
Config.HiddenStyles = {}
