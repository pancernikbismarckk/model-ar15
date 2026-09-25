-- weapon_styles (client): the /style menu and the chosen styles on your ped and on other players.
--
-- native mode   the game plays the style itself: a weapon animation set (rifle / pistol / pistol in
--               cover) and a movement mode (stealth) per ped, switched with the weapon in hand
-- overlay mode  the style's idle / walk / run / sprint clips on the upper body (TaskPlayAnim, which
--               OneSync syncs); used when the game does not take the add-on clip sets and for
--               add-on weapons that have no entries in the sets
-- Choices are kept per player (resource KVP) and shared through the player state bag 'wstyles'.

local CATS, ORDER = {}, {}
for _, cat in ipairs(Catalog.categories) do
    local c = { key = cat.key, label = cat.label, hint = cat.hint, kind = cat.kind, styles = {}, list = {} }
    for _, st in ipairs(cat.styles) do
        c.styles[st.id] = st
        c.list[#c.list + 1] = st
    end
    CATS[cat.key] = c
    ORDER[#ORDER + 1] = cat.key
end

local excluded, hidden = {}, {}
for _, w in ipairs(Config.ExcludedWeapons or {}) do excluded[GetHashKey(w)] = true end
for _, id in ipairs(Config.HiddenStyles or {}) do hidden[id] = true end

-- the game's own weapon animation set and movement mode per player model (pedpersonality), which a
-- reset goes back to; the female freemode ped gets the styles' _F variants
local BASE = {
    [`mp_f_freemode_01`] = { set = `MP_F_Freemode`, mode = 'DEFAULT_ACTION', female = true },
    [`player_zero`] = { set = `Michael`, mode = 'MICHAEL_ACTION' },
    [`player_one`] = { set = `Franklin`, mode = 'FRANKLIN_ACTION' },
    [`player_two`] = { set = `Trevor`, mode = 'TREVOR_ACTION' },
}
local BASE_DEFAULT = { set = `Default`, mode = 'DEFAULT_ACTION' }
local OVERLAY_FLAGS = 1 + 16 + 32           -- loop, upper body only, player keeps control
local GROUPS = {
    [`GROUP_PISTOL`] = 'pistol', [`GROUP_STUNGUN`] = 'pistol',
    [`GROUP_RIFLE`] = 'rifle', [`GROUP_SMG`] = 'rifle', [`GROUP_MG`] = 'rifle',
    [`GROUP_SHOTGUN`] = 'rifle', [`GROUP_SNIPER`] = 'rifle',
}
local IsPedSwappingWeapon = IsPedSwappingWeapon or function() return false end

local nativeMode = false
local prefs = {}

local function style(cat, id)
    local c = CATS[cat]
    return c and id and c.styles[id] or nil
end

local function validId(key, id)
    return id == 'default' or (key == 'rifle' and id == 'ar15') or (CATS[key] and CATS[key].styles[id] ~= nil)
end

-- ------------------------------------------------------------------------------------------------
-- choices
-- ------------------------------------------------------------------------------------------------
local KVP = 'weapon_styles'

local function loadPrefs()
    local ok, saved = pcall(json.decode, GetResourceKvpString(KVP) or '')
    saved = ok and type(saved) == 'table' and saved or {}
    for _, key in ipairs(ORDER) do
        local id = saved[key]
        prefs[key] = (type(id) == 'string' and validId(key, id)) and id or (Config.Defaults[key] or 'default')
    end
end

local function savePrefs()
    SetResourceKvp(KVP, json.encode(prefs))
    TriggerServerEvent('weapon_styles:set', prefs)
end

-- ------------------------------------------------------------------------------------------------
-- weapons
-- ------------------------------------------------------------------------------------------------
local function weaponKind(weapon)
    if weapon == `WEAPON_UNARMED` then return 'unarmed' end
    if excluded[weapon] then return nil end
    if Catalog.native.rifle[weapon] then return 'rifle' end
    if Catalog.native.pistol[weapon] then return 'pistol' end
    return GROUPS[GetWeapontypeGroup(weapon)]
end

-- ------------------------------------------------------------------------------------------------
-- native mode
-- ------------------------------------------------------------------------------------------------
local applied = {}      -- ped -> { set = name | false, mode = name | false }

local function base(ped)
    return BASE[GetEntityModel(ped)] or BASE_DEFAULT
end

-- the weapon animation set and movement mode a ped should have (false = the game's own)
local function nativeTargets(ped, p, isMe)
    local weapon = GetSelectedPedWeapon(ped)
    local kind = weaponKind(weapon)
    -- your own first person view keeps the game's first person animations
    if not kind or (isMe and GetFollowPedCamViewMode() == 4) then return false, false end
    local female = base(ped).female
    if kind == 'unarmed' then
        local ss = style('unarmed_stealth', p.unarmed_stealth)
        return false, ss and ss.mode and (female and ss.modeF or ss.mode) or false
    end
    if not Catalog.native[kind][weapon] then return false, false end     -- no entries: overlay
    local st
    if kind == 'pistol' and (IsPedInCover(ped, false) or IsPedGoingIntoCover(ped)) then
        st = style('pistol_cover', p.pistol_cover)
    end
    st = st or style(kind, p[kind])
    local ss = style(kind .. '_stealth', p[kind .. '_stealth'])
    return st and st.set and (female and st.setF or st.set) or false,
        ss and ss.mode and (female and ss.modeF or ss.mode) or false
end

local function applyNative(ped, p, isMe)
    local set, mode = nativeTargets(ped, p, isMe)
    local a = applied[ped]
    if not a then
        a = { set = false, mode = false }
        applied[ped] = a
    end
    local b = base(ped)
    if set ~= a.set then
        SetWeaponAnimationOverride(ped, set and GetHashKey(set) or b.set)
        a.set = set
    end
    if mode ~= a.mode then
        SetMovementModeOverride(ped, mode or b.mode)
        a.mode = mode
    end
end

local function resetNative(ped)
    local a = applied[ped]
    if a and DoesEntityExist(ped) then
        local b = base(ped)
        if a.set then SetWeaponAnimationOverride(ped, b.set) end
        if a.mode then SetMovementModeOverride(ped, b.mode) end
    end
    applied[ped] = nil
end

-- the game takes the add-on clip sets only if CLIP_SETS_FILE works on this server / build
CreateThread(function()
    if Config.Mode == 'overlay' then return end
    if Config.Mode == 'native' then
        nativeMode = true
        return
    end
    RequestClipSet(Catalog.testClipSet)
    local t0 = GetGameTimer()
    while not HasClipSetLoaded(Catalog.testClipSet) and GetGameTimer() - t0 < 6000 do Wait(100) end
    nativeMode = HasClipSetLoaded(Catalog.testClipSet)
    print(('[weapon_styles] %s'):format(nativeMode and 'native mode (the game plays the styles)'
        or 'overlay mode (add-on clip sets not available, the script plays the styles)'))
end)

-- ------------------------------------------------------------------------------------------------
-- overlay mode (your own ped; TaskPlayAnim is synced to the other players by the game)
-- ------------------------------------------------------------------------------------------------
local overlay = nil      -- { dict, clip } we are playing
local lastPlay = 0

local function aiming(ped)
    return IsPlayerFreeAiming(PlayerId()) or IsControlPressed(0, 25) or IsDisabledControlPressed(0, 25)
        or IsControlPressed(0, 24) or IsDisabledControlPressed(0, 24) or IsPedShooting(ped)
end

local function overlayAllowed(ped)
    return GetFollowPedCamViewMode() ~= 4
        and not IsPedInAnyVehicle(ped, true) and not IsPedGettingIntoAVehicle(ped)
        and not IsPedInCover(ped, false) and not IsPedGoingIntoCover(ped)
        and not IsPedRagdoll(ped) and not IsPedFalling(ped) and not IsPedJumping(ped)
        and not IsPedClimbing(ped) and not IsPedVaulting(ped) and not IsPedSwimming(ped)
        and not IsPedDeadOrDying(ped, true) and not IsPedInParachuteFreeFall(ped)
        and GetPedParachuteState(ped) <= 0 and not IsPedUsingAnyScenario(ped)
        and not IsPedSwappingWeapon(ped) and not IsPedInMeleeCombat(ped)
        and not IsPedPerformingMeleeAction(ped) and not IsPedReloading(ped)
end

local function overlayTarget(ped)
    local weapon = GetSelectedPedWeapon(ped)
    local kind = weaponKind(weapon)
    if not kind then return nil end
    local st
    if GetPedStealthMovement(ped) then
        st = style(kind .. '_stealth', prefs[kind .. '_stealth'])
        if nativeMode and st and (kind == 'unarmed' or Catalog.native[kind][weapon]) then return nil end
    elseif kind ~= 'unarmed' then
        st = style(kind, prefs[kind])
        if nativeMode and st and Catalog.native[kind][weapon] then return nil end
    end
    if not st or not st.dict or not st.clips then return nil end
    local move = IsPedSprinting(ped) and 'sprint' or IsPedRunning(ped) and 'run'
        or IsPedWalking(ped) and 'walk' or 'idle'
    return st.dict, st.clips[move]
end

local function otherAnim(ped)
    if GetScriptTaskStatus(ped, `SCRIPT_TASK_PLAY_ANIM`) == 7 then return false end
    return not (overlay and IsEntityPlayingAnim(ped, overlay.dict, overlay.clip, 3))
end

local function stopOverlay(ped, speed)
    if overlay then
        if IsEntityPlayingAnim(ped, overlay.dict, overlay.clip, 3) then
            StopAnimTask(ped, overlay.dict, overlay.clip, speed)
        end
        overlay = nil
    end
end

local function tickOverlay(ped)
    local aim = aiming(ped)
    local dict, clip
    if not aim and overlayAllowed(ped) then dict, clip = overlayTarget(ped) end
    if not dict then
        stopOverlay(ped, aim and 8.0 or 3.0)
        return
    end
    local playing = overlay and overlay.dict == dict and overlay.clip == clip
        and IsEntityPlayingAnim(ped, dict, clip, 3)
    if playing or otherAnim(ped) or GetGameTimer() - lastPlay < 250 then return end
    if not HasAnimDictLoaded(dict) then
        RequestAnimDict(dict)
        return
    end
    TaskPlayAnim(ped, dict, clip, 3.0, 3.0, -1, OVERLAY_FLAGS, 0.0, false, false, false)
    overlay = { dict = dict, clip = clip }
    lastPlay = GetGameTimer()
end

-- ------------------------------------------------------------------------------------------------
-- menu
-- ------------------------------------------------------------------------------------------------
local menuOpen = false
local menuClosedAt = -10000

local function menuData()
    local cats = {}
    for _, key in ipairs(ORDER) do
        local c = CATS[key]
        local list = { { id = 'default', label = 'GTA', variant = 'bez zmian', desc = 'Animacje z gry.' } }
        if key == 'rifle' then
            list[#list + 1] = { id = 'ar15', label = 'AR-15 low ready', variant = 'tylko AR-15',
                desc = 'Low ready z zasobu weapon_ar15; pozostałe karabiny jak w GTA.', img = 'img/ar15.png',
                disabled = GetResourceState('weapon_ar15') ~= 'started' }
        end
        for _, st in ipairs(c.list) do
            if not hidden[st.id] then
                list[#list + 1] = { id = st.id, label = st.label, variant = st.variant, desc = st.desc, img = st.img }
            end
        end
        cats[#cats + 1] = { key = key, label = c.label, hint = c.hint, styles = list }
    end
    return cats
end

local function openMenu()
    if menuOpen then return end
    menuOpen = true
    SendNUIMessage({ action = 'open', categories = menuData(), prefs = prefs, mode = nativeMode and 'native' or 'overlay' })
    SetNuiFocus(true, true)
    SetNuiFocusKeepInput(true)          -- walk around while the menu is open to see the style
end

local function closeMenu()
    if not menuOpen then return end
    menuOpen = false
    menuClosedAt = GetGameTimer()
    SetNuiFocus(false, false)
    SetNuiFocusKeepInput(false)
    SendNUIMessage({ action = 'close' })
end

RegisterCommand(Config.Command, openMenu, false)

RegisterNUICallback('select', function(data, cb)
    local key, id = data and data.category, data and data.id
    if type(key) == 'string' and type(id) == 'string' and CATS[key] and validId(key, id) then
        prefs[key] = id
        savePrefs()
    end
    cb({ prefs = prefs })
end)

RegisterNUICallback('close', function(_, cb)
    closeMenu()
    cb('ok')
end)

-- ------------------------------------------------------------------------------------------------
-- loops
-- ------------------------------------------------------------------------------------------------
CreateThread(function()
    loadPrefs()
    while not NetworkIsPlayerActive(PlayerId()) do Wait(500) end
    savePrefs()
end)

CreateThread(function()
    while true do
        local ped = PlayerPedId()
        local kind = weaponKind(GetSelectedPedWeapon(ped))
        -- the ESC that closed the menu must not open the pause menu a moment later
        local guard = menuOpen or GetGameTimer() - menuClosedAt < 500
        local busy = guard or kind == 'rifle' or kind == 'pistol' or (kind == 'unarmed' and GetPedStealthMovement(ped))
        if nativeMode then applyNative(ped, prefs, true) end
        tickOverlay(ped)
        if menuOpen then
            -- the mouse is on the menu: no looking around, shooting or pause menu
            for _, c in ipairs({ 1, 2, 24, 25, 68, 69, 70, 91, 92, 106, 140, 141, 142, 199, 200, 257, 263, 264, 322 }) do
                DisableControlAction(0, c, true)
            end
            if IsDisabledControlJustReleased(0, 200) or IsDisabledControlJustReleased(0, 322) then closeMenu() end
        elseif guard then
            DisableControlAction(0, 199, true)
            DisableControlAction(0, 200, true)
            DisableControlAction(0, 322, true)
        end
        Wait(busy and 0 or 250)
    end
end)

-- other players' styles (native mode; the overlay is synced by the game)
CreateThread(function()
    while true do
        if nativeMode then
            local me = PlayerPedId()
            local pos = GetEntityCoords(me)
            for _, player in ipairs(GetActivePlayers()) do
                local ped = GetPlayerPed(player)
                if ped ~= me and ped ~= 0 and DoesEntityExist(ped)
                    and #(GetEntityCoords(ped) - pos) < Config.SyncDistance then
                    local p = Player(GetPlayerServerId(player)).state.wstyles
                    if type(p) == 'table' then applyNative(ped, p, false) end
                end
            end
            for ped in pairs(applied) do
                if not DoesEntityExist(ped) then applied[ped] = nil end
            end
        end
        Wait(200)
    end
end)

exports('GetStyles', function() return prefs end)

AddEventHandler('onResourceStop', function(name)
    if name ~= GetCurrentResourceName() then return end
    closeMenu()
    stopOverlay(PlayerPedId(), 8.0)
    for ped in pairs(applied) do resetNative(ped) end
end)
