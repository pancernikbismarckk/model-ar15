-- weapon_ar15: names, iron sights, laser beam.

local WEAPON = `WEAPON_AR15`
local SIGHTS = `COMPONENT_AR15_SIGHTS`
local HOLO = `COMPONENT_AT_AR15_SCOPE_HOLO`
local LASER = `COMPONENT_AT_AR15_LASER`

local LASER_BONE = 'WAPSupp_2'     -- laser attach bone = beam origin (weapon points along +X)
local LASER_RANGE = 150.0
local LASER_VIEW_DISTANCE = 80.0   -- draw other players' lasers within this distance
local LASER_COLOUR = { 255, 25, 20 }

AddTextEntry('WT_AR15', 'AR-15')
AddTextEntry('WCD_AR15_CLIP1', 'Standardowy magazynek na 30 naboi.')
AddTextEntry('WCT_AR15_SIGHTS', 'Przyrządy celownicze')
AddTextEntry('WCD_AR15_SIGHTS', 'Składane mechaniczne przyrządy celownicze.')
AddTextEntry('WCT_AR15_HOLO', 'Celownik holograficzny')
AddTextEntry('WCD_AR15_HOLO', 'Celownik holograficzny; przyrządy mechaniczne składają się pod nim.')
AddTextEntry('WCT_AR15_AFGRIP', 'Chwyt przedni kątowy')
AddTextEntry('WCD_AR15_AFGRIP', 'Kątowy chwyt przedni na szynę M-LOK.')
AddTextEntry('WCT_AR15_FLSH', 'Latarka taktyczna')
AddTextEntry('WCD_AR15_FLSH', 'Latarka na broń. Włączanie jak w zwykłej broni z latarką.')
AddTextEntry('WCT_AR15_LASER', 'Laser')
AddTextEntry('WCD_AR15_LASER', 'Czerwony laser. Włącz/wyłącz: klawisz z ustawień (domyślnie J).')

local function hasLaser(ped)
    return GetSelectedPedWeapon(ped) == WEAPON and HasPedGotWeaponComponent(ped, WEAPON, LASER)
end

-- The raised iron sights are the default component on the scope mount. Fitting the holo replaces
-- them (its model carries the folded sights); when the holo is taken off, put the raised sights back.
CreateThread(function()
    while true do
        local ped = PlayerPedId()
        local sleep = 1000
        if GetSelectedPedWeapon(ped) == WEAPON then
            sleep = 400
            if not HasPedGotWeaponComponent(ped, WEAPON, HOLO) and not HasPedGotWeaponComponent(ped, WEAPON, SIGHTS) then
                GiveWeaponComponentToPed(ped, WEAPON, SIGHTS)
            end
        end
        Wait(sleep)
    end
end)

-- laser -----------------------------------------------------------------------------------------
local laserOn = false

RegisterCommand('ar15laser', function()
    if not hasLaser(PlayerPedId()) then return end
    laserOn = not laserOn
    LocalPlayer.state:set('ar15laser', laserOn, true)
    PlaySoundFrontend(-1, 'NAV_UP_DOWN', 'HUD_FRONTEND_DEFAULT_SOUNDSET', true)
end, false)
RegisterKeyMapping('ar15laser', 'AR-15: laser wł./wył.', 'keyboard', 'J')

local function drawLaser(ped)
    local weapon = GetCurrentPedWeaponEntityIndex(ped)
    if weapon == 0 or not DoesEntityExist(weapon) then return end
    local bone = GetEntityBoneIndexByName(weapon, LASER_BONE)
    if bone == -1 then return end
    local from = GetWorldPositionOfEntityBone(weapon, bone)
    local dir = GetOffsetFromEntityInWorldCoords(weapon, 1.0, 0.0, 0.0) - GetEntityCoords(weapon)
    local to = from + dir * LASER_RANGE
    local ray = StartExpensiveSynchronousShapeTestLosProbe(from.x, from.y, from.z, to.x, to.y, to.z, 283, weapon, 7)
    local _, hit, pos = GetShapeTestResult(ray)
    hit = hit == true or hit == 1
    local stop = hit and pos or to
    local r, g, b = LASER_COLOUR[1], LASER_COLOUR[2], LASER_COLOUR[3]
    DrawLine(from.x, from.y, from.z, stop.x, stop.y, stop.z, r, g, b, 170)
    if hit then
        DrawMarker(28, stop.x, stop.y, stop.z, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.012, 0.012, 0.012,
            r, g, b, 230, false, false, 2, false, nil, nil, false)
    end
end

CreateThread(function()
    while true do
        local sleep = 300
        local me = PlayerPedId()
        if laserOn and hasLaser(me) then
            drawLaser(me)
            sleep = 0
        end
        local myCoords = GetEntityCoords(me)
        for _, player in ipairs(GetActivePlayers()) do
            local ped = GetPlayerPed(player)
            if ped ~= me and Player(GetPlayerServerId(player)).state.ar15laser and hasLaser(ped)
                and #(GetEntityCoords(ped) - myCoords) < LASER_VIEW_DISTANCE then
                drawLaser(ped)
                sleep = 0
            end
        end
        Wait(sleep)
    end
end)
