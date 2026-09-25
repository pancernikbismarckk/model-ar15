-- weapon_styles (client): the /style menu and the chosen styles on your ped.
--
-- native   the style's clip set in place of the weapon's own movement clip set
--          (SET_PED_WEAPON_MOVEMENT_CLIPSET: standing, walking, running, sprinting, turns, idle <->
--          aim; the game syncs it to the other players) and, with a pistol, in place of its cover
--          clip set (SET_PED_MOTION_IN_COVER_CLIPSET_OVERRIDE, set here on the other players too)
-- overlay  the style's idle / walk / run / sprint clips on the upper body (TaskPlayAnim, synced by
--          the game): the stealth styles, and every style when the game does not take the add-on
--          clip sets (overlay mode)
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

local FEMALE = `mp_f_freemode_01`
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
-- { category, movement clip set chain (male, female freemode), cover chain } or nil (no styles)
local function weaponInfo(weapon)
    if weapon == `WEAPON_UNARMED` or excluded[weapon] then return nil end
    local w = Catalog.weapons[weapon]
    if w then return w end
    local kind = GROUPS[GetWeapontypeGroup(weapon)]
    return kind and Catalog.fallback[kind] or nil
end

local function weaponKind(weapon)
    if weapon == `WEAPON_UNARMED` then return 'unarmed' end
    local w = weaponInfo(weapon)
    return w and w[1] or nil
end

-- ------------------------------------------------------------------------------------------------
-- native mode
-- ------------------------------------------------------------------------------------------------
local function clipSetReady(name)
    if HasClipSetLoaded(name) then return true end
    RequestClipSet(name)
    return false
end

-- the movement and cover clip sets a ped should have (false = the game's own)
local function nativeTargets(ped, p, isMe, sprint)
    local w = weaponInfo(GetSelectedPedWeapon(ped))
    -- your own first person view keeps the game's first person animations
    if not w or (isMe and GetFollowPedCamViewMode() == 4) then return false, false end
    local st = style(w[1], p[w[1]])
    local motion = st and (st.dict .. '@' .. (GetEntityModel(ped) == FEMALE and w[3] or w[2])) or false
    -- sprinting with a rifle: the game's own sprint underneath (the left arm free, as in single
    -- player) and the style's sprint on top as the overlay (see overlayTarget)
    if sprint and w[1] == 'rifle' and Config.RifleSprintOverlay ~= false then motion = false end
    local cover = false
    if w[1] == 'pistol' then
        local cs = style('pistol_cover', p.pistol_cover)
        cover = cs and (cs.dict .. '@' .. w[4]) or false
    end
    return motion, cover
end

-- st: what this script set on the ped ({ motion, cover }); only what we set is ever reset, so the
-- clip sets other scripts put on the ped (carrying a box, a jerry can...) stay theirs
local function syncMotion(ped, st, motion, force)
    if motion == st.motion and not (force and motion) then return true end
    if motion then
        if not clipSetReady(motion) then return false end
        SetPedWeaponMovementClipset(ped, motion)
    else
        ResetPedWeaponMovementClipset(ped)
    end
    st.motion = motion
    return true
end

local function syncCover(ped, st, cover)
    if cover == st.cover then return end
    if cover then
        if not clipSetReady(cover) then return end
        SetPedCoverClipsetOverride(ped, cover)
    else
        ClearPedCoverClipsetOverride(ped)
    end
    st.cover = cover
end

local mine = { ped = 0, weapon = 0, motion = false, cover = false, force = false, settled = true }

