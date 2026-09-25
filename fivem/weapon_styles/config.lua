Config = {}

-- the menu command
Config.Command = 'style'

-- 'auto'    native styles (the game plays them itself, walking and turning included) when the game
--           takes the add-on clip sets, otherwise the script plays them on the upper body
-- 'native'  always native     'overlay'  always the script (upper body: idle, walk, run, sprint)
-- (the stealth styles are always played by the script)
Config.Mode = 'auto'

-- native mode: the game does not play the style's sprint clip (it keeps the style's two-handed hold
-- while sprinting), so for the sprint the style comes off and the script plays the style's sprint on
-- the upper body over the game's own (the "sprint: High Port / na pasie" variants need this);
-- false = no sprint handling
Config.RifleSprintOverlay = true

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

-- native mode: other players' style clip sets are streamed in (and their cover style set) within
-- this distance; the rest is synced by the game itself
Config.SyncDistance = 150.0

-- weapons that keep their own animations, e.g. an add-on weapon with its own holding script:
-- Config.ExcludedWeapons = { 'WEAPON_GLOCK17' }
Config.ExcludedWeapons = {}

-- style ids to hide from the menu, e.g. { 'r17', 'p12' }
Config.HiddenStyles = {}
