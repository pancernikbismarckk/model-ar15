Config = {}

-- Low ready (the rifle held across the chest, muzzle down to the left) whenever the AR-15 is out
-- and not being aimed or fired. Each player can switch it off for themselves: /ar15lowready
-- (a key can be bound in Settings > Key Bindings > FiveM).
Config.LowReady = true           -- with weapon_styles: only while its rifle style is "AR-15 low ready"
Config.LowReadyWhileSprinting = false

-- Custom reload (magazine pulled and dropped, a fresh one from the belt, bolt catch on an empty
-- rifle). The game's own reload still runs underneath, so ammo works exactly as before
-- (ox_inventory, codem-inventory, vanilla ammo).
Config.CustomReload = true

-- The pulled magazine falls to the ground and stays there for a while.
Config.DropMagazines = true
Config.MagazineLifetime = 20.0        -- seconds
Config.MaxDroppedMagazines = 10

-- Bolt, trigger, dust cover and bolt catch move with every shot and reload.
Config.WeaponPartAnims = true

-- Other players' magazines (in the hand, dropped) are drawn within this distance.
Config.DrawDistance = 60.0
