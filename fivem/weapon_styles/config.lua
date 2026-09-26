Config = {}

-- the menu command
Config.Command = 'style'

-- 'auto'    native styles (the game plays them itself, walking and turning included) when the game
--           takes the add-on clip sets, otherwise the script plays them on the upper body
-- 'native'  always native     'overlay'  always the script (upper body: idle, walk, run, sprint)
-- (the stealth styles are always played by the script)
Config.Mode = 'auto'

-- a player's choice before they open the menu for the first time ('default' = the game's animations)
Config.Defaults = {
    rifle = 'default',
    pistol = 'default',
    rifle_stealth = 'default',
    pistol_stealth = 'default',
    unarmed_stealth = 'default',
    pistol_cover = 'default',
}

-- native mode: other players' style clip sets are streamed in (and their cover style set) within
-- this distance; the rest is synced by the game itself
Config.SyncDistance = 150.0

-- weapons that keep their own animations, e.g. an add-on weapon with its own holding script:
-- Config.ExcludedWeapons = { 'WEAPON_GLOCK17' }
Config.ExcludedWeapons = {}

-- style ids to hide from the menu, e.g. { 'r17', 'p12' }
Config.HiddenStyles = {}