local function applyMine(ped, sprint)
    if ped ~= mine.ped then mine = { ped = ped, weapon = 0, motion = false, cover = false, force = false, settled = true } end
    local motion, cover = false, false
    if nativeMode then motion, cover = nativeTargets(ped, prefs, true, sprint) end
    -- set it again after a weapon change, a weapon swap, death, a vehicle or a ragdoll
    local weapon = GetSelectedPedWeapon(ped)
    local settled = not IsPedSwappingWeapon(ped) and not IsEntityDead(ped) and not IsPedInAnyVehicle(ped, false)
        and not IsPedRagdoll(ped)
    if weapon ~= mine.weapon or (settled and not mine.settled) then mine.force = true end
    mine.weapon, mine.settled = weapon, settled
    if syncMotion(ped, mine, motion, mine.force) then mine.force = false end
    syncCover(ped, mine, cover)
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
-- overlay (your own ped; TaskPlayAnim is synced to the other players by the game)
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

local function overlayTarget(ped, sprint)
    local kind = weaponKind(GetSelectedPedWeapon(ped))
    if not kind then return nil end
    local move = sprint and 'sprint' or IsPedRunning(ped) and 'run'
        or IsPedWalking(ped) and 'walk' or 'idle'
    local st
    if GetPedStealthMovement(ped) then
        st = style(kind .. '_stealth', prefs[kind .. '_stealth'])
    elseif kind ~= 'unarmed' then
        st = style(kind, prefs[kind])
        -- native mode: the game plays the style, except the rifle sprint: it does not take the
        -- style's sprint clip (the "sprint: High Port / na pasie" variants are only that clip, the
        -- right arm) and keeps the style's two-handed hold, so the style comes off for the sprint
        -- (nativeTargets) and its sprint is played here over the game's own
        if nativeMode and not (kind == 'rifle' and move == 'sprint' and Config.RifleSprintOverlay ~= false) then
            st = nil
        end
    end
    if not st or not st.clips then return nil end
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

local function tickOverlay(ped, sprint)
    local aim = aiming(ped)
    local dict, clip
    if not aim and overlayAllowed(ped) then dict, clip = overlayTarget(ped, sprint) end
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
                disabled = GetResourceState('weapon_ar15') ~= 'started' or nil,
                why = 'Zasób weapon_ar15 nie jest uruchomiony.' }
        end
        for _, st in ipairs(c.list) do
            if not hidden[st.id] then
                list[#list + 1] = { id = st.id, label = st.label, variant = st.variant, desc = st.desc, img = st.img,
                    disabled = c.kind == 'cover' and not nativeMode or nil, why = 'Działa tylko w trybie natywnym.' }
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
-- sprinting, held for a moment after the last sprinting frame, so the style is not switched back and
-- forth where a sprint starts and ends
local lastSprintAt = -10000

local function sprinting(ped)
    if IsPedSprinting(ped) then lastSprintAt = GetGameTimer() end
    return GetGameTimer() - lastSprintAt < 300
end

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
        local sprint = sprinting(ped)
        applyMine(ped, sprint)
        tickOverlay(ped, sprint)
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

-- other players (native mode): the game syncs their movement clip set, so it only has to be
-- streamed in here; their cover clip set is not synced and is set here
local others = {}        -- ped -> { cover = clip set | false }

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
                    if type(p) == 'table' then
                        local motion, cover = nativeTargets(ped, p, false)
                        if motion then clipSetReady(motion) end
                        local st = others[ped]
                        if not st then
                            st = { cover = false }
                            others[ped] = st
                        end
                        syncCover(ped, st, cover)
                    end
                end
            end
            for ped in pairs(others) do
                if not DoesEntityExist(ped) then others[ped] = nil end
            end
        end
        Wait(200)
    end
end)

exports('GetStyles', function() return prefs end)

AddEventHandler('onResourceStop', function(name)
    if name ~= GetCurrentResourceName() then return end
    closeMenu()
    local ped = PlayerPedId()
    stopOverlay(ped, 8.0)
    if mine.ped == ped then
        if mine.motion then ResetPedWeaponMovementClipset(ped) end
        if mine.cover then ClearPedCoverClipsetOverride(ped) end
    end
    for p, st in pairs(others) do
        if st.cover and DoesEntityExist(p) then ClearPedCoverClipsetOverride(p) end
    end
end)
